from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Select,
    Static,
)

from arg_options.broker import create_broker
from arg_options.broker.interfaces import BrokerConfig
from arg_options.config.config_persist import (
    load_yaml,
    resolve_project_root,
    resolve_settings_yaml_path,
    resolve_screening_path_for_settings,
    save_chain_profile,
    save_screening_file,
)
from arg_options.config.settings import load_settings
from arg_options.db import (
    get_positions,
    get_orders,
    get_strategies,
    init_db,
    log_event,
    save_strategy,
)

logger = logging.getLogger(__name__)

LOG_FILE = resolve_project_root() / "data" / "arg_options.log"

MODE_STYLES = {
    "test": "bold yellow on default",
    "production": "bold white on red",
}

HEADER_BAR = """
#app-header { height: 3; dock: top; padding: 0 1; }
#app-header > #header-title { width: 1fr; height: 3; content-align: left middle; }
#app-header > #mode-indicator { width: auto; height: 3; content-align: right middle; padding: 0 2; }
#app-header > #mode-indicator.test { color: yellow; }
#app-header > #mode-indicator.production { color: red; }
"""

LEFT_PANEL = """
#left-panel { width: 35%; min-width: 40; height: 1fr; border: solid $primary; overflow: auto; padding: 0 1; }
#left-panel > #config-scroll { height: 1fr; overflow: auto; }
.form-section { height: auto; margin: 0 0 1 0; }
.form-section > Label { margin: 1 0 0 0; text-style: bold; }
.form-section > .section-title { text-style: bold underline; margin: 1 0 0 0; }
.form-row { height: auto; layout: horizontal; }
.form-row > Input { width: 1fr; margin: 0 1 0 0; }
.form-row > Button { width: auto; min-width: 8; }
.form-row > .quick-select { width: auto; min-width: 6; margin: 0 1 0 0; }
.button-row { height: auto; layout: horizontal; margin: 1 0; }
.button-row > Button { width: 1fr; margin: 0 1 0 0; }
"""

RIGHT_PANEL = """
#right-panel { width: 65%; height: 1fr; border: solid $secondary; }
#status-bar { height: 1; dock: top; background: $surface; color: $text; padding: 0 1; }
#results-table { height: 1fr; }
#log-panel { height: 40%; min-height: 6; border-top: solid $border; }
"""

MODAL_CSS = """
EnvSwitchScreen { align: center middle; }
EnvSwitchScreen > #dialog { width: 50; height: auto; padding: 2 3; border: thick $error; background: $surface; }
EnvSwitchScreen > #dialog > Label { width: 1fr; text-align: center; margin: 1 0; }
EnvSwitchScreen > #dialog > #prod-warning { color: $error; text-style: bold; text-align: center; }
EnvSwitchScreen > #dialog > Horizontal { height: auto; align: center middle; margin: 1 0; }
EnvSwitchScreen > #dialog > Horizontal > Button { margin: 0 1; }

OrderDetailScreen { align: center middle; }
OrderDetailScreen > #dialog { width: 60; height: auto; padding: 2 3; border: thick $primary; background: $surface; }
OrderDetailScreen > #dialog > Label { width: 1fr; margin: 0 0; }
OrderDetailScreen > #dialog > .title { text-style: bold; text-align: center; margin: 0 0 1 0; }
OrderDetailScreen > #dialog > Horizontal { height: auto; align: center middle; margin: 1 0; }
OrderDetailScreen > #dialog > Horizontal > Button { margin: 0 1; }

OpportunityApprovalScreen { align: center middle; }
OpportunityApprovalScreen > #dialog { width: 80; height: 80%; padding: 1 2; border: thick $success; background: $surface; }
OpportunityApprovalScreen > #dialog > .title { text-style: bold; text-align: center; margin: 0 0 1 0; }
.opp-card { height: auto; border: solid $border; margin: 0 0 1 0; padding: 1; }
.opp-card > Label { width: 1fr; }
.opp-card > Horizontal { height: auto; align: center middle; margin: 1 0 0 0; }
.opp-card > Horizontal > Button { margin: 0 1; }

StrategyConfigScreen { align: center middle; }
StrategyConfigScreen > #dialog { width: 50; height: auto; padding: 2 3; border: thick $primary; background: $surface; }
StrategyConfigScreen > #dialog > .title { text-style: bold; text-align: center; margin: 0 0 1 0; }
StrategyConfigScreen > #dialog > Label { margin: 1 0 0 0; }
StrategyConfigScreen > #dialog > Input { width: 1fr; }
StrategyConfigScreen > #dialog > Select { width: 1fr; }
StrategyConfigScreen > #dialog > Horizontal { height: auto; align: center middle; margin: 1 0; }
StrategyConfigScreen > #dialog > Horizontal > Button { margin: 0 1; }

LogViewerScreen { align: center middle; }
LogViewerScreen > #dialog { width: 80; height: 80%; padding: 1 2; border: thick $primary; background: $surface; }
LogViewerScreen > #dialog > #log-title { text-style: bold; text-align: center; margin: 0 0 1 0; }
LogViewerScreen > #dialog > #log-content { width: 1fr; height: 1fr; margin: 0 0 1 0; }
LogViewerScreen > #dialog > Horizontal { height: auto; align: center middle; }
LogViewerScreen > #dialog > Horizontal > Button { margin: 0 1; }
"""


