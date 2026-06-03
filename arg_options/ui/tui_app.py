from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
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

from arg_options.config.config_persist import (
    load_yaml,
    resolve_project_root,
    resolve_settings_yaml_path,
    resolve_screening_path_for_settings,
    save_chain_profile,
    save_screening_file,
)
from arg_options.core.discovery import Opportunity, Leg
from arg_options.services.account_service import AccountService
from arg_options.services.chain_service import ChainService
from arg_options.services.journal_service import JournalService
from arg_options.services.screening_service import ScreeningService
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

DiscoveryResultScreen { background: $surface; }
DiscoveryResultScreen #dr-title { dock: top; height: 1; text-align: center; text-style: bold; padding: 1 0; }
DiscoveryResultScreen #dr-scroll { height: 1fr; }
DiscoveryResultScreen #dr-close { dock: bottom; width: 100%; }
DiscoveryResultScreen .opp-card { height: auto; border: solid $border; margin: 0 0 1 0; padding: 1; }
DiscoveryResultScreen .opp-btn { width: auto; min-width: 12; margin: 1 0 0 0; }

OpportunityDetailScreen { background: $surface; }
OpportunityDetailScreen #od-title { dock: top; height: 1; text-align: center; text-style: bold; padding: 1 0; }
OpportunityDetailScreen #od-body { height: 1fr; padding: 0 2; }
OpportunityDetailScreen #od-body Label { margin: 0 0 0 0; }
OpportunityDetailScreen #od-actions { dock: bottom; height: auto; align: center middle; margin: 1 0; }
OpportunityDetailScreen #od-actions > Button { margin: 0 1; min-width: 16; }
OpportunityDetailScreen .sizing-box { width: 30; height: 3; border: solid $border; padding: 0 1; margin: 0 0 0 2; }

StrategiesScreen { background: $surface; }
StrategiesScreen #st-title { dock: top; height: 1; text-align: center; text-style: bold; padding: 1 0; }
StrategiesScreen #st-scroll { height: 1fr; }
StrategiesScreen .st-card { height: auto; border: solid $border; margin: 0 0 1 0; padding: 1; }
StrategiesScreen #st-actions { dock: bottom; height: auto; align: center middle; margin: 1 0; }
StrategiesScreen #st-actions > Button { margin: 0 1; min-width: 16; }
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


