# argoptions — Opciones BYMA via PPI

## Entrypoints

- **CLI command**: `arg-options` (Typer). Subcommands: `chain`, `screen`, `status`, `orders`, `journal`, `cancel`, `run`.
- **`python -m arg_options`** — same as `arg-options`.
- **TUI**: `./run.sh` (test/sandbox) or `./run_prod.sh` (production — real trades possible).
- **Every `run_*.sh` script is self-bootstrapping**: auto-creates `.venv` with `uv`, installs `-e ".[dev]"`, copies example configs. No manual setup.

## Modes

- Two modes: `test` (sandbox, default) and `production`.
- Mode controlled by `--prod` flag or `ARGOPTIONS_MODE=production` env var.
- Credentials in `.env_test` (sandbox) or `.env_prod` (live).
- `ALLOW_LIVE_ORDERS=true` must be explicitly set in `.env_prod` for production trades (safety gate).
- TUI key `t` toggles mode with confirmation dialog.

## Config files (YAML, under `config/`)

| File | Purpose |
|---|---|
| `settings.yaml` | Broker config, option roots, risk params, file paths |
| `screening.yaml` | Screening filter rules (DTE, volume, spread, delta) |
| `strategies.yaml` | Defined strategies (created via TUI) |
| `alerts.yaml` | Alert conditions (optional, read by engine) |

## Architecture

```
cli.py (Typer) → services/ → core/ (business logic) + broker/ppi/ (PPI API)
TUI (Textual) → services/ → core/ + broker/ppi/
engine/ (scheduler, strategies, approvals) — headless automation
```

- **`arg_options/services/`** — wrapper layer: `AccountService`, `ChainService`, `ScreeningService`, `JournalService`.
- **`arg_options/core/`** — pure logic: `chain.py`, `screen.py`, `discovery.py`, `greeks.py`, `journal.py`, `alerts.py`.
- **`arg_options/broker/ppi/`** — PPI API implementation with `_patch_restclient()` wrapping HTTP calls for response logging.
- **`arg_options/broker/interfaces.py`** — abstract base classes (`Broker`, `BrokerConfig`, `MarketDataService`, etc.).
- **`arg_options/db.py`** — SQLite database (journal, orders, positions, strategies, approvals). Auto-creates `data/journal.db`.
- **`arg_options/engine/`** — headless automation: `scheduler.py` (TradingEngine loop), `strategies.py`, `approval.py`.

Tests have been removed.

## TUI keybindings

| Key | Action |
|---|---|
| `c` | Build chain |
| `s` | Screen (from stored file) |
| `f` | Screen (from form settings) |
| `d` | Discovery |
| `j` | Journal sync |
| `a` | Alerts |
| `l` | Log viewer |
| `w` | Toggle auto-refresh watch |
| `t` | Toggle test/production |
| `o` | Active orders |
| `r` | Discovery results (full-screen browse, click card → detail + budget + save) |
| `v` | Approval queue |
| `n` | Saved strategies (list + New button) |
| `?` | Help |
| `q` | Quit |

## Discovery assessment flow

- Press `d` → runs discovery engine → grades opportunities A/B/C/F (A = iron condor / OTM spreads, ROC > 15%; B = near-ATM spreads, ROC > 5%; C = deep ITM; F = noise/stale)
- Top 10 shown in log; press `r` for full-screen list of all 39-60 opps
- Click `▶ Details` on any card → `OpportunityDetailScreen`:
  - Full leg layout, metrics, ROC, warning
  - **Budget input** (max risk $) — position sizing auto-calculates (contracts × risk)
  - **Save to Engine** → writes to `strategies` table in `data/journal.db` as pending
- Press `n` to see all saved strategies with leg structures displayed
- `d` skips re-running discovery if chain unchanged (checks `data/last_discovery.json`)

## Crash logging

- **Shell level**: `_bootstrap.sh` tees stderr to `data/run-YYYYMMDD-HHMMSS.log` (ANSI + all output)
- **Python level**: `CrashLogger` in `tui_app.py` sets `sys.excepthook` + asyncio exception handler → writes plain text to `data/crash.log`
- stderr is also redirected to `_StderrLogger` which writes to `data/crash.log`
- Check both files on any unexpected TUI exit

## Persisted data files

| File | Purpose |
|---|---|
| `data/chains/chain_*.parquet` | Chain data (timestamped) |
| `data/last_discovery.json` | Cached discovery results (auto-loaded on TUI start if chain unchanged) |
| `data/run-*.log` | stderr capture from shell launch |
| `data/crash.log` | Python unhandled exceptions |
| `data/journal.db` | SQLite: journal, orders, positions, strategies, approvals |

## Known quirks

- **PPI sandbox `SearchInstrument` endpoint returns HTTP 400 for ALL requests** (SQL stored procedure error). The sandbox simply does not support this endpoint. Chain building in sandbox mode returns 0 instruments gracefully with a warning. Use `production` mode or load from stored chain data. The production API likely works.
- **Textual `RichLog` has no selection/copy.** The TUI's `_log()` also writes to `data/arg_options.log` via Python logging, stripped of Rich markup. Run `tail -f data/arg_options.log` alongside the TUI.
- **PPI sandbox rate limit:** 10 calls/hour. Error message shown in TUI when hit. Use `--stored` flag in screening subcommand where possible to reuse last chain data.
- **`resolve_project_root()`** walks up from the file's location looking for `.env_test`. Multiple implementations exist (`config_persist.py`, `settings.py`, `db.py`) — keep in sync.
- **Chain data is persisted** as Parquet in `data/chains/` (timestamped).
- **Strike scaling**: BYMA raw strike from ticker is /10 (not /100). GFGC74307J → strike 7430.7 vs spot ~7420.
- **Intrinsic value guard**: Chain builder skips rows where `mid < 0.9 * intrinsic` to filter out deep-ITM pre-split artifacts.
- **Python version**: `.venv` may be Python 3.11 while system is newer. `Path.write_text(append=)` is 3.13+ — use `open(mode='a')` instead.
