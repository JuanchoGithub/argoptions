# PPI Python Library — API Documentation

## Overview

**PPI** (Portfolio Personal Inversiones) is an Argentine brokerage API that provides programmatic access to account management, market data, order placement, and real-time streaming for local and international financial instruments.

**Python library:** `ppi-client`

**Requirements:** Python 3.10.2+

---

## Installation & Setup

```bash
pip install ppi-client
```

### Required Imports

```python
from ppi_client.api.constants import ACCOUNTDATA_TYPE_ACCOUNT_NOTIFICATION, ACCOUNTDATA_TYPE_PUSH_NOTIFICATION, \
    ACCOUNTDATA_TYPE_ORDER_NOTIFICATION
from ppi_client.models.account_movements import AccountMovements
from ppi_client.models.bank_account_request import BankAccountRequest
from ppi_client.models.foreign_bank_account_request import ForeignBankAccountRequest, ForeignBankAccountRequestDTO
from ppi_client.models.cancel_bank_account_request import CancelBankAccountRequest
from ppi_client.models.order import Order
from ppi_client.ppi import PPI
from ppi_client.models.order_budget import OrderBudget
from ppi_client.models.order_confirm import OrderConfirm
from ppi_client.models.disclaimer import Disclaimer
from ppi_client.models.investing_profile import InvestingProfile
from ppi_client.models.investing_profile_answer import InvestingProfileAnswer
from ppi_client.models.instrument import Instrument
from datetime import datetime, timedelta
from ppi_client.models.estimate_bonds import EstimateBonds
import asyncio
import json
import traceback
import os
```

---

## Environment Configuration

### Sandbox vs Production

```python
# Sandbox environment (testing)
ppi = PPI(sandbox=True)

# Production environment (live)
ppi = PPI(sandbox=False)
```

### Login

```python
ppi.account.login_api('<public_key>', '<private_key>')
```

Credentials are provided by PPI for the API. Each environment (sandbox/production) has its own set of keys.

---

## Account Service

All account-related operations are accessed via `ppi.account.*`.

### `get_accounts()`

Returns a list of accounts associated with the authenticated user, including officer contact information.

```python
print("\nGetting bank account information of %s" % account_number)
bank_accounts = ppi.account.get_bank_accounts(account_number)
for bank_account in bank_accounts:
    print(bank_account)
```

**Response:**

```json
[
  {
    "accountNumber": "string",
    "name": "string",
    "officer": {
      "name": "string",
      "eMail": "string",
      "phone": "string"
    }
  }
]
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `accountNumber` | string | Account number |
| `name` | string | Account name or alias |
| `officer.name` | string | Assigned officer name |
| `officer.eMail` | string | Officer email address |
| `officer.phone` | string | Officer phone number |

---

### `get_bank_accounts(account_number)`

Returns the registered bank accounts for a given brokerage account.

```python
bank_accounts = ppi.account.get_bank_accounts(account_number)
for bank_account in bank_accounts:
    print(bank_account)
```

**Response:**

Array of bank account objects. Shape is consistent with the account listing response above.

**Fields:**

| Field | Type | Description |
|---|---|---|
| `accountNumber` | string | Account number |
| `name` | string | Bank account description / alias |
| `officer.name` | string | Officer name |
| `officer.eMail` | string | Officer email |
| `officer.phone` | string | Officer phone |

---

### `get_available_balance(account_number)`

Returns available balances broken down by currency and settlement type.

```python
print("\nGetting available balance of %s" % account_number)
balances = ppi.account.get_available_balance(account_number)
for balance in balances:
    print("Currency %s - Settlement %s - Amount %s %s" % (
        balance['name'], balance['settlement'], balance['symbol'], balance['amount']))
```

**Response:**

```json
[
  {
    "name": "string",
    "simbol": "string",
    "amount": 0,
    "settlement": "string"
  }
]
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `name` | string | Currency name (e.g. `ARS`, `USD`) |
| `simbol` | string | Currency symbol (e.g. `$`, `U$S`) |
| `amount` | number | Available amount |
| `settlement` | string | Settlement term (e.g. `INMEDIATA`, `A-24HS`, `A-48HS`, `A-72HS`) |

---

### `get_balance_and_positions(account_number)`

Returns grouped currency availability and instrument positions for the account.

```python
print("\nGetting balance and positions of %s" % account_number)
balances_positions = ppi.account.get_balance_and_positions(account_number)
for balance in balances_positions["groupedAvailability"]:
    for currency in balance['availability']:
        print("Currency %s Settlement %s Amount %s %s" % (
            currency['name'], currency['settlement'], currency['symbol'], currency['amount']))
for instruments in balances_positions["groupedInstruments"]:
    print("Instrument %s " % instruments['name'])
    for instrument in instruments['instruments']:
        print("Ticker %s Price %s Amount %s" % (
            instrument['ticker'], instrument['price'], instrument['amount']))
```

**Response:**

```json
[
  {
    "currency": "string",
    "availability": [
      {
        "name": "string",
        "simbol": "string",
        "amount": 0,
        "settlement": "string"
      }
    ]
  }
]
```

**Fields (`groupedAvailability`):**

| Field | Type | Description |
|---|---|---|
| `currency` | string | Currency code |
| `availability[].name` | string | Currency name |
| `availability[].simbol` | string | Currency symbol |
| `availability[].amount` | number | Available amount |
| `availability[].settlement` | string | Settlement term |

**Fields (`groupedInstruments`):**

The response also contains a `groupedInstruments` key (not shown in the simplified JSON above). Each entry contains:

| Field | Type | Description |
|---|---|---|
| `name` | string | Instrument type name |
| `instruments[].ticker` | string | Ticker symbol |
| `instruments[].price` | number | Last / current price |
| `instruments[].amount` | number | Quantity held |

---

### `get_movements(AccountMovements)`

Returns account movements filtered by a date range and optional currency.

```python
print("\nGetting movements of %s" % account_number)
movements = ppi.account.get_movements(AccountMovements(account_number, datetime(2021, 12, 1),
                                                       datetime(2021, 12, 31), None))
for mov in movements:
    print("%s %s - Currency %s Amount %s " % (
        mov['settlementDate'], mov['description'], mov['currency'], mov['amount']))
```

**Constructor:** `AccountMovements(account_number, start_date, end_date, currency)`

| Parameter | Type | Description |
|---|---|---|
| `account_number` | string | Account number |
| `start_date` | datetime | Start of date range |
| `end_date` | datetime | End of date range |
| `currency` | string or None | Currency filter (e.g. `"ARS"`, `"USD"`) |

**Response:**

```json
[
  {
    "agreementDate": "2022-01-19T14:32:51.776Z",
    "settlementDate": "2022-01-19T14:32:51.776Z",
    "currency": "string",
    "amount": 0,
    "price": 0,
    "description": "string",
    "ticker": "string",
    "quantity": 0,
    "balance": 0
  }
]
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `agreementDate` | string (ISO 8601) | Trade / agreement date |
| `settlementDate` | string (ISO 8601) | Settlement date |
| `currency` | string | Currency code |
| `amount` | number | Movement amount |
| `price` | number | Unit price |
| `description` | string | Movement description |
| `ticker` | string | Instrument ticker (if applicable) |
| `quantity` | number | Quantity of instruments |
| `balance` | number | Running balance after movement |

---

### `get_investing_profile_questions()`

Returns the investing profile questionnaire with all questions and possible answers.

```python
investing_profile_questions = ppi.account.get_investing_profile_questions()
for question in investing_profile_questions:
    print("%s - %s " % (question["code"], question["description"]))
    for answer in question["answers"]:
        print("%s - %s " % (answer["code"], answer["description"]))
