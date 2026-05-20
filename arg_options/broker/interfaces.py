from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from arg_options.broker.models import (
    Account,
    BalancesAndPositions,
    BankAccount,
    Balance,
    Book,
    Holiday,
    Instrument,
    IntradayPoint,
    InvestingProfile,
    InvestingProfileQuestion,
    MarketDataPoint,
    Movement,
    Order,
    OrderBudgetResult,
    OrderConfirmation,
    OrderBudget,
)


@dataclass
class BrokerConfig:
    api_key: str = ""
    api_secret: str = ""
    account_number: str = ""
    authorized_client: str = ""
    client_key: str = ""
    sandbox: bool = True
    allow_live_orders: bool = False
    daily_notional_cap_ars: float = 1_000_000
    max_contracts_per_order: int = 100
    contract_multiplier: int = 1
    risk_free_rate: float = 0.05


class AccountService(ABC):
    @abstractmethod
    def get_accounts(self) -> list[Account]:
        ...

    @abstractmethod
    def get_bank_accounts(self, account_number: str) -> list[BankAccount]:
        ...

    @abstractmethod
    def get_available_balance(self, account_number: str) -> list[Balance]:
        ...

    @abstractmethod
    def get_balance_and_positions(self, account_number: str) -> BalancesAndPositions:
        ...

    @abstractmethod
    def get_movements(
        self,
        account_number: str,
        date_from: datetime,
        date_to: datetime,
        ticker: Optional[str] = None,
    ) -> list[Movement]:
        ...

    @abstractmethod
    def get_investing_profile_questions(self) -> list[InvestingProfileQuestion]:
        ...

    @abstractmethod
    def get_investing_profile_instrument_types(self) -> list[str]:
        ...

    @abstractmethod
    def get_investing_profile(self, account_number: str) -> InvestingProfile:
        ...

    @abstractmethod
    def set_investing_profile(
        self,
        account_number: str,
        answers: list[dict],
        instrument_types: list[str],
    ) -> InvestingProfile:
        ...

    @abstractmethod
    def register_bank_account(
        self,
        account_number: str,
        currency: str,
        cbu: str,
        cuit: str,
        alias: str,
        bank_account_number: str,
    ) -> str:
        ...

    @abstractmethod
    def cancel_bank_account(
        self,
        account_number: str,
        cbu: str,
        bank_account_number: str,
    ) -> str:
        ...


class ConfigurationService(ABC):
    @abstractmethod
    def get_instrument_types(self) -> list[str]:
        ...

    @abstractmethod
    def get_markets(self) -> list[str]:
        ...

    @abstractmethod
    def get_settlements(self) -> list[str]:
        ...

    @abstractmethod
    def get_quantity_types(self) -> list[str]:
        ...

    @abstractmethod
    def get_operation_terms(self) -> list[str]:
        ...

    @abstractmethod
    def get_operation_types(self) -> list[str]:
        ...

    @abstractmethod
    def get_operations(self) -> list[str]:
        ...

    @abstractmethod
    def get_holidays(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        is_usa: bool = False,
    ) -> list[Holiday]:
        ...

    @abstractmethod
    def is_local_holiday(self) -> bool:
        ...

    @abstractmethod
    def is_usa_holiday(self) -> bool:
        ...


class MarketDataService(ABC):
    @abstractmethod
    def search_instruments(
        self,
        ticker: str,
        name: Optional[str] = None,
        market: Optional[str] = None,
        instrument_type: Optional[str] = None,
    ) -> list[Instrument]:
        ...

    @abstractmethod
    def get_historical(
        self,
        ticker: str,
        instrument_type: str,
        settlement: str,
        date_from: datetime,
        date_to: datetime,
    ) -> list[MarketDataPoint]:
        ...

    @abstractmethod
    def get_current(
        self,
        ticker: str,
        instrument_type: str,
        settlement: str,
    ) -> Optional[MarketDataPoint]:
        ...

    @abstractmethod
    def get_book(
        self,
        ticker: str,
        instrument_type: str,
        settlement: str,
    ) -> Optional[Book]:
        ...

    @abstractmethod
    def get_intraday(
        self,
        ticker: str,
        instrument_type: str,
        settlement: str,
    ) -> list[IntradayPoint]:
        ...

    @abstractmethod
    def estimate_bonds(
        self,
        ticker: str,
        date: datetime,
        quantity_type: str,
        quantity: float,
        price: float,
    ) -> dict[str, Any]:
        ...


class OrderService(ABC):
    @abstractmethod
    def get_orders(
        self,
        account_number: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> list[Order]:
        ...

    @abstractmethod
    def get_active_orders(self, account_number: str) -> list[Order]:
        ...

    @abstractmethod
    def get_order_detail(self, account_number: str, order_id: int) -> Optional[Order]:
        ...

    @abstractmethod
    def budget(self, budget: OrderBudget) -> OrderBudgetResult:
        ...

    @abstractmethod
    def confirm(self, confirmation: OrderConfirmation) -> Order:
        ...

    @abstractmethod
    def cancel_order(self, account_number: str, order_id: int) -> Order:
        ...

    @abstractmethod
    def mass_cancel(self, account_number: str) -> str:
        ...


RealtimeMarketDataCallback = Callable[[dict[str, Any]], None]
RealtimeAccountCallback = Callable[[dict[str, Any]], None]
ConnectionCallback = Callable[[], None]
DisconnectionCallback = Callable[[], None]


class RealtimeService(ABC):
    @abstractmethod
    def connect_to_market_data(
        self,
        on_connect: ConnectionCallback,
        on_disconnect: DisconnectionCallback,
        on_data: RealtimeMarketDataCallback,
    ) -> None:
        ...

    @abstractmethod
    def connect_to_account(
        self,
        on_connect: ConnectionCallback,
        on_disconnect: DisconnectionCallback,
        on_data: RealtimeAccountCallback,
    ) -> None:
        ...

    @abstractmethod
    def subscribe_to_element(
        self,
        ticker: str,
        instrument_type: str,
        settlement: str,
    ) -> None:
        ...

    @abstractmethod
    def subscribe_to_account_data(self, account_number: str) -> None:
        ...

    @abstractmethod
    def start_connections(self) -> None:
        ...

    @abstractmethod
    def stop_connections(self) -> None:
        ...


class Broker(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def sandbox(self) -> bool:
        ...

    @abstractmethod
    def connect(self) -> None:
        ...

    @abstractmethod
    def disconnect(self) -> None:
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        ...

    @property
    @abstractmethod
    def account(self) -> AccountService:
        ...

    @property
    @abstractmethod
    def configuration(self) -> ConfigurationService:
        ...

    @property
    @abstractmethod
    def market_data(self) -> MarketDataService:
        ...

    @property
    @abstractmethod
    def orders(self) -> OrderService:
        ...

    @property
    @abstractmethod
    def realtime(self) -> RealtimeService:
        ...

    @property
    @abstractmethod
    def config(self) -> BrokerConfig:
        ...
