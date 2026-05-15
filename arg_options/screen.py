"""Pantallas configurables sobre la última cadena."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from arg_options import chain as chainmod
from arg_options.config_persist import resolve_screening_path_for_settings
from arg_options.settings import AppSettings

logger = logging.getLogger(__name__)


def resolve_screening_path(settings: AppSettings | None = None) -> Path:
    paths = settings.paths if settings else None
    return resolve_screening_path_for_settings(paths)


def load_screening_config(path: Path | None = None, settings: AppSettings | None = None) -> dict[str, Any]:
    path = path or resolve_screening_path(settings)
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _days_to_expiry(expiry: pd.Series) -> pd.Series:
    exp = pd.to_datetime(expiry, errors="coerce").dt.normalize()
    today = pd.Timestamp.now().normalize()
    return (exp - today).dt.days


def apply_screen(df: pd.DataFrame, rules: dict[str, Any]) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if "expiry" in out.columns:
        out["_dte"] = _days_to_expiry(out["expiry"])
        if "min_days_to_expiry" in rules:
            lo = float(rules["min_days_to_expiry"])
            out = out[out["_dte"].isna() | (out["_dte"] >= lo)]
        if "max_days_to_expiry" in rules:
            hi = float(rules["max_days_to_expiry"])
            out = out[out["_dte"].isna() | (out["_dte"] <= hi)]

    if "volume" in out.columns and "min_open_interest_proxy_volume" in rules:
        v = pd.to_numeric(out["volume"], errors="coerce").fillna(0)
        out = out[v >= float(rules["min_open_interest_proxy_volume"])]

    if {"bid", "ask", "mid"}.issubset(out.columns) and "max_bid_ask_spread_pct_mid" in rules:
        bid = pd.to_numeric(out["bid"], errors="coerce")
        ask = pd.to_numeric(out["ask"], errors="coerce")
        mid = pd.to_numeric(out["mid"], errors="coerce")
        spread_pct = (ask - bid) / mid.replace(0, pd.NA) * 100
        lim = float(rules["max_bid_ask_spread_pct_mid"])
        # Sin bid y ask no hay spread: no descartamos (PPI a veces solo devuelve last/mid).
        out = out[spread_pct.isna() | (spread_pct <= lim)]

    if "delta" in out.columns:
        d = pd.to_numeric(out["delta"], errors="coerce").abs()
        if "min_abs_delta" in rules:
            lo = float(rules["min_abs_delta"])
            if lo > 0:
                out = out[d.isna() | (d >= lo)]
        if "max_abs_delta" in rules:
            hi = float(rules["max_abs_delta"])
            if hi < 1.0:
                out = out[d.isna() | (d <= hi)]

    if (
        {"right", "strike", "underlying_spot_ticker"}.issubset(out.columns)
        and "min_underlying_vs_strike_pct_otm_call" in rules
    ):
        # Requiere columna spot enriquecida; si no existe, se omite el filtro.
        pass

    if "_dte" in out.columns:
        out = out.drop(columns=["_dte"], errors="ignore")
    return out


def explain_why_screen_empty(latest: pd.DataFrame, rules: dict[str, Any]) -> str:
    """Pista cuando apply_screen devuelve 0 filas pero latest no está vacío."""
    if latest.empty or not rules:
        return ""
    hints: list[str] = []
    if "expiry" in latest.columns:
        dte = _days_to_expiry(latest["expiry"])
        if "min_days_to_expiry" in rules:
            lo = float(rules["min_days_to_expiry"])
            if lo > 0 and (dte < lo).all():
                hints.append(
                    f"ninguna fila cumple DTE ≥ {lo:.0f} días (rango actual ~{dte.min()}-{dte.max()}). Bajá min_days_to_expiry en screening.yaml."
                )
        if "max_days_to_expiry" in rules:
            hi = float(rules["max_days_to_expiry"])
            if (dte > hi).all():
                hints.append(f"ninguna fila cumple DTE ≤ {hi:.0f} días.")
    if "delta" in latest.columns:
        d = pd.to_numeric(latest["delta"], errors="coerce").abs()
        if "min_abs_delta" in rules and float(rules["min_abs_delta"]) > 0:
            lo = float(rules["min_abs_delta"])
            if (d.fillna(0) < lo).all() and d.notna().any():
                hints.append(f"ningún |delta| ≥ {lo} (relajá min_abs_delta o revisá spot/mid para Greeks).")
        if "max_abs_delta" in rules and float(rules["max_abs_delta"]) < 1.0:
            hi = float(rules["max_abs_delta"])
            if (d > hi).all() and d.notna().any():
                hints.append(f"todos los |delta| superan {hi}.")
    if {"bid", "ask", "mid"}.issubset(latest.columns) and "max_bid_ask_spread_pct_mid" in rules:
        bid = pd.to_numeric(latest["bid"], errors="coerce")
        ask = pd.to_numeric(latest["ask"], errors="coerce")
        mid = pd.to_numeric(latest["mid"], errors="coerce")
        spread_pct = (ask - bid) / mid.replace(0, pd.NA) * 100
        lim = float(rules["max_bid_ask_spread_pct_mid"])
        if spread_pct.notna().any() and (spread_pct.notna() & (spread_pct > lim)).all():
            hints.append(f"spread % vs mid supera {lim} en todas las filas con bid/ask.")
    return " ".join(hints) if hints else "Relajá reglas en config/screening.yaml (DTE, delta, spread)."


def get_latest_snapshot_rows(settings: AppSettings) -> pd.DataFrame:
    df = chainmod.load_last_snapshots(settings)
    if df.empty:
        return df
    latest_ts = df["ts"].max()
    return df[df["ts"] == latest_ts]


def run_screen(
    settings: AppSettings,
    screening_path: Path | None = None,
    out_csv: Path | None = None,
    out_json: Path | None = None,
    rules_override: dict[str, Any] | None = None,
) -> pd.DataFrame:
    if rules_override is not None:
        rules = rules_override
    elif screening_path is not None:
        rules = load_screening_config(screening_path)
    else:
        rules = load_screening_config(None, settings)
    df = chainmod.load_last_snapshots(settings)
    if df.empty:
        return df
    latest_ts = df["ts"].max()
    latest = df[df["ts"] == latest_ts]
    filtered = apply_screen(latest, rules)
    if len(latest) > 0 and len(filtered) == 0 and rules:
        logger.warning(
            "Screening dejó 0 filas de %s en el último snapshot. "
            "Relajá min/max DTE, spread o delta en config/screening.yaml.",
            len(latest),
        )
    if out_csv:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        filtered.to_csv(out_csv, index=False)
    if out_json:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        filtered.to_json(out_json, orient="records", date_format="iso")
    return filtered