```

**Response:**

```json
[
  {
    "code": "string",
    "description": "string",
    "answers": [
      {
        "code": "string",
        "description": "string"
      }
    ]
  }
]
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `code` | string | Question code (used when submitting answers) |
| `description` | string | Question text |
| `answers[].code` | string | Answer code |
| `answers[].description` | string | Answer text |

---

### `get_investing_profile_instrument_types()`

Returns the list of instrument type options available for the investing profile.

```python
investing_profile_instrument_types = ppi.account.get_investing_profile_instrument_types()
for instrument in investing_profile_instrument_types:
    print(instrument)
```

**Response:**

```json
["string"]
```

Returns a list of instrument type strings (e.g. `"BONOS-(RENTA-FIJA)"`, `"ACCIONES-ARGENTINAS-(RENTA-VARIABLE-LOCAL)"`, etc.).

---

### `get_investing_profile(account_number)`

Returns the current investing profile for the account.

```python
profile = ppi.account.get_investing_profile(account_number)
print("Date: %s - Type: %s - %s" % (profile["date"], profile["type"], profile["description"]))
```

**Response:**

```json
{
  "date": "2022-06-14T19:47:11.402Z",
  "type": "string",
  "description": "string"
}
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `date` | string (ISO 8601) | Date the profile was set |
| `type` | string | Profile type code |
| `description` | string | Profile description (e.g. risk level) |

---

### `set_investing_profile(InvestingProfile)`

Submits answers to the investing profile questionnaire and sets the instrument types the account is allowed to trade.

```python
answers = [InvestingProfileAnswer("GRADO_CONOCIMIENTO", "A"), InvestingProfileAnswer("INVERSION_ANTERIOR", "C"),
           InvestingProfileAnswer("PORCENTAJE_AHORRO", "A"), InvestingProfileAnswer("PLAZO_MAXIMO", "C"),
           InvestingProfileAnswer("INVERSION_PREOCUPACION", "A"),
           InvestingProfileAnswer("PORCENTAJE_DISMINUCION", "B"),
           InvestingProfileAnswer("MONTO_INVERSION", "A")]
instrument_types = ["BONOS-(RENTA-FIJA)", "ACCIONES-ARGENTINAS-(RENTA-VARIABLE-LOCAL)",
                    "FIDEICOMISOS-FINANCIEROS"]
new_profile = ppi.account.set_investing_profile(InvestingProfile(account_number, answers, instrument_types))
print("New investing profile - Date: %s - Type: %s - %s" % (new_profile["date"], new_profile["type"],
                                                            new_profile["description"]))
```

**Constructor:** `InvestingProfile(account_number, answers, instrument_types)`

| Parameter | Type | Description |
|---|---|---|
| `account_number` | string | Account number |
| `answers` | list[InvestingProfileAnswer] | List of question code → answer code pairs |
| `instrument_types` | list[string] | Allowed instrument types |

**`InvestingProfileAnswer(code, answer)`**

| Parameter | Type | Description |
|---|---|---|
| `code` | string | Question code (from `get_investing_profile_questions()`) |
| `answer` | string | Answer code (from the question's answer options) |

**Response:**

```json
{
  "date": "2022-06-14T19:47:11.402Z",
  "type": "string",
  "description": "string"
}
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `date` | string (ISO 8601) | Date the profile was saved |
| `type` | string | Profile type code (e.g. `CONSERVADOR`, `MODERADO`, `AGRESIVO`) |
| `description` | string | Profile description |

---

### `register_bank_account(BankAccountRequest)`

Registers a local (ARS) bank account for withdrawals.

```python
bank_account_request = ppi.account.register_bank_account(
    BankAccountRequest(account_number, currency="ARS", cbu="", cuit="00000000000",
                       alias="ALIASCBU", bank_account_number=""))
print(bank_account_request)
```

**Constructor:** `BankAccountRequest(account_number, currency, cbu, cuit, alias, bank_account_number)`

| Parameter | Type | Description |
|---|---|---|
| `account_number` | string | Brokerage account number |
| `currency` | string | Currency (`"ARS"`) |
| `cbu` | string | CBU number (bank account identifier) |
| `cuit` | string | Tax ID (CUIT/CUIL) |
| `alias` | string | CBU alias |
| `bank_account_number` | string | Bank account number |

**Response:**

Returns the registered bank account object. The exact response shape mirrors the bank account listing.

---

### `register_foreign_bank_account(ForeignBankAccountRequest)`

Registers a foreign (USD) bank account for international wire transfers. Requires a supporting document (bank statement or equivalent).

```python
data = ForeignBankAccountRequestDTO(account_number=account_number, cuit="00000000000", intermediary_bank="",
                                    intermediary_bank_account_number="", intermediary_bank_swift="",
                                    bank="The Bank of Tokyo-Mitsubishi, Ltd.", bank_account_number="12345678",
                                    swift="ABC", ffc="Juan Perez")
extract_file_route = "C:\\Documents\\example.pdf"
extract_file = (os.path.basename(extract_file_route), open(extract_file_route, 'rb'))
foreign_bank_account_request = ppi.account.register_foreign_bank_account(
    ForeignBankAccountRequest(data, extract_file))
print(foreign_bank_account_request)
```

**`ForeignBankAccountRequestDTO` fields:**

| Field | Type | Description |
|---|---|---|
| `account_number` | string | Brokerage account number |
| `cuit` | string | Tax ID |
| `intermediary_bank` | string | Intermediary bank name (if applicable) |
| `intermediary_bank_account_number` | string | Intermediary bank account number |
| `intermediary_bank_swift` | string | Intermediary bank SWIFT code |
| `bank` | string | Destination bank name |
| `bank_account_number` | string | Destination bank account number |
| `swift` | string | Destination bank SWIFT code |
| `ffc` | string | Beneficiary name (For Further Credit) |

**`ForeignBankAccountRequest(dto, file_tuple)`**

| Parameter | Type | Description |
|---|---|---|
| `dto` | ForeignBankAccountRequestDTO | Account details |
| `file_tuple` | tuple (str, file object) | `(filename, open(file, 'rb'))` — supporting document |

**Response:**

Returns the registered foreign bank account object.

---

### `cancel_bank_account(CancelBankAccountRequest)`

Cancels / unregisters a previously registered bank account.

```python
cancel_bank_account_request = ppi.account.cancel_bank_account(
    CancelBankAccountRequest(account_number, cbu="0000000000000000000000", bank_account_number=""))
print(cancel_bank_account_request)
```

**Constructor:** `CancelBankAccountRequest(account_number, cbu, bank_account_number)`

| Parameter | Type | Description |
|---|---|---|
| `account_number` | string | Brokerage account number |
| `cbu` | string | CBU of the account to cancel |
| `bank_account_number` | string | Bank account number to cancel |

