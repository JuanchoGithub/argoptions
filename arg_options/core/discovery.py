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
        
        logger.info(f"Screening rules: DTE {dte_min}-{dte_max}, Volume >= {volume_min}, Spread <= {max_spread}")

        mask = (
            (df["dte"] >= dte_min)
            & (df["dte"] <= dte_max)
            & (df["volume"] >= volume_min)
            & (df["spread_pct"] <= max_spread)
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
                        metrics={"credit": round(credit, 2), "width": round(width, 2)},
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
                        metrics={"credit": round(credit, 2), "width": round(width, 2)},
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