class EnvSwitchScreen(ModalScreen[bool]):
    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("SWITCH TO PRODUCTION MODE", id="prod-warning")
            yield Label(
                "You are about to enable LIVE TRADING.\n"
                "Real orders WILL be placed.\n"
                "Real money WILL be at risk."
            )
            yield Label("Are you absolutely sure?")
            with Horizontal():
                yield Button("Yes, switch to PRODUCTION", variant="error", id="confirm")
                yield Button("Cancel", variant="primary", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)


class OrderDetailScreen(ModalScreen[None]):
    def __init__(self, order: Any) -> None:
        super().__init__()
        self._order = order

    def compose(self) -> ComposeResult:
        o = self._order
        with Vertical(id="dialog"):
            yield Label(f"Order #{o.id}", classes="title")
            yield Label(f"Ticker:    {o.ticker}")
            yield Label(f"Operation: {o.operation}")
            yield Label(f"Quantity:  {o.quantity}")
            yield Label(f"Price:     {o.price}")
            yield Label(f"Status:    {o.status}")
            yield Label(f"Type:      {o.order_type}")
            yield Label(f"Settlement: {o.settlement}")
            yield Label(f"Date:      {o.date}")
            with Horizontal():
                yield Button("Cancel Order", variant="error", id="cancel-order")
                yield Button("Close", variant="primary", id="close")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-order":
            app = self.app
            if isinstance(app, ArgOptionsApp):
                app._log(f"Cancelling order #{self._order.id}...")
                app._cancel_single_order(self._order.id)
            self.dismiss(None)
        else:
            self.dismiss(None)


class OpportunityApprovalScreen(ModalScreen[None]):
    def __init__(self, opportunities: list[dict]) -> None:
        super().__init__()
        self._opps = opportunities

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(f"Pending Approvals ({len(self._opps)})", classes="title")
            if not self._opps:
                yield Label("No pending opportunities.")
            for opp in self._opps:
                opp_id = opp.get("id", "?")
                data = opp.get("opportunity_data", opp)
                with Vertical(classes="opp-card"):
                    yield Label(f"ID: {opp_id}")
                    for k, v in data.items() if isinstance(data, dict) else []:
                        yield Label(f"  {k}: {v}")
                    with Horizontal():
                        yield Button(
                            f"Approve #{opp_id}",
                            variant="success",
                            id=f"approve_{opp_id}",
                        )
                        yield Button(
                            f"Reject #{opp_id}",
                            variant="error",
                            id=f"reject_{opp_id}",
                        )
            yield Button("Close", variant="primary", id="close")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id.startswith("approve_"):
            opp_id = int(btn_id.split("_", 1)[1])
            from arg_options.db import approve_or_reject

            approve_or_reject(opp_id, "approved")
            app = self.app
            if isinstance(app, ArgOptionsApp):
                app._log(f"Approved opportunity #{opp_id}")
        elif btn_id.startswith("reject_"):
            opp_id = int(btn_id.split("_", 1)[1])
            from arg_options.db import approve_or_reject

            approve_or_reject(opp_id, "rejected")
            app = self.app
            if isinstance(app, ArgOptionsApp):
                app._log(f"Rejected opportunity #{opp_id}")
        elif btn_id == "close":
            self.dismiss(None)
        self.dismiss(None)