**Response:**

Returns the cancellation confirmation object.

---

## Configuration Service

All configuration methods are accessed via `ppi.configuration.*`.

### `get_instrument_types()`

Returns the list of available instrument types.

```python
print("\nGetting instrument types")
instruments = ppi.configuration.get_instrument_types()
for item in instruments:
    print(item)
```

**Response:**

```json
["BONOS", "LETRAS", "NOBAC", "LEBAC", "ON", "FCI", "CAUCIONES", "ACCIONES", "ETF", "CEDEARS", "OPCIONES", "FUTUROS", "ACCIONES-USA", "FCI-EXTERIOR"]
```

**Fields:**

| Value | Description |
|---|---|
| `BONOS` | Bonds |
| `LETRAS` | Treasury bills (letras) |
| `NOBAC` | Negotiable obligations (NOBAC) |
| `LEBAC` | Central bank letters (LEBAC) |
| `ON` | Corporate bonds (Obligaciones Negociables) |
| `FCI` | Mutual funds (Fondos Comunes de Inversión) |
| `CAUCIONES` | Collateralized loans (caución) |
| `ACCIONES` | Argentine stocks |
| `ETF` | Exchange traded funds |
| `CEDEARS` | Argentine depositary receipts |
| `OPCIONES` | Options |
| `FUTUROS` | Futures |
| `ACCIONES-USA` | US stocks |
| `FCI-EXTERIOR` | Foreign mutual funds |

---

### `get_markets()`

Returns the list of available markets.

```python
print("\nGetting markets")
markets = ppi.configuration.get_markets()
for item in markets:
    print(item)
```

**Response:**

```json
["ROFEX", "OTC", "NYSE", "BYMA"]
```

| Value | Description |
|---|---|
| `ROFEX` | Rosario Futures Exchange |
| `OTC` | Over the counter |
| `NYSE` | New York Stock Exchange |
| `BYMA` | Bolsas y Mercados Argentinos |

---

### `get_settlements()`

Returns the list of available settlement terms.

```python
print("\nGetting settlements")
settlements = ppi.configuration.get_settlements()
for item in settlements:
    print(item)
```

**Response:**

```json
["INMEDIATA", "A-24HS", "A-48HS", "A-72HS"]
```

| Value | Description |
|---|---|
| `INMEDIATA` | Immediate settlement (t+0) |
| `A-24HS` | 24-hour settlement (t+1) |
| `A-48HS` | 48-hour settlement (t+2) |
| `A-72HS` | 72-hour settlement (t+3) |

---

### `get_quantity_types()`

Returns the list of quantity types used in orders.

```python
quantity_types = ppi.configuration.get_quantity_types()
```

**Response:**

```json
["DINERO", "PAPELES", "CANTIDAD-TOTAL"]
```

| Value | Description |
|---|---|
| `DINERO` | Money amount (nominal value) |
| `PAPELES` | Number of shares / contracts |
| `CANTIDAD-TOTAL` | Total quantity |

---

### `get_operation_terms()`

Returns the list of order validity terms.

```python
operation_terms = ppi.configuration.get_operation_terms()
```

**Response:**

```json
["POR-EL-DÍA", "HASTA-SU-EJECUCIÓN", "VÁLIDA-HASTA-EL", "72-HS"]
```

| Value | Description |
|---|---|
| `POR-EL-DÍA` | Good for the day |
| `HASTA-SU-EJECUCIÓN` | Good till executed (GTC) |
| `VÁLIDA-HASTA-EL` | Valid until a specific date |
| `72-HS` | 72 hours |

---

### `get_operation_types()`

Returns the list of order operation types.

```python
operation_types = ppi.configuration.get_operation_types()
```

**Response:**

```json
["PRECIO-DE-MERCADO", "PRECIO-LIMITE"]
```

| Value | Description |
|---|---|
| `PRECIO-DE-MERCADO` | Market price order |
| `PRECIO-LIMITE` | Limit price order |

---

### `get_operations()`

Returns the list of operation sides (buy/sell/etc).

```python
operations = ppi.configuration.get_operations()
```

**Response:**

```json
["COMPRA", "VENTA", "SUSCRIPCIÓN-FCI", "RESCATE-FCI", "COLOCAR-CAUCIÓN"]
```

| Value | Description |
|---|---|
| `COMPRA` | Buy |
| `VENTA` | Sell |
| `SUSCRIPCIÓN-FCI` | Mutual fund subscription |
| `RESCATE-FCI` | Mutual fund redemption |
| `COLOCAR-CAUCIÓN` | Place collateralized loan |

---

### `get_holidays(start_date, end_date, is_usa)`

Returns the list of holidays within a date range. Use `is_usa=True` for US holidays.

```python
print("\nGet local holidays for the current year")
holidays = ppi.configuration.get_holidays(start_date=datetime(2022, 1, 1), end_date=datetime(2022, 12, 31))
for holiday in holidays:
    print("%s - %s " % (holiday["date"][0:10], holiday["description"]))

print("\nGet USA holidays for the current year")
holidays = ppi.configuration.get_holidays(start_date=datetime(2022, 1, 1), end_date=datetime(2022, 12, 31),
                                          is_usa=True)
for holiday in holidays:
    print("%s - %s " % (holiday["date"][0:10], holiday["description"]))
```

**Response:**

```json
[
  {
    "date": "2022-06-14T19:19:33.529Z",
    "description": "string",
    "isUSA": true
  }
]
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `date` | string (ISO 8601) | Holiday date |
| `description` | string | Holiday name / description |
| `isUSA` | boolean | Whether it is a US holiday |

---

### `is_local_holiday()`

Returns `True` if today is a local (Argentine) holiday, `False` otherwise.

```python
print("\nIs today a local holiday?")
print(ppi.configuration.is_local_holiday())
```

**Response:** `true` / `false` (boolean)

---

### `is_usa_holiday()`

Returns `True` if today is a US holiday, `False` otherwise.

```python
print("\nIs today a holiday in the USA?")
print(ppi.configuration.is_usa_holiday())
```

**Response:** `true` / `false` (boolean)

---

## Market Data Service

All market data methods are accessed via `ppi.marketdata.*`.

### `search_instrument(ticker, name, market, type)`

Searches for instruments by ticker, name, market, and/or type. All parameters are strings; pass empty string `""` to skip a filter.

```python
print("\nSearching instruments")
instruments = ppi.marketdata.search_instrument("GGAL", "", "Byma", "Acciones")
for ins in instruments:
    print(ins)
```

**Response:**

```json
[
  {
    "ticker": "string",
    "description": "string",
    "currency": "string",
    "type": "string",
    "market": "string"
  }
]
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `ticker` | string | Instrument ticker symbol |
| `description` | string | Instrument name / description |
| `currency` | string | Trading currency |
| `type` | string | Instrument type |
| `market` | string | Market where it trades |

---

### `search(ticker, type, settlement, date_from, date_to)`

Returns historical market data (daily OHLCV) for a given instrument.

