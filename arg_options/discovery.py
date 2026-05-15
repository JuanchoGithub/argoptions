"""Discovery Engine: escanea la cadena y aplica todas las estrategias documentadas."""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from arg_options import chain as chainmod
from arg_options import db as dbmod
from arg_options import screen as screenmod
from arg_options.ppi_client import connect_ppi
from arg_options.settings import AppSettings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Leg:
    ticker: str
    side: str
    qty: int
    strike: float
    right: str
    mid: float | None = None
    delta: float | None = None
    bid: float | None = None
    ask: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "side": self.side,
            "qty": self.qty,
            "strike": self.strike,
            "right": self.right,
            "mid": self.mid,
            "delta": self.delta,
            "bid": self.bid,
            "ask": self.ask,
        }


@dataclass
class Opportunity:
    root: str
    strategy: str
    side: str
    legs: list[Leg]
    metrics: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0
    expiry: str | None = None

    def to_structure_dicts(self) -> list[dict[str, Any]]:
        return [l.to_dict() for l in self.legs]


STRATEGY_LABELS = {
    "mariposa": "Mariposa",
    "renta_ic": "Iron Condor",
    "credit_spread": "Credit Spread",
    "calendar": "Calendar",
    "sintetico": "Sintético",
}

SIDE_LABELS = {
    "neutral": "Neutral",
    "compra": "Compra",
    "venta": "Venta",
}


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def resolve_discovery_rules_path(settings: AppSettings | None = None) -> Path:
    if settings:
        p = settings.paths.get("discovery_rules")
        if p:
            return Path(p)
    return Path("config/discovery_rules.yaml")


def load_discovery_rules(
    path: Path | None = None, settings: AppSettings | None = None
) -> dict[str, Any]:
    path = path or resolve_discovery_rules_path(settings)
    if not path.is_file():
        return _default_rules()
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else _default_rules()


def _default_rules() -> dict[str, Any]:
    return {
        "auto_chain_if_stale": True,
        "chain_stale_minutes": 30,
        "min_confidence": 30,
        "strategies": {
            "mariposa": {
                "enabled": True,
                "target_delta": 0.50,
                "delta_range": [0.30, 0.70],
                "max_cost_pct_of_width": 50,
            },
            "renta_ic": {
                "enabled": True,
                "short_delta_target": 0.20,
                "short_delta_range": [0.15, 0.30],
                "insurance_delta_target": 0.10,
                "insurance_delta_range": [0.05, 0.15],
                "min_credit_pct_of_width": 5,
            },
            "temporal": {
                "enabled": True,
                "min_dte_short": 7,
                "max_dte_short": 30,
                "min_dte_long": 45,
                "max_dte_long": 90,
            },
            "sintetico": {
                "enabled": True,
            },
        },
    }


# ---------------------------------------------------------------------------
# Discovery Engine
# ---------------------------------------------------------------------------

