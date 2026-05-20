from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from arg_options.broker.exceptions import BrokerError
from arg_options.broker.interfaces import OrderService
from arg_options.broker.models import (
    Disclaimer,
    Order,
    OrderBudget,
    OrderBudgetResult,
    OrderConfirmation,
)
from ppi_client.models.disclaimer import Disclaimer as PpiDisclaimer
from ppi_client.models.order import Order as PpiOrder
from ppi_client.models.order_budget import OrderBudget as PpiOrderBudget
from ppi_client.models.order_confirm import OrderConfirm


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _build_order_from_dict(d: dict) -> Order:
    return Order(
        id=d.get("id", 0),
        instrument_type=d.get("instrumentType", ""),
        operation=d.get("operation", ""),
        ticker=d.get("ticker", ""),
        status=d.get("status", ""),
        date=_parse_datetime(d.get("date")),
        settlement=d.get("settlement", ""),
        quantity=d.get("quantity", 0),
        order_type=d.get("orderType", ""),
        operation_type=d.get("operationType", ""),
        operation_max_date=_parse_datetime(d.get("operationMaxDate")),
        price=d.get("price", 0),
        currency=d.get("currency", ""),
        amount=d.get("amount", 0),
        external_id=d.get("externalId"),
    )


def _build_order_budget_result_from_dict(d: dict) -> OrderBudgetResult:
    disclaimers = [
        Disclaimer(
            code=di.get("code", ""),
            description=di.get("description", ""),
            mandatory=di.get("mandatory", False),
            accepted=di.get("accepted", False),
        )
        for di in d.get("disclaimers", [])
    ]
    return OrderBudgetResult(
        id=d.get("id", 0),
        instrument_type=d.get("instrumentType", ""),
        operation=d.get("operation", ""),
        ticker=d.get("ticker", ""),
        status=d.get("status", ""),
        date=_parse_datetime(d.get("date")),
        settlement=d.get("settlement", ""),
        quantity=d.get("quantity", 0),
        order_type=d.get("orderType", ""),
        operation_type=d.get("operationType", ""),
        operation_max_date=_parse_datetime(d.get("operationMaxDate")),
        price=d.get("price", 0),
        currency=d.get("currency", ""),
        amount=d.get("amount", 0),
        disclaimers=disclaimers,
        external_id=d.get("externalId"),
    )


class PpiOrderService(OrderService):
    def __init__(self, ppi: Any) -> None:
        self._ppi = ppi

    def get_orders(
        self,
        account_number: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> list[Order]:
        try:
            data = self._ppi.orders.get_orders(
                account_number, date_from=date_from, date_to=date_to
            )
            return [_build_order_from_dict(d) for d in data]
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_active_orders(self, account_number: str) -> list[Order]:
        try:
            data = self._ppi.orders.get_active_orders(account_number)
            return [_build_order_from_dict(d) for d in data]
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_order_detail(
        self, account_number: str, order_id: int
    ) -> Optional[Order]:
        try:
            data = self._ppi.orders.get_order_detail(
                account_number, order_id, None
            )
            if not data:
                return None
            return _build_order_from_dict(data)
        except Exception as e:
            raise BrokerError(str(e)) from e

    def budget(self, budget: OrderBudget) -> OrderBudgetResult:
        try:
            ppi_budget = PpiOrderBudget(
                account_number=budget.account_number,
                quantity=budget.quantity,
                price=budget.price,
                ticker=budget.ticker,
                instrument_type=budget.instrument_type,
                quantity_type=budget.quantity_type,
                operation_type=budget.operation_type,
                operation_term=budget.operation_term,
                expiration_date=budget.expiration_date,
                operation=budget.operation,
                settlement=budget.settlement,
                stop_price=budget.stop_price,
            )
            result = self._ppi.orders.budget(ppi_budget)
            return _build_order_budget_result_from_dict(result)
        except Exception as e:
            raise BrokerError(str(e)) from e

    def confirm(self, confirmation: OrderConfirmation) -> Order:
        try:
            ppi_disclaimers = [
                PpiDisclaimer(
                    code=d.code,
                    description=d.description,
                    mandatory=d.mandatory,
                    accepted=d.accepted,
                )
                for d in confirmation.disclaimers
            ]
            ppi_confirm = OrderConfirm(
                account_number=confirmation.account_number,
                quantity=confirmation.quantity,
                price=confirmation.price,
                ticker=confirmation.ticker,
                instrument_type=confirmation.instrument_type,
                quantity_type=confirmation.quantity_type,
                operation_type=confirmation.operation_type,
                operation_term=confirmation.operation_term,
                expiration_date=confirmation.expiration_date,
                operation=confirmation.operation,
                settlement=confirmation.settlement,
                disclaimers=ppi_disclaimers,
                external_id=confirmation.external_id,
                stop_price=confirmation.stop_price,
            )
            result = self._ppi.orders.confirm(ppi_confirm)
            return _build_order_from_dict(result)
        except Exception as e:
            raise BrokerError(str(e)) from e

    def cancel_order(self, account_number: str, order_id: int) -> Order:
        try:
            ppi_order = PpiOrder(
                order_id=order_id,
                account_number=account_number,
                external_id=None,
            )
            result = self._ppi.orders.cancel_order(ppi_order)
            return _build_order_from_dict(result)
        except Exception as e:
            raise BrokerError(str(e)) from e

    def mass_cancel(self, account_number: str) -> str:
        try:
            result = self._ppi.orders.mass_cancel_order(account_number)
            return str(result)
        except Exception as e:
            raise BrokerError(str(e)) from e
