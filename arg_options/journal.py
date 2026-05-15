"""Sincroniza posiciones y órdenes desde PPI hacia SQLite."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from ppi_client.ppi import PPI

from arg_options import db as dbmod
from arg_options.ppi_client import with_retries
from arg_options.settings import AppSettings

logger = logging.getLogger(__name__)


def sync_journal(ppi: PPI, settings: AppSettings) -> dict[str, Any]:
    acc = settings.ppi_account_number
    if not acc:
        raise ValueError("Definí PPI_ACCOUNT_NUMBER para el diario.")
    conn = dbmod.connect(settings.db_path())
    summary: dict[str, Any] = {"account": acc}

    pos = with_retries(lambda: ppi.account.get_balance_and_positions(acc))
    dbmod.append_positions_snapshot(conn, acc, pos)
    summary["positions_groups"] = len(pos.get("groupedInstruments", []))

    date_to = datetime.today()
    date_from = date_to + timedelta(days=-120)
    orders = with_retries(lambda: ppi.orders.get_orders(acc, date_from, date_to))
    n = dbmod.append_orders_batch(conn, acc, orders or [])
    summary["orders_appended"] = n
    conn.close()
    return summary


def summarize_pnl_proxy(settings: AppSettings) -> dict[str, Any]:
    """
    PnL 'proxy' desde último snapshot de posiciones en JSON.
    No reemplaza contabilidad del broker; sirve para panel rápido.
    """
    conn = dbmod.connect(settings.db_path())
    cur = conn.execute(
        "SELECT payload FROM positions_raw WHERE account_number = ? ORDER BY id DESC LIMIT 1",
        (settings.ppi_account_number,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"error": "sin posiciones sincronizadas"}
    import json

    payload = json.loads(row["payload"])
    instruments = []
    for g in payload.get("groupedInstruments", []):
        for ins in g.get("instruments", []):
            instruments.append(
                {
                    "ticker": ins.get("ticker"),
                    "amount": ins.get("amount"),
                    "price": ins.get("price"),
                }
            )
    mkt = 0.0
    for i in instruments:
        amt = float(i.get("amount") or 0)
        px = float(i.get("price") or 0)
        mkt += amt * px
    return {"positions_count": len(instruments), "market_value_proxy": mkt, "raw_instruments": instruments}