class DiscoveryEngine:
    def __init__(
        self,
        settings: AppSettings,
        rules: dict[str, Any] | None = None,
        rules_path: Path | None = None,
    ):
        self.settings = settings
        self.rules = rules or load_discovery_rules(rules_path, settings)

    def run(self) -> list[Opportunity]:
        logger.info("Discovery: asegurando datos de cadena...")
        df = self._ensure_chain_data()
        if df.empty:
            logger.warning("Discovery: no hay datos de cadena disponibles.")
            return []

        # No hay filtro previo — cada analyzer controla calidad via _safe_float

        try:
            ppi = connect_ppi(self.settings)
        except Exception as exc:
            logger.warning("Discovery: sin PPI para spot (%s). Estrategias sin delta pueden quedar fuera.", exc)
            ppi = None

        spot_cache: dict[str, float | None] = {}
        all_opps: list[Opportunity] = []
        for root in sorted(df["option_root"].unique()):
            root_df = df[df["option_root"] == root].copy()
            logger.info("Discovery: analizando root %s (%d filas)", root, len(root_df))

            spot: float | None = None
            if ppi:
                spot_ticker = self.settings.underlying_spot.get(root)
                if spot_ticker and spot_ticker not in spot_cache:
                    spot_cache[spot_ticker] = chainmod.fetch_spot_price(ppi, spot_ticker, self.settings)
                spot = spot_cache.get(spot_ticker)

            all_opps.extend(self._analyze_root(root, root_df, spot))

        self._persist(all_opps)
        logger.info("Discovery: %d oportunidades encontradas.", len(all_opps))
        return all_opps

    def _ensure_chain_data(self) -> pd.DataFrame:
        df = screenmod.get_latest_snapshot_rows(self.settings)
        if df.empty and self.rules.get("auto_chain_if_stale", True):
            logger.info("Discovery: ejecutando chain automático...")
            ppi = connect_ppi(self.settings)
            rows = chainmod.build_full_chain(ppi, self.settings)
            chainmod.persist_chain(rows, self.settings)
            df = screenmod.get_latest_snapshot_rows(self.settings)
        return df

    def _analyze_root(self, root: str, df: pd.DataFrame, spot: float | None) -> list[Opportunity]:
        opps: list[Opportunity] = []
        strat = self.rules.get("strategies", {})

        grouped = df.groupby("expiry")
        for expiry, exp_df in grouped:
            if strat.get("mariposa", {}).get("enabled", True):
                bf = analyze_butterfly(root, expiry, exp_df, self.rules, spot=spot)
                if bf:
                    opps.append(bf)
                else:
                    logger.debug("Mariposa %s/%s: no encontrada", root, expiry)

            if strat.get("renta_ic", {}).get("enabled", True):
                ic = analyze_iron_condor(root, expiry, exp_df, self.rules, spot=spot)
                if ic:
                    opps.append(ic)
                else:
                    logger.debug("IC %s/%s: no encontrado", root, expiry)

            if strat.get("sintetico", {}).get("enabled", True):
                syn = analyze_synthetics_single(root, expiry, exp_df, self.rules)
                opps.extend(syn)

        if strat.get("temporal", {}).get("enabled", True):
            cals = analyze_calendars(root, df, self.rules)
            opps.extend(cals)

        return opps

    def _persist(self, opps: list[Opportunity]) -> None:
        conn = dbmod.connect(self.settings.db_path())
        ts = dbmod.utc_now_iso()
        try:
            for opp in opps:
                dbmod.insert_discovery_opportunity(
                    conn,
                    root=opp.root,
                    strategy=opp.strategy,
                    side=opp.side,
                    expiry=opp.expiry,
                    structure=opp.to_structure_dicts(),
                    metrics=opp.metrics,
                    confidence=opp.confidence,
                    ts=ts,
                )
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Helpers for strike matching
# ---------------------------------------------------------------------------

def _find_nearest_strike(df: pd.DataFrame, target: float) -> pd.Series | None:
    """Find the row in df with strike closest to target."""
    if df.empty:
        return None
    df = df.reset_index(drop=True)
    idx = int((df["strike"].astype(float) - target).abs().idxmin())
    return df.iloc[[idx]].iloc[0]





def _has_enough_delta(df: pd.DataFrame, min_valid: int = 3) -> bool:
    """Check if enough rows have valid delta values."""
    deltas = pd.to_numeric(df.get("delta", pd.Series(dtype=float)), errors="coerce")
    return deltas.notna().sum() >= min_valid


# ---------------------------------------------------------------------------
# Butterfly Analyzer
# ---------------------------------------------------------------------------