```python
print("\nSearching MarketData")
market_data = ppi.marketdata.search("GGAL", "Acciones", "A-48HS", datetime(2021, 1, 1), datetime(2021, 12, 31))
for ins in market_data:
    print("%s - %s - Volume %s - Opening %s - Min %s - Max %s" % (
        ins['date'], ins['price'], ins['volume'], ins['openingPrice'], ins['min'], ins['max']))
```

**Response:**

```json
[
  {
    "date": "string",
    "price": 0,
    "volume": 0,
    "openingPrice": 0,
    "max": 0,
    "min": 0
  }
]
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `date` | string (ISO 8601) | Date of the data point |
| `price` | number | Closing / last price |
| `volume` | number | Trading volume |
| `openingPrice` | number | Opening price |
| `max` | number | Maximum price |
| `min` | number | Minimum price |

---

### `current(ticker, type, settlement)`

Returns the most recent price data point for an instrument.

```python
print("\nSearching Current MarketData")
current_market_data = ppi.marketdata.current("GGAL", "Acciones", "A-48HS")
print(current_market_data)
```

**Response:**

```json
{
  "date": "string",
  "price": 0,
  "volume": 0,
  "openingPrice": 0,
  "max": 0,
  "min": 0
}
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `date` | string (ISO 8601) | Date / time of the data point |
| `price` | number | Last traded price |
| `volume` | number | Volume at last trade |
| `openingPrice` | number | Session opening price |
| `max` | number | Session maximum price |
| `min` | number | Session minimum price |

---

### `book(ticker, type, settlement)`

Returns the current order book (bids and offers) for an instrument.

```python
print("\nSearching Current Book")
current_book = ppi.marketdata.book("GGAL", "Acciones", "A-48HS")
print(current_book)
```

**Response:**

```json
{
  "date": "2022-02-24T12:31:04.581Z",
  "offers": [
    {
      "position": 0,
      "price": 0,
      "quantity": 0
    }
  ],
  "bids": [
    {
      "position": 0,
      "price": 0,
      "quantity": 0
    }
  ]
}
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `date` | string (ISO 8601) | Timestamp of the snapshot |
| `offers[].position` | number | Position in the book (ascending by price) |
| `offers[].price` | number | Offer (ask) price |
| `offers[].quantity` | number | Quantity available at that price |
| `bids[].position` | number | Position in the book (descending by price) |
| `bids[].price` | number | Bid price |
| `bids[].quantity` | number | Quantity bid at that price |

---

### `intraday(ticker, type, settlement)`

Returns intraday price data for the current trading session.

```python
print("\nSearching Intraday MarketData")
intraday_market_data = ppi.marketdata.intraday("GGAL", "Acciones", "A-48HS")
for intra in intraday_market_data:
    print(intra)
```

**Response:**

```json
[
  {
    "date": "string",
    "price": 0,
    "volume": 0
  }
]
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `date` | string (ISO 8601) | Timestamp of the intraday data point |
| `price` | number | Price at that time |
| `volume` | number | Volume at that time |

---

### `estimate_bonds(EstimateBonds)`

Estimates bond prices using the bond calculator.

```python
estimate = ppi.marketdata.estimate_bonds(EstimateBonds(ticker="CUAP", date=datetime.today(),
                                                       quantityType="PAPELES", quantity=100, price=4555))
print(estimate)
```

**Constructor:** `EstimateBonds(ticker, date, quantityType, quantity, price)`

| Parameter | Type | Description |
|---|---|---|
| `ticker` | string | Bond ticker symbol |
| `date` | datetime | Valuation date |
| `quantityType` | string | Type of quantity (`"PAPELES"`, `"DINERO"`, `"CANTIDAD-TOTAL"`) |
| `quantity` | number | Quantity |
| `price` | number | Price input for estimation |

**Response:**

Returns estimated bond price information.

---

## Orders Service

All order methods are accessed via `ppi.orders.*`.

### `get_orders(account, date_from, date_to)`

Returns a list of orders for the account within a date range.

```python
print("\nGet orders")
orders = ppi.orders.get_orders(account_number, date_from=datetime.today() + timedelta(days=-100),
                               date_to=datetime.today())
for order in orders:
    print(order)
```

**Response:**

```json
[
  {
    "id": 0,
    "instrumentType": "string",
    "operation": "string",
    "ticker": "string",
    "status": "string",
    "date": "2022-01-31T19:28:19.627Z",
    "settlement": "string",
    "quantity": 0,
    "orderType": "string",
    "operationType": "string",
    "operationMaxDate": "2022-01-31T19:28:19.627Z",
    "price": 0,
    "currency": "string",
    "amount": 0,
    "externalID": "string"
  }
]
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `id` | number | Order ID |
| `instrumentType` | string | Instrument type (e.g. `ACCIONES`, `BONOS`) |
| `operation` | string | Operation side (`COMPRA` / `VENTA`) |
| `ticker` | string | Instrument ticker |
| `status` | string | Order status code |
| `date` | string (ISO 8601) | Order creation date |
| `settlement` | string | Settlement term |
| `quantity` | number | Order quantity |
| `orderType` | string | Quantity type (`DINERO` / `PAPELES` / `CANTIDAD-TOTAL`) |
| `operationType` | string | Operation type (`PRECIO-DE-MERCADO` / `PRECIO-LIMITE`) |
| `operationMaxDate` | string (ISO 8601) | Order validity expiration |
| `price` | number | Order price |
| `currency` | string | Currency |
| `amount` | number | Total amount |
| `externalID` | string | External reference ID |

---

### `get_active_orders(account)`

Returns all currently active (open) orders for the account.

```python
print("\nGet active orders")
active_orders = ppi.orders.get_active_orders(account_number)
for order in active_orders:
    print(order)
```

**Response:**

Returns an array of order objects with the same shape as `get_orders()` but filtered to active / open orders only.

---

### `budget(OrderBudget)`

Calculates the budget for an order, including fees and disclaimers that must be accepted before placing the order.

```python
budget_order = ppi.orders.budget(OrderBudget(account_number, 10000, 150, "GGAL", "ACCIONES", "Dinero",
                                             "PRECIO-LIMITE", "HASTA-SU-EJECUCIÓN", None, "Compra",
                                             "INMEDIATA"))
