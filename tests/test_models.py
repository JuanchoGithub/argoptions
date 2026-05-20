from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from arg_options.broker.models import (
    Account,
    Balance,
    BalancesAndPositions,
    BankAccount,
    Book,
    BookEntry,
    CancelBankAccountRequest,
    CreateBankAccountRequest,
    CurrencyAvailability,
    Disclaimer,
    Holiday,
    Instrument,
    InstrumentType,
    IntradayPoint,
    InvestingProfile,
    InvestingProfileAnswer,
    InvestingProfileQuestion,
    Market,
    MarketDataPoint,
    Movement,
    Officer,
    OperationTerm,
    OperationType,
    Order,
    OrderBudget,
    OrderBudgetResult,
    OrderConfirmation,
    OrderOperation,
    Position,
    QuantityType,
    Settlement,
)


def test_instrument_type_enum_values():
    assert InstrumentType.BONOS.value == "BONOS"
    assert InstrumentType.LETRAS.value == "LETRAS"
    assert InstrumentType.NOBAC.value == "NOBAC"
    assert InstrumentType.LEBAC.value == "LEBAC"
    assert InstrumentType.ON.value == "ON"
    assert InstrumentType.FCI.value == "FCI"
    assert InstrumentType.CAUCIONES.value == "CAUCIONES"
    assert InstrumentType.ACCIONES.value == "ACCIONES"
    assert InstrumentType.ETF.value == "ETF"
    assert InstrumentType.CEDEARS.value == "CEDEARS"
    assert InstrumentType.OPCIONES.value == "OPCIONES"
    assert InstrumentType.FUTUROS.value == "FUTUROS"
    assert InstrumentType.ACCIONES_USA.value == "ACCIONES-USA"
    assert InstrumentType.FCI_EXTERIOR.value == "FCI-EXTERIOR"


def test_market_enum_values():
    assert Market.ROFEX.value == "ROFEX"
    assert Market.OTC.value == "OTC"
    assert Market.NYSE.value == "NYSE"
    assert Market.BYMA.value == "BYMA"


def test_settlement_enum_values():
    assert Settlement.INMEDIATA.value == "INMEDIATA"
    assert Settlement.A_24HS.value == "A-24HS"
    assert Settlement.A_48HS.value == "A-48HS"
    assert Settlement.A_72HS.value == "A-72HS"


def test_quantity_type_enum_values():
    assert QuantityType.DINERO.value == "DINERO"
    assert QuantityType.PAPELES.value == "PAPELES"
    assert QuantityType.CANTIDAD_TOTAL.value == "CANTIDAD-TOTAL"


def test_operation_term_enum_values():
    assert OperationTerm.POR_EL_DIA.value == "POR-EL-DÍA"
    assert OperationTerm.HASTA_SU_EJECUCION.value == "HASTA-SU-EJECUCIÓN"
    assert OperationTerm.VALIDA_HASTA_EL.value == "VÁLIDA-HASTA-EL"
    assert OperationTerm.SETENTA_DOS_HS.value == "72-HS"


def test_operation_type_enum_values():
    assert OperationType.PRECIO_DE_MERCADO.value == "PRECIO-DE-MERCADO"
    assert OperationType.PRECIO_LIMITE.value == "PRECIO-LIMITE"


def test_order_operation_enum_values():
    assert OrderOperation.COMPRA.value == "COMPRA"
    assert OrderOperation.VENTA.value == "VENTA"
    assert OrderOperation.SUSCRIPCION_FCI.value == "SUSCRIPCIÓN-FCI"
    assert OrderOperation.RESCATE_FCI.value == "RESCATE-FCI"
    assert OrderOperation.COLOCAR_CAUCION.value == "COLOCAR-CAUCIÓN"
    assert OrderOperation.STOP_ORDER.value == "Stop Order"
    assert OrderOperation.STOP_LIMIT.value == "Stop Limit"


def test_officer_creation():
    o = Officer(name="John", email="john@example.com", phone="123456")
    assert o.name == "John"
    assert o.email == "john@example.com"
    assert o.phone == "123456"


def test_account_creation():
    a = Account(account_number="123456", name="Test Account")
    assert a.account_number == "123456"
    assert a.name == "Test Account"
    assert a.officer is None


def test_account_with_officer():
    o = Officer(name="John", email="john@example.com", phone="123456")
    a = Account(account_number="123456", name="Test Account", officer=o)
    assert a.officer is not None
    assert a.officer.name == "John"


def test_bank_account_creation():
    b = BankAccount(
        bank_name="Test Bank",
        bank_account_number="ACC123",
        bank_identifier="BANKID",
        currency="ARS",
        tax_holder_identifier="CUIT123",
    )
    assert b.bank_name == "Test Bank"
    assert b.bank_account_number == "ACC123"
    assert b.bank_identifier == "BANKID"
    assert b.currency == "ARS"
    assert b.tax_holder_identifier == "CUIT123"


