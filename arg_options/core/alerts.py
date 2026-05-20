from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from arg_options.broker import create_broker
from arg_options.broker.interfaces import BrokerConfig
from arg_options.core.chain import build_full_chain, get_latest_chain, persist_chain
from arg_options.db import get_positions, log_event

logger = logging.getLogger(__name__)


def _send_notification(message: str) -> None:
    print(f"[ALERT] {message}")


def check_near_expiry(
    df: list[dict],
    threshold_days: int,
) -> list[str]:
    alerts: list[str] = []
    today = date.today()

    for row in df:
        expiry_str = row.get("expiry", "")
        if not expiry_str or len(expiry_str) != 8:
            continue
        try:
            expiry = datetime.strptime(expiry_str, "%Y%m%d").date()
        except (ValueError, OverflowError):
            continue

        dte = (expiry - today).days
        if 0 <= dte <= threshold_days:
            alerts.append(
                f"{row.get('ticker', '?')} expires in {dte} days "
                f"(expiry {expiry_str})"
            )

    return alerts


def check_price_breach(
    positions: list[dict],
    current_prices: dict[str, float],
) -> list[str]:
    alerts: list[str] = []
    for pos in positions:
        ticker = pos.get("ticker", "")
        current = current_prices.get(ticker)
        if current is None:
            continue
        entry = pos.get("entry_price", 0) or 0
        side = pos.get("side", "").upper()
        if side == "BUY" and current <= entry * 0.95:
            alerts.append(
                f"{ticker} is down 5% from entry ({entry:.2f} -> {current:.2f})"
            )
        elif side == "SELL" and current >= entry * 1.05:
            alerts.append(
                f"{ticker} is up 5% from entry ({entry:.2f} -> {current:.2f})"
            )
    return alerts


def run_alerts_once(settings: BrokerConfig) -> list[str]:
    config = load_alert_config()
    all_alerts: list[str] = []

    chains = get_latest_chain(settings)
    if not chains:
        logger.info("No chain data for alerts, building fresh chain")
        broker = create_broker(settings)
        broker.connect()
        try:
            chains = build_full_chain(broker, settings)
            persist_chain(chains, settings)
        finally:
            try:
                broker.disconnect()
            except Exception:
                pass

    expiry_threshold = config.get("near_expiry_days", 7)
    expiry_alerts = check_near_expiry(chains, expiry_threshold)
    for msg in expiry_alerts:
        all_alerts.append(f"[NEAR EXPIRY] {msg}")

    positions = get_positions(open_only=True)
    if positions:
        current_prices: dict[str, float] = {}
        for row in chains:
            ticker = row.get("ticker", "")
            mid = row.get("mid", 0) or row.get("last", 0) or 0
            if mid > 0:
                current_prices[ticker] = float(mid)

        price_alerts = check_price_breach(positions, current_prices)
        for msg in price_alerts:
            all_alerts.append(f"[PRICE BREACH] {msg}")

    volume_threshold = config.get("unusual_volume_mult", 3.0)
    if chains:
        try:
            import pandas as pd
            df = pd.DataFrame(chains)
            avg_volume = df["volume"].mean()
            if avg_volume > 0:
                unusual = df[df["volume"] > avg_volume * volume_threshold]
                for _, row in unusual.iterrows():
                    ticker = row.get("ticker", "?")
                    vol = row.get("volume", 0)
                    all_alerts.append(
                        f"[UNUSUAL VOLUME] {ticker} volume={int(vol)} "
                        f"({vol / avg_volume:.1f}x average)"
                    )
        except Exception:
            pass

    iv_change_threshold = config.get("iv_change_threshold", 0.1)
    if chains:
        try:
            import pandas as pd
            df = pd.DataFrame(chains)
            avg_iv = df["iv"].mean()
            if avg_iv > 0:
                high_iv = df[df["iv"] > avg_iv * (1 + iv_change_threshold)]
                for _, row in high_iv.iterrows():
                    ticker = row.get("ticker", "?")
                    iv_val = row.get("iv", 0)
                    all_alerts.append(
                        f"[HIGH IV] {ticker} iv={iv_val:.2%} "
                        f"({iv_val / avg_iv:.1f}x average)"
                    )
        except Exception:
            pass

    for msg in all_alerts:
        _send_notification(msg)
        log_event("alert", msg, "")

    return all_alerts


def load_alert_config() -> dict:
    from arg_options.config.config_persist import load_yaml, resolve_project_root

    p = resolve_project_root() / "config" / "alerts.yaml"
    if not p.exists():
        return {
            "near_expiry_days": 7,
            "unusual_volume_mult": 3.0,
            "iv_change_threshold": 0.1,
        }
    data = load_yaml(p)
    return data.get("alerts", data)