class DiscoveryResultScreen(ModalScreen[None]):
    def __init__(self, opps: list[Any]) -> None:
        super().__init__()
        from arg_options.core.discovery import assess_all, grade_counts
        self._assessed = assess_all(opps)
        self._counts = grade_counts(self._assessed)

    def compose(self) -> ComposeResult:
        total = len(self._assessed)
        grade_str = "  ".join(
            f"{g}{self._counts.get(g, 0)}" for g in ("A", "B", "C", "F")
        )
        yield Label(f"Discovery Results ({total}) — {grade_str}", id="dr-title")
        colors = {"A": "green", "B": "yellow", "C": "dim", "F": "red"}
        cards: list[Vertical] = []
        for idx, (opp, a) in enumerate(self._assessed):
            color = colors.get(a.grade, "white")
            children: list[Label] = [
                Label(f"[bold {color}]{a.grade}[/bold {color}]  {opp.strategy} — {a.tag}"),
                Label(f"  {a.summary}"),
            ]
            if a.warning:
                children.append(Label(f"  [red]\u26a0 {a.warning}[/red]"))
            children.append(Label(f"  [dim]{a.detail.replace(chr(10), ' | ')}[/dim]"))
            children.append(Button("▶ Details", id=f"opp-btn-{idx}", classes="opp-btn"))
            cards.append(Vertical(*children, classes="opp-card"))
        yield ScrollableContainer(*cards, id="dr-scroll")
        yield Button("Close", variant="primary", id="dr-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "dr-close":
            self.dismiss(None)
        elif event.button.id and event.button.id.startswith("opp-btn-"):
            idx = int(event.button.id.split("-")[-1])
            opp, a = self._assessed[idx]
            self.app.push_screen(OpportunityDetailScreen(opp, a))


def _compute_position(opp: Opportunity, budget: float) -> dict:
    strat = opp.strategy
    m = opp.metrics
    if strat in ("bear_call_spread", "bull_put_spread"):
        risk_per = max(0, m.get("width", 1) - m.get("credit", 0))
        contracts = int(budget // risk_per) if risk_per > 0 else 0
    elif strat == "iron_condor":
        risk_per = max(0, m.get("max_loss", 1))
        contracts = int(budget // risk_per) if risk_per > 0 else 0
    elif strat == "mariposa":
        risk_per = max(0, m.get("cost", 1))
        contracts = int(budget // risk_per) if risk_per > 0 else 0
    elif strat == "synthetic":
        risk_per = max(0, abs(m.get("cost", 1)))
        contracts = int(budget // risk_per) if risk_per > 0 else 0
    elif strat == "calendar":
        risk_per = max(0, m.get("cost", 1))
        contracts = int(budget // risk_per) if risk_per > 0 else 0
    else:
        risk_per = 0
        contracts = 0
    contracts = max(0, contracts)
    return {
        "contracts": contracts,
        "risk_per": risk_per,
        "total_risk": risk_per * contracts,
        "total_credit": contracts * (m.get("credit") or m.get("net_credit") or m.get("cost") or 0),
    }


class OpportunityDetailScreen(ModalScreen[None]):
    def __init__(self, opp: Opportunity, assessment: Any) -> None:
        super().__init__()
        self._opp = opp
        self._a = assessment

    def compose(self) -> ComposeResult:
        opp, a = self._opp, self._a
        colors = {"A": "green", "B": "yellow", "C": "dim", "F": "red"}
        color = colors.get(a.grade, "white")
        yield Label(
            f"[bold {color}]{a.grade}[/bold {color}]  {opp.strategy} — {a.tag}",
            id="od-title",
        )
        m = opp.metrics
        with ScrollableContainer(id="od-body"):
            yield Label("[bold]Legs[/bold]")
            for l in opp.legs:
                yield Label(f"  {l.side:4s} {l.ticker}  strike={l.strike:.0f}  {l.right:4s}  x{l.qty}")
            yield Label("")
            metric_line = "  ".join(f"{k}={v}" for k, v in sorted(m.items()))
            yield Label(f"[bold]Metrics:[/bold] {metric_line}")
            yield Label(f"[bold]ROC:[/bold] {a.roc:.1%}")
            if a.warning:
                yield Label(f"[red]\u26a0 {a.warning}[/red]")
            yield Label("")
            yield Label("[bold]Position Sizing[/bold]")
            budget_default = int(
                (m.get("width", 0) or m.get("max_loss", 0) or m.get("cost", 0) or 500) * 2
            )
            with Horizontal():
                yield Input(
                    value=str(budget_default),
                    id="od-budget",
                    placeholder="Max risk ($)",
                )
                yield Static(id="od-sizing", classes="sizing-box")
        with Horizontal(id="od-actions"):
            yield Button("Save to Engine", variant="success", id="od-save")
            yield Button("Cancel", variant="primary", id="od-close")

    def on_mount(self) -> None:
        self._update_sizing()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "od-budget":
            self._update_sizing()

    def _update_sizing(self) -> None:
        try:
            budget_str = self.query_one("#od-budget", Input).value.strip()
            budget = float(budget_str) if budget_str else 0
        except ValueError:
            budget = 0
        pos = _compute_position(self._opp, budget)
        sizing = self.query_one("#od-sizing", Static)
        if pos["contracts"] <= 0 or budget <= 0:
            sizing.update("[dim]Enter a budget to see position sizing[/dim]")
            return
        sizing.update(
            f"[bold]{pos['contracts']} contract(s)[/bold]\n"
            f"Risk: ${pos['total_risk']:.0f}\n"
            f"{'Credit' if self._opp.side == 'SELL' else 'Cost'}: ${pos['total_credit']:.0f}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "od-close":
            self.dismiss(None)
        elif event.button.id == "od-save":
            try:
                budget_str = self.query_one("#od-budget", Input).value.strip()
                budget = float(budget_str) if budget_str else 0
            except ValueError:
                budget = 0
            pos = _compute_position(self._opp, budget)
            entry = {
                "root": self._opp.root,
                "strategy": self._opp.strategy,
                "side": self._opp.side,
                "assessment_grade": self._a.grade,
                "assessment_tag": self._a.tag,
                "budget": budget,
                "contracts": pos["contracts"],
                "risk_per": pos["risk_per"],
                "total_risk": pos["total_risk"],
                "total_credit": pos["total_credit"],
                "legs": [
                    {"ticker": l.ticker, "side": l.side, "strike": l.strike, "right": l.right, "qty": l.qty * max(pos["contracts"], 1)}
                    for l in self._opp.legs
                ],
                "metrics": dict(self._opp.metrics),
                "status": "pending",
            }
            from arg_options.db import save_strategy
            save_strategy(
                f"{self._opp.strategy}_{self._opp.root}_{self._a.grade}",
                self._opp.strategy,
                entry,
            )
            app = self.app
            if isinstance(app, ArgOptionsApp):
                app._log(f"[green]Opportunity saved to engine:[/green] {self._opp.strategy} {self._opp.root} ({pos['contracts']} ctcts)")
            self.dismiss(None)


class StrategiesScreen(ModalScreen[None]):
    def compose(self) -> ComposeResult:
        strategies = get_strategies(enabled_only=False)
        yield Label(f"Saved Strategies ({len(strategies)})", id="st-title")
        with ScrollableContainer(id="st-scroll"):
            if not strategies:
                yield Label("[dim]No saved strategies.[/dim]")
            for s in strategies:
                cfg = s.get("config", {})
                strat_type = cfg.get("strategy", s["type"])
                grade = cfg.get("assessment_grade", "?")
                contracts = cfg.get("contracts", 0)
                leg_lines = []
                for l in cfg.get("legs", []):
                    leg_lines.append(
                        f"    {l['side']:4s} {'CALL' if l.get('right') in ('CALL','') else 'PUT':4s}  strike={l['strike']:.0f}"
                    )
                with Vertical(classes="st-card"):
                    yield Label(
                        f"[bold]{strat_type}[/bold]  grade={grade}  "
                        f"contracts={contracts}  status={s.get('status', '?')}"
                    )
                    yield Label(
                        f"[dim]  Budget: ${cfg.get('budget', 0):.0f}  "
                        f"Risk: ${cfg.get('total_risk', 0):.0f}  "
                        f"Credit: ${cfg.get('total_credit', 0):.0f}[/dim]"
                    )
                    if leg_lines:
                        yield Label(f"  [dim]{chr(10).join(leg_lines)}[/dim]")
        with Horizontal(id="st-actions"):
            yield Button("New Strategy", variant="success", id="st-new")
            yield Button("Close", variant="primary", id="st-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "st-new":
            self.dismiss(None)
            from arg_options.ui.tui_app import ArgOptionsApp
            app = self.app
            if isinstance(app, ArgOptionsApp):
                app.push_screen(StrategyConfigScreen())
        elif event.button.id == "st-close":
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


class CrashLogger:
    _file: Path | None = None

    @classmethod
    def setup(cls) -> None:
        cls._file = resolve_project_root() / "data" / "crash.log"
        cls._file.parent.mkdir(parents=True, exist_ok=True)

        def _write(msg: str) -> None:
            if cls._file:
                with open(cls._file, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.now().isoformat()} {msg}\n")

        def _excepthook(typ, val, tb) -> None:
            _write("UNHANDLED EXCEPTION\n" + "".join(traceback.format_exception(typ, val, tb)))

        sys.excepthook = _excepthook

        def _asyncio_handler(loop, context) -> None:
            _write(f"ASYNCIO EXCEPTION\n{context.get('message', '')}\n{traceback.format_exc()}")

        try:
            asyncio.get_event_loop().set_exception_handler(_asyncio_handler)
        except RuntimeError:
            pass

        class _StderrLogger:
            def write(self, buf: str) -> None:
                if buf.strip():
                    _write(f"STDERR: {buf.rstrip()}")

            def flush(self) -> None:
                pass

        sys.stderr = _StderrLogger()  # type: ignore[assignment]


CrashLogger.setup()


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
        Binding("r", "show_discovery", "Discovery Rs"),
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
        self._discovery_chain: str = ""
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

    # ---- Discovery persistence ----

    @property
    def _discovery_path(self) -> Path:
        return resolve_project_root() / "data" / "last_discovery.json"

    @property
    def _latest_chain_name(self) -> str:
        chains_dir = resolve_project_root() / "data" / "chains"
        if not chains_dir.exists():
            return ""
        files = sorted(chains_dir.glob("chain_*.parquet"), reverse=True)
        return files[0].name if files else ""

    def _save_discovery(self) -> None:
        if not self._discovery_opps:
            return
        import json
        chain_name = self._latest_chain_name
        self._discovery_chain = chain_name
        payload = {
            "chain": chain_name,
            "saved_at": datetime.now().isoformat(),
            "opportunities": [
                {
                    "root": o.root,
                    "strategy": o.strategy,
                    "side": o.side,
                    "confidence": o.confidence,
                    "legs": [
                        {"ticker": l.ticker, "side": l.side, "qty": l.qty,
                         "strike": l.strike, "right": l.right, "bid": l.bid, "ask": l.ask}
                        for l in o.legs
                    ],
                    "metrics": dict(o.metrics),
                }
                for o in self._discovery_opps
            ],
        }
        self._discovery_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load_discovery(self) -> None:
        path = self._discovery_path
        if not path.exists():
            return
        import json
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        chain_name = payload.get("chain", "")
        if chain_name != self._latest_chain_name:
            self._log("[dim]Saved discovery is stale (chain changed)[/dim]")
            return
        raw = payload.get("opportunities", [])
        self._discovery_opps = [
            Opportunity(
                root=o["root"], strategy=o["strategy"], side=o["side"],
                confidence=o["confidence"],
                legs=[Leg(**l) for l in o["legs"]],
                metrics=o.get("metrics", {}),
            )
            for o in raw
        ]
        self._discovery_chain = chain_name
        self._log(f"[green]Loaded {len(self._discovery_opps)} cached discovery results[/green]")

    def on_mount(self) -> None:
        self._init_file_logging()
        table = self.query_one("#results-table", DataTable)
        table.add_columns("Time", "Action", "Result")
        self._log("argoptions TUI started")
        self._log(f"Mode: {self._mode.upper()}")

        self._populate_form()
        self._load_discovery()
        self._status(f"Ready — {self._mode.upper()} mode")

        if self._watch_on and self._watch_interval_s:
            self._start_watch()

    def _status(self, msg: str) -> None:
        bar = self.query_one("#status-bar", Static)
        bar.update(f" {msg}")

    def _init_file_logging(self) -> None:
        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            for h in logging.getLogger().handlers:
                if isinstance(h, logging.FileHandler) and h.baseFilename == str(LOG_FILE):
                    return
            handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
            handler.setLevel(logging.DEBUG)
            handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
            root = logging.getLogger()
            root.setLevel(logging.DEBUG)
            root.addHandler(handler)
        except Exception:
            pass

    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        try:
            log = self.query_one("#log-panel", RichLog)
            log.write(f"[dim]{ts}[/dim] {msg}")
        except Exception:
            pass
        plain = re.sub(r'\[/?\w+\]', '', msg)
        logger.info("TUI: %s", plain)

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

    def action_show_discovery(self) -> None:
        if not self._discovery_opps:
            self._log("[yellow]No discovery results cached — press [bold]d[/bold] to run discovery[/yellow]")
            return
        self.push_screen(DiscoveryResultScreen(self._discovery_opps))

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
        self.push_screen(StrategiesScreen())

    def _check_live_allowed(self) -> bool:
        if self._mode == "production":
            service = AccountService(mode="production")
            config = service.config
            if not config.allow_live_orders:
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
            
            # Use shared chain service
            service = ChainService(mode=self._mode)
            count, ts = service.build_and_save_chain()
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
        )

        try:
            self.call_from_thread(self._status, "Running screen...")
            self.call_from_thread(self._log, f"Running screen (source={source})...")
            
            # Use shared screening service
            service = ScreeningService(mode=self._mode, use_stored=True)
            df = service.run_screening()
            stats = service.get_screening_stats(df)
            
            count = stats["total_rows"]
            msg = f"Screen results: {count} rows"
            self.call_from_thread(self._log, f"[green]{msg}[/green]")
            self.call_from_thread(self._append_result, "Screen", msg)
            if df.empty:
                rules = load_screening_config(settings=service.config)
                reason = explain_why_screen_empty([], rules)
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
        from arg_options.core.discovery import (
            DiscoveryEngine, Opportunity, assess_all, grade_counts,
        )
        import logging

        logging.getLogger('arg_options.core.discovery').setLevel(logging.DEBUG)

        try:
            current_chain = self._latest_chain_name
            if self._discovery_opps and self._discovery_chain == current_chain:
                opps = self._discovery_opps
                self.call_from_thread(self._log, "[green]Chain unchanged — using cached discovery[/green]")
            else:
                self.call_from_thread(self._status, "Discovering opportunities...")
                self.call_from_thread(self._log, "Running discovery...")

                service = AccountService(mode=self._mode)
                engine = DiscoveryEngine(service.config)
                opps = engine.run()
            self._discovery_opps = opps
            assessed = assess_all(opps)
            counts = grade_counts(assessed)

            total = len(opps)
            grade_str = "  ".join(
                f"{grade}{counts.get(grade, 0)}" for grade in ("A", "B", "C", "F")
            )
            self.call_from_thread(self._log, f"[green]Discovery: {total} opportunities[/green]")
            self.call_from_thread(self._log, f"[bold]Grades:[/bold] {grade_str}")
            self.call_from_thread(self._log, f"[bold]Top picks:[/bold]")

            shown = 0
            for opp, a in assessed:
                if shown >= 10:
                    break
                color = {"A": "green", "B": "yellow", "C": "dim", "F": "red"}.get(a.grade, "white")
                prefix = {"A": " \u25b6", "B": " \u25b8", "C": "  ", "F": " \u2716"}.get(a.grade, "  ")
                self.call_from_thread(
                    self._log,
                    f"  {prefix} [bold {color}]{a.grade}[/bold {color}] {a.summary}",
                )
                shown += 1

            self.call_from_thread(self._log, f"[dim]Press [bold]r[/bold] to browse all, [bold]v[/bold] for approvals, [bold]n[/bold] for new strategy[/dim]")
            self.call_from_thread(self._append_result, "Discovery", f"{total} opps ({grade_str})")
            self.call_from_thread(self._status, f"Discovery: {total} opps")
            self._save_discovery()
        except Exception as e:
            self.call_from_thread(self._log, f"[red]Discovery error:[/red] {e}")
            self.call_from_thread(self._status, f"Discovery error: {e}")
            import traceback
            self.call_from_thread(self._log, f"[dim]{traceback.format_exc()}[/dim]")

    @work(thread=True, exclusive=True, name="sync-journal")
    def _sync_journal(self) -> None:
        from arg_options.core.journal import summarize_pnl

        try:
            self.call_from_thread(self._status, "Syncing journal...")
            self.call_from_thread(self._log, "Syncing journal / P&L...")
            
            # Use shared journal service
            service = JournalService(mode=self._mode)
            summary = service.sync_and_summarize()
            pnl = summarize_pnl(service.config)
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
            
            # Use shared settings pattern through account service
            service = AccountService(mode=self._mode)
            results = run_alerts_once(service.config)
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
            
            # Use shared account service
            service = AccountService(mode=self._mode)
            accounts = service.get_account_status()
            msg = f"Login OK — {len(accounts)} account(s)"
            for acc_info in accounts:
                acc = acc_info["account"]
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
            
            # Use shared account service
            service = AccountService(mode=self._mode)
            active = service.get_active_orders()
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
            if not self._check_live_allowed():
                return
            
            # Use shared account service
            service = AccountService(mode=self._mode)
            result = service.cancel_orders(order_id=order_id)
            self.call_from_thread(
                self._log, f"[green]{result}[/green]"
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