print(budget_order)
disclaimers_order = budget_order['disclaimers']
```

**Constructor:** `OrderBudget(account_number, quantity, price, ticker, instrument, quantity_type, operation_type, term, expiration_date, operation, settlement, stop_price=None)`

| Parameter | Type | Description |
|---|---|---|
| `account_number` | string | Account number |
| `quantity` | number | Quantity |
| `price` | number | Price |
| `ticker` | string | Instrument ticker |
| `instrument` | string | Instrument type |
| `quantity_type` | string | `"Dinero"` / `"Papeles"` / `"Cantidad-Total"` |
| `operation_type` | string | `"PRECIO-DE-MERCADO"` / `"PRECIO-LIMITE"` |
| `term` | string | Validity term (e.g. `"HASTA-SU-EJECUCIÓN"`) |
| `expiration_date` | string or None | Expiration date for `"VÁLIDA-HASTA-EL"` term |
| `operation` | string | `"Compra"` / `"Venta"` / `"Stop Order"` |
| `settlement` | string | Settlement term |
| `stop_price` | number or None | Stop price (only for stop orders) |

**Response:**

```json
{
  "id": 0,
  "instrumentType": "string",
  "operation": "string",
  "ticker": "string",
  "status": "string",
  "date": "2022-01-31T19:41:14.986Z",
  "settlement": "string",
  "quantity": 0,
  "orderType": "string",
  "operationType": "string",
  "operationMaxDate": "2022-01-31T19:41:14.986Z",
  "price": 0,
  "currency": "string",
  "amount": 0,
  "disclaimers": [
    {
      "code": "string",
      "description": "string",
      "mandatory": true,
      "accepted": true
    }
  ]
}
```

**Fields (in addition to standard order fields):**

| Field | Type | Description |
|---|---|---|
| `disclaimers[].code` | string | Disclaimer code |
| `disclaimers[].description` | string | Disclaimer text |
| `disclaimers[].mandatory` | boolean | Whether acceptance is mandatory |
| `disclaimers[].accepted` | boolean | Whether the disclaimer has been accepted |

---

### `confirm(OrderConfirm)`

Places (confirms) an order after accepting its disclaimers.

```python
accepted_disclaimers = []
for disclaimer in disclaimers_order:
    accepted_disclaimers.append(Disclaimer(disclaimer['code'], True))
confirmation = ppi.orders.confirm(OrderConfirm(account_number, 10000, 150, "GGAL", "ACCIONES", "Dinero",
                                               "PRECIO-LIMITE", "HASTA-SU-EJECUCIÓN", None, "Compra",
                                               "INMEDIATA", accepted_disclaimers, None))
print(confirmation)
order_id = confirmation["id"]
```

**Constructor:** `OrderConfirm(account_number, quantity, price, ticker, instrument, quantity_type, operation_type, term, expiration_date, operation, settlement, disclaimers, external_id, stop_price=None)`

| Parameter | Type | Description |
|---|---|---|
| `account_number` | string | Account number |
| `quantity` | number | Quantity |
| `price` | number | Price |
| `ticker` | string | Instrument ticker |
| `instrument` | string | Instrument type |
| `quantity_type` | string | Quantity type |
| `operation_type` | string | Operation type |
| `term` | string | Validity term |
| `expiration_date` | string or None | Expiration date |
| `operation` | string | `"Compra"` / `"Venta"` / `"Stop Order"` |
| `settlement` | string | Settlement term |
| `disclaimers` | list[Disclaimer] | Accepted disclaimers |
| `external_id` | string or None | External reference ID |
| `stop_price` | number or None | Stop price (only for stop orders) |

**`Disclaimer(code, accepted)`**

| Parameter | Type | Description |
|---|---|---|
| `code` | string | Disclaimer code from the budget response |
| `accepted` | boolean | Must be `True` to place the order |

**Response:**

```json
{
  "id": 0,
  "instrumentType": "string",
  "operation": "string",
  "ticker": "string",
  "status": "string",
  "date": "2022-02-24T11:59:18.708Z",
  "settlement": "string",
  "quantity": 0,
  "orderType": "string",
  "operationType": "string",
  "operationMaxDate": "2022-02-24T11:59:18.708Z",
  "price": 0,
  "currency": "string",
  "amount": 0,
  "externalID": "string"
}
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `id` | number | Created order ID (use this for subsequent operations) |
| `instrumentType` | string | Instrument type |
| `operation` | string | Operation side |
| `ticker` | string | Ticker |
| `status` | string | Order status |
| `date` | string (ISO 8601) | Creation timestamp |
| `settlement` | string | Settlement term |
| `quantity` | number | Quantity |
| `orderType` | string | Quantity type |
| `operationType` | string | Operation type |
| `operationMaxDate` | string (ISO 8601) | Validity expiration |
| `price` | number | Price |
| `currency` | string | Currency |
| `amount` | number | Total amount |
| `externalID` | string | External reference ID |

---

### Stop Orders

Stop orders use the same `OrderBudget` and `OrderConfirm` flow but with `operation="Stop Order"` and a `stop_price` parameter.

**Stop Order — Budget:**

```python
budget_stop_order = ppi.orders.budget(OrderBudget(account_number, 1000, 3000.5, "GOOGL", "CEDEARS",
                                                  "Papeles", "PRECIO-LIMITE", "HASTA-SU-EJECUCIÓN", None,
                                                  "Stop Order", "INMEDIATA", 2998.5))
print(budget_stop_order)
disclaimers_stop_order = budget_stop_order['disclaimers']
```

**Stop Order — Confirm:**

```python
accepted_disclaimers = []
for disclaimer in disclaimers_stop_order:
    accepted_disclaimers.append(Disclaimer(disclaimer['code'], True))
stop_order_confirmation = ppi.orders.confirm(OrderConfirm(account_number, 1000, 3000.5, "GOOGL", "CEDEARS",
                                                          "Papeles", "PRECIO-LIMITE", "HASTA-SU-EJECUCIÓN",
                                                          None, "Stop Order", "INMEDIATA",
                                                          accepted_disclaimers, None, 2998.5))
print(stop_order_confirmation)
stop_order_id = stop_order_confirmation["id"]
```

**Key difference:** `operation="Stop Order"` and the additional `stop_price` parameter (the price that triggers the stop order). The response shape is identical to a standard order confirmation.

---

### `get_order_detail(account, order_id)`

Returns detailed information for a specific order.

```python
detail = ppi.orders.get_order_detail(account_number, order_id, None)
print(detail)
```

| Parameter | Type | Description |
|---|---|---|
| `account` | string | Account number |
| `order_id` | number | Order ID |
| `external_id` | string or None | External reference ID (optional) |

**Response:**

Returns the full order detail object with the same shape as the order confirmation response.

---

### `cancel_order(Order)`

Cancels a single order by ID.

```python
cancel = ppi.orders.cancel_order(Order(order_id, account_number, None))
print(cancel)
```

**Constructor:** `Order(order_id, account, external_id)`

| Parameter | Type | Description |
|---|---|---|
| `order_id` | number | Order ID to cancel |
| `account` | string | Account number |
| `external_id` | string or None | External reference ID |

**Response:**

Returns the cancellation confirmation object.

---

### `mass_cancel_order(account)`

Cancels all active orders for the account.

```python
cancels = ppi.orders.mass_cancel_order(account_number)
print(cancels)
```

| Parameter | Type | Description |
|---|---|---|
| `account` | string | Account number |

**Response:**

Returns a list of cancellation results for each cancelled order.

---

## Real-time Service

All real-time methods are accessed via `ppi.realtime.*`. The library uses WebSocket connections for streaming market and account data.

### `connect_to_market_data(on_connect, on_disconnect, on_data)`

Opens a WebSocket connection to receive real-time market data. Requires three callback functions.