def analyze_butterfly(
    root: str, expiry: str, df: pd.DataFrame, rules: dict[str, Any],
    spot: float | None = None,
) -> Opportunity | None:
    sr = rules.get("strategies", {}).get("mariposa", {})
    target_delta = sr.get("target_delta", 0.50)
    delta_range = sr.get("delta_range", [0.30, 0.70])
    max_cost_pct = sr.get("max_cost_pct_of_width", 50)

    calls = df[df["right"] == "C"].copy().reset_index(drop=True)
    if len(calls) < 3:
        logger.debug("Mariposa %s/%s: menos de 3 calls", root, expiry)
        return None

    strikes = sorted(calls["strike"].unique())
    gap = _infer_strike_gap(strikes)

    # Find K2 (central strike) — by delta if available, else by spot
    k2: pd.Series | None = None
    if _has_enough_delta(calls):
        calls["_dabs"] = pd.to_numeric(calls["delta"], errors="coerce").abs()
        candidates = calls[
            (calls["_dabs"] >= delta_range[0]) & (calls["_dabs"] <= delta_range[1])
        ]
        if not candidates.empty:
            k2_idx = int((candidates["_dabs"] - target_delta).abs().idxmin())
            k2 = calls.iloc[[k2_idx]].iloc[0]

    if k2 is None and spot is not None and spot > 0:
        nearest = _find_nearest_strike(calls, spot)
        if nearest is not None and abs(float(nearest["strike"]) - spot) / spot < 0.1:
            k2 = nearest
            logger.debug("Mariposa %s/%s: K2 por spot %.0f → strike %.0f",
                         root, expiry, spot, float(k2["strike"]))

    if k2 is None:
        logger.debug("Mariposa %s/%s: no se pudo determinar K2", root, expiry)
        return None

    k2_strike = float(k2["strike"])
    k1_strike = k2_strike - gap
    k3_strike = k2_strike + gap

    # Find nearest strikes if exact match fails
    k1_candidates = calls[calls["strike"] == k1_strike]
    k1 = k1_candidates.iloc[0] if not k1_candidates.empty else _find_nearest_strike(calls, k1_strike)

    k3_candidates = calls[calls["strike"] == k3_strike]
    k3 = k3_candidates.iloc[0] if not k3_candidates.empty else _find_nearest_strike(calls, k3_strike)

    if k1 is None or k3 is None:
        logger.debug("Mariposa %s/%s: alas K1=%.0f K3=%.0f no encontradas en strikes %s",
                     root, expiry, k1_strike, k3_strike, strikes[:5])
        return None

    actual_gap = float(k3["strike"]) - float(k1["strike"])

    k1_ask = _safe_float(k1, "ask")
    k3_ask = _safe_float(k3, "ask")
    k2_bid = _safe_float(k2, "bid")

    if k1_ask is None or k3_ask is None or k2_bid is None:
        logger.debug("Mariposa %s/%s: bid/ask faltante en alguna pata", root, expiry)
        return None

    net_debit = max(k1_ask + k3_ask - 2 * k2_bid, 0)
    max_profit = actual_gap - net_debit

    legs = [
        Leg(k1["ticker"], "COMPRA", 1, float(k1["strike"]), "C",
            _safe_float(k1, "mid"), _safe_float(k1, "delta"),
            _safe_float(k1, "bid"), k1_ask),
        Leg(k2["ticker"], "VENTA", 2, float(k2["strike"]), "C",
            _safe_float(k2, "mid"), _safe_float(k2, "delta"),
            k2_bid, _safe_float(k2, "ask")),
        Leg(k3["ticker"], "COMPRA", 1, float(k3["strike"]), "C",
            _safe_float(k3, "mid"), _safe_float(k3, "delta"),
            _safe_float(k3, "bid"), k3_ask),
    ]

    metrics = {
        "gap": actual_gap,
        "net_debit": round(net_debit, 2),
        "max_profit": round(max_profit, 2),
        "max_loss": round(net_debit, 2),
        "cost_pct_of_width": round(net_debit / actual_gap * 100, 1) if actual_gap > 0 else 0,
        "k2_delta": round(float(k2.get("delta", 0)), 4),
        "prob_success": round(max(0, 1 - net_debit / actual_gap), 3) if actual_gap > 0 else 0,
    }

    confidence = _score_butterfly(k1, k2, k3, net_debit, actual_gap, target_delta, max_cost_pct)
    return Opportunity(
        root=root, strategy="mariposa", side="neutral", legs=legs,
        metrics=metrics, confidence=confidence, expiry=expiry,
    )


# ---------------------------------------------------------------------------
# Iron Condor Analyzer
# ---------------------------------------------------------------------------

def _ic_strike_by_delta(df: pd.DataFrame, target: float, rng: list[float]) -> pd.Series | None:
    """Find row in df with abs(delta) closest to target within range."""
    df = df.copy().reset_index(drop=True)
    df["_dabs"] = pd.to_numeric(df["delta"], errors="coerce").abs()
    cands = df[(df["_dabs"] >= rng[0]) & (df["_dabs"] <= rng[1])]
    if cands.empty:
        return None
    idx = int((cands["_dabs"] - target).abs().idxmin())
    return df.iloc[[idx]].iloc[0]


def _ic_strike_by_moneyness(df: pd.DataFrame, spot: float, pct_otm: float, above: bool) -> pd.Series | None:
    """Find nearest strike at a percentage away from spot."""
    target = spot * (1 + pct_otm) if above else spot * (1 - pct_otm)
    return _find_nearest_strike(df, target)


