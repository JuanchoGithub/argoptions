# Market Orders Research — PPI API vs IOL Legacy API

## 1. IOL v2 API — Full ComprarBindingModel (from Swagger spec)

**Endpoint**: `POST /api/v2/operar/Comprar`
**Base URL**: `https://api.invertironline.com`

```json
{
  "required": ["mercado", "simbolo", "precio", "plazo", "validez"],
  "properties": {
    "mercado":       { "enum": ["bCBA", "nYSE", "nASDAQ", "aMEX", "bCS", "rOFX"], "type": "string" },
    "simbolo":       { "type": "string" },
    "cantidad":      { "format": "double", "type": "number" },
    "precio":        { "format": "double", "type": "number" },
    "plazo":         { "enum": ["t0", "t1", "t2", "t3"], "type": "string" },
    "validez":       { "format": "date-time", "type": "string" },
    "tipoOrden":     { "enum": ["precioLimite", "precioMercado"], "type": "string" },
    "monto":         { "format": "double", "type": "number" },
    "idFuente":      { "format": "int32", "type": "integer" }
  }
}
```

## 2. IOL v2 API — Full VenderBindingModel (from Swagger spec)

**Endpoint**: `POST /api/v2/operar/Vender`

```json
{
  "required": ["mercado", "simbolo", "cantidad", "precio", "validez"],
  "properties": {
    "mercado":       { "enum": ["bCBA", "nYSE", "nASDAQ", "aMEX", "bCS", "rOFX"], "type": "string" },
    "simbolo":       { "type": "string" },
    "cantidad":      { "format": "double", "type": "number" },
    "precio":        { "format": "double", "type": "number" },
    "validez":       { "format": "date-time", "type": "string" },
    "tipoOrden":     { "enum": ["precioLimite", "precioMercado"], "type": "string" },
    "plazo":         { "enum": ["t0", "t1", "t2", "t3"], "type": "string" },
    "idFuente":      { "format": "int32", "type": "integer" }
  }
}
```

## 3. IOL v2 Response Models — OperacionModel & OperacionDetalleModel

These show how the IOL API represents orders after creation:

**OperacionModel** (list view):
```json
{
  "numero":          { "format": "int32", "type": "integer" },
  "fechaOrden":      { "format": "date-time", "type": "string" },
  "tipo":            { "type": "string" },
  "estado":          { "enum": ["iniciada", "en_Proceso", "parcialmente_Terminada", "terminada", "cancelada", ...] },
  "mercado":         { "type": "string" },
  "simbolo":         { "type": "string" },
  "cantidad":        { "format": "double", "type": "number" },
  "monto":           { "format": "double", "type": "number" },
  "modalidad":       { "enum": ["precio_Limite", "precio_Mercado"], "type": "string" },
  "precio":          { "format": "double", "type": "number" },
  "fechaOperada":    { "format": "date-time", "type": "string" },
  "cantidadOperada": { "format": "double", "type": "number" },
  "precioOperado":   { "format": "double", "type": "number" },
  "montoOperado":    { "format": "double", "type": "number" },
  "plazo":           { "enum": ["sinValor", "a72horas", "a24horas", "inmediata", "a48horas"] }
}
```

**OperacionDetalleModel** (detail view) — same `modalidad` enum:
```json
{
  "modalidad": { "enum": ["precio_Limite", "precio_Mercado"] },
  ...plus: "numero", "aranceles", "operaciones", "fondosParaOperacion", etc.
}
```

## 4. Complete Field Mapping: IOL Input → IOL Response → PPI

