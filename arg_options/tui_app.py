"""TUI configurable: cadena + screening en formulario con guardado en YAML y tabla de resultados."""

from __future__ import annotations

import logging
import traceback
from typing import Any, Callable, Optional

import pandas as pd
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Input, RichLog, Static, Select

from arg_options import chain as chainmod
from arg_options import journal as journalmod
from arg_options import screen as screenmod
from arg_options.alerts import run_alerts_once
from arg_options.config_persist import (
    resolve_screening_path_for_settings,
    resolve_settings_yaml_path,
    save_chain_profile,
    save_screening_file,
)
from arg_options.ppi_client import connect_ppi, ping_readonly
from arg_options.settings import load_settings

TABLE_COLUMNS = [
    "ticker",
    "strike",
    "right",
    "expiry",
    "bid",
    "ask",
    "mid",
    "last",
    "volume",
    "iv",
    "delta",
]

_DISPLAY_TITLE = "Resultados (chain o screen)"


def _quiet_loggers() -> None:
    for name in ("", "arg_options", "urllib3", "ppi_client"):
        logging.getLogger(name).setLevel(logging.WARNING)


def _populate_data_table(table: DataTable, df: pd.DataFrame, max_rows: int = 100) -> None:
    table.clear(columns=True)
    if df is None or df.empty:
        return
    cols = [c for c in TABLE_COLUMNS if c in df.columns]
    if not cols:
        cols = list(df.columns)[:14]
    for c in cols:
        table.add_column(c, key=c)
    for _, row in df.head(max_rows).iterrows():
        cells = []
        for c in cols:
            v = row.get(c)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                cells.append("")
            else:
                cells.append(str(v)[:72])
        table.add_row(*cells)