def analyze_iron_condor(
    root: str, expiry: str, df: pd.DataFrame, rules: dict[str, Any],
    spot: float | None = None,
) -> Opportunity | None:
    sr = rules.get("strategies", {}).get("renta_ic", {})
    short_target = sr.get("short_delta_target", 0.20)
    short_range = sr.get("short_delta_range", [0.15, 0.30])
    ins_target = sr.get("insurance_delta_target", 0.10)
    ins_range = sr.get("insurance_delta_range", [0.05, 0.15])
    min_credit_pct = sr.get("min_credit_pct_of_width", 5)

    calls = df[df["right"] == "C"].copy()
    puts = df[df["right"] == "P"].copy()
    if calls.empty or puts.empty:
        return None

    use_delta = _has_enough_delta(df, min_valid=4)
    sc: pd.Series | None = None
    lc: pd.Series | None = None
    sp: pd.Series | None = None
    lp: pd.Series | None = None

    if use_delta:
        sc = _ic_strike_by_delta(calls, short_target, short_range)
        lc = _ic_strike_by_delta(calls, ins_target, ins_range)
        sp = _ic_strike_by_delta(puts, short_target, short_range)
        lp = _ic_strike_by_delta(puts, ins_target, ins_range)

    if sc is None or lc is None or sp is None or lp is None:
        if spot is not None and spot > 0:
            if sc is None:
                sc = _ic_strike_by_moneyness(calls, spot, 0.20, above=True)
            if lc is None:
                lc = _ic_strike_by_moneyness(calls, spot, 0.30, above=True)
            if sp is None:
                sp = _ic_strike_by_moneyness(puts, spot, 0.20, above=False)
            if lp is None:
                lp = _ic_strike_by_moneyness(puts, spot, 0.30, above=False)
        else:
            return None

    if sc is None or lc is None or sp is None or lp is None:
        logger.debug("IC %s/%s: no se encontraron las 4 patas", root, expiry)
        return None

    if float(lc["strike"]) <= float(sc["strike"]) or float(lp["strike"]) >= float(sp["strike"]):
        logger.debug("IC %s/%s: strikes de seguro no válidos", root, expiry)
        return None

    sc_bid = _safe_float(sc, "bid")
    lc_ask = _safe_float(lc, "ask")
    sp_bid = _safe_float(sp, "bid")
    lp_ask = _safe_float(lp, "ask")

    if any(v is None for v in [sc_bid, lc_ask, sp_bid, lp_ask]):
        logger.debug("IC %s/%s: bid/ask faltante en alguna pata", root, expiry)
        return None

    credit = sc_bid + sp_bid - lc_ask - lp_ask
    if credit <= 0:
        logger.debug("IC %s/%s: crédito <= 0 (%.2f)", root, expiry, credit)
        return None

    call_width = float(lc["strike"]) - float(sc["strike"])
    put_width = float(sp["strike"]) - float(lp["strike"])
    avg_width = (call_width + put_width) / 2

    if credit / avg_width * 100 < min_credit_pct:
        return None

    legs = [
        Leg(sc["ticker"], "VENTA", 1, float(sc["strike"]), "C",
            _safe_float(sc, "mid"), _safe_float(sc, "delta"),
            sc_bid, _safe_float(sc, "ask")),
        Leg(lc["ticker"], "COMPRA", 1, float(lc["strike"]), "C",
            _safe_float(lc, "mid"), _safe_float(lc, "delta"),
            _safe_float(lc, "bid"), lc_ask),
        Leg(sp["ticker"], "VENTA", 1, float(sp["strike"]), "P",
            _safe_float(sp, "mid"), _safe_float(sp, "delta"),
            sp_bid, _safe_float(sp, "ask")),
        Leg(lp["ticker"], "COMPRA", 1, float(lp["strike"]), "P",
            _safe_float(lp, "mid"), _safe_float(lp, "delta"),
            _safe_float(lp, "bid"), lp_ask),
    ]

    max_loss = max(call_width, put_width) - credit
    sc_delta = float(sc.get("delta", 0))
    sp_delta = float(sp.get("delta", 0))
    prob_success = round(1 - abs(sc_delta) - abs(sp_delta), 3) if abs(sc_delta) > 0 else 0

    metrics = {
        "credit_received": round(credit, 2),
        "call_width": call_width,
        "put_width": put_width,
        "max_loss": round(max_loss, 2),
        "prob_success": max(0, prob_success),
        "credit_pct_of_width": round(credit / avg_width * 100, 1),
    }

    confidence = _score_ic(sc, lc, sp, lp, credit, avg_width)
    return Opportunity(
        root=root, strategy="renta_ic", side="neutral", legs=legs,
        metrics=metrics, confidence=confidence, expiry=expiry,
    )