| Concept | IOL Input Field | IOL Input Value | IOL Response (`modalidad`) | PPI Request (`operationType`) | PPI Response (`orderType`) |
|---------|----------------|-----------------|---------------------------|------------------------------|---------------------------|
| Limit order | `tipoOrden` | `"precioLimite"` | `"precio_Limite"` | `"PRECIO-LIMITE"` | `"PRECIO-LIMITE"` |
| Market order | `tipoOrden` | `"precioMercado"` | `"precio_Mercado"` | `"PRECIO-DE-MERCADO"` | N/A (rejected) |
| Settlement | `plazo` | `"t0"`, `"t1"`, `"t2"`, `"t3"` | `"inmediata"`, `"a24horas"`, `"a48horas"`, `"a72horas"` | `"INMEDIATA"`, `"A-24HS"`, `"A-48HS"`, `"A-72HS"` | same as request |
| Validity | `validez` | ISO datetime | ISO datetime | `operationTerm`: `"POR-EL-DIA"`, etc. | `operationType` (response!) = term |
| Side | N/A (endpoint path) | `/Comprar` or `/Vender` | `"compra"` / `"venta"` | `"COMPRA"` / `"VENTA"` | `"COMPRA"` / `"VENTA"` |
| Market | `mercado` | `"bCBA"` | `"bCBA"` | implicit from instrument | N/A |
| Instrument type | N/A | N/A | N/A | `"ACCIONES"`, `"OPCIONES"` | `"ACCIONES"`, `"OPCIONES"` |
| Quantity | `cantidad` | float | float | `quantity` (int) | int |

**CRITICAL OBSERVATION**: The PPI response uses `orderType` for what we call `operationType` (limit/market), and `operationType` for what we call `operationTerm` (day/GTC). This naming collision in the PPI API is confusing but confirmed by the successful limit order response:

```json
{
  "orderType": "PRECIO-LIMITE",        // ← the order type (limit/market)
  "operationType": "HASTA-SU-EJECUCION" // ← the validity term (day/GTC)
}
```

## 5. IOL `validez` Field — Does NOT Have Market-Order-Specific Values

The `validez` field is a **datetime** (e.g. `"2026-05-20T17:00:00"`), NOT an enum.
There are no special values like `"alInicioDelDia"` or `"alCierreDelDia"`.
Market orders in IOL are specified **solely** through `tipoOrden: "precioMercado"`.

The IOL API has **no concept of `POR-EL-DIA` or `HASTA-SU-EJECUCION`** — those are PPI-specific.
IOL uses a concrete expiry datetime instead.

## 6. IOL API Endpoint URLs for Orders

| Action | v1 Endpoint | v2 Endpoint |
|--------|------------|------------|
| Buy | `POST /api/operar/Comprar` | `POST /api/v2/operar/Comprar` |
| Sell | `POST /api/operar/Vender` | `POST /api/v2/operar/Vender` |
| Buy D-specie | N/A | `POST /api/v2/operar/ComprarEspecieD` |
| Sell D-specie | N/A | `POST /api/v2/operar/VenderEspecieD` |
| Cancel | N/A | `DELETE /api/v2/operaciones/{numero}` |
| List orders | N/A | `GET /api/v2/operaciones` |
| Order detail | N/A | `GET /api/v2/operaciones/{numero}` |
| FCI Subscribe | N/A | `POST /api/v2/operar/suscripcion/fci` |
| FCI Redeem | N/A | `POST /api/v2/operar/rescate/fci` |

**Auth**: Bearer token from `POST /token` (OAuth2 password grant)

## 7. Can You Place Market Orders via the PPI API?

### Evidence from logs — ALL attempts fail

Every combination of `PRECIO-DE-MERCADO` has been tried and ALL return `"Modalidad inválida"`:

| # | instrumentType | settlement | operationTerm | price | Error |
|---|---------------|------------|--------------|-------|-------|
| 1 | ACCIONES | INMEDIATA | POR-EL-DIA | 0 | Modalidad inválida |
| 2 | ACCIONES | INMEDIATA | HASTA-SU-EJECUCION | 0 | Modalidad inválida |
| 3 | ACCIONES | A-48HS | HASTA-SU-EJECUCION | 0 | Modalidad inválida |
| 4 | ACCIONES | A-48HS | POR-EL-DIA | 0 | Modalidad inválida |
| 5 | ACCIONES | A-24HS | HASTA-SU-EJECUCION | 0 | Modalidad inválida |
| 6 | ACCIONES | A-24HS | POR-EL-DIA | 0 | Modalidad inválida |
| 7 | ACCIONES | A-72HS | POR-EL-DIA | 0 | Modalidad inválida |
| 8 | ACCIONES | A-72HS | 72-HS | 0 | Modalidad inválida |
| 9 | ACCIONES | A-48HS | VALIDA-HASTA-EL | 0 | Modalidad inválida |
| 10 | ACCIONES | A-24HS | 72-HS | 0 | Modalidad inválida |
| 11 | ACCIONES | A-24HS | VALIDA-HASTA-EL | 0 | Modalidad inválida |
| 12 | OPCIONES | A-48HS | POR-EL-DIA | 0 | Instrument not found |
| 13 | CEDEARS | A-48HS | POR-EL-DIA | 0 | Instrument not found |
| 14 | BONOS | A-48HS | POR-EL-DIA | 0 | Instrument not found |
| 15 | ETF | A-48HS | POR-EL-DIA | 0 | Instrument not found |
| 16 | ACCIONES | A-48HS | HASTA-SU-EJECUCION | 0 | Modalidad inválida |

