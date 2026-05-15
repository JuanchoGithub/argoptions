"""TUI configurable: cadena + screening en formulario con guardado en YAML y tabla de resultados."""

from __future__ import annotations

import logging
import math
import traceback
from typing import Any, Callable, Optional

import pandas as pd
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, RichLog, Static, Select

from arg_options import chain as chainmod
from arg_options import discovery as dscmod
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


# ---------------------------------------------------------------------------
# Discovery detail popup (modal screen)
# ---------------------------------------------------------------------------

_STRATEGY_EXPLANATIONS = {
    "mariposa": (
        "Mariposa (Call Butterfly)",
        "Comprás 1 Call abajo, vendés 2 Calls en el medio, comprás 1 Call arriba.",
        "Ganás si el precio del activo se mantiene cerca del strike central al vencimiento.",
        "Riesgo limitado al débito pagado. Beneficio máximo si el precio cierra exactamente en K2.",
        "Conviene cuando esperás baja volatilidad y movimiento lateral.",
    ),
    "renta_ic": (
        "Iron Condor",
        "Vendés 1 Call y 1 Put fuera del dinero, comprando seguros más lejos.",
        "Ganás si el precio se mantiene entre los strikes vendidos.",
        "Riesgo limitado al ancho entre el strike vendido y el seguro, menos el crédito recibido.",
        "Ideal para mercados laterales con alta probabilidad de éxito.",
    ),
    "credit_spread": (
        "Credit Spread",
        "Vendés una opción y comprás otra más lejana como seguro.",
        "Ganás si el precio no supera el strike vendido.",
        "Riesgo limitado. Estrategia direccional con alta probabilidad.",
        "Usar cuando tenés una visión direccional pero querés probabilidad alta.",
    ),
    "calendar": (
        "Calendar Spread",
        "Vendés una opción de corto plazo y comprás la misma opción a largo plazo.",
        "Ganás por la diferencia en la velocidad de deterioro temporal (Theta).",
        "La opción corta pierde valor más rápido que la larga. Riesgo limitado.",
        "Aprovechás la asimetría temporal. Mejor en mercados laterales.",
    ),
    "sintetico": (
        "Sintético",
        "Combinación de Call y Put en el mismo strike que replica tener el activo.",
        "Sintético Long = Comprar Call + Vender Put (equivalente a tener la acción).",
        "Sintético Short = Vender Call + Comprar Put (equivalente a estar corto).",
        "Usar para eficiencia de capital o cuando la acción no está disponible.",
    ),
}