def test_balance_creation():
    b = Balance(name="Caja de Ahorro", symbol="ARS", amount=1000.50, settlement="INMEDIATA")
    assert b.name == "Caja de Ahorro"
    assert b.symbol == "ARS"
    assert b.amount == 1000.50
    assert b.settlement == "INMEDIATA"


def test_currency_availability_creation():
    b = Balance(name="Caja de Ahorro", symbol="ARS", amount=1000.0, settlement="INMEDIATA")
    ca = CurrencyAvailability(currency="ARS", availability=[b])
    assert ca.currency == "ARS"
    assert len(ca.availability) == 1
    assert ca.availability[0].amount == 1000.0


def test_position_creation():
    p = Position(ticker="GGAL", price=150.0, amount=100.0)
    assert p.ticker == "GGAL"
    assert p.price == 150.0
    assert p.amount == 100.0
    assert p.instrument is None


def test_position_with_instrument():
    p = Position(ticker="GGAL", price=150.0, amount=100.0, instrument="ACCIONES")
    assert p.instrument == "ACCIONES"


def test_balances_and_positions():
    b = Balance(name="Caja", symbol="ARS", amount=5000.0, settlement="INMEDIATA")
    ca = CurrencyAvailability(currency="ARS", availability=[b])
    pos = Position(ticker="GGAL", price=150.0, amount=100.0)
    bp = BalancesAndPositions(grouped_availability=[ca], grouped_instruments=[pos])
    assert len(bp.grouped_availability) == 1
    assert len(bp.grouped_instruments) == 1


def test_movement_creation():
    dt = datetime(2025, 1, 15, 10, 30, 0)
    m = Movement(
        agreement_date=dt,
        settlement_date=dt,
        currency="ARS",
        amount=5000.0,
        price=150.0,
        description="Compra acciones",
        ticker="GGAL",
        quantity=100.0,
        balance=500000.0,
    )
    assert m.agreement_date == dt
    assert m.ticker == "GGAL"
    assert m.quantity == 100.0


def test_instrument_creation():
    i = Instrument(ticker="GGAL", description="Grupo Financiero", currency="ARS", type="ACCIONES", market="BYMA")
    assert i.ticker == "GGAL"
    assert i.description == "Grupo Financiero"
    assert i.currency == "ARS"
    assert i.type == "ACCIONES"
    assert i.market == "BYMA"


def test_market_data_point_creation():
    dt = datetime(2025, 1, 15, 12, 0, 0)
    mdp = MarketDataPoint(
        date=dt, price=150.0, volume=10000.0,
        opening_price=148.0, max=152.0, min=147.0,
    )
    assert mdp.date == dt
    assert mdp.price == 150.0
    assert mdp.max == 152.0


def test_intraday_point_creation():
    dt = datetime(2025, 1, 15, 12, 0, 0)
    ip = IntradayPoint(date=dt, price=150.0, volume=500.0)
    assert ip.date == dt
    assert ip.price == 150.0


def test_book_entry_creation():
    be = BookEntry(position=1, price=150.0, quantity=1000.0)
    assert be.position == 1
    assert be.price == 150.0
    assert be.quantity == 1000.0


def test_book_creation():
    dt = datetime(2025, 1, 15, 12, 0, 0)
    offer = BookEntry(position=1, price=151.0, quantity=500.0)
    bid = BookEntry(position=1, price=149.0, quantity=800.0)
    book = Book(date=dt, offers=[offer], bids=[bid])
    assert book.date == dt
    assert len(book.offers) == 1
    assert len(book.bids) == 1
    price_level = book.offers[0]
    assert price_level.price == 151.0


def test_disclaimer_creation():
    d = Disclaimer(code="RISK", description="High risk", mandatory=True)
    assert d.code == "RISK"
    assert d.mandatory is True
    assert d.accepted is False


def test_order_budget_defaults():
    ob = OrderBudget(
        account_number="ACC001",
        quantity=100.0,
        price=150.0,
        ticker="GGAL",
        instrument_type="ACCIONES",
        quantity_type="PAPELES",
        operation_type="PRECIO-LIMITE",
        operation_term="POR-EL-DÍA",
        expiration_date=None,
        operation="COMPRA",
        settlement="A-48HS",
    )
    assert ob.stop_price is None


