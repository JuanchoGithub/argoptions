from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from arg_options.broker import create_broker
from arg_options.broker.interfaces import Broker, BrokerConfig
from arg_options.db import (
    get_orders,
    get_positions,
    log_event,
    save_order,
    save_position,
)

logger = logging.getLogger(__name__)


def sync_journal(broker: Broker, config: BrokerConfig) -> str:
    broker_orders = broker.orders.get_orders(
        config.account_number,
        date_from=datetime.now() - timedelta(days=30),
    )

    synced = 0
    for o in broker_orders:
        data = {
            "order_id": o.id,
            "account_number": config.account_number,
            "ticker": o.ticker,
            "operation": o.operation,
            "quantity": o.quantity,
            "price": o.price,
            "status": o.status,
            "instrument_type": o.instrument_type,
            "settlement": o.settlement,
            "order_type": o.order_type,
            "operation_type": o.operation_type,
        }
        save_order(data)
        synced += 1

    log_event("journal_sync", f"Synced {synced} orders from broker", "")
    return f"Synced {synced} orders from broker"


def summarize_pnl(settings: BrokerConfig) -> str:
    positions = get_positions(open_only=True)
    if not positions:
        return "No open positions."

    total_pnl = 0.0
    lines: list[str] = []
    for p in positions:
        entry = p.get("entry_price", 0) or 0
        current = p.get("current_price", 0) or 0
        qty = p.get("quantity", 0) or 0
        pnl = p.get("pnl", None)
        if pnl is None:
            pnl = (current - entry) * qty
        total_pnl += pnl
        lines.append(
            f"{p.get('ticker', '?')} {p.get('side', '?')} "
            f"qty={qty} entry={entry:.2f} last={current:.2f} pnl={pnl:.2f}"
        )

    header = f"--- P&L Summary ({len(positions)} positions) ---"
    footer = f"Total P&L: {total_pnl:.2f}"
    return "\n".join([header] + lines + [footer])


def get_recent_trades(limit: int = 20) -> list[dict]:
    return get_orders(limit=limit)


def log_trade(
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    strategy: str = "",
) -> None:
    now = datetime.now().isoformat()
    position_data = {
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "entry_price": price,
        "current_price": price,
        "pnl": 0.0,
        "opened_at": now,
        "strategy": strategy,
    }
    save_position(position_data)
    log_event(
        "trade_logged",
        f"{side} {quantity} {ticker} @ {price} [{strategy}]",
        json.dumps(position_data),
    )
