"""Órdenes con dry-run, tope diario y flag explícito para producción."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from ppi_client.models.disclaimer import Disclaimer
from ppi_client.models.order_budget import OrderBudget
from ppi_client.models.order_confirm import OrderConfirm
from ppi_client.ppi import PPI

from arg_options import db as dbmod
from arg_options.ppi_client import with_retries
from arg_options.settings import AppSettings

logger = logging.getLogger(__name__)


@dataclass
class LimitOrderRequest:
    ticker: str
    side: str  # COMPRA o VENTA
    quantity: int
    limit_price: float
    settlement: str = "A-48HS"
    instrument_type: str = "OPCIONES"
    quantity_type: str = "Papeles"
    operation_type: str = "PRECIO-LIMITE"
    operation_term: str = "HASTA-SU-EJECUCIÓN"


def _estimate_notional(req: LimitOrderRequest, contract_multiplier: int) -> float:
    return abs(req.quantity) * abs(req.limit_price) * contract_multiplier


def place_limit_order(
    ppi: PPI,
    settings: AppSettings,
    req: LimitOrderRequest,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    """
    Flujo: validar límites → budget → confirm (solo si live y no dry_run).
    """
    acc = settings.ppi_account_number
    if not acc:
        raise ValueError("PPI_ACCOUNT_NUMBER requerido.")

    if dry_run is None:
        dry_run = not settings.allow_live_orders

    mult = settings.contract_multiplier
    notional = _estimate_notional(req, mult)
    conn = dbmod.connect(settings.db_path())
    try:
        used = dbmod.get_daily_notional(conn)
        cap = settings.daily_order_notional_cap_ars

        if req.quantity > settings.max_contracts_per_order:
            raise ValueError(
                f"quantity {req.quantity} supera MAX_CONTRACTS_PER_ORDER={settings.max_contracts_per_order}"
            )

        if used + notional > cap:
            raise ValueError(f"Tope diario excedido: usado={used} + orden={notional} > cap={cap}")

        payload: dict[str, Any] = {
            "dry_run": dry_run or not settings.allow_live_orders,
            "allow_live_orders": settings.allow_live_orders,
            "request": req.__dict__,
            "estimated_notional_ars": notional,
        }

        force_dry = dry_run or not settings.allow_live_orders
        if force_dry:
            logger.info("Dry-run orden %s — no se llama a PPI confirm.", req.ticker)
            payload["status"] = "skipped_dry_run"
            return payload

        op = req.side
        if op.upper() == "COMPRA":
            op = "Compra"
        elif op.upper() == "VENTA":
            op = "Venta"

        op_max = datetime.now() + timedelta(days=1)
        budget = with_retries(
            lambda: ppi.orders.budget(
                OrderBudget(
                    accountNumber=acc,
                    quantity=req.quantity,
                    price=req.limit_price,
                    ticker=req.ticker,
                    instrumentType=req.instrument_type,
                    quantityType=req.quantity_type,
                    operationType=req.operation_type,
                    operationTerm=req.operation_term,
                    operationMaxDate=op_max,
                    operation=op,
                    settlement=req.settlement,
                )
            )
        )
        disclaimers_raw = budget.get("disclaimers") or []
        accepted = [Disclaimer(code=d["code"], accepted=True) for d in disclaimers_raw]
        ext = str(uuid.uuid4())[:32]
        confirm = with_retries(
            lambda: ppi.orders.confirm(
                OrderConfirm(
                    accountNumber=acc,
                    quantity=req.quantity,
                    price=req.limit_price,
                    ticker=req.ticker,
                    instrumentType=req.instrument_type,
                    quantityType=req.quantity_type,
                    operationType=req.operation_type,
                    operationTerm=req.operation_term,
                    operationMaxDate=op_max,
                    operation=op,
                    settlement=req.settlement,
                    disclaimers=accepted,
                    externalId=ext,
                )
            )
        )
        dbmod.add_daily_notional(conn, notional)
        payload["status"] = "submitted"
        payload["budget"] = budget
        payload["confirm"] = confirm
        return payload
    finally:
        conn.close()