```python
def onconnect_marketdata():
    try:
        print("\nConnected to realtime market data")
        ppi.realtime.subscribe_to_element(Instrument("GGAL", "ACCIONES", "A-48HS"))
        ppi.realtime.subscribe_to_element(Instrument("AAPL", "CEDEARS", "A-48HS"))
        ppi.realtime.subscribe_to_element(Instrument("AL30", "BONOS", "INMEDIATA"))
        ppi.realtime.subscribe_to_element(Instrument("AL30D", "BONOS", "INMEDIATA"))
        ppi.realtime.subscribe_to_element(Instrument("DLR/MAR22", "FUTUROS", "INMEDIATA"))
    except Exception as error:
        traceback.print_exc()

def ondisconnect_marketdata():
    try:
        print("\nDisconnected from realtime market data")
    except Exception as error:
        traceback.print_exc()

def onmarketdata(data):
    try:
        msg = json.loads(data)
        if msg["Trade"]:
            print("%s [%s-%s] Price %.2f Volume %.2f" % (
                msg['Date'], msg['Ticker'], msg['Settlement'], msg['Price'], msg['VolumeAmount']))
        else:
            if len(msg['Bids']) > 0:
                bid = msg['Bids'][0]['Price']
            else:
                bid = 0
            if len(msg['Offers']) > 0:
                offer = msg['Offers'][0]['Price']
            else:
                offer = 0
            print(
                "%s [%s-%s] Offers: %.2f-%.2f Opening: %.2f MaxDay: %.2f MinDay: %.2f Accumulated Volume %.2f" %
                (msg['Date'], msg['Ticker'], msg['Settlement'], bid, offer,
                 msg['OpeningPrice'], msg['MaxDay'], msg['MinDay'], msg['VolumeTotalAmount']))
    except Exception as error:
        print(datetime.now())
        traceback.print_exc()

ppi.realtime.connect_to_market_data(onconnect_marketdata, ondisconnect_marketdata, onmarketdata)
```

**Market Data — Trade Message:**

```json
{
  "Ticker": "string",
  "Price": 0.0,
  "VolumeAmount": 0.0,
  "VolumeCurrency": 0.0,
  "Date": "2022-03-14T16:52:51.87-03:00",
  "Type": "string",
  "Settlement": "string",
  "VarDay": 0.0,
  "Offers": [],
  "Bids": [],
  "Trade": true,
  "OpeningPrice": 0.0,
  "MaxDay": 0.0,
  "MinDay": 0.0,
  "VolumeTotalAmount": 0
}
```

**Fields (Trade):**

| Field | Type | Description |
|---|---|---|
| `Ticker` | string | Instrument ticker |
| `Price` | number | Trade price |
| `VolumeAmount` | number | Volume in quantity |
| `VolumeCurrency` | number | Volume in currency |
| `Date` | string (ISO 8601 with offset) | Trade timestamp |
| `Type` | string | Instrument type |
| `Settlement` | string | Settlement term |
| `VarDay` | number | Daily variation percentage |
| `Offers` | array (empty) | No offers in trade messages |
| `Bids` | array (empty) | No bids in trade messages |
| `Trade` | boolean | Always `true` for trade messages |
| `OpeningPrice` | number | Session opening price |
| `MaxDay` | number | Session maximum price |
| `MinDay` | number | Session minimum price |
| `VolumeTotalAmount` | number | Accumulated volume for the session |

**Market Data — Book Message:**

```json
{
  "Ticker": "string",
  "Price": 0.0,
  "VolumeAmount": 0.0,
  "VolumeCurrency": 0.0,
  "Date": "2022-03-14T16:52:51.87-03:00",
  "Type": "string",
  "Settlement": "string",
  "VarDay": 0.0,
  "Offers": [{"Price": 0.0, "Quantity": 0.0, "Position": 0}],
  "Bids": [{"Price": 0.0, "Quantity": 0.0, "Position": 0}],
  "Trade": false,
  "OpeningPrice": 0.0,
  "MaxDay": 0.0,
  "MinDay": 0.0,
  "VolumeTotalAmount": 0
}
```

**Fields (Book):**

| Field | Type | Description |
|---|---|---|
| `Ticker` | string | Instrument ticker |
| `Price` | number | Last price |
| `VolumeAmount` | number | Volume in quantity |
| `VolumeCurrency` | number | Volume in currency |
| `Date` | string (ISO 8601 with offset) | Snapshot timestamp |
| `Type` | string | Instrument type |
| `Settlement` | string | Settlement term |
| `VarDay` | number | Daily variation percentage |
| `Offers[].Price` | number | Offer (ask) price |
| `Offers[].Quantity` | number | Quantity available |
| `Offers[].Position` | number | Position in book |
| `Bids[].Price` | number | Bid price |
| `Bids[].Quantity` | number | Quantity bid |
| `Bids[].Position` | number | Position in book |
| `Trade` | boolean | Always `false` for book messages |
| `OpeningPrice` | number | Session opening price |
| `MaxDay` | number | Session maximum price |
| `MinDay` | number | Session minimum price |
| `VolumeTotalAmount` | number | Accumulated volume for the session |

---

### `connect_to_account(on_connect, on_disconnect, on_data)`

Opens a WebSocket connection for real-time account notifications (push messages, account updates, and order status changes).

```python
def onconnect_accountdata():
    try:
        print("Connected to account data")
        ppi.realtime.subscribe_to_account_data(account_number)
    except Exception as error:
        traceback.print_exc()

def ondisconnect_accountdata():
    try:
        print("Disconnected from account data")
    except Exception as error:
        traceback.print_exc()

def onaccountdata(data):
    try:
        msg = json.loads(data)
        if msg["Type"] == ACCOUNTDATA_TYPE_PUSH_NOTIFICATION:
            print("%s - %s" % (msg['Title'], msg['Message']))
        if msg["Type"] == ACCOUNTDATA_TYPE_ACCOUNT_NOTIFICATION:
            print("%s - %s" % (msg['Date'], msg['Message']))
        if msg["Type"] == ACCOUNTDATA_TYPE_ORDER_NOTIFICATION:
            print("Ticker: %s OrderId: %s Quantity executed: %.2f Status: %s Last update: %s Operation: %s" % (
                msg['Ticker'], msg['OrderId'], msg['QuantityExecuted'], msg['Status'],
                msg['LastUpdateDate'], msg['Operation']))
    except Exception as error:
        traceback.print_exc()

ppi.realtime.connect_to_account(onconnect_accountdata, ondisconnect_accountdata, onaccountdata)
ppi.realtime.start_connections()
```

**Account Data — Push Notification (`ACCOUNTDATA_TYPE_PUSH_NOTIFICATION`):**

```json
{
  "Title": "string",
  "Message": "string"
}
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `Title` | string | Notification title |
| `Message` | string | Notification body |

**Account Data — Account Notification (`ACCOUNTDATA_TYPE_ACCOUNT_NOTIFICATION`):**

```json
{
  "Message": "string",
  "Date": "2022-03-14T16:52:51.87-03:00"
}
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `Message` | string | Notification message |
| `Date` | string (ISO 8601 with offset) | Notification timestamp |

**Account Data — Order Notification (`ACCOUNTDATA_TYPE_ORDER_NOTIFICATION`):**

