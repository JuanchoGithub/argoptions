# PPI API Configuration Reference

Fetched from PPI sandbox API on 2026-05-18.

These are the exact `code` values the PPI API expects in order requests.
All codes are **UPPERCASE**. The API rejects mixed-case or lowercase variants.

## Instrument Types

| Code |
|------|
| BONOS |
| LETRAS |
| NOBAC |
| LEBAC |
| ON |
| FCI |
| CAUCIONES |
| ACCIONES |
| ETF |
| CEDEARS |
| OPCIONES |
| FUTUROS |
| LICITACIONES |
| ACCIONES-USA |
| FCI-EXTERIOR |

## Markets

| Code |
|------|
| ROFEX |
| OTC |
| NYSE |
| NASDAQ |
| BYMA |

## Settlements

| Code |
|------|
| INMEDIATA |
| A-24HS |
| A-48HS |
| A-72HS |

## Quantity Types

| Code |
|------|
| DINERO |
| PAPELES |
| CANTIDAD-TOTAL |

## Operation Types (order types)

| Code | Meaning |
|------|---------|
| PRECIO-DE-MERCADO | Market order — price ignored, executes at market |
| PRECIO-LIMITE | Limit order — requires price |

## Operation Terms (order validity)

| Code | Meaning |
|------|---------|
| POR-EL-DIA | Day order — expires at end of trading day |
| HASTA-SU-EJECUCION | GTC — good till cancelled/executed |
| VALIDA-HASTA-EL | Valid until a specific date |
| 72-HS | Valid for 72 hours |

## Operations (sides/actions)

| Code | Meaning |
|------|---------|
| COMPRA | Buy |
| VENTA | Sell |
| SUSCRIPCION-FCI | FCI subscription (mutual fund buy) |
| RESCATE-FCI | FCI redemption (mutual fund sell) |
| EJERCER-CALL | Exercise call option |
| EJERCER-PUT | Exercise put option |
| LANZAMIENTO | Writing/launching options |
| COLOCAR-CAUCION | Place caucion (repo) |
| STOP-ORDER | Stop order — requires activationPrice |
| LICITAR | Bid in auction |

## Key rules

- **Market orders** (`PRECIO-DE-MERCADO`): price must be 0 or omitted. PPI rejects if price > 0.
- **Limit orders** (`PRECIO-LIMITE`): price is required. PPI rejects if price = 0.
- **Stop orders** (`STOP-ORDER`): requires `activationPrice`.
- **FCI operations** (`SUSCRIPCION-FCI` / `RESCATE-FCI`): only valid when `instrumentType` = `FCI` or `FCI-EXTERIOR`.
- **Exercise operations** (`EJERCER-CALL` / `EJERCER-PUT`): only valid for options.
- **Settlement `INMEDIATA`** is a real settlement type (cash/immediate), NOT an operation type.
- The PPI API config endpoint returns flat string lists (not `{code, description}` dicts) for these endpoints.

## PPI SDK model field mapping

OrderBudget / OrderConfirm fields → what to pass:

| SDK field | Source |
|-----------|--------|
| operationType | from `operation_types` list (e.g. `PRECIO-LIMITE`) |
| operationTerm | from `operation_terms` list (e.g. `HASTA-SU-EJECUCION`) |
| operation | from `operations` list (e.g. `COMPRA`, `VENTA`) |
| settlement | from `settlements` list (e.g. `A-48HS`) |
| instrumentType | from `instrument_types` list (e.g. `OPCIONES`) |
| quantityType | from `quantity_types` list (e.g. `PAPELES`) |
| activationPrice | only for `STOP-ORDER` operation |