Earlier attempt with `operation_type: "Mercado"` returned `"Operation Type not found"` — proving PPI requires UPPERCASE-HYPHEN format.

### Earlier attempt with mixed-case also failed

```
operation_type: "Precio-Limite" → "Se debe informar el precio para una orden a precio limite"
```
This means PPI accepts mixed-case for PRECIO-LIMITE (or at least doesn't reject the format),
but when price=0 it correctly says "price required for limit order".

Then with correct UPPERCASE PRECIO-LIMITE + price=1 → SUCCESS.

### Successful limit order response (reference)

```json
{
  "disclaimers": [],
  "id": 0,
  "instrumentType": "ACCIONES",
  "operation": "COMPRA",
  "ticker": "GGAL",
  "status": "PENDIENTE-DE-EJECUCION",
  "date": "2026-05-18T16:21:23.4819107-03:00",
  "settlement": "A-48HS",
  "quantity": 1,
  "orderType": "PRECIO-LIMITE",
  "operationType": "HASTA-SU-EJECUCION",
  "operationMaxDate": "2026-05-19T16:21:22.99116-03:00",
  "price": 1,
  "currency": "Pesos",
  "amount": 0
}
```

## 8. Python Code Examples

### IOL Legacy API — Market Order (theoretical, based on Swagger spec)

```python
import requests

# Step 1: Get auth token
token_response = requests.post(
    "https://api.invertironline.com/token",
    data={
        "grant_type": "password",
        "username": "YOUR_USERNAME",
        "password": "YOUR_PASSWORD",
    }
)
token = token_response.json()["access_token"]

# Step 2: Place market order
order_response = requests.post(
    "https://api.invertironline.com/api/v2/operar/Comprar",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "mercado": "bCBA",
        "simbolo": "GGAL",
        "cantidad": 1.0,          # float, NOT int
        "precio": 0.0,            # still sent, but ignored for market orders
        "plazo": "t2",            # t0=inmediata, t1=24hs, t2=48hs, t3=72hs
        "validez": "2026-05-20T17:00:00",  # ISO datetime expiry
        "tipoOrden": "precioMercado"  # THIS IS THE KEY FIELD
    }
)
```

**NOTE**: No existing Python IOL client library implements `tipoOrden`. The `asperduti/iol-rest-client`,
`aairabella/iol-python-api`, `afreisinger/iol-client`, and `matuu/python-invertironline` clients
all omit this field, meaning they can only place limit orders.

### PPI API — Market Order (current code — FAILS)

```python
from ppi_client.models.order_budget import OrderBudget

# This is what our code does — and it ALWAYS returns "Modalidad inválida"
params = OrderBudget(
    accountNumber="12345",
    quantity=1,
    price=0,                           # Required by dataclass, sent as 0
    ticker="GGAL",
    instrumentType="ACCIONES",
    quantityType="PAPELES",
    operationType="PRECIO-DE-MERCADO",  # Rejected by PPI
    operationTerm="POR-EL-DIA",
    operationMaxDate=datetime.now(),
    operation="COMPRA",
    settlement="A-48HS",
)
ppi.orders.budget(params)  # → Exception: Modalidad inválida
```

### PPI API — Bypass SDK to send price=null (UNTESTED)

```python
import json
import requests

# Bypass the ppi_client SDK to send price as null instead of 0
body = {
    "accountNumber": "12345",
    "quantity": 1,
    "price": None,                      # or omit the key entirely
    "ticker": "GGAL",
    "instrumentType": "ACCIONES",
    "quantityType": "PAPELES",
    "operationType": "PRECIO-DE-MERCADO",
    "operationTerm": "POR-EL-DIA",
    "operationMaxDate": datetime.now().isoformat(),
    "operation": "COMPRA",
    "settlement": "A-48HS",
    "activationPrice": None
}
# Remove None values
body = {k: v for k, v in body.items() if v is not None}

headers = {
    "Authorization": f"Bearer {ppi_token}",
    "AuthorizedClient": "API_CLI_PYTHON",
    "ClientKey": "pp19PythonApp12",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

response = requests.post(
    "https://clientapisandbox.portfoliopersonal.com/api/1.0/Order/Budget",
    data=json.dumps(body),
    headers=headers,
    verify=False  # sandbox
)
```

## 9. Key Insights

### 9a. The IOL API uses an explicit `tipoOrden` field for market orders

The IOL API does NOT use price=0 as an implicit market order signal. It has an explicit
`tipoOrden` field with values `"precioLimite"` / `"precioMercado"`. Setting `precio=0`
without `tipoOrden: "precioMercado"` would just be a limit order at price 0.

### 9b. The PPI API and IOL API are fundamentally different APIs

They are NOT just different versions of the same API. They have:
- Different field names (`operationType` vs `tipoOrden`)
- Different value casing (`PRECIO-DE-MERCADO` vs `precioMercado`)
- Different request structures (PPI has Budget→Confirm two-phase, IOL has single POST)
- Different settlement naming (`A-48HS` vs `t2`)
- Different validity model (enum terms vs datetime)
- Different auth (API key+secret vs password grant)

### 9c. The PPI SDK always sends `price` — even for market orders

The `OrderBudget` dataclass has `price: decimal` as a required field with no default.
The SDK's `OrdersApi.budget()` method always includes `"price": parameters.price` in
the JSON body, even when it's 0. This means:
- `price=0` is always sent in the JSON body
- There's no way to omit the `price` field using the SDK
- The PPI API might reject market orders BECAUSE price=0 is present

### 9d. "Modalidad inválida" — what it means

"Modalidad" is Spanish for "modality/mode". The IOL API response model uses
`modalidad` as the field name for the order type (limit/market). The PPI error
`"Modalidad inválida"` is saying the order type value is invalid — it's the PPI
backend rejecting `PRECIO-DE-MERCADO` as an `operationType`.

The fact that PPI's OWN `1.0/Configuration/OperationTypes` endpoint lists
`PRECIO-DE-MERCADO` as valid but the order endpoint rejects it suggests:
1. It may be a sandbox-only restriction (not available in test env)
2. It may require specific account permissions
3. The `price` field being 0 may cause the validation to fail before the
   `operationType` is even checked (but the error says "Modalidad" not "Precio")
4. PPI may not actually support market orders via API despite listing the value

## 10. Recommended Next Steps

### Immediate (can do now):
1. **Try `price: null` / omit `price`** — bypass the SDK and POST directly to
   `1.0/Order/Budget` with `price` set to `null` or omitted entirely
2. **Try on PRODUCTION** (not sandbox) — sandbox may have market orders disabled
3. **Try `precioMercado` (camelCase)** — on the off chance PPI accepts IOL-style values
4. **Try `MERCADO`** — maybe a simpler value exists

### Medium-term (requires IOL credentials):
5. **Implement IOL API fallback** — authenticate via `POST /token` with
   username/password, then `POST /api/v2/operar/Comprar` with
   `tipoOrden: "precioMercado"` for market orders, while continuing to use
   the PPI API for limit orders

### Long-term:
6. **Contact PPI API support** — report that `Configuration/OperationTypes`
   lists `PRECIO-DE-MERCADO` but `Order/Budget` returns `"Modalidad inválida"`
7. **Try with real PPI account permissions** — may need specific trading
   permissions enabled on the account
8. **Check PPI web app network traffic** — when placing a market order via the
   PPI web interface, intercept the actual API call to see what fields/values
   the frontend sends

## 11. Settlement Mapping: IOL ↔ PPI

| Settlement | IOL (`plazo`) | IOL Response (`plazo`) | PPI (`settlement`) |
|-----------|-------------|---------------------|-------------------|
| Immediate | `t0` | `inmediata` | `INMEDIATA` |
| T+1 (24hs) | `t1` | `a24horas` | `A-24HS` |
| T+2 (48hs) | `t2` | `a48horas` | `A-48HS` |
| T+3 (72hs) | `t3` | `a72horas` | `A-72HS` |