```json
{
  "Ticker": "string",
  "OrderId": "string",
  "QuantityExecuted": 0,
  "Status": "string",
  "LastUpdateDate": "2022-03-14T16:52:51.87-03:00",
  "Operation": "string"
}
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `Ticker` | string | Instrument ticker |
| `OrderId` | string | Order ID |
| `QuantityExecuted` | number | Executed quantity |
| `Status` | string | Current order status |
| `LastUpdateDate` | string (ISO 8601 with offset) | Last status update timestamp |
| `Operation` | string | Operation side (`COMPRA` / `VENTA`) |

---

### `subscribe_to_element(Instrument)`

Subscribes to real-time market data for a specific instrument. Must be called from within the `on_connect` callback.

```python
ppi.realtime.subscribe_to_element(Instrument("GGAL", "ACCIONES", "A-48HS"))
```

**Constructor:** `Instrument(ticker, type, settlement)`

| Parameter | Type | Description |
|---|---|---|
| `ticker` | string | Instrument ticker |
| `type` | string | Instrument type |
| `settlement` | string | Settlement term |

---

### `subscribe_to_account_data(account)`

Subscribes to real-time account notifications for a specific account. Must be called from within the `on_connect` callback.

```python
ppi.realtime.subscribe_to_account_data(account_number)
```

| Parameter | Type | Description |
|---|---|---|
| `account` | string | Account number |

---

### `start_connections()`

Starts all configured real-time WebSocket connections. Must be called after `connect_to_market_data` and/or `connect_to_account` to begin streaming data.

```python
ppi.realtime.start_connections()
```

---

## Complete Example

Below is a full reference implementation (`ejemploRunner.py`) demonstrating the entire lifecycle: initialization, login, account data, market data, orders, and real-time streaming.

```python
from ppi_client.api.constants import ACCOUNTDATA_TYPE_ACCOUNT_NOTIFICATION, ACCOUNTDATA_TYPE_PUSH_NOTIFICATION, \
    ACCOUNTDATA_TYPE_ORDER_NOTIFICATION
from ppi_client.models.account_movements import AccountMovements
from ppi_client.models.bank_account_request import BankAccountRequest
from ppi_client.models.foreign_bank_account_request import ForeignBankAccountRequest, ForeignBankAccountRequestDTO
from ppi_client.models.cancel_bank_account_request import CancelBankAccountRequest
from ppi_client.models.order import Order
from ppi_client.ppi import PPI
from ppi_client.models.order_budget import OrderBudget
from ppi_client.models.order_confirm import OrderConfirm
from ppi_client.models.disclaimer import Disclaimer
from ppi_client.models.investing_profile import InvestingProfile
from ppi_client.models.investing_profile_answer import InvestingProfileAnswer
from ppi_client.models.instrument import Instrument
from datetime import datetime, timedelta
from ppi_client.models.estimate_bonds import EstimateBonds
import asyncio
import json
import traceback
import os

# Change sandbox variable to False to connect to production environment
ppi = PPI(sandbox=False)

# Change login credential to connect to the API
ppi.account.login_api('<public key>', '<private key>')

# Getting accounts information
accounts = ppi.account.get_accounts()
account_number = accounts[0]['accountNumber']

# Getting bank account information
print("\nGetting bank account information of %s" % account_number)
bank_accounts = ppi.account.get_bank_accounts(account_number)
for bank_account in bank_accounts:
    print(bank_account)

# Getting available balance
print("\nGetting available balance of %s" % account_number)
balances = ppi.account.get_available_balance(account_number)
for balance in balances:
    print("Currency %s - Settlement %s - Amount %s %s" % (
        balance['name'], balance['settlement'], balance['symbol'], balance['amount']))

# Getting balance and positions
print("\nGetting balance and positions of %s" % account_number)
balances_positions = ppi.account.get_balance_and_positions(account_number)
for balance in balances_positions["groupedAvailability"]:
    for currency in balance['availability']:
        print("Currency %s Settlement %s Amount %s %s" % (
            currency['name'], currency['settlement'], currency['symbol'], currency['amount']))
for instruments in balances_positions["groupedInstruments"]:
    print("Instrument %s " % instruments['name'])
    for instrument in instruments['instruments']:
        print("Ticker %s Price %s Amount %s" % (
            instrument['ticker'], instrument['price'], instrument['amount']))

# Getting movements
print("\nGetting movements of %s" % account_number)
movements = ppi.account.get_movements(AccountMovements(account_number, datetime(2021, 12, 1),
                                                       datetime(2021, 12, 31), None))
for mov in movements:
    print("%s %s - Currency %s Amount %s " % (
        mov['settlementDate'], mov['description'], mov['currency'], mov['amount']))

# Getting instrument types
print("\nGetting instrument types")
instruments = ppi.configuration.get_instrument_types()
for item in instruments:
    print(item)

# Getting markets
print("\nGetting markets")
markets = ppi.configuration.get_markets()
for item in markets:
    print(item)

# Getting settlements
print("\nGetting settlements")
settlements = ppi.configuration.get_settlements()
for item in settlements:
    print(item)

# Getting holidays
print("\nGet local holidays for the current year")
holidays = ppi.configuration.get_holidays(start_date=datetime(2022, 1, 1), end_date=datetime(2022, 12, 31))
for holiday in holidays:
    print("%s - %s " % (holiday["date"][0:10], holiday["description"]))

print("\nGet USA holidays for the current year")
holidays = ppi.configuration.get_holidays(start_date=datetime(2022, 1, 1), end_date=datetime(2022, 12, 31),
                                          is_usa=True)
for holiday in holidays:
    print("%s - %s " % (holiday["date"][0:10], holiday["description"]))

# Checking holidays
print("\nIs today a local holiday?")
print(ppi.configuration.is_local_holiday())
print("\nIs today a holiday in the USA?")
print(ppi.configuration.is_usa_holiday())

# Searching instruments
print("\nSearching instruments")
instruments = ppi.marketdata.search_instrument("GGAL", "", "Byma", "Acciones")
for ins in instruments:
    print(ins)

# Historical market data
print("\nSearching MarketData")
market_data = ppi.marketdata.search("GGAL", "Acciones", "A-48HS", datetime(2021, 1, 1), datetime(2021, 12, 31))
for ins in market_data:
    print("%s - %s - Volume %s - Opening %s - Min %s - Max %s" % (
        ins['date'], ins['price'], ins['volume'], ins['openingPrice'], ins['min'], ins['max']))

# Current market data
print("\nSearching Current MarketData")
current_market_data = ppi.marketdata.current("GGAL", "Acciones", "A-48HS")
print(current_market_data)

# Current book
print("\nSearching Current Book")
current_book = ppi.marketdata.book("GGAL", "Acciones", "A-48HS")
print(current_book)

# Intraday market data
print("\nSearching Intraday MarketData")
intraday_market_data = ppi.marketdata.intraday("GGAL", "Acciones", "A-48HS")
for intra in intraday_market_data:
    print(intra)

# Getting orders
print("\nGet orders")
orders = ppi.orders.get_orders(account_number, date_from=datetime.today() + timedelta(days=-100),
                               date_to=datetime.today())
for order in orders:
    print(order)

# Getting active orders
print("\nGet active orders")
active_orders = ppi.orders.get_active_orders(account_number)
for order in active_orders:
    print(order)

# Budget of an order
budget_order = ppi.orders.budget(OrderBudget(account_number, 10000, 150, "GGAL", "ACCIONES", "Dinero",
                                             "PRECIO-LIMITE", "HASTA-SU-EJECUCIÓN", None, "Compra",
                                             "INMEDIATA"))
