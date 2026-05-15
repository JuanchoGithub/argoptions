# argoptions — agent guide

## Entrypoints

- CLI app: `arg_options/cli.py` → Typer `app`. Registered as `arg-options` console script in `pyproject.toml`.
- Also runnable: `python -m arg_options`
- TUI: `arg-options interactive` (Textual, blocks terminal)

## Config

Two-layer config (check `settings.py`):

1. **`.env`** — loaded via python-dotenv. Path via `ARG_OPTIONS_ENV` (default `.env` in package dir). Contains `PPI_API_KEY`, `PPI_API_SECRET`, `PPI_ACCOUNT_NUMBER`, `ALLOW_LIVE_ORDERS`, etc.
2. **YAML** — `ARG_OPTIONS_CONFIG` env var (default `config/settings.yaml`). Maps option roots → spot tickers, chain config, paths.
3. **Screening YAML** — `ARG_OPTIONS_SCREENING` env var (default from `paths.screening` in settings, or `config/screening.yaml`).

## Safety

- **Orders are dry-run by default.** Two independent guards for live orders: `ALLOW_LIVE_ORDERS=true` in `.env` **AND** `--send-live` flag on `place-order`.
- Daily notional cap and max contracts per order enforced via env vars.
- DB tracks `daily_order_usage` table to enforce caps across sessions.

## Commands

| Command | What |
|---|---|
| `arg-options login-test` | Verify PPI credentials |
| `arg-options chain` | Download option chain → SQLite snapshot |
| `arg-options screen` | Apply screening YAML to latest snapshot |
| `arg-options journal-sync` | Sync positions/orders from PPI → local SQLite |
| `arg-options alerts-once` | Evaluate alerts (expiry, etc.) once |
| `arg-options place-order TICKER COMPRA/VENTA QTY PRICE` | Place limit order (dry-run unless `--send-live`) |
| `arg-options interactive` | TUI: `c` chain · `s` screen · `f` screen form · `j` journal · `a` alerts · `w` auto · `q` quit |

## Tests

```bash
pytest
```

Tests use fakes (no real PPI credentials needed in most cases). See `test_orders.py` for `_FakePPI` pattern. No other test runner or config needed.

## Build & dev

```bash
pip install -e ".[dev]"   # editable install with dev deps
```

No formatter, linter, or typechecker configured. No pre-commit hook. No CI workflow.

## Notable quirks

- **BYMA option ticker format**: e.g. `GFGC2800MY` → root `GFG`, right `C`/`V` (compra/venta), strike, month suffix `MY` (May), optional 2-digit year suffix.
- **Expiry heuristic**: `third_thursday()` of the month (BYMA convention).
- **Greeks**: European Black-Scholes via scipy; IV via `brentq`.
- **SQLite DB** auto-created at `paths.database` (default `data/arg_options.db`). Schema auto-initialized on connect.
- **Throttle**: 150ms sleep between option quote fetches (configurable in `build_chain_for_root`).
- `chain` must run before `screen` — screening reads the latest snapshot from SQLite.
- **`.env` lives inside `arg_options/`**, not at repo root.
