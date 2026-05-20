from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from arg_options.broker import create_broker
from arg_options.broker.interfaces import Broker, BrokerConfig
from arg_options.broker.models import (
    Disclaimer,
    Order,
    OrderBudget,
    OrderConfirmation,
    OperationTerm,
    OperationType,
    OrderOperation,
    QuantityType,
    Settlement,
)
from arg_options.broker.exceptions import BrokerError, OrderBudgetError
from arg_options.db import log_event, save_order

logger = logging.getLogger(__name__)

_NOTIONAL_CHECKED: set[str] = set()


def _build_budget(
    config: BrokerConfig,
    ticker: str,
    operation: str,
    quantity: float,
    price: float,
    instrument_type: str,
    settlement: str,
    stop_price: float | None = None,
) -> OrderBudget:
    return OrderBudget(
        account_number=config.account_number,
        quantity=quantity,
        price=price,
        ticker=ticker,
        instrument_type=instrument_type,
        quantity_type=QuantityType.PAPELES,
        operation_type=OperationType.PRECIO_LIMITE if price > 0 else OperationType.PRECIO_DE_MERCADO,
        operation_term=OperationTerm.POR_EL_DIA,
        expiration_date=None,
        operation=operation,
        settlement=settlement,
        stop_price=stop_price,
    )


def _build_confirmation(
    config: BrokerConfig,
    ticker: str,
    operation: str,
    quantity: float,
    price: float,
    instrument_type: str,
    settlement: str,
    disclaimers: list[Disclaimer],
    external_id: str | None = None,
    stop_price: float | None = None,
) -> OrderConfirmation:
    return OrderConfirmation(
        account_number=config.account_number,
        quantity=quantity,
        price=price,
        ticker=ticker,
        instrument_type=instrument_type,
        quantity_type=QuantityType.PAPELES,
        operation_type=OperationType.PRECIO_LIMITE if price > 0 else OperationType.PRECIO_DE_MERCADO,
        operation_term=OperationTerm.POR_EL_DIA,
        expiration_date=None,
        operation=operation,
        settlement=settlement,
        disclaimers=disclaimers,
        external_id=external_id,
        stop_price=stop_price,
    )


def _place_order(
    broker: Broker,
    config: BrokerConfig,
    ticker: str,
    operation: str,
    quantity: float,
    instrument_type: str,
    settlement: str,
    price: float = 0.0,
    stop_price: float | None = None,
) -> dict:
    if not config.sandbox and not config.allow_live_orders:
        raise BrokerError(
            "Live orders are disabled. Set ALLOW_LIVE_ORDERS=true in env to enable."
        )

    if quantity > config.max_contracts_per_order:
        raise BrokerError(
            f"Order quantity {quantity} exceeds max_contracts_per_order ({config.max_contracts_per_order})"
        )

    estimated_notional = quantity * price * config.contract_multiplier
    if estimated_notional > config.daily_notional_cap_ars:
        raise BrokerError(
            f"Estimated notional {estimated_notional:.0f} ARS exceeds "
            f"daily_notional_cap_ars ({config.daily_notional_cap_ars:.0f})"
        )

    budget = _build_budget(
        config=config,
        ticker=ticker,
        operation=operation,
        quantity=quantity,
        price=price,
        instrument_type=instrument_type,
        settlement=settlement,
        stop_price=stop_price,
    )

    try:
        budget_result = broker.orders.budget(budget)
    except BrokerError:
        raise
    except Exception as e:
        raise OrderBudgetError(f"Budget request failed: {e}") from e

    if budget_result.status.lower() not in ("aceptada", "accepted", "ok"):
        raise OrderBudgetError(
            f"Budget rejected with status: {budget_result.status}"
        )

    for d in budget_result.disclaimers:
        d.accepted = True

    confirmation = _build_confirmation(
        config=config,
        ticker=ticker,
        operation=operation,
        quantity=quantity,
        price=budget_result.price,
        instrument_type=instrument_type,
        settlement=settlement,
        disclaimers=budget_result.disclaimers,
        external_id=budget_result.external_id,
        stop_price=stop_price,
    )

    try:
        order = broker.orders.confirm(confirmation)
    except BrokerError:
        raise
    except Exception as e:
        raise BrokerError(f"Order confirmation failed: {e}") from e

    order_data = {
        "order_id": order.id,
        "account_number": config.account_number,
        "ticker": ticker,
        "operation": operation,
        "quantity": quantity,
        "price": order.price,
        "status": order.status,
        "instrument_type": instrument_type,
        "settlement": settlement,
        "order_type": order.order_type,
        "operation_type": budget_result.operation_type,
        "external_id": order.external_id,
        "raw_response": json.dumps({
            "budget_id": budget_result.id,
            "order_id": order.id,
        }),
    }
    save_order(order_data)
    log_event(
        "order_placed",
        f"{operation} {quantity} {ticker} @ {order.price}",
        json.dumps(order_data),
    )

    return {
        "order": {
            "id": order.id,
            "ticker": ticker,
            "operation": operation,
            "quantity": quantity,
            "price": order.price,
            "status": order.status,
        },
        "budget": {
            "id": budget_result.id,
            "amount": budget_result.amount,
        },
    }


def place_market_order(
    broker: Broker,
    config: BrokerConfig,
    ticker: str,
    operation: str,
    quantity: float,
    instrument_type: str,
    settlement: str = "A-48HS",
) -> dict:
    return _place_order(
        broker=broker,
        config=config,
        ticker=ticker,
        operation=operation,
        quantity=quantity,
        instrument_type=instrument_type,
        settlement=settlement,
        price=0.0,
        stop_price=None,
    )


def place_limit_order(
    broker: Broker,
    config: BrokerConfig,
    ticker: str,
    operation: str,
    quantity: float,
    price: float,
    instrument_type: str,
    settlement: str = "A-48HS",
) -> dict:
    return _place_order(
        broker=broker,
        config=config,
        ticker=ticker,
        operation=operation,
        quantity=quantity,
        instrument_type=instrument_type,
        settlement=settlement,
        price=price,
        stop_price=None,
    )


def place_stop_order(
    broker: Broker,
    config: BrokerConfig,
    ticker: str,
    operation: str,
    quantity: float,
    price: float,
    stop_price: float,
    instrument_type: str,
    settlement: str = "A-48HS",
) -> dict:
    return _place_order(
        broker=broker,
        config=config,
        ticker=ticker,
        operation=operation,
        quantity=quantity,
        instrument_type=instrument_type,
        settlement=settlement,
        price=price,
        stop_price=stop_price,
    )


def cancel_order(
    broker: Broker,
    config: BrokerConfig,
    order_id: int,
) -> dict:
    order = broker.orders.cancel_order(config.account_number, order_id)
    data = {
        "order_id": order.id,
        "account_number": config.account_number,
        "ticker": order.ticker,
        "status": order.status,
    }
    save_order(data)
    log_event("order_cancelled", f"Cancelled order {order_id}", json.dumps(data))
    return data


def cancel_all(broker: Broker, config: BrokerConfig) -> str:
    result = broker.orders.mass_cancel(config.account_number)
    log_event("mass_cancel", f"Mass cancel result: {result}", "")
    return result


def get_open_orders(broker: Broker, config: BrokerConfig) -> list[Order]:
    return broker.orders.get_active_orders(config.account_number)


def get_order_history(
    broker: Broker,
    config: BrokerConfig,
    days: int = 100,
) -> list[Order]:
    date_from = datetime.now() - timedelta(days=days)
    return broker.orders.get_orders(
        config.account_number,
        date_from=date_from,
    )