class StrategyConfigScreen(ModalScreen[Optional[dict]]):
    def __init__(self, strategy: Optional[dict] = None) -> None:
        super().__init__()
        self._strategy = strategy

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Strategy Configuration", classes="title")
            yield Label("Name")
            yield Input(
                placeholder="e.g. covered-call-ggal",
                id="strategy-name",
                value=(self._strategy or {}).get("name", ""),
            )
            yield Label("Type")
            yield Select(
                [
                    ("Covered Call", "covered_call"),
                    ("Cash Secured Put", "cash_secured_put"),
                    ("Vertical Spread", "vertical_spread"),
                    ("Iron Condor", "iron_condor"),
                    ("Custom", "custom"),
                ],
                prompt="Select type...",
                id="strategy-type",
                value=(self._strategy or {}).get("type"),
            )
            yield Label("Config (JSON)")
            existing = (self._strategy or {}).get("config", {})
            yield Input(
                placeholder='{"key": "value"}',
                id="strategy-config",
                value=json.dumps(existing) if existing else "",
            )
            with Horizontal():
                yield Button("Save", variant="success", id="save")
                yield Button("Cancel", variant="primary", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            name = self.query_one("#strategy-name", Input).value
            type_widget = self.query_one("#strategy-type", Select)
            type_val = type_widget.value if type_widget.value else "custom"
            config_str = self.query_one("#strategy-config", Input).value
            try:
                config = json.loads(config_str) if config_str.strip() else {}
            except json.JSONDecodeError as e:
                self._log(f"Invalid JSON config: {e}")
                return
            self.dismiss({"name": name, "type": type_val, "config": config})
        else:
            self.dismiss(None)

    def _log(self, msg: str) -> None:
        app = self.app
        if isinstance(app, ArgOptionsApp):
            app._log(msg)


class LogViewerScreen(ModalScreen[None]):
    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Logs (last 20 lines)", id="log-title")
            content = self._read_logs()
            yield RichLog(id="log-content", highlight=True, markup=True)
            with Horizontal():
                yield Button("Refresh", id="refresh")
                yield Button("Close", variant="primary", id="close")

    def _read_logs(self) -> str:
        log_path = LOG_FILE
        if not log_path or not log_path.exists():
            return "No log file found."
        lines = log_path.read_text(encoding="utf-8").splitlines()
        return "\n".join(lines[-20:])

    def on_mount(self) -> None:
        content = self._read_logs()
        log_widget = self.query_one("#log-content", RichLog)
        log_widget.clear()
        log_widget.write(content)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh":
            content = self._read_logs()
            log_widget = self.query_one("#log-content", RichLog)
            log_widget.clear()
            log_widget.write(content)
        else:
            self.dismiss(None)


class ArgOptionsApp(App[None]):
    DEFAULT_CSS = HEADER_BAR + LEFT_PANEL + RIGHT_PANEL + MODAL_CSS

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("c", "build_chain", "Chain"),
        Binding("s", "run_screen_file", "Screen"),
        Binding("f", "run_screen_form", "Screen(f)"),
        Binding("d", "discover", "Discover"),
        Binding("j", "journal", "Journal"),
        Binding("a", "alerts", "Alerts"),
        Binding("l", "show_logs", "Logs"),
        Binding("w", "toggle_watch", "Watch"),
        Binding("t", "toggle_env", "Test↔Prod"),
        Binding("o", "show_orders", "Orders"),
        Binding("v", "approval_queue", "Approvals"),
        Binding("n", "new_strategy", "New Strat"),
        Binding("question_mark", "show_help", "Help"),
    ]

    def __init__(
        self,
        mode: str = "test",
        watch_interval_s: Optional[float] = None,
    ) -> None:
        super().__init__()
        self._mode = mode
        self._watch_interval_s = watch_interval_s
        self._watch_on = watch_interval_s is not None
        self._watch_timer: Optional[str] = None
        self._discovery_opps: list[Any] = []
        init_db()

    @property
    def mode(self) -> str:
        return self._mode

    def compose(self) -> ComposeResult:
        with Horizontal(id="app-header"):
            yield Static("argoptions", id="header-title")
            yield Static(self._mode_label(), id="mode-indicator", classes=self._mode)
        with Horizontal():
            with Vertical(id="left-panel"):
                with ScrollableContainer(id="config-scroll"):
                    with Vertical(classes="form-section"):
                        yield Label("Chain Config", classes="section-title")
                        yield Label("Spot Ticker")
                        with Horizontal(classes="form-row"):
                            yield Input(
                                placeholder="e.g. GGAL", id="spot-ticker", value="GGAL"
                            )
                            yield Button("GGAL", id="qsel-ggal", classes="quick-select")
                            yield Button("YPFD", id="qsel-ypfd", classes="quick-select")
                            yield Button("PAMP", id="qsel-pamp", classes="quick-select")
                        yield Label("Option Root")
                        with Horizontal(classes="form-row"):
                            yield Input(
                                placeholder="e.g. GFG", id="option-root", value="GFG"
                            )
                        yield Label("Spot Price Reference")
                        with Horizontal(classes="form-row"):
                            yield Input(
                                placeholder="e.g. 3500", id="spot-price", value=""
                            )
                        with Horizontal(classes="button-row"):
                            yield Button("Save Chain Profile", id="save-chain-profile")
                            yield Button("Build Chain", id="build-chain", variant="primary")

                    with Vertical(classes="form-section"):
                        yield Label("Screening Config", classes="section-title")
                        yield Label("DTE Range")
                        with Horizontal(classes="form-row"):
                            yield Input(placeholder="Min DTE", id="min-dte", value="7")
                            yield Input(placeholder="Max DTE", id="max-dte", value="45")
                        yield Label("Volume / Spread")
                        with Horizontal(classes="form-row"):
                            yield Input(
                                placeholder="Min Volume", id="min-volume", value="100"
                            )
                            yield Input(
                                placeholder="Max Spread %",
                                id="max-spread",
                                value="10",
                            )
                        yield Label("Delta Range")
                        with Horizontal(classes="form-row"):
                            yield Input(
                                placeholder="Min Delta", id="min-delta", value="0.2"
                            )
                            yield Input(
                                placeholder="Max Delta", id="max-delta", value="0.8"
                            )
                        with Horizontal(classes="button-row"):
                            yield Button("Save Screen Config", id="save-screen-config")
                            yield Button("Screen!", id="run-screen", variant="primary")

                    with Vertical(classes="form-section"):
                        yield Label("Alerts", classes="section-title")
                        with Horizontal(classes="form-row"):
                            yield Input(
                                placeholder="Alert ticker",
                                id="alert-ticker",
                                value="",
                            )
                        with Horizontal(classes="button-row"):
                            yield Button("Run Alerts", id="run-alerts")

                    with Vertical(classes="form-section"):
                        yield Label("Actions", classes="section-title")
                        with Horizontal(classes="button-row"):
                            yield Button("Discover", id="discover-opps")
                            yield Button("Journal", id="sync-journal")
                            yield Button("Orders", id="show-orders")
                        with Horizontal(classes="button-row"):
                            yield Button("Login Test", id="login-test")
                            yield Button("Approvals", id="approval-queue")
                            yield Button("New Strategy", id="new-strategy")

            with Vertical(id="right-panel"):
                yield Static(id="status-bar")
                yield DataTable(id="results-table")
                yield RichLog(id="log-panel", highlight=True, markup=True)

        yield Footer()

    def _mode_label(self) -> str:
        if self._mode == "production":
            return " [PRODUCTION] LIVE TRADING "
        return " [TEST] Sandbox "

    def on_mount(self) -> None:
        table = self.query_one("#results-table", DataTable)
        table.add_columns("Time", "Action", "Result")
        self._log("argoptions TUI started")
        self._log(f"Mode: {self._mode.upper()}")

        self._populate_form()
        self._status(f"Ready — {self._mode.upper()} mode")

        if self._watch_on and self._watch_interval_s:
            self._start_watch()

    def _status(self, msg: str) -> None:
        bar = self.query_one("#status-bar", Static)
        bar.update(f" {msg}")

    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        log = self.query_one("#log-panel", RichLog)
        log.write(f"[dim]{ts}[/dim] {msg}")

    def _append_result(self, action: str, result: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        table = self.query_one("#results-table", DataTable)
        table.add_row(ts, action, result)

    def _clear_results(self) -> None:
        table = self.query_one("#results-table", DataTable)
        table.clear()

    def _get_form_value(self, widget_id: str, default: str = "") -> str:
        try:
            w = self.query_one(f"#{widget_id}", Input)
            return w.value.strip() or default
        except Exception:
            return default

    def _set_form_value(self, widget_id: str, value: str) -> None:
        try:
            w = self.query_one(f"#{widget_id}", Input)
            w.update(value)
        except Exception:
            pass

    def _set_form_values(self, values: dict[str, str]) -> None:
        for wid, val in values.items():
            self._set_form_value(wid, val)

    def _populate_form(self) -> None:
        try:
            yaml_path = resolve_settings_yaml_path()
            data = load_yaml(yaml_path)
            chain_cfg = data.get("chain", {})
            screen_cfg = data.get("screening", {})
            vals: dict[str, str] = {}
            roots = chain_cfg.get("option_roots", [])
            if roots:
                vals["option-root"] = roots[0]
            spot = chain_cfg.get("underlying_spot", "")
            if spot:
                vals["spot-price"] = str(spot)
            spot_ticker = chain_cfg.get("spot_ticker", "")
            if spot_ticker:
                vals["spot-ticker"] = spot_ticker
            for key, widget_id in [
                ("min_dte", "min-dte"),
                ("max_dte", "max-dte"),
                ("min_volume", "min-volume"),
                ("max_spread", "max-spread"),
                ("min_delta", "min-delta"),
                ("max_delta", "max-delta"),
            ]:
                val = screen_cfg.get(key)
                if val is not None:
                    vals[widget_id] = str(val)
            if vals:
                self._set_form_values(vals)
        except Exception:
            pass

    def _start_watch(self) -> None:
        if not self._watch_interval_s:
            return
        self._watch_on = True
        self._log(
            f"Auto-refresh every {self._watch_interval_s}s [green]ON[/green]"
        )

    def _stop_watch(self) -> None:
        self._watch_on = False
        self._log("Auto-refresh [red]OFF[/red]")

    async def _watch_cycle(self) -> None:
        if not self._watch_on:
            return
        self._log("Auto-refresh cycle...")
        self._build_chain()
        await self._delay(self._watch_interval_s or 30)
        self._watch_cycle()

    async def _delay(self, seconds: float) -> None:
        import asyncio

        await asyncio.sleep(seconds)

    def action_toggle_watch(self) -> None:
        if self._watch_on:
            self._stop_watch()
        else:
            self._start_watch()

    def action_toggle_env(self) -> None:
        if self._mode == "production":
            self._mode = "test"
            indicator = self.query_one("#mode-indicator", Static)
            indicator.classes = "test"
            indicator.update(self._mode_label())
            self._log("Switched to [yellow]TEST[/yellow] mode")
            self._status("TEST mode")
        else:

            def _on_dismiss(result: bool) -> None:
                if result:
                    self._mode = "production"
                    indicator = self.query_one("#mode-indicator", Static)
                    indicator.classes = "production"
                    indicator.update(self._mode_label())
                    self._log("Switched to [red]PRODUCTION[/red] mode — LIVE TRADING")
                    self._status("PRODUCTION mode — LIVE TRADING")
                else:
                    self._log("Production switch cancelled")

            self.app.push_screen(EnvSwitchScreen(), _on_dismiss)

    def action_show_logs(self) -> None:
        self.push_screen(LogViewerScreen())

    def action_show_help(self) -> None:
        self._status("Bindings: q=quit c=chain s=screen(f) f=screen d=discover j=journal a=alerts l=logs w=watch t=test/prod o=orders v=approvals n=strat")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "build-chain":
            self._build_chain()
        elif btn_id == "save-chain-profile":
            self._save_chain_profile()
        elif btn_id == "run-screen":
            self._run_screen(None)
        elif btn_id == "save-screen-config":
            self._save_screen_config()
        elif btn_id == "discover-opps":
            self._discover()
        elif btn_id == "sync-journal":
            self._sync_journal()
        elif btn_id == "show-orders":
            self._show_orders()
        elif btn_id == "login-test":
            self._login_test()
        elif btn_id == "run-alerts":
            self._run_alerts()
        elif btn_id == "approval-queue":
            self._show_approvals()
        elif btn_id == "new-strategy":
            self._new_strategy()
        elif btn_id and btn_id.startswith("qsel-"):
            from arg_options.core.instruments import resolve_option_root
            ticker = btn_id.split("-", 1)[1].upper()
            root = resolve_option_root(ticker)
            self._set_form_value("spot-ticker", ticker)
            self._set_form_value("option-root", root)

    def action_build_chain(self) -> None:
        self._build_chain()

    def action_run_screen_file(self) -> None:
        self._run_screen("file")

    def action_run_screen_form(self) -> None:
        self._run_screen("form")

    def action_discover(self) -> None:
        self._discover()

    def action_journal(self) -> None:
        self._sync_journal()

    def action_alerts(self) -> None:
        self._run_alerts()

    def action_login_test(self) -> None:
        self._login_test()

    def action_show_orders(self) -> None:
        self._show_orders()

    def action_approval_queue(self) -> None:
        self._show_approvals()

    def action_new_strategy(self) -> None:
        self._new_strategy()

    def _check_live_allowed(self) -> bool:
        if self._mode == "production":
            cfg = load_settings("production")
            if not cfg.allow_live_orders:
                self._log("[red]ERROR:[/red] allow_live_orders is FALSE. Set ALLOW_LIVE_ORDERS=true in .env_prod")
                self._status("LIVE ORDERS NOT ALLOWED — check .env_prod")
                return False
        return True

    @work(thread=True, exclusive=True, name="build-chain")
    def _build_chain(self) -> None:
        from arg_options.core.chain import build_full_chain, persist_chain

        try:
            self.call_from_thread(self._status, "Building chain...")
            self.call_from_thread(self._log, "Building option chain...")
            config = load_settings(self._mode)
            broker = create_broker(config)
            broker.connect()
            rows = build_full_chain(broker, config)
            count, ts = persist_chain(rows, config)
            msg = f"Chain saved: {count} rows at {ts}"
            self.call_from_thread(self._log, f"[green]{msg}[/green]")
            self.call_from_thread(self._append_result, "Chain", msg)
            self.call_from_thread(self._status, f"Chain: {count} rows")
        except Exception as e:
            self.call_from_thread(self._log, f"[red]Chain error:[/red] {e}")
            self.call_from_thread(self._status, f"Chain error: {e}")

    def _save_chain_profile(self) -> None:
        try:
            spot = self._get_form_value("spot-ticker", "GGAL")
            root = self._get_form_value("option-root", "GGAL")
            yaml_path = resolve_settings_yaml_path()
            save_chain_profile(yaml_path, root, spot)
            self._log(f"[green]Chain profile saved:[/green] root={root}, spot={spot}")
            self._status("Chain profile saved")
        except Exception as e:
            self._log(f"[red]Save chain error:[/red] {e}")

    def _save_screen_config(self) -> None:
        try:
            rules = {
                "min_dte": int(self._get_form_value("min-dte", "7")),
                "max_dte": int(self._get_form_value("max-dte", "45")),
                "min_volume": int(self._get_form_value("min-volume", "100")),
                "max_spread": float(self._get_form_value("max-spread", "10")),
                "min_delta": float(self._get_form_value("min-delta", "0.2")),
                "max_delta": float(self._get_form_value("max-delta", "0.8")),
            }
            yaml_path = resolve_settings_yaml_path()
            data = load_yaml(yaml_path)
            screen_path = resolve_screening_path_for_settings(data)
            save_screening_file(screen_path, rules)
            self._log(f"[green]Screen config saved:[/green] {screen_path}")
            self._status("Screen config saved")
        except Exception as e:
            self._log(f"[red]Save screen error:[/red] {e}")

    @work(thread=True, exclusive=True, name="run-screen")
    def _run_screen(self, source: Optional[str]) -> None:
        from arg_options.core.screen import (
            explain_why_screen_empty,
            load_screening_config,
            run_screen,
        )

        try:
            self.call_from_thread(self._status, "Running screen...")
            self.call_from_thread(self._log, f"Running screen (source={source})...")
            config = load_settings(self._mode)
            df = run_screen(config)
            count = len(df)
            msg = f"Screen results: {count} rows"
            self.call_from_thread(self._log, f"[green]{msg}[/green]")
            self.call_from_thread(self._append_result, "Screen", msg)
            if df.empty:
                from arg_options.core.screen import get_latest_snapshot_rows
                latest_rows = get_latest_snapshot_rows(config)
                rules = load_screening_config(settings=config)
                reason = explain_why_screen_empty(latest_rows, rules)
                self.call_from_thread(self._log, f"[yellow]Empty:[/yellow] {reason}")
                self.call_from_thread(self._status, f"Screen empty: {reason}")
            else:
                self.call_from_thread(self._status, f"Screen: {count} hits")
                self.call_from_thread(self._display_df, df)
        except Exception as e:
            self.call_from_thread(self._log, f"[red]Screen error:[/red] {e}")
            tb = traceback.format_exc()
            self.call_from_thread(self._log, f"[dim]{tb}[/dim]")
            self.call_from_thread(self._status, f"Screen error: {e}")

    def _display_df(self, df: Any) -> None:
        try:
            table = self.query_one("#results-table", DataTable)
            table.clear()
            columns = list(df.columns)
            table.add_columns(*columns)
            for _, row in df.iterrows():
                vals = [str(row[c]) for c in columns]
                table.add_row(*vals)
        except Exception as e:
            self._log(f"[red]Display error:[/red] {e}")

    @work(thread=True, exclusive=True, name="discover")
    def _discover(self) -> None:
        from arg_options.core.discovery import DiscoveryEngine, Opportunity

        try:
            self.call_from_thread(self._status, "Discovering opportunities...")
            self.call_from_thread(self._log, "Running discovery...")
            config = load_settings(self._mode)
            engine = DiscoveryEngine(config)
            opps = engine.run()
            self._discovery_opps = opps
            msg = f"Discovery: {len(opps)} opportunities"
            self.call_from_thread(self._log, f"[green]{msg}[/green]")
            self.call_from_thread(self._append_result, "Discovery", msg)
            for opp in opps[:10]:
                self.call_from_thread(
                    self._log, f"  [cyan]{opp}[/cyan]"
                )
            self.call_from_thread(self._status, msg)
        except Exception as e:
            self.call_from_thread(self._log, f"[red]Discovery error:[/red] {e}")
            self.call_from_thread(self._status, f"Discovery error: {e}")

    @work(thread=True, exclusive=True, name="sync-journal")
    def _sync_journal(self) -> None:
        from arg_options.core.journal import summarize_pnl, sync_journal

        try:
            self.call_from_thread(self._status, "Syncing journal...")
            self.call_from_thread(self._log, "Syncing journal / P&L...")
            config = load_settings(self._mode)
            broker = create_broker(config)
            broker.connect()
            summary = sync_journal(broker, config)
            pnl = summarize_pnl(config)
            self.call_from_thread(
                self._log, f"[green]Journal synced[/green]"
            )
            self.call_from_thread(self._log, f"P&L: {pnl}")
            self.call_from_thread(self._append_result, "Journal", str(pnl)[:80])
            self.call_from_thread(self._status, f"P&L: {pnl}")
        except Exception as e:
            self.call_from_thread(self._log, f"[red]Journal error:[/red] {e}")
            self.call_from_thread(self._status, f"Journal error: {e}")

    @work(thread=True, exclusive=True, name="run-alerts")
    def _run_alerts(self) -> None:
        from arg_options.core.alerts import run_alerts_once

        try:
            self.call_from_thread(self._status, "Running alerts...")
            self.call_from_thread(self._log, "Running alerts...")
            config = load_settings(self._mode)
            results = run_alerts_once(config)
            msg = f"Alerts executed: {results}"
            self.call_from_thread(self._log, f"[green]{msg}[/green]")
            self.call_from_thread(self._append_result, "Alerts", str(results)[:80])
            self.call_from_thread(self._status, msg)
        except Exception as e:
            self.call_from_thread(self._log, f"[red]Alerts error:[/red] {e}")
            self.call_from_thread(self._status, f"Alerts error: {e}")

    @work(thread=True, exclusive=True, name="login-test")
    def _login_test(self) -> None:
        try:
            self.call_from_thread(self._status, "Testing login...")
            self.call_from_thread(self._log, "Testing PPI API connection...")
            config = load_settings(self._mode)
            broker = create_broker(config)
            broker.connect()
            accounts = broker.account.get_accounts()
            msg = f"Login OK — {len(accounts)} account(s)"
            for acc in accounts:
                msg += f" [{acc.account_number} {acc.name}]"
            self.call_from_thread(self._log, f"[green]{msg}[/green]")
            self.call_from_thread(self._append_result, "Login", msg)
            self.call_from_thread(self._status, "Login OK")
        except Exception as e:
            self.call_from_thread(self._log, f"[red]Login error:[/red] {e}")
            self.call_from_thread(self._status, f"Login failed: {e}")

    @work(thread=True, exclusive=True, name="show-orders")
    def _show_orders(self) -> None:
        try:
            self.call_from_thread(self._status, "Fetching orders...")
            self.call_from_thread(self._log, "Fetching active orders...")
            config = load_settings(self._mode)
            broker = create_broker(config)
            broker.connect()
            active = broker.orders.get_active_orders(config.account_number)
            if not active:
                self.call_from_thread(self._log, "[yellow]No active orders[/yellow]")
                self.call_from_thread(self._status, "No active orders")
                return
            self.call_from_thread(self._render_orders, active)
            self.call_from_thread(
                self._log, f"[green]{len(active)} active orders[/green]"
            )
            self.call_from_thread(self._status, f"{len(active)} active orders")
        except Exception as e:
            self.call_from_thread(self._log, f"[red]Orders error:[/red] {e}")
            self.call_from_thread(self._status, f"Orders error: {e}")

    def _render_orders(self, active: list) -> None:
        table = self.query_one("#results-table", DataTable)
        table.clear()
        table.add_columns("ID", "Ticker", "Op", "Qty", "Price", "Status")
        for o in active:
            table.add_row(
                str(o.id), o.ticker, o.operation, str(o.quantity), str(o.price), o.status
            )

    @work(thread=True, exclusive=True, name="cancel-single")
    def _cancel_single_order(self, order_id: int) -> None:
        try:
            config = load_settings(self._mode)
            if not config.allow_live_orders:
                self.call_from_thread(
                    self._log, "[red]ERROR:[/red] allow_live_orders is FALSE"
                )
                return
            broker = create_broker(config)
            broker.connect()
            result = broker.orders.cancel_order(config.account_number, order_id)
            self.call_from_thread(
                self._log, f"[green]Order #{order_id} cancelled: {result.status}[/green]"
            )
            self.call_from_thread(self._status, f"Order #{order_id} cancelled")
        except Exception as e:
            self.call_from_thread(self._log, f"[red]Cancel error:[/red] {e}")

    def _show_approvals(self) -> None:
        from arg_options.db import get_pending_approvals

        opps = get_pending_approvals()
        self.push_screen(OpportunityApprovalScreen(opps))

    async def _new_strategy(self) -> None:
        result = await self.push_screen_wait(StrategyConfigScreen())
        if result:
            try:
                save_strategy(result["name"], result["type"], result["config"])
                self._log(f"[green]Strategy saved:[/green] {result['name']} ({result['type']})")
                self._status("Strategy saved")
            except Exception as e:
                self._log(f"[red]Save strategy error:[/red] {e}")