class DiscoveryDetailScreen(ModalScreen[None]):
    """Pantalla modal con detalle completo de una oportunidad."""

    def __init__(self, opp: dscmod.Opportunity) -> None:
        super().__init__()
        self.opp = opp

    def compose(self) -> ComposeResult:
        opp = self.opp
        title, desc, earning, risk, when = _STRATEGY_EXPLANATIONS.get(
            opp.strategy,
            (opp.strategy, "", "—", "—", "—"),
        )

        with Vertical():
            yield Static(f"[bold cyan]{title}[/bold cyan]", id="detail_title")

            yield Static(f"[bold]Root:[/bold] {opp.root}")
            yield Static(f"[bold]Confianza:[/bold] [green]{opp.confidence:.0f}%[/green]")

            yield Static("", classes="sep")
            yield Static(f"[bold]¿Qué es?[/bold]\n{desc}")
            yield Static(f"[bold]¿Cómo se gana?[/bold]\n{earning}")
            yield Static(f"[bold]Riesgo:[/bold]\n{risk}")
            yield Static(f"[bold]¿Cuándo usarla?[/bold]\n{when}")

            yield Static("", classes="sep")
            yield Static("[bold]Estructura (patas)[/bold]")
            for leg in opp.legs:
                side_tag = "[green]COMPRA[/green]" if leg.side == "COMPRA" else "[red]VENTA[/red]"
                bid_str = f"bid=${leg.bid}" if leg.bid is not None else ""
                ask_str = f"ask=${leg.ask}" if leg.ask is not None else ""
                price_str = f" | {bid_str} / {ask_str}" if bid_str or ask_str else ""
                yield Static(
                    f"  {side_tag} [bold]{leg.ticker}[/bold] "
                    f"x[bold]{leg.qty}[/bold] "
                    f"strike={leg.strike:.0f} {leg.right}"
                    f"{price_str}"
                )

            yield Static("", classes="sep")
            yield Static("[bold]KPIs[/bold]")
            kpi_lines = self._kpi_lines()
            for line in kpi_lines:
                yield Static(f"  {line}")

            yield Static("", classes="sep")
            hint = self._action_hint()
            yield Static(f"[bold]¿Qué hacer?[/bold]\n{hint}")

            yield Static("", classes="sep")
            yield Button("Cerrar", id="btn_close_detail", variant="primary")

    CSS = """
    DiscoveryDetailScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    DiscoveryDetailScreen > Vertical {
        width: 80;
        max-height: 90%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
        overflow-y: auto;
    }
    DiscoveryDetailScreen #detail_title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }
    DiscoveryDetailScreen .sep {
        height: 1;
    }
    DiscoveryDetailScreen Static {
        margin-bottom: 0;
    }
    DiscoveryDetailScreen Button {
        dock: bottom;
        width: 20;
        margin-top: 1;
    }
    """

    def _safe(self, v: Any, default: float = 0) -> float:
        if v is None:
            return default
        try:
            f = float(v)
            return default if math.isnan(f) else f
        except (ValueError, TypeError):
            return default

    def _kpi_lines(self) -> list[str]:
        m = self.opp.metrics
        if self.opp.strategy == "mariposa":
            return [
                f"Débito neto:   ${self._safe(m.get('net_debit')):.0f} (riesgo máximo)",
                f"Ganancia max:  ${self._safe(m.get('max_profit')):.0f}",
                f"Gap entre alas: {self._safe(m.get('gap')):.0f} puntos",
                f"Costo / width:  {self._safe(m.get('cost_pct_of_width')):.1f}%",
                f"Delta K2:       {self._safe(m.get('k2_delta')):.2f}",
                f"Prob éxito:     {self._safe(m.get('prob_success')):.0%}",
            ]
        if self.opp.strategy == "renta_ic":
            return [
                f"Crédito recibido:  ${self._safe(m.get('credit_received')):.0f}",
                f"Pérdida máxima:    ${self._safe(m.get('max_loss')):.0f}",
                f"Ancho calls:       {self._safe(m.get('call_width')):.0f}",
                f"Ancho puts:        {self._safe(m.get('put_width')):.0f}",
                f"Crédito / width:   {self._safe(m.get('credit_pct_of_width')):.1f}%",
                f"Prob éxito:        {self._safe(m.get('prob_success')):.0%}",
            ]
        if self.opp.strategy == "calendar":
            return [
                f"Costo:          ${self._safe(m.get('cost')):.0f}",
                f"DTE corto:      {m.get('short_dte', '?')} días",
                f"DTE largo:      {m.get('long_dte', '?')} días",
                f"Theta corto:    {self._safe(m.get('short_theta'))}",
                f"Theta largo:    {self._safe(m.get('long_theta'))}",
                f"Diferencia θ:   {self._safe(m.get('theta_diff'))}",
            ]
        if self.opp.strategy == "sintetico":
            return [
                f"Costo neto: ${self._safe(m.get('net_cost')):.0f}",
                f"Strike:     {self._safe(m.get('strike')):.0f}",
            ]
        return [f"{k}: {v}" for k, v in m.items()]

    def _action_hint(self) -> str:
        if self.opp.strategy == "mariposa":
            return (
                "Si querés operarla, ejecutá las 3 patas en orden:\n"
                "  arg-options place-order [K1_ticker] COMPRA 1 [ask_price]\n"
                "  arg-options place-order [K2_ticker] VENTA 2 [bid_price]\n"
                "  arg-options place-order [K3_ticker] COMPRA 1 [ask_price]\n"
                "El débito total no debe superar el estimado."
            )
        if self.opp.strategy == "renta_ic":
            return (
                "Ejecutá las 4 patas:\n"
                "  VENDER Call (strike alto)\n"
                "  COMPRAR Call (strike más alto, seguro)\n"
                "  VENDER Put (strike bajo)\n"
                "  COMPRAR Put (strike más bajo, seguro)\n"
                "El crédito neto es tu ingreso inicial."
            )
        if self.opp.strategy == "calendar":
            return (
                "VENDER la opción de corto plazo.\n"
                "COMPRAR la opción de largo plazo.\n"
                "Monitoreá la diferencia de Theta."
            )
        if self.opp.strategy == "sintetico":
            side = "Comprar Call + Vender Put" if self.opp.side == "compra" else "Vender Call + Comprar Put"
            tickers = ", ".join(l.ticker for l in self.opp.legs)
            return (
                f"{side}\n"
                f"Tickers: {tickers}\n"
                "Usar cuando buscás exposición direccional con menos capital."
            )
        return "Revisá los tickers y decidí si operar."

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_close_detail":
            self.app.pop_screen()


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

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
        Binding("d", "discover", "Descubrir"),
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
        self._discovery_opps: list[dscmod.Opportunity] = []
        self._discovery_mode = False
        self._discovery_cursor_idx: int | None = None

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
                yield DataTable(id="tbl", zebra_stripes=True, cursor_type="row")
                yield Static("", id="screen_status")
                yield Button("Ver detalle", id="btn_detail", variant="primary")
                yield RichLog(id="log", highlight=True, markup=True, max_lines=120)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#log", RichLog).write(
            "[bold green]arg-options[/bold green] — [dim]c chain · s screen · f form · d discover · j journal · a alerts · w auto · ? ayuda · q salir[/dim]"
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
        elif bid == "btn_detail":
            self._show_detail_for_cursor()

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

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if not self._discovery_mode:
            return
        try:
            self._discovery_cursor_idx = int(event.row_key.value)
        except (ValueError, AttributeError):
            self._discovery_cursor_idx = None

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if not self._discovery_mode:
            self._log("[dim]selección ignorada (no en modo discovery)[/dim]")
            return
        self._log(f"[dim]fila seleccionada: {event.row_key.value}[/dim]")
        self._show_detail_for_row(event.row_key.value)

    def _show_detail_for_cursor(self) -> None:
        if self._discovery_cursor_idx is not None and 0 <= self._discovery_cursor_idx < len(self._discovery_opps):
            self.push_screen(DiscoveryDetailScreen(self._discovery_opps[self._discovery_cursor_idx]))
        else:
            self._log("[yellow]Seleccioná una fila primero (click o flechas)[/yellow]")

    def _show_detail_for_row(self, row_key: object) -> None:
        try:
            idx = int(str(row_key))
            if 0 <= idx < len(self._discovery_opps):
                self.push_screen(DiscoveryDetailScreen(self._discovery_opps[idx]))
        except (ValueError, IndexError):
            pass


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
        self._discovery_mode = False
        self.query_one("#tbl_title", Static).update(title)
        _populate_data_table(self.query_one("#tbl", DataTable), df)

    def action_help(self) -> None:
        self._log(
            "[bold]Ayuda[/bold]\n"
            "• Guardá [bold]cadena[/bold] para persistir raíz+spot en settings YAML.\n"
            "• [bold]Screen (archivo)[/bold] usa el YAML guardado; [bold]Screen (form)[/bold] usa solo lo que ves (sin guardar).\n"
            "• [bold]Discover[/bold] escanea todas las estrategias y guarda en DB.\n"
            "• En resultados de discover, usá [bold]Ver detalle[/bold] o Enter para ver la explicación completa.\n"
            "• Teclas: c chain · s screen · f form · d discover · j journal · a alerts · l login · w auto · ? ayuda · q salir."
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

    def action_discover(self) -> None:
        self.run_discover_worker()

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


    @work(thread=True, exclusive=True, name="discover")
    def run_discover_worker(self) -> None:
        self._from_thread(lambda: self._log("[dim]descubriendo oportunidades…[/dim]"))
        try:
            s = load_settings()
            engine = dscmod.DiscoveryEngine(s)
            try:
                opps = engine.run()
            except Exception as inner:
                self._from_thread(lambda err=inner: self._log(f"[red]engine.run:[/red] {err}"))
                return

            if not opps:
                self.call_from_thread(lambda: self._log("[yellow]descubrimiento: sin oportunidades[/yellow]"))
                return

            def show() -> None:
                try:
                    self._log(f"[green]descubrimiento OK[/green] — {len(opps)} oportunidades")
                    self._set_discovery_results(opps)
                except Exception as e:
                    self._log(f"[red]error mostrando discovery:[/red] {e}")

            self.call_from_thread(show)
        except Exception as e:
            tb = traceback.format_exc()
            self._from_thread(lambda err=e, tb=tb: self._log(f"[red]descubrimiento:[/red] {err}\n{tb}"))

    @staticmethod
    def _safe(v: Any, default: float = 0) -> float:
        if v is None:
            return default
        try:
            f = float(v)
            return default if math.isnan(f) else f
        except (ValueError, TypeError):
            return default

    def _discovery_summary(self, strategy: str, meta: dict) -> str:
        if strategy == "mariposa":
            return (
                f"K={self._safe(meta.get('k2_delta')):.2f}D "
                f"Debit=${self._safe(meta.get('net_debit')):.0f} "
                f"MaxP=${self._safe(meta.get('max_profit')):.0f}"
            )
        if strategy == "renta_ic":
            return (
                f"Credit=${self._safe(meta.get('credit_received')):.0f} "
                f"Width={self._safe(meta.get('call_width')):.0f}"
            )
        if strategy == "calendar":
            return (
                f"S-DTE={meta.get('short_dte', '?')} "
                f"L-DTE={meta.get('long_dte', '?')} "
                f"Costo=${self._safe(meta.get('cost')):.0f}"
            )
        if strategy == "sintetico":
            return f"Costo=${self._safe(meta.get('net_cost')):.0f} K={self._safe(meta.get('strike')):.0f}"
        return str(meta)

    def _set_discovery_results(self, opps: list[dscmod.Opportunity]) -> None:
        self._discovery_opps = opps
        self._discovery_mode = True
        table = self.query_one("#tbl", DataTable)
        table.clear(columns=True)
        table.add_column("Root", key="d_root", width=6)
        table.add_column("Estrategia", key="d_strat", width=14)
        table.add_column("Conf", key="d_conf", width=5)
        table.add_column("Side", key="d_side", width=8)
        table.add_column("Estructura", key="d_struct", width=48)
        table.add_column("KPIs", key="d_kpis", width=40)

        for i, opp in enumerate(sorted(opps, key=lambda o: o.confidence, reverse=True)):
            label = dscmod.STRATEGY_LABELS.get(opp.strategy, opp.strategy)
            side_label = dscmod.SIDE_LABELS.get(opp.side, opp.side)
            tickers = ", ".join(f"{l.ticker}" for l in opp.legs)
            summary = self._discovery_summary(opp.strategy, opp.metrics)
            table.add_row(opp.root, label, f"{opp.confidence:.0f}", side_label, tickers, summary, key=str(i))

        text = f"[bold]Discovery[/bold] · {len(opps)} oportunidades · click en fila para detalle"
        self.query_one("#tbl_title", Static).update(text)
        self._update_status(f"Discovery: {len(opps)} oportunidades", "green")

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