def test_order_budget_result_creation():
    dt = datetime(2025, 1, 15, 12, 0, 0)
    obr = OrderBudgetResult(
        id=1, instrument_type="ACCIONES", operation="COMPRA",
        ticker="GGAL", status="Aceptada", date=dt, settlement="A-48HS",
        quantity=100.0, order_type="LIMITE", operation_type="PRECIO-LIMITE",
        operation_max_date=dt, price=150.0, currency="ARS", amount=15000.0,
    )
    assert obr.id == 1
    assert obr.status == "Aceptada"
    assert obr.disclaimers == []
    assert obr.external_id is None


def test_order_confirmation_creation():
    d = Disclaimer(code="RISK", description="High risk", mandatory=True)
    oc = OrderConfirmation(
        account_number="ACC001", quantity=100.0, price=150.0,
        ticker="GGAL", instrument_type="ACCIONES", quantity_type="PAPELES",
        operation_type="PRECIO-LIMITE", operation_term="POR-EL-DÍA",
        expiration_date=None, operation="COMPRA", settlement="A-48HS",
        disclaimers=[d], external_id="ext-001", stop_price=None,
    )
    assert oc.account_number == "ACC001"
    assert oc.disclaimers[0].code == "RISK"
    assert oc.external_id == "ext-001"


def test_order_creation():
    dt = datetime(2025, 1, 15, 12, 0, 0)
    o = Order(
        id=1, instrument_type="ACCIONES", operation="COMPRA",
        ticker="GGAL", status="pending", date=dt, settlement="A-48HS",
        quantity=100.0, order_type="LIMITE", operation_type="PRECIO-LIMITE",
    )
    assert o.id == 1
    assert o.price == 0
    assert o.currency == ""
    assert o.amount == 0
    assert o.external_id is None
    assert o.operation_max_date is None


def test_holiday_creation():
    dt = datetime(2025, 1, 1, 0, 0, 0)
    h = Holiday(date=dt, description="New Year", is_usa=True)
    assert h.date == dt
    assert h.is_usa is True


def test_create_bank_account_request():
    req = CreateBankAccountRequest(
        account_number="ACC001", currency="ARS", cbu="CBU123",
        cuit="CUIT123", alias="alias", bank_account_number="BAN123",
    )
    assert req.cbu == "CBU123"
    assert req.alias == "alias"


def test_cancel_bank_account_request():
    req = CancelBankAccountRequest(
        account_number="ACC001", cbu="CBU123", bank_account_number="BAN123",
    )
    assert req.cbu == "CBU123"


def test_investing_profile_answer_creation():
    a = InvestingProfileAnswer(question_code="Q1", answer_code="A1")
    assert a.question_code == "Q1"
    assert a.answer_code == "A1"


def test_investing_profile_question_with_objects():
    answers = [
        InvestingProfileAnswer(question_code="Q1", answer_code="A1"),
        InvestingProfileAnswer(question_code="Q1", answer_code="A2"),
    ]
    ipq = InvestingProfileQuestion(code="Q1", description="Risk tolerance?", answers=answers)
    assert len(ipq.answers) == 2
    assert isinstance(ipq.answers[0], InvestingProfileAnswer)


def test_investing_profile_question_with_dicts():
    answers = [
        {"question_code": "Q1", "answer_code": "A1"},
        {"question_code": "Q1", "answer_code": "A2"},
    ]
    ipq = InvestingProfileQuestion(code="Q1", description="Risk tolerance?", answers=answers)
    assert len(ipq.answers) == 2
    assert isinstance(ipq.answers[0], InvestingProfileAnswer)
    assert ipq.answers[0].question_code == "Q1"
    assert ipq.answers[0].answer_code == "A1"


def test_investing_profile_creation():
    dt = datetime(2025, 1, 15, 0, 0, 0)
    ip = InvestingProfile(date=dt, type="MODERADO", description="Moderate profile")
    assert ip.type == "MODERADO"
    assert ip.description == "Moderate profile"


def test_all_models_serialize_with_asdict():
    dt = datetime(2025, 1, 15, 0, 0, 0)
    obr = OrderBudgetResult(
        id=1, instrument_type="ACCIONES", operation="COMPRA",
        ticker="GGAL", status="Aceptada", date=dt, settlement="A-48HS",
        quantity=100.0, order_type="LIMITE", operation_type="PRECIO-LIMITE",
        operation_max_date=dt, price=150.0, currency="ARS", amount=15000.0,
    )
    d = asdict(obr)
    assert d["id"] == 1
    assert d["ticker"] == "GGAL"
    assert d["disclaimers"] == []
    assert d["external_id"] is None

    o = Order(
        id=1, instrument_type="ACCIONES", operation="COMPRA",
        ticker="GGAL", status="pending", date=dt, settlement="A-48HS",
        quantity=100.0, order_type="LIMITE", operation_type="PRECIO-LIMITE",
    )
    d2 = asdict(o)
    assert d2["id"] == 1
    assert d2["external_id"] is None