print(budget_order)
disclaimers_order = budget_order['disclaimers']

# Create an order
accepted_disclaimers = []
for disclaimer in disclaimers_order:
    accepted_disclaimers.append(Disclaimer(disclaimer['code'], True))
confirmation = ppi.orders.confirm(OrderConfirm(account_number, 10000, 150, "GGAL", "ACCIONES", "Dinero",
                                               "PRECIO-LIMITE", "HASTA-SU-EJECUCIÓN", None, "Compra",
                                               "INMEDIATA", accepted_disclaimers, None))
print(confirmation)
order_id = confirmation["id"]

# Order detail
detail = ppi.orders.get_order_detail(account_number, order_id, None)
print(detail)

# Cancel order
cancel = ppi.orders.cancel_order(Order(order_id, account_number, None))
print(cancel)

# Mass cancel
cancels = ppi.orders.mass_cancel_order(account_number)
print(cancels)

# Investing profile questions
investing_profile_questions = ppi.account.get_investing_profile_questions()
for question in investing_profile_questions:
    print("%s - %s " % (question["code"], question["description"]))
    for answer in question["answers"]:
        print("%s - %s " % (answer["code"], answer["description"]))

# Investing profile instrument types
investing_profile_instrument_types = ppi.account.get_investing_profile_instrument_types()
for instrument in investing_profile_instrument_types:
    print(instrument)

# Get investing profile
profile = ppi.account.get_investing_profile(account_number)
print("Date: %s - Type: %s - %s" % (profile["date"], profile["type"], profile["description"]))

# Set investing profile
answers = [InvestingProfileAnswer("GRADO_CONOCIMIENTO", "A"), InvestingProfileAnswer("INVERSION_ANTERIOR", "C"),
           InvestingProfileAnswer("PORCENTAJE_AHORRO", "A"), InvestingProfileAnswer("PLAZO_MAXIMO", "C"),
           InvestingProfileAnswer("INVERSION_PREOCUPACION", "A"),
           InvestingProfileAnswer("PORCENTAJE_DISMINUCION", "B"),
           InvestingProfileAnswer("MONTO_INVERSION", "A")]
instrument_types = ["BONOS-(RENTA-FIJA)", "ACCIONES-ARGENTINAS-(RENTA-VARIABLE-LOCAL)",
                    "FIDEICOMISOS-FINANCIEROS"]
new_profile = ppi.account.set_investing_profile(InvestingProfile(account_number, answers, instrument_types))
print("New investing profile - Date: %s - Type: %s - %s" % (new_profile["date"], new_profile["type"],
                                                            new_profile["description"]))

# Register bank account
bank_account_request = ppi.account.register_bank_account(
    BankAccountRequest(account_number, currency="ARS", cbu="", cuit="00000000000",
                       alias="ALIASCBU", bank_account_number=""))
print(bank_account_request)

# Register foreign bank account
data = ForeignBankAccountRequestDTO(account_number=account_number, cuit="00000000000", intermediary_bank="",
                                    intermediary_bank_account_number="", intermediary_bank_swift="",
                                    bank="The Bank of Tokyo-Mitsubishi, Ltd.", bank_account_number="12345678",
                                    swift="ABC", ffc="Juan Perez")
extract_file_route = "C:\\Documents\\example.pdf"
extract_file = (os.path.basename(extract_file_route), open(extract_file_route, 'rb'))
foreign_bank_account_request = ppi.account.register_foreign_bank_account(
    ForeignBankAccountRequest(data, extract_file))
print(foreign_bank_account_request)

# Cancel bank account
cancel_bank_account_request = ppi.account.cancel_bank_account(
    CancelBankAccountRequest(account_number, cbu="0000000000000000000000", bank_account_number=""))
print(cancel_bank_account_request)

# Bonds calculator
estimate = ppi.marketdata.estimate_bonds(EstimateBonds(ticker="CUAP", date=datetime.today(),
                                                       quantityType="PAPELES", quantity=100, price=4555))
print(estimate)

# Real-time market data
def onconnect_marketdata():
    try:
        print("\nConnected to realtime market data")
        ppi.realtime.subscribe_to_element(Instrument("GGAL", "ACCIONES", "A-48HS"))
        ppi.realtime.subscribe_to_element(Instrument("AAPL", "CEDEARS", "A-48HS"))
        ppi.realtime.subscribe_to_element(Instrument("AL30", "BONOS", "INMEDIATA"))
        ppi.realtime.subscribe_to_element(Instrument("AL30D", "BONOS", "INMEDIATA"))
        ppi.realtime.subscribe_to_element(Instrument("DLR/MAR22", "FUTUROS", "INMEDIATA"))
    except Exception as error:
        traceback.print_exc()

def ondisconnect_marketdata():
    try:
        print("\nDisconnected from realtime market data")
    except Exception as error:
        traceback.print_exc()

def onmarketdata(data):
    try:
        msg = json.loads(data)
        if msg["Trade"]:
            print("%s [%s-%s] Price %.2f Volume %.2f" % (
                msg['Date'], msg['Ticker'], msg['Settlement'], msg['Price'], msg['VolumeAmount']))
        else:
            if len(msg['Bids']) > 0:
                bid = msg['Bids'][0]['Price']
            else:
                bid = 0
            if len(msg['Offers']) > 0:
                offer = msg['Offers'][0]['Price']
            else:
                offer = 0
            print(
                "%s [%s-%s] Offers: %.2f-%.2f Opening: %.2f MaxDay: %.2f MinDay: %.2f Accumulated Volume %.2f" %
                (msg['Date'], msg['Ticker'], msg['Settlement'], bid, offer,
                 msg['OpeningPrice'], msg['MaxDay'], msg['MinDay'], msg['VolumeTotalAmount']))
    except Exception as error:
        print(datetime.now())
        traceback.print_exc()

ppi.realtime.connect_to_market_data(onconnect_marketdata, ondisconnect_marketdata, onmarketdata)

# Real-time account data
def onconnect_accountdata():
    try:
        print("Connected to account data")
        ppi.realtime.subscribe_to_account_data(account_number)
    except Exception as error:
        traceback.print_exc()

def ondisconnect_accountdata():
    try:
        print("Disconnected from account data")
    except Exception as error:
        traceback.print_exc()

def onaccountdata(data):
    try:
        msg = json.loads(data)
        if msg["Type"] == ACCOUNTDATA_TYPE_PUSH_NOTIFICATION:
            print("%s - %s" % (msg['Title'], msg['Message']))
        if msg["Type"] == ACCOUNTDATA_TYPE_ACCOUNT_NOTIFICATION:
            print("%s - %s" % (msg['Date'], msg['Message']))
        if msg["Type"] == ACCOUNTDATA_TYPE_ORDER_NOTIFICATION:
            print("Ticker: %s OrderId: %s Quantity executed: %.2f Status: %s Last update: %s Operation: %s" % (
                msg['Ticker'], msg['OrderId'], msg['QuantityExecuted'], msg['Status'],
                msg['LastUpdateDate'], msg['Operation']))
    except Exception as error:
        traceback.print_exc()

ppi.realtime.connect_to_account(onconnect_accountdata, ondisconnect_accountdata, onaccountdata)
ppi.realtime.start_connections()
```
