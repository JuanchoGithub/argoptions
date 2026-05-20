from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class InstrumentType(str, Enum):
    BONOS = "BONOS"
    LETRAS = "LETRAS"
    NOBAC = "NOBAC"
    LEBAC = "LEBAC"
    ON = "ON"
    FCI = "FCI"
    CAUCIONES = "CAUCIONES"
    ACCIONES = "ACCIONES"
    ETF = "ETF"
    CEDEARS = "CEDEARS"
    OPCIONES = "OPCIONES"
    FUTUROS = "FUTUROS"
    ACCIONES_USA = "ACCIONES-USA"
    FCI_EXTERIOR = "FCI-EXTERIOR"


class Market(str, Enum):
    ROFEX = "ROFEX"
    OTC = "OTC"
    NYSE = "NYSE"
    BYMA = "BYMA"


class Settlement(str, Enum):
    INMEDIATA = "INMEDIATA"
    A_24HS = "A-24HS"
    A_48HS = "A-48HS"
    A_72HS = "A-72HS"


class QuantityType(str, Enum):
    DINERO = "DINERO"
    PAPELES = "PAPELES"
    CANTIDAD_TOTAL = "CANTIDAD-TOTAL"


class OperationTerm(str, Enum):
    POR_EL_DIA = "POR-EL-DÍA"
    HASTA_SU_EJECUCION = "HASTA-SU-EJECUCIÓN"
    VALIDA_HASTA_EL = "VÁLIDA-HASTA-EL"
    SETENTA_DOS_HS = "72-HS"


class OperationType(str, Enum):
    PRECIO_DE_MERCADO = "PRECIO-DE-MERCADO"
    PRECIO_LIMITE = "PRECIO-LIMITE"


class OrderOperation(str, Enum):
    COMPRA = "COMPRA"
    VENTA = "VENTA"
    SUSCRIPCION_FCI = "SUSCRIPCIÓN-FCI"
    RESCATE_FCI = "RESCATE-FCI"
    COLOCAR_CAUCION = "COLOCAR-CAUCIÓN"
    STOP_ORDER = "Stop Order"
    STOP_LIMIT = "Stop Limit"


@dataclass
class Officer:
    name: str
    email: str
    phone: str


@dataclass
class Account:
    account_number: str
    name: str
    officer: Optional[Officer] = None


@dataclass
class BankAccount:
    bank_name: str
    bank_account_number: str
    bank_identifier: str
    currency: str
    tax_holder_identifier: str


@dataclass
class Balance:
    name: str
    symbol: str
    amount: float
    settlement: str


@dataclass
class CurrencyAvailability:
    currency: str
    availability: list[Balance]


@dataclass
class Position:
    ticker: str
    price: float
    amount: float
    instrument: Optional[str] = None


@dataclass
class BalancesAndPositions:
    grouped_availability: list[CurrencyAvailability]
    grouped_instruments: list[Position]


@dataclass
class Movement:
    agreement_date: datetime
    settlement_date: datetime
    currency: str
    amount: float
    price: float
    description: str
    ticker: Optional[str] = None
    quantity: float = 0
    balance: float = 0


@dataclass
class Instrument:
    ticker: str
    description: str
    currency: str
    type: str
    market: str


@dataclass
class MarketDataPoint:
    date: datetime
    price: float
    volume: float
    opening_price: float
    max: float
    min: float


@dataclass
class IntradayPoint:
    date: datetime
    price: float
    volume: float


@dataclass
class BookEntry:
    position: int
    price: float
    quantity: float


@dataclass
class Book:
    date: datetime
    offers: list[BookEntry]
    bids: list[BookEntry]


@dataclass
class Disclaimer:
    code: str
    description: str
    mandatory: bool
    accepted: bool = False


@dataclass
class OrderBudget:
    account_number: str
    quantity: float
    price: float
    ticker: str
    instrument_type: str
    quantity_type: str
    operation_type: str
    operation_term: str
    expiration_date: Optional[datetime]
    operation: str
    settlement: str
    stop_price: Optional[float] = None


@dataclass
class OrderBudgetResult:
    id: int
    instrument_type: str
    operation: str
    ticker: str
    status: str
    date: datetime
    settlement: str
    quantity: float
    order_type: str
    operation_type: str
    operation_max_date: datetime
    price: float
    currency: str
    amount: float
    disclaimers: list[Disclaimer] = field(default_factory=list)
    external_id: Optional[str] = None


@dataclass
class OrderConfirmation:
    account_number: str
    quantity: float
    price: float
    ticker: str
    instrument_type: str
    quantity_type: str
    operation_type: str
    operation_term: str
    expiration_date: Optional[datetime]
    operation: str
    settlement: str
    disclaimers: list[Disclaimer]
    external_id: Optional[str] = None
    stop_price: Optional[float] = None


@dataclass
class Order:
    id: int
    instrument_type: str
    operation: str
    ticker: str
    status: str
    date: datetime
    settlement: str
    quantity: float
    order_type: str
    operation_type: str
    operation_max_date: Optional[datetime] = None
    price: float = 0
    currency: str = ""
    amount: float = 0
    external_id: Optional[str] = None


@dataclass
class Holiday:
    date: datetime
    description: str
    is_usa: bool


@dataclass
class CreateBankAccountRequest:
    account_number: str
    currency: str
    cbu: str
    cuit: str
    alias: str
    bank_account_number: str


@dataclass
class CancelBankAccountRequest:
    account_number: str
    cbu: str
    bank_account_number: str


@dataclass
class InvestingProfileQuestion:
    code: str
    description: str
    answers: list[InvestingProfileAnswer]

    def __post_init__(self):
        if self.answers and isinstance(self.answers[0], dict):
            self.answers = [InvestingProfileAnswer(**a) for a in self.answers]


@dataclass
class InvestingProfileAnswer:
    question_code: str
    answer_code: str


@dataclass
class InvestingProfile:
    date: datetime
    type: str
    description: str