class ArgOptionsApp(App):
    """Formulario + tabla. Guardá cadena y screening en archivos; screen desde archivo o formulario."""

    CSS = """
    #main_row { height: 100%; }
    #left_scroll {
        width: 46%;
        min-width: 32;
        border: solid $accent;
        padding: 0 1 1 1;
        height: 100%;
    }
    #right_col { width: 1fr; border: solid $accent; padding: 0 1; }
    #tbl { height: 50%; min-height: 10; }
    #log { height: 1fr; min-height: 6; border: tall $border-blurred; }
    #tbl_title { padding: 0 0 1 0; }
    #screen_status {
        height: 4;
        margin-bottom: 1;
        padding: 0 1;
        background: $surface;
        color: $text;
        border: solid $border;
        overflow-y: scroll;
    }
    /* Los Input en Horizontal se quedaban con ancho 0; acá ocupan todo el panel */
    #left_scroll Input {
        width: 1fr;
        height: auto;
        min-height: 3;
        margin: 0 0 1 0;
    }
    #spot_row {
        height: auto;
        margin-bottom: 1;
    }
    #sel_quick {
        width: 20;
        margin-left: 1;
    }
    #dte_row, #vol_spread_row, #delta_row, #alert_row {
        height: auto;
        margin-bottom: 1;
    }
    #left_scroll .field-label {
        height: auto;
        margin-top: 1;
        color: $text-muted;
    }
    #left_scroll .section-title {
        height: auto;
        margin: 1 0 0 0;
    }
    #left_scroll .btn-row {
        height: auto;
        margin: 1 0 1 0;
    }
    #left_scroll .btn-row Button {
        margin-right: 1;
        margin-bottom: 0;
    }
    Button { margin-right: 1; margin-bottom: 1; }
    """


    BINDINGS = [
        Binding("q", "quit", "Salir"),
        Binding("c", "chain", "Chain"),
        Binding("s", "screen_file", "Screen"),
        Binding("f", "screen_form", "ScrForm"),
        Binding("j", "journal", "Journal"),
        Binding("a", "alerts", "Alertas"),
        Binding("l", "login_test", "Login"),
        Binding("w", "toggle_watch", "Auto"),
        Binding("question_mark", "help", "Ayuda"),
    ]

    def __init__(self, watch_interval_s: Optional[float] = None) -> None:
        super().__init__()
        self._watch_interval_s = watch_interval_s
        self._watch_timer = None
        self._watch_on = bool(watch_interval_s and watch_interval_s > 0)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main_row"):
            with ScrollableContainer(id="left_scroll"):
                yield Static(
                    "[bold]Cadena (acción)[/bold] — raíz BYMA + spot en PPI",
                    classes="section-title",
                )
                yield Static("Spot (Ticker)", classes="field-label")
                with Horizontal(id="spot_row"):
                    yield Input(placeholder="GGAL", id="in_spot")
                    yield Select(
                        options=[
                            ("GGAL", "GGAL"),
                            ("YPF", "YPF"),
                            ("PAMP", "PAMP"),
                            ("BMA", "BMA"),
                        ],
                        id="sel_quick",
                    )
                yield Static("Raíz (prefijo opción, ej. GFG)", classes="field-label")
                yield Input(placeholder="GFG", id="in_root")
                with Horizontal(classes="btn-row"):
                    yield Button("Validar con PPI", id="btn_validate", variant="primary")
                    yield Button("Guardar cadena", id="btn_save_chain")
                    yield Button("Ejecutar chain", id="btn_chain")
                yield Static(
                    "[bold]Screening[/bold] — se guarda en screening.yaml (ver paths.screening)",
                    classes="section-title",
                )
                yield Static("DTE (días al vencimiento)", classes="field-label")
                with Horizontal(id="dte_row"):
                    yield Input(placeholder="min", id="in_min_dte")
                    yield Input(placeholder="max", id="in_max_dte")
                yield Static("Volumen / Spread %", classes="field-label")
                with Horizontal(id="vol_spread_row"):
                    yield Input(placeholder="min vol", id="in_min_vol")
                    yield Input(placeholder="max spread", id="in_max_spread")
                yield Static("Delta |Δ|", classes="field-label")
                with Horizontal(id="delta_row"):
                    yield Input(placeholder="min delta", id="in_min_delta")
                    yield Input(placeholder="max delta", id="in_max_delta")
                yield Static("Alertas (intervalo seg / vencimiento días)", classes="field-label")
                with Horizontal(id="alert_row"):
                    yield Input(placeholder="intervalo seg", id="in_alert_int")
                    yield Input(placeholder="vencimiento días", id="in_near_exp")
                with Horizontal(classes="btn-row"):
                    yield Button("Guardar screening", id="btn_save_screen", variant="success")
                    yield Button("Screen (archivo)", id="btn_screen_file")
                    yield Button("Screen (form)", id="btn_screen_form")

            with Vertical(id="right_col"):
                yield Static(_DISPLAY_TITLE, id="tbl_title")
                yield DataTable(id="tbl", zebra_stripes=True)
                yield Static("", id="screen_status")
                yield RichLog(id="log", highlight=True, markup=True, max_lines=120)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#log", RichLog).write(
            "[bold green]arg-options[/bold green] — [dim]c/s/f/s keys · w auto · ? ayuda · q salir[/dim]"
        )
        self._reload_form_from_disk()
        if self._watch_on and self._watch_interval_s:
            self._log(
                f"[cyan]Auto-chain[/cyan] cada {self._watch_interval_s:.0f}s "
                "(w pausa). Primera corrida en ~1s."
            )
            self._watch_timer = self.set_interval(self._watch_interval_s, self._watch_tick)
            self.set_timer(0.75, self.action_chain)
        else:
            self._log("[dim]Auto OFF — w activa 300s o usá interactive --watch N[/dim]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "btn_validate":
            root = self.query_one("#in_root", Input).value.strip()
            spot = self.query_one("#in_spot", Input).value.strip()
            self.run_validate_worker(root, spot)
        elif bid == "btn_save_chain":
            self._save_chain_clicked()
        elif bid == "btn_chain":
            self.action_chain()
        elif bid == "btn_save_screen":
            self._save_screen_clicked()
        elif bid == "btn_screen_file":
            self.action_screen_file()
        elif bid == "btn_screen_form":
            self.action_screen_form()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "sel_quick":
            val = event.value
            mapping = {
                "GGAL": "GFG",
                "YPF": "YPF",
                "PAMP": "PMP",
                "BMA": "BMA",
            }
            self.query_one("#in_spot", Input).value = val
            self.query_one("#in_root", Input).value = mapping.get(val, "")

    # Removed on_select_changed


    def _reload_form_from_disk(self) -> None:
        s = load_settings()
        roots = list(s.chain_config.get("option_roots") or [])
        root = roots[0] if roots else ""
        spot_map = s.underlying_spot
        spot = spot_map.get(root, next(iter(spot_map.values()), "") if spot_map else "")
        self.query_one("#in_spot", Input).value = spot
        self.query_one("#in_root", Input).value = root
        rules = screenmod.load_screening_config(None, s)
        al = rules.get("alerts") or {}

        def gv(key: str, default: Any) -> str:
            v = rules.get(key)
            if v is None:
                return str(default)
            return str(v)

        self.query_one("#in_min_dte", Input).value = gv("min_days_to_expiry", 0)
        self.query_one("#in_max_dte", Input).value = gv("max_days_to_expiry", 45)
        self.query_one("#in_min_vol", Input).value = gv("min_open_interest_proxy_volume", 0)
        self.query_one("#in_max_spread", Input).value = gv("max_bid_ask_spread_pct_mid", 35)
        self.query_one("#in_min_delta", Input).value = gv("min_abs_delta", 0)
        self.query_one("#in_max_delta", Input).value = gv("max_abs_delta", 0.99)
        self.query_one("#in_alert_int", Input).value = str(al.get("min_interval_seconds", 3600))
        self.query_one("#in_near_exp", Input).value = str(al.get("near_expiry_days", 7))

    def _float_in(self, id_: str, default: float = 0.0) -> float:
        v = self.query_one(f"#{id_}", Input).value.strip()
        return float(v) if v else default

    def _int_in(self, id_: str, default: int = 0) -> int:
        v = self.query_one(f"#{id_}", Input).value.strip()
        return int(float(v)) if v else default

    def _rules_from_form(self) -> dict[str, Any]:
        return {
            "min_days_to_expiry": self._float_in("in_min_dte", 0),
            "max_days_to_expiry": self._float_in("in_max_dte", 365),
            "min_open_interest_proxy_volume": self._float_in("in_min_vol", 0),
            "max_bid_ask_spread_pct_mid": self._float_in("in_max_spread", 100),
            "min_abs_delta": self._float_in("in_min_delta", 0),
            "max_abs_delta": self._float_in("in_max_delta", 1),
            "alerts": {
                "min_interval_seconds": self._int_in("in_alert_int", 3600),
                "near_expiry_days": self._int_in("in_near_exp", 7),
            },
        }

    def _save_chain_clicked(self) -> None:
        try:
            root = self.query_one("#in_root", Input).value.strip()
            spot = self.query_one("#in_spot", Input).value.strip()
            path = resolve_settings_yaml_path()
            save_chain_profile(path, root, spot)
            self._log(f"[green]Guardado[/green] cadena en [cyan]{path}[/cyan] ({root} → {spot})")
            self._reload_form_from_disk()
        except Exception as e:
            self._log(f"[red]No se guardó cadena:[/red] {e}")

    def _save_screen_clicked(self) -> None:
        try:
            rules = self._rules_from_form()
            s = load_settings()
            spath = resolve_screening_path_for_settings(s.paths)
            save_screening_file(spath, rules)
            self._log(f"[green]Guardado[/green] screening en [cyan]{spath}[/cyan]")
        except Exception as e:
            self._log(f"[red]No se guardó screening:[/red] {e}")

    def _log(self, msg: str) -> None:
        self.query_one("#log", RichLog).write(msg)

    def _set_results_table(self, df: pd.DataFrame, title: str) -> None:
        self.query_one("#tbl_title", Static).update(title)
        _populate_data_table(self.query_one("#tbl", DataTable), df)

    def action_help(self) -> None:
        self._log(
            "[bold]Ayuda[/bold]\n"
            "• Guardá [bold]cadena[/bold] para persistir raíz+spot en settings YAML.\n"
            "• [bold]Screen (archivo)[/bold] usa el YAML guardado; [bold]Screen (form)[/bold] usa solo lo que ves (sin guardar).\n"
            "• Teclas: c chain · s screen archivo · f screen form · w auto."
        )

    def action_quit(self) -> None:
        self.exit()

    def action_chain(self) -> None:
        self.run_chain_worker()

    def action_screen_file(self) -> None:
        self.run_screen_file_worker()

    def action_screen_form(self) -> None:
        rules = self._rules_from_form()
        self.run_screen_form_worker(rules)

    def action_journal(self) -> None:
        self.run_journal_worker()

    def action_alerts(self) -> None:
        self.run_alerts_worker()

    def action_login_test(self) -> None:
        self.run_login_worker()

    def action_toggle_watch(self) -> None:
        if self._watch_interval_s is None or self._watch_interval_s <= 0:
            self._watch_interval_s = 300.0
            self._log("[cyan]Auto 300s[/cyan] — al arrancar podés usar [bold]--watch N[/bold].")
        self._watch_on = not self._watch_on
        if self._watch_on:
            if self._watch_timer is None:
                self._watch_timer = self.set_interval(self._watch_interval_s, self._watch_tick)
            else:
                self._watch_timer.resume()
            self._log(f"[cyan]Auto-chain ON[/cyan] cada {self._watch_interval_s:.0f}s")
        else:
            if self._watch_timer is not None:
                self._watch_timer.pause()
            self._log("[dim]Auto pausado[/dim]")

    def _watch_tick(self) -> None:
        if self._watch_on:
            self.run_chain_worker()

    @work(thread=True, exclusive=True, name="validate")
    def run_validate_worker(self, root: str, spot: str) -> None:
        self._from_thread(lambda: self._log("[dim]validando…[/dim]"))
        try:
            s = load_settings()
            ppi = connect_ppi(s)
            root_u = root.strip().upper()
            spot_u = spot.strip().upper()
            market = s.ppi.get("market", "Byma")
            opt = s.ppi.get("instrument_type_options", "OPCIONES")
            eq = s.ppi.get("instrument_type_equity", "ACCIONES")
            stk = s.ppi.get("default_settlement", "A-48HS")
            raw = ppi.marketdata.search_instrument(root_u, "", market, opt)
            nopt = len(raw or [])
            q = ppi.marketdata.current(spot_u, eq, stk)
            px = q.get("price")

            def done() -> None:
                self._log(
                    f"[green]OK[/green] — opciones listadas: [bold]{nopt}[/bold] · "
                    f"spot [bold]{spot_u}[/bold] último=[bold]{px}[/bold]"
                )

            self.call_from_thread(done)
        except Exception as e:
            self._from_thread(lambda err=e: self._log(f"[red]Validación:[/red] {err}"))

    @work(thread=True, exclusive=True, name="chain")
    def run_chain_worker(self) -> None:
        self._from_thread(lambda: self._log("[dim]chain…[/dim]"))
        try:
            s = load_settings()
            ppi = connect_ppi(s)
            rows = chainmod.build_full_chain(ppi, s)
            n, ts = chainmod.persist_chain(rows, s, export_parquet=False)
            latest = screenmod.get_latest_snapshot_rows(s)

            def done() -> None:
                self._log(f"[green]chain OK[/green] — {n} filas · {ts}")
                self._set_results_table(latest, f"Última cadena · {n} contratos · {ts}")

            self.call_from_thread(done)
        except Exception as e:
            self._from_thread(lambda err=e: self._log(f"[red]chain:[/red] {err}"))

    @work(thread=True, exclusive=True, name="screen_file")
    def run_screen_file_worker(self) -> None:
        self._from_thread(lambda: self._log("[dim]screen (archivo)…[/dim]"))
        try:
            s = load_settings()
            df = screenmod.run_screen(s)
            self._finish_screen_ui(df, from_file=True, rules_for_hint=screenmod.load_screening_config(None, s))
        except Exception as e:
            self._from_thread(lambda err=e: self._log(f"[red]screen:[/red] {err}"))

    @work(thread=True, exclusive=True, name="screen_form")
    def run_screen_form_worker(self, rules: dict[str, Any]) -> None:
        self._from_thread(lambda: self._log("[dim]screen (form)…[/dim]"))
        try:
            s = load_settings()
            df = screenmod.run_screen(s, rules_override=rules)
            self._finish_screen_ui(df, from_file=False, rules_for_hint=rules)
        except Exception as e:
            self._from_thread(lambda err=e: self._log(f"[red]screen:[/red] {err}"))

    def _update_status(self, msg: str, color: str = "white") -> None:
        self.query_one("#screen_status", Static).update(f"[{color}]{msg}[/]")

    def _finish_screen_ui(self, df: pd.DataFrame, from_file: bool, rules_for_hint: dict[str, Any]) -> None:
        if df.empty:
            s = load_settings()
            latest = screenmod.get_latest_snapshot_rows(s)
            hint = (
                screenmod.explain_why_screen_empty(latest, rules_for_hint)
                if len(latest)
                else "Sin snapshot — ejecutá chain primero."
            )

            def empty() -> None:
                self._log(f"[yellow]screen: 0 filas[/yellow]")
                self._update_status(hint, "yellow")
                self._set_results_table(pd.DataFrame(), "Screen (0 filas)")

            self.call_from_thread(empty)
            return

        src = "archivo" if from_file else "formulario"

        def show() -> None:
            self._log(f"[green]screen OK[/green] — {len(df)} filas ({src})")
            self._update_status(f"Screen OK: {len(df)} filas encontradas.", "green")
            self._set_results_table(df, f"Screen ({src}) · {len(df)} filas")

        self.call_from_thread(show)


    @work(thread=True, exclusive=True, name="journal")
    def run_journal_worker(self) -> None:
        self._from_thread(lambda: self._log("[dim]journal…[/dim]"))
        try:
            s = load_settings()
            ppi = connect_ppi(s)
            summary = journalmod.sync_journal(ppi, s)
            pnl = journalmod.summarize_pnl_proxy(s)

            def done() -> None:
                self._log(f"[green]journal OK[/green] — {summary}")
                self._log(f"[dim]{pnl}[/dim]")

            self.call_from_thread(done)
        except Exception as e:
            self._from_thread(lambda err=e: self._log(f"[red]journal:[/red] {err}"))

    @work(thread=True, exclusive=True, name="alerts")
    def run_alerts_worker(self) -> None:
        self._from_thread(lambda: self._log("[dim]alerts…[/dim]"))
        try:
            s = load_settings()
            sent = run_alerts_once(s)

            def done() -> None:
                for m in sent:
                    self._log(m)

            self.call_from_thread(done)
        except Exception as e:
            tb = traceback.format_exc()
            self._from_thread(lambda err=e, tb=tb: self._log(f"[red]alerts:[/red] {err}\n{tb}"))

    @work(thread=True, exclusive=True, name="login")
    def run_login_worker(self) -> None:
        self._from_thread(lambda: self._log("[dim]login…[/dim]"))
        try:
            s = load_settings()
            ppi = connect_ppi(s)
            out = ping_readonly(ppi, s.ppi_account_number)
            acc = out.pop("accounts", None)

            def done() -> None:
                self._log(f"[green]login OK[/green] — mercados: {len(out.get('markets', []))}")
                if acc:
                    self._log(f"[dim]{acc}[/dim]")

            self.call_from_thread(done)
        except Exception as e:
            self._from_thread(lambda err=e: self._log(f"[red]login:[/red] {err}"))

    def _from_thread(self, fn: Callable[[], None]) -> None:
        self.call_from_thread(fn)


def run_interactive(watch_interval_s: Optional[float] = None) -> None:
    _quiet_loggers()
    ArgOptionsApp(watch_interval_s=watch_interval_s).run()
