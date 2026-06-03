from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from arg_options.broker import create_broker
from arg_options.broker.interfaces import BrokerConfig
from arg_options.core.chain import build_full_chain
from arg_options.core.instruments import parse_ticker_parts
from arg_options.core.screen import load_screening_config

logger = logging.getLogger(__name__)


@dataclass
class Assessment:
    grade: str      # A / B / C / F
    tag: str        # short label like "OTM credit spread"
    summary: str    # one-liner for the log
    detail: str     # multi-line for the modal
    roc: float      # return on capital (credit/width or similar)
    warning: str    # empty string if none


@dataclass
class Leg:
    ticker: str
    side: str
    qty: int
    strike: float
    right: str
    bid: float = 0.0
    ask: float = 0.0


@dataclass
class Opportunity:
    root: str
    strategy: str
    side: str
    confidence: float
    legs: list[Leg] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


class DiscoveryEngine:
    def __init__(self, settings: BrokerConfig) -> None:
        self._settings = settings
        self._rules = load_screening_config(settings=settings)
        self._broker = create_broker(settings)

    def run(self) -> list[Opportunity]:
        logger.info("=== DISCOVERY STARTED ===")
        self._broker.connect()
        try:
            rows = build_full_chain(self._broker, self._settings)
            logger.info(f"Chain built with {len(rows)} rows")
        finally:
            try:
                self._broker.disconnect()
            except Exception:
                pass

        if not rows:
            logger.info("No chain data for discovery")
            return []

        df = pd.DataFrame(rows)
        logger.info(f"DataFrame created with {len(df)} rows")
        
        df = self._apply_screening(df)
        logger.info(f"After screening: {len(df)} rows")

        if df.empty:
            logger.info("Chain empty after screening")
            return []

        opportunities: list[Opportunity] = []

        for finder in (
            self._find_mariposa,
            self._find_iron_condor,
            self._find_calendar,
            self._find_credit_spread,
            self._find_synthetic,
        ):
            try:
                found = finder(df)
                logger.info(f"{finder.__name__} found {len(found)} opportunities")
                opportunities.extend(found)
            except Exception as e:
                logger.warning("Strategy %s failed: %s", finder.__name__, e)

        opportunities.sort(key=lambda o: o.confidence, reverse=True)
        logger.info("Discovery found %d opportunities total", len(opportunities))
        return opportunities

    def _apply_screening(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info(f"Applying screening to {len(df)} rows")
        dte_min = self._rules.get("dte_min", 0)
        dte_max = self._rules.get("dte_max", 9999)
        volume_min = self._rules.get("volume_min", 0)
        max_spread = self._rules.get("max_spread_pct", 1.0)
        
        logger.info(f"Screening rules: DTE {dte_min}-{dte_max}, Volume >= {volume_min}, Spread <= {max_spread}, Bid>0, Ask>0")

        mask = (
            (df["dte"] >= dte_min)
            & (df["dte"] <= dte_max)
            & (df["volume"] >= volume_min)
            & (df["spread_pct"] <= max_spread)
            & (df["bid"] > 0)
            & (df["ask"] > 0)
        )
        screened = df[mask].copy()
        logger.info(f"Screening filtered {len(df) - len(screened)} rows, {len(screened)} remaining")
        return screened

    def _find_mariposa(self, df: pd.DataFrame) -> list[Opportunity]:
        opportunities: list[Opportunity] = []
        for expiry, group in df.groupby("expiry"):
            if len(group) < 3:
                continue
            calls = group[group["right"] == "CALL"].sort_values("strike")
            if len(calls) < 3:
                continue

            strikes = calls["strike"].values
            for i in range(len(strikes) - 2):
                k1, k2, k3 = float(strikes[i]), float(strikes[i + 1]), float(strikes[i + 2])
                spacing = (k3 - k1) / 2
                if abs(k2 - k1 - spacing) > spacing * 0.1:
                    continue

                leg1 = calls.iloc[i]
                leg2 = calls.iloc[i + 1]
                leg3 = calls.iloc[i + 2]

                cost = (
                    (leg1["ask"] or 0)
                    - 2 * (leg2["bid"] or 0)
                    + (leg3["ask"] or 0)
                )
                width = k3 - k1
                if width <= 0:
                    continue
                ratio = cost / width
                if ratio <= 0 or ratio > 0.5:
                    continue

                opportunities.append(Opportunity(
                    root=str(leg1.get("root", "")),
                    strategy="mariposa",
                    side="BUY",
                    confidence=1.0 - ratio,
                    legs=[
                        Leg(ticker=str(leg1["ticker"]), side="BUY", qty=1,
                            strike=float(leg1["strike"]), right="CALL",
                            bid=float(leg1["bid"]), ask=float(leg1["ask"])),
                        Leg(ticker=str(leg2["ticker"]), side="SELL", qty=2,
                            strike=float(leg2["strike"]), right="CALL",
                            bid=float(leg2["bid"]), ask=float(leg2["ask"])),
                        Leg(ticker=str(leg3["ticker"]), side="BUY", qty=1,
                            strike=float(leg3["strike"]), right="CALL",
                            bid=float(leg3["bid"]), ask=float(leg3["ask"])),
                    ],
                    metrics={"cost": round(cost, 2), "width": round(width, 2), "ratio": round(ratio, 4)},
                ))
        return opportunities

    def _find_iron_condor(self, df: pd.DataFrame) -> list[Opportunity]:
        opportunities: list[Opportunity] = []
        for expiry, group in df.groupby("expiry"):
            calls = group[group["right"] == "CALL"].sort_values("strike")
            puts = group[group["right"] == "PUT"].sort_values("strike", ascending=False)
            if len(calls) < 2 or len(puts) < 2:
                continue

            spot = float(group["spot"].iloc[0])
            otm_calls = calls[calls["strike"] > spot]
            otm_puts = puts[puts["strike"] < spot]

            if len(otm_calls) < 2 or len(otm_puts) < 2:
                continue

            sell_call = otm_calls.iloc[0]
            buy_call = otm_calls.iloc[1]
            sell_put = otm_puts.iloc[0]
            buy_put = otm_puts.iloc[1]

            net_credit = (
                (sell_put["bid"] or 0)
                + (sell_call["bid"] or 0)
                - (buy_put["ask"] or 0)
                - (buy_call["ask"] or 0)
            )
            width_call = float(buy_call["strike"]) - float(sell_call["strike"])
            width_put = float(sell_put["strike"]) - float(buy_put["strike"])
            max_loss = max(width_call, width_put)

            if net_credit <= 0 or max_loss <= 0:
                continue

            opportunities.append(Opportunity(
                root=str(sell_call.get("root", "")),
                strategy="iron_condor",
                side="SELL",
                confidence=min(net_credit / max_loss, 0.95),
                legs=[
                    Leg(ticker=str(sell_put["ticker"]), side="SELL", qty=1,
                        strike=float(sell_put["strike"]), right="PUT",
                        bid=float(sell_put["bid"]), ask=float(sell_put["ask"])),
                    Leg(ticker=str(buy_put["ticker"]), side="BUY", qty=1,
                        strike=float(buy_put["strike"]), right="PUT",
                        bid=float(buy_put["bid"]), ask=float(buy_put["ask"])),
                    Leg(ticker=str(sell_call["ticker"]), side="SELL", qty=1,
                        strike=float(sell_call["strike"]), right="CALL",
                        bid=float(sell_call["bid"]), ask=float(sell_call["ask"])),
                    Leg(ticker=str(buy_call["ticker"]), side="BUY", qty=1,
                        strike=float(buy_call["strike"]), right="CALL",
                        bid=float(buy_call["bid"]), ask=float(buy_call["ask"])),
                ],
                metrics={"net_credit": round(net_credit, 2), "max_loss": round(max_loss, 2)},
            ))
        return opportunities

    def _find_calendar(self, df: pd.DataFrame) -> list[Opportunity]:
        opportunities: list[Opportunity] = []
        for right in ("CALL", "PUT"):
            subset = df[df["right"] == right]
            grouped = subset.groupby(["root", "strike"])
            for (root, strike), group in grouped:
                if len(group) < 2:
                    continue
                sorted_group = group.sort_values("dte")
                near = sorted_group.iloc[0]
                far = sorted_group.iloc[-1]

                if far["dte"] <= near["dte"]:
                    continue

                cost = (near["ask"] or 0) if near["ask"] else (far["ask"] or 0)
                if cost <= 0:
                    continue

                opportunities.append(Opportunity(
                    root=str(root),
                    strategy="calendar",
                    side="SELL" if right == "CALL" else "BUY",
                    confidence=0.5,
                    legs=[
                        Leg(ticker=str(near["ticker"]), side="SELL", qty=1,
                            strike=float(near["strike"]), right=right,
                            bid=float(near["bid"]), ask=float(near["ask"])),
                        Leg(ticker=str(far["ticker"]), side="BUY", qty=1,
                            strike=float(far["strike"]), right=right,
                            bid=float(far["bid"]), ask=float(far["ask"])),
                    ],
                    metrics={"near_dte": int(near["dte"]), "far_dte": int(far["dte"]), "cost": round(cost, 2)},
                ))
        return opportunities

    def _find_credit_spread(self, df: pd.DataFrame) -> list[Opportunity]:
        opportunities: list[Opportunity] = []
        for expiry, group in df.groupby("expiry"):
            spot = float(group["spot"].iloc[0])
            calls = group[group["right"] == "CALL"].sort_values("strike")
            puts = group[group["right"] == "PUT"].sort_values("strike", ascending=False)

            bear_calls = calls[calls["strike"] <= spot]
            for i in range(len(bear_calls) - 1):
                sell = bear_calls.iloc[i]
                buy = bear_calls.iloc[i + 1]
                credit = (sell["bid"] or 0) - (buy["ask"] or 0)
                width = float(buy["strike"]) - float(sell["strike"])
                if credit > 0 and width > 0:
                    opportunities.append(Opportunity(
                        root=str(sell.get("root", "")),
                        strategy="bear_call_spread",
                        side="SELL",
                        confidence=min(credit / width, 0.95),
                        legs=[
                            Leg(ticker=str(sell["ticker"]), side="SELL", qty=1,
                                strike=float(sell["strike"]), right="CALL",
                                bid=float(sell["bid"]), ask=float(sell["ask"])),
                            Leg(ticker=str(buy["ticker"]), side="BUY", qty=1,
                                strike=float(buy["strike"]), right="CALL",
                                bid=float(buy["bid"]), ask=float(buy["ask"])),
                        ],
                        metrics={"credit": round(credit, 2), "width": round(width, 2), "spot": round(spot, 2)},
                    ))

            bull_puts = puts[puts["strike"] >= spot]
            for i in range(len(bull_puts) - 1):
                sell = bull_puts.iloc[i]
                buy = bull_puts.iloc[i + 1]
                credit = (sell["bid"] or 0) - (buy["ask"] or 0)
                width = float(sell["strike"]) - float(buy["strike"])
                if credit > 0 and width > 0:
                    opportunities.append(Opportunity(
                        root=str(sell.get("root", "")),
                        strategy="bull_put_spread",
                        side="SELL",
                        confidence=min(credit / width, 0.95),
                        legs=[
                            Leg(ticker=str(sell["ticker"]), side="SELL", qty=1,
                                strike=float(sell["strike"]), right="PUT",
                                bid=float(sell["bid"]), ask=float(sell["ask"])),
                            Leg(ticker=str(buy["ticker"]), side="BUY", qty=1,
                                strike=float(buy["strike"]), right="PUT",
                                bid=float(buy["bid"]), ask=float(buy["ask"])),
                        ],
                metrics={"credit": round(credit, 2), "width": round(width, 2), "spot": round(spot, 2)},
            ))
        return opportunities

    def _find_synthetic(self, df: pd.DataFrame) -> list[Opportunity]:
        opportunities: list[Opportunity] = []
        for expiry, group in df.groupby("expiry"):
            for strike, pair in group.groupby("strike"):
                calls = pair[pair["right"] == "CALL"]
                puts = pair[pair["right"] == "PUT"]
                if calls.empty or puts.empty:
                    continue

                call = calls.iloc[0]
                put = puts.iloc[0]

                cost = (call["ask"] or 0) - (put["bid"] or 0)
                if abs(cost) < 1e-6:
                    continue

                side = "BUY" if cost < 0 else "SELL"
                synthetic_price = abs(cost)
                spot = float(pair["spot"].iloc[0])
                strike_f = float(strike)

                diff = abs(synthetic_price - (spot - strike_f))
                confidence = max(0.0, 1.0 - diff / max(spot, 1))

                opportunities.append(Opportunity(
                    root=str(call.get("root", "")),
                    strategy="synthetic",
                    side=side,
                    confidence=confidence,
                    legs=[
                        Leg(ticker=str(call["ticker"]), side="BUY" if side == "BUY" else "SELL",
                            qty=1, strike=strike_f, right="CALL",
                            bid=float(call["bid"]), ask=float(call["ask"])),
                        Leg(ticker=str(put["ticker"]), side="SELL" if side == "BUY" else "BUY",
                            qty=1, strike=strike_f, right="PUT",
                            bid=float(put["bid"]), ask=float(put["ask"])),
                    ],
                    metrics={
                        "cost": round(cost, 2),
                        "synthetic_price": round(synthetic_price, 2),
                        "spot": round(spot, 2),
                        "strike": strike_f,
                    },
                ))
        return opportunities


def _min_vol(opp: Opportunity) -> float:
    return min((l.bid + l.ask) for l in opp.legs if l.bid > 0 and l.ask > 0)


def assess_opportunity(opp: Opportunity) -> Assessment:
    strat = opp.strategy
    legs = opp.legs
    metrics = opp.metrics
    min_volume = _min_vol(opp)

    if strat in ("bear_call_spread", "bull_put_spread"):
        credit = metrics.get("credit", 0)
        width = metrics.get("width", 1)
        spot = metrics.get("spot", 0)
        roc = credit / width if width > 0 else 0

        sell_leg = legs[0]
        buy_leg = legs[1]
        sell_bid = sell_leg.bid
        buy_ask = buy_leg.ask

        if roc < 0.02:
            return Assessment("F", "Noise",
                f"{strat} credit={credit:.0f} width={width:.0f} — too small to trade",
                f"Credit of {credit:.0f} on {width:.0f} width is effectively noise.",
                roc, "Credit near zero")
        if buy_ask == 0 or sell_bid == 0:
            return Assessment("F", "No liquidity",
                f"{strat} — buy leg has no ask or sell leg has no bid",
                f"One leg has zero bid/ask. Unreliable pricing.",
                roc, "Missing market data")

        itm_depth = 0.0
        if strat == "bear_call_spread" and spot > 0:
            itm_depth = max(0, spot - sell_leg.strike) / spot
        elif strat == "bull_put_spread" and spot > 0:
            itm_depth = max(0, sell_leg.strike - spot) / spot

        warning = ""
        if itm_depth > 0.05:
            warning = f"Deep ITM ({itm_depth:.0%} below spot) — most credit is intrinsic"

        if itm_depth > 0.15:
            return Assessment("C", "Deep ITM spread",
                f"{strat} {sell_leg.strike:.0f}/{buy_leg.strike:.0f}  credit={credit:.0f}  roc={roc:.0%}",
                f"Sell {sell_leg.ticker} @ {sell_bid:.2f}\n"
                f"Buy  {buy_leg.ticker} @ {buy_ask:.2f}\n"
                f"Credit: {credit:.0f}  Width: {width:.0f}  ROC: {roc:.1%}\n"
                f"Warning: {warning}",
                roc, warning)

        if sell_bid < 1 and buy_ask < 1:
            warning = "Very low prices — wide relative spread"

        grade = "A" if roc >= 0.15 and min_volume > 100 and itm_depth < 0.02 else \
                "B" if roc >= 0.05 else \
                "C" if roc >= 0.02 else "F"

        tag = "OTM spread" if itm_depth < 0.02 else \
              "Near ATM spread" if itm_depth < 0.05 else \
              "ITM spread"

        summary = f"{strat} {sell_leg.strike:.0f}/{buy_leg.strike:.0f}  credit={credit:.0f}  roc={roc:.0%}"
        detail = (f"Sell {sell_leg.ticker} @ {sell_bid:.2f}\n"
                  f"Buy  {buy_leg.ticker} @ {buy_ask:.2f}\n"
                  f"Credit: {credit:.0f}  Width: {width:.0f}  ROC: {roc:.1%}")
        if warning:
            detail += f"\nWarning: {warning}"

        return Assessment(grade, tag, summary, detail, roc, warning)

    if strat == "iron_condor":
        net_credit = metrics.get("net_credit", 0)
        max_loss = metrics.get("max_loss", 1)
        roc = net_credit / max_loss if max_loss > 0 else 0

        if net_credit <= 0:
            return Assessment("F", "No credit", "Iron condor — net credit is zero or negative", "", 0, "No credit")

        grade = "A" if roc >= 0.25 and min_volume > 100 else \
                "B" if roc >= 0.15 else \
                "C" if roc >= 0.05 else "F"

        summary = f"Iron Condor  credit={net_credit:.0f}  max_loss={max_loss:.0f}  roc={roc:.0%}"
        detail_lines = []
        for l in legs:
            where = " (short)" if l.side == "SELL" else " (long)"
            detail_lines.append(f"  {l.side:4s} {l.ticker}  strike={l.strike:.0f}  {l.right:4s}{where}")
        detail_lines.append(f"Net credit: {net_credit:.0f}  Max loss: {max_loss:.0f}  ROC: {roc:.1%}")
        detail = "\n".join(detail_lines)
        tag = "OTM iron condor" if roc >= 0.20 else "Iron condor"
        return Assessment(grade, tag, summary, detail, roc, "")

    if strat == "mariposa":
        cost = metrics.get("cost", 0)
        width = metrics.get("width", 1)
        ratio = metrics.get("ratio", 1)
        roc = 1.0 - ratio if ratio <= 1 else 0

        if cost <= 0 or ratio <= 0:
            return Assessment("F", "No cost",
                f"Mariposa — cost={cost:.0f} ratio={ratio:.3f} — invalid",
                "", 0, "Invalid parameters")

        grade = "B" if roc >= 0.5 and min_volume > 50 else \
                "C" if roc >= 0.3 else "F"

        summary = f"Mariposa  cost={cost:.0f}  width={width:.0f}  roc={roc:.0%}"
        detail_lines = []
        for l in legs:
            detail_lines.append(f"  {l.side:4s} {l.ticker} x{l.qty}  strike={l.strike:.0f}")
        detail_lines.append(f"Cost: {cost:.0f}  Width: {width:.0f}  ROC: {roc:.1%}")
        tag = "Call butterfly"
        return Assessment(grade, tag, summary, "\n".join(detail_lines), roc, "")

    if strat == "synthetic":
        cost = metrics.get("cost", 0)
        spot = metrics.get("spot", 0)
        strike = metrics.get("strike", 0)
        confidence = opp.confidence

        near_spot = abs(strike - spot) / max(spot, 1) < 0.10
        min_vol = min((l.bid + l.ask) for l in legs if l.bid > 0 and l.ask > 0)

        if not near_spot:
            return Assessment("F", "Far OTM",
                f"Synthetic @ {strike:.0f} — far from spot {spot:.0f}, arb vanishes on execution",
                f"Strike {strike:.0f} is far from spot {spot:.0f}. "
                f"The put-call parity arb disappears in bid-ask friction.", confidence, "Far from spot")

        grade = "C" if min_vol > 50 else "F"
        tag = "ATM synthetic" if grade == "C" else "Low liquidity synthetic"

        summary = f"Synthetic {opp.side} @ {strike:.0f}  cost={cost:.2f}  conf={confidence:.3f}"
        detail_lines = []
        for l in legs:
            detail_lines.append(f"  {l.side:4s} {l.ticker}  strike={l.strike:.0f}  {l.right:4s}")
        detail_lines.append(f"Cost: {cost:.2f}  Spot: {spot:.0f}  Strike: {strike:.0f}")
        detail_lines.append(f"Note: Synthetic arbs require spread execution — legging risk")
        return Assessment(grade, tag, summary, "\n".join(detail_lines), confidence, "")

    if strat == "calendar":
        cost = metrics.get("cost", 0)
        near_dte = metrics.get("near_dte", 0)
        far_dte = metrics.get("far_dte", 0)
        return Assessment("C", "Calendar spread",
            f"Calendar {near_dte}d/{far_dte}d  cost={cost:.0f}",
            f"Sell {near_dte} DTE, buy {far_dte} DTE. Cost: {cost:.0f}",
            0, "Calendar spreads not fully validated")

    return Assessment("F", "Unknown", f"Unknown strategy: {strat}", "", 0, "")


def assess_all(opps: list[Opportunity]) -> list[tuple[Opportunity, Assessment]]:
    result = [(opp, assess_opportunity(opp)) for opp in opps]
    grade_order = {"A": 0, "B": 1, "C": 2, "F": 3}
    result.sort(key=lambda x: (grade_order.get(x[1].grade, 9), -x[1].roc))
    return result


def grade_counts(assessed: list[tuple[Opportunity, Assessment]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _, a in assessed:
        counts[a.grade] = counts.get(a.grade, 0) + 1
    return counts