# ---------------------------------------------------------------------------
# Calendar / Temporal Analyzer
# ---------------------------------------------------------------------------

def analyze_calendars(
    root: str, df: pd.DataFrame, rules: dict[str, Any]
) -> list[Opportunity]:
    sr = rules.get("strategies", {}).get("temporal", {})
    min_dte_short = sr.get("min_dte_short", 7)
    max_dte_short = sr.get("max_dte_short", 30)
    min_dte_long = sr.get("min_dte_long", 45)
    max_dte_long = sr.get("max_dte_long", 90)

    df["_dte"] = _days_to_expiry(df["expiry"])
    opps: list[Opportunity] = []

    for (strike, right), group in df.groupby(["strike", "right"]):
        group = group.sort_values("_dte")
        shorts = group[
            (group["_dte"] >= min_dte_short) & (group["_dte"] <= max_dte_short)
        ]
        longs = group[
            (group["_dte"] >= min_dte_long) & (group["_dte"] <= max_dte_long)
        ]
        if shorts.empty or longs.empty:
            continue

        short_r = shorts.iloc[0]
        long_r = longs.iloc[0]

        short_bid = _safe_float(short_r, "bid")
        long_ask = _safe_float(long_r, "ask")
        if short_bid is None or long_ask is None:
            continue

        cost = long_ask - short_bid

        legs = [
            Leg(short_r["ticker"], "VENTA", 1, float(short_r["strike"]),
                str(short_r["right"]), _safe_float(short_r, "mid"),
                _safe_float(short_r, "delta"), short_bid,
                _safe_float(short_r, "ask")),
            Leg(long_r["ticker"], "COMPRA", 1, float(long_r["strike"]),
                str(long_r["right"]), _safe_float(long_r, "mid"),
                _safe_float(long_r, "delta"), _safe_float(long_r, "bid"),
                long_ask),
        ]

        short_theta = _safe_float(short_r, "theta") or 0
        long_theta = _safe_float(long_r, "theta") or 0

        metrics = {
            "cost": round(cost, 2),
            "short_dte": int(short_r["_dte"]),
            "long_dte": int(long_r["_dte"]),
            "theta_diff": round(long_theta - short_theta, 4),
            "short_theta": round(short_theta, 4),
            "long_theta": round(long_theta, 4),
        }

        confidence = _score_calendar(short_r, long_r, cost)
        opps.append(
            Opportunity(
                root=root, strategy="calendar",
                side="neutral" if str(short_r["right"]) == str(long_r["right"]) else "neutral",
                legs=legs, metrics=metrics, confidence=confidence,
                expiry=str(short_r.get("expiry", "")),
            )
        )

        if len(opps) >= 3:
            break

    return opps


# ---------------------------------------------------------------------------
# Synthetic Analyzer (same expiry)
# ---------------------------------------------------------------------------

