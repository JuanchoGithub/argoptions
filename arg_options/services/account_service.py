"""Shared service for account and order operations."""

from __future__ import annotations

import logging
from typing import Any, List

from arg_options.broker import create_broker
from arg_options.config.settings import load_settings

logger = logging.getLogger(__name__)


class AccountService:
    """Centralized service for account and order management."""

    def __init__(self, mode: str = "test"):
        self.mode = mode
        self.config = load_settings(mode)

    def get_account_status(self) -> List[dict]:
        """Fetches account details and balances."""
        broker = create_broker(self.config)
        try:
            broker.connect()
            accounts = broker.account.get_accounts()
            results = []
            for acc in accounts:
                balances = broker.account.get_available_balance(acc.account_number)
                results.append({
                    "account": acc,
                    "balances": balances
                })
            return results
        finally:
            try:
                broker.disconnect()
            except Exception:
                pass

    def get_active_orders(self) -> List[Any]:
        """Fetches all active orders for the account."""
        broker = create_broker(self.config)
        try:
            broker.connect()
            return broker.orders.get_active_orders(self.config.account_number)
        finally:
            try:
                broker.disconnect()
            except Exception:
                pass

    def cancel_orders(self, order_id: int | None = None, all_orders: bool = False) -> str:
        """Cancels specific or all active orders."""
        broker = create_broker(self.config)
        try:
            broker.connect()
            if all_orders or order_id is None:
                result = broker.orders.mass_cancel(self.config.account_number)
                return f"Mass cancel: {result}"
            else:
                result = broker.orders.cancel_order(self.config.account_number, order_id)
                return f"Order #{order_id} cancelled: {result.status}"
        finally:
            try:
                broker.disconnect()
            except Exception:
                pass