def analyze_synthetics_single(
    root: str, expiry: str, df: pd.DataFrame, rules: dict[str, Any]
) -> list[Opportunity]:
    calls = df[df["right"] == "C"].copy()
    puts = df[df["right"] == "P"].copy()
    opps: list[Opportunity] = []

    common_strikes = set(calls["strike"].unique()) & set(puts["strike"].unique())
    for strike in sorted(common_strikes)[:5]:
        c = calls[calls["strike"] == strike].iloc[0]
        p = puts[puts["strike"] == strike].iloc[0]

        c_ask = _safe_float(c, "ask")
        p_bid = _safe_float(p, "bid")
        c_bid = _safe_float(c, "bid")
        p_ask = _safe_float(p, "ask")

        if any(v is None for v in [c_ask, p_bid, c_bid, p_ask]):
            continue

        syn_long_cost = c_ask - p_bid
        syn_short_cost = p_ask - c_bid

        for label, side_label, cost, c_leg_side, p_leg_side in [
            ("sintético Long", "compra", syn_long_cost, "COMPRA", "VENTA"),
            ("sintético Short", "venta", syn_short_cost, "VENTA", "COMPRA"),
        ]:
            legs = [
                Leg(c["ticker"], c_leg_side, 1, float(c["strike"]), "C",
                    _safe_float(c, "mid"), _safe_float(c, "delta"),
                    _safe_float(c, "bid"), _safe_float(c, "ask")),
                Leg(p["ticker"], p_leg_side, 1, float(p["strike"]), "P",
                    _safe_float(p, "mid"), _safe_float(p, "delta"),
                    _safe_float(p, "bid"), _safe_float(p, "ask")),
            ]

            metrics = {
                "net_cost": round(cost, 2),
                "strike": strike,
            }

            bid_sum = legs[0].bid or 0 if c_leg_side == "VENTA" else 0
            bid_sum += legs[1].bid or 0 if p_leg_side == "VENTA" else 0
            volume_ok = (_safe_float(c, "volume") or 0) > 0 and (
                _safe_float(p, "volume") or 0
            ) > 0
            conf = 50 + (10 if volume_ok else 0) + (10 if bid_sum > 0 else 0)

            opps.append(
                Opportunity(
                    root=root, strategy="sintetico", side=side_label,
                    legs=legs, metrics=metrics, confidence=min(conf, 95),
                    expiry=expiry,
                )
            )

    return opps


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _score_butterfly(
    k1: pd.Series, k2: pd.Series, k3: pd.Series,
    net_debit: float, gap: float, target_delta: float, max_cost_pct: float,
) -> float:
    base = 60.0
    delta_diff = abs(float(k2.get("delta", 0)) - target_delta)
    if delta_diff <= 0.05:
        base += 15
    elif delta_diff <= 0.10:
        base += 8
    for row in [k1, k2, k3]:
        if (_safe_float(row, "volume") or 0) > 0:
            base += 3
        spread = _calc_spread_pct(row)
        if spread is not None and spread < 15:
            base += 3
    if gap > 0 and net_debit / gap * 100 < max_cost_pct * 0.5:
        base += 5
    elif gap > 0 and net_debit / gap * 100 < max_cost_pct:
        base += 2
    return min(base, 100)


def _score_ic(
    sc: pd.Series, lc: pd.Series, sp: pd.Series, lp: pd.Series,
    credit: float, avg_width: float,
) -> float:
    base = 60.0
    for row in [sc, lc, sp, lp]:
        if (_safe_float(row, "volume") or 0) > 0:
            base += 2
        spread = _calc_spread_pct(row)
        if spread is not None and spread < 15:
            base += 3
    if avg_width > 0 and credit / avg_width * 100 > 15:
        base += 10
    elif avg_width > 0 and credit / avg_width * 100 > 10:
        base += 5
    return min(base, 100)


def _score_calendar(short_r: pd.Series, long_r: pd.Series, cost: float) -> float:
    base = 60.0
    for row in [short_r, long_r]:
        if (_safe_float(row, "volume") or 0) > 0:
            base += 5
        spread = _calc_spread_pct(row)
        if spread is not None and spread < 20:
            base += 5
    short_theta = abs(_safe_float(short_r, "theta") or 0)
    long_theta = abs(_safe_float(long_r, "theta") or 0)
    if short_theta > long_theta * 1.5:
        base += 10
    if cost < 0:
        base += 5
    return min(base, 100)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_float(row: pd.Series, col: str) -> float | None:
    v = row.get(col)
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def _calc_spread_pct(row: pd.Series) -> float | None:
    bid = _safe_float(row, "bid")
    ask = _safe_float(row, "ask")
    mid = _safe_float(row, "mid")
    if bid is not None and ask is not None and mid is not None and mid > 0:
        return (ask - bid) / mid * 100
    return None


def _infer_strike_gap(strikes: list[float]) -> float:
    if len(strikes) < 2:
        return 50.0
    gaps = [strikes[i + 1] - strikes[i] for i in range(len(strikes) - 1)]
    gaps = [g for g in gaps if g > 0]
    if not gaps:
        return 50.0
    # return most common gap
    from collections import Counter

    rounded = [round(g, -1) for g in gaps]
    most_common = Counter(rounded).most_common(1)
    return float(most_common[0][0]) if most_common else gaps[0]


def _days_to_expiry(expiry_series: pd.Series) -> pd.Series:
    exp = pd.to_datetime(expiry_series, errors="coerce").dt.normalize()
    today = pd.Timestamp.now().normalize()
    return (exp - today).dt.days
