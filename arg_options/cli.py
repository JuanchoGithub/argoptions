"""App de terminal: cadena, pantalla, diario, alertas, órdenes (Typer + Rich)."""

from __future__ import annotations

import json
import logging
import math
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Any, Annotated, Optional

import typer
from rich.console import Console
from rich.json import JSON
from rich.table import Table

from arg_options import chain as chainmod
from arg_options import db as dbmod
from arg_options import discovery as dscmod
from arg_options import journal as journalmod
from arg_options import orders as ordersmod
from arg_options import screen as screenmod
from arg_options.alerts import run_alerts_once
from arg_options.ppi_client import connect_ppi, ping_readonly
from arg_options.settings import load_settings

console = Console(stderr=False)
err = Console(stderr=True)

app = typer.Typer(
    name="arg-options",
    help="Opciones BYMA vía PPI: cadena, Greeks, screening, diario, alertas y órdenes.",
    rich_markup_mode="rich",
    no_args_is_help=True,
    add_completion=False,
)


@app.command("login-test")
def login_test() -> None:
    """Verifica credenciales PPI y muestra tipos de instrumento y mercados."""
    s = load_settings()
    try:
        ppi = connect_ppi(s)
    except Exception as e:
        if "Credenciales" in str(e) or "invalid" in str(e).lower():
            err.print(
                "[red]PPI rechazó el login (credenciales).[/red]\n"
                "Revisá en .env: [bold]PPI_API_KEY[/bold] y [bold]PPI_API_SECRET[/bold] "
                "(sin comillas extra ni espacios al pegar).\n"
                "Si generaste claves en [bold]PRODUCCIÓN[/bold], poné [bold]PPI_SANDBOX=false[/bold].\n"
                "Si usás sandbox, las claves deben ser las del entorno de pruebas de PPI.\n"
                f"Detalle: {e}"
            )
            raise typer.Exit(code=1) from e
        raise
    out = ping_readonly(ppi, s.ppi_account_number)
    small = {k: out[k] for k in out if k != "accounts"}
    console.print(JSON(json.dumps(small, default=str)))
    if "accounts" in out:
        console.print("\n[bold]Cuentas[/bold]")
        console.print(JSON(json.dumps(out["accounts"], default=str)))


@app.command()
def chain(
    parquet: Annotated[
        bool,
        typer.Option("--parquet", help="Exportar también a Parquet si está definido en settings.yaml"),
    ] = False,
) -> None:
    """Descarga la cadena configurada (option_roots) y guarda un snapshot en SQLite."""
    s = load_settings()
    ppi = connect_ppi(s)
    rows = chainmod.build_full_chain(ppi, s)
    n, ts = chainmod.persist_chain(rows, s, export_parquet=parquet)
    console.print(f"[green]Guardados[/green] {n} filas en snapshot [cyan]{ts}[/cyan]")


def _screen_display_columns() -> list[str]:
    return [
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
        "description",
    ]


@app.command()
def screen(
    screening: Annotated[
        Optional[Path],
        typer.Option("--screening", help="Ruta al YAML de reglas (default: config/screening.yaml)"),
    ] = None,
    out_csv: Annotated[
        Optional[Path],
        typer.Option("--out-csv", help="Exportar resultado a CSV"),
    ] = None,
    out_json: Annotated[
        Optional[Path],
        typer.Option("--out-json", help="Exportar resultado a JSON"),
    ] = None,
    rows: Annotated[int, typer.Option("--rows", "-n", help="Máximo de filas a mostrar en la tabla")] = 50,
    plain: Annotated[bool, typer.Option("--plain", help="Salida texto plano en lugar de tabla Rich")] = False,
) -> None:
    """Aplica screening al último snapshot guardado con [bold]chain[/bold]."""
    s = load_settings()
    sp = screening
    df = screenmod.run_screen(
        s,
        screening_path=sp,
        out_csv=out_csv,
        out_json=out_json,
    )
    if df.empty:
        console.print("[yellow]Sin filas[/yellow] (no hay snapshot o el screening descartó todo).")
        raise typer.Exit(code=0)
    if plain:
        console.print(df.head(rows).to_string())
    else:
        cols = [c for c in _screen_display_columns() if c in df.columns]
        if not cols:
            cols = list(df.columns)
        sub = df[cols].head(rows)
        table = Table(show_header=True, header_style="bold", show_lines=False)
        for c in sub.columns:
            table.add_column(str(c), overflow="ellipsis", max_width=28 if c == "description" else 14)
        for _, row in sub.iterrows():
            table.add_row(*["" if v is None or (isinstance(v, float) and str(v) == "nan") else str(v) for v in row])
        console.print(table)
    console.print(f"\n[dim]Total filas: {len(df)}[/dim]")


@app.command()
def discover(
    discovery_rules: Annotated[
        Optional[Path],
        typer.Option("--rules", help="Ruta al YAML de reglas de discovery"),
    ] = None,
    min_confidence: Annotated[
        int,
        typer.Option("--min-conf", "-c", help="Confianza mínima para mostrar (0-100)"),
    ] = 0,
    show_history: Annotated[
        bool,
        typer.Option("--history", help="Mostrar historial de la DB en vez de escanear"),
    ] = False,
    root_filter: Annotated[
        Optional[str],
        typer.Option("--root", "-r", help="Filtrar por raíz de opción (ej. GFG)"),
    ] = None,
    plain: Annotated[
        bool,
        typer.Option("--plain", help="Salida texto plano en lugar de tabla Rich"),
    ] = False,
) -> None:
    """Escanea la cadena y descubre oportunidades para TODAS las estrategias.

    Analiza Mariposa, Iron Condor, Calendar y Sintéticos sobre el último snapshot.
    Guarda resultados en la DB para análisis histórico.
    """
    s = load_settings()
    rules_path = discovery_rules
    if show_history:
        conn = dbmod.connect(s.db_path())
        try:
            rows = dbmod.load_latest_discovery(
                conn, root=root_filter, limit=200
            )
        finally:
            conn.close()
        if not rows:
            console.print("[yellow]Sin historial de discovery.[/yellow]")
            raise typer.Exit(code=0)
        if plain:
            for r in rows:
                console.print(
                    f"{r['ts'][:19]} | {r['strategy']:12s} | {r['root']:5s} "
                    f"| conf {r['confidence_score']:3.0f} | {r.get('metrics_json','')[:120]}"
                )
        else:
            table = Table(show_header=True, header_style="bold")
            table.add_column("Tiempo", width=20)
            table.add_column("Estrategia", width=14)
            table.add_column("Root", width=6)
            table.add_column("Conf", width=5)
            table.add_column("Side", width=8)
            table.add_column("Resumen", width=80)
            for r in rows:
                meta = json.loads(r.get("metrics_json", "{}"))
                summary = _summarize_metrics(r["strategy"], meta)
                table.add_row(
                    r["ts"][:19],
                    dscmod.STRATEGY_LABELS.get(r["strategy"], r["strategy"]),
                    r["root"],
                    f"{r['confidence_score']:.0f}",
                    dscmod.SIDE_LABELS.get(r.get("side", ""), r.get("side", "")),
                    summary,
                )
            console.print(table)
        return

    engine = dscmod.DiscoveryEngine(s, rules_path=rules_path)
    opps = engine.run()

    if not opps:
        console.print("[yellow]Discovery: sin oportunidades encontradas.[/yellow]")
        raise typer.Exit(code=0)

    filtered = [o for o in opps if o.confidence >= min_confidence]
    if not filtered:
        console.print(
            f"[yellow]Discovery: {len(opps)} encontradas, "
            f"ninguna supera confianza mínima {min_confidence}.[/yellow]"
        )
        raise typer.Exit(code=0)

    if root_filter:
        filtered = [o for o in filtered if o.root.upper() == root_filter.upper()]

    _render_discoveries(filtered, console, plain)
    console.print(f"\n[dim]Total oportunidades: {len(opps)} | mostradas: {len(filtered)}[/dim]")


def _safe_metric(v: Any, default: float = 0) -> float:
    if v is None:
        return default
    try:
        f = float(v)
        return default if math.isnan(f) else f
    except (ValueError, TypeError):
        return default


def _summarize_metrics(strategy: str, meta: dict) -> str:
    if strategy == "mariposa":
        return (
            f"K={_safe_metric(meta.get('k2_delta')):.2f}D "
            f"Debit=${_safe_metric(meta.get('net_debit')):.0f} "
            f"MaxP=${_safe_metric(meta.get('max_profit')):.0f} "
            f"P={_safe_metric(meta.get('prob_success')):.0%}"
        )
    if strategy == "renta_ic":
        return (
            f"Credit=${_safe_metric(meta.get('credit_received')):.0f} "
            f"Width={_safe_metric(meta.get('call_width')):.0f} "
            f"MaxL=${_safe_metric(meta.get('max_loss')):.0f} "
            f"P={_safe_metric(meta.get('prob_success')):.0%}"
        )
    if strategy == "calendar":
        return (
            f"S-DTE={meta.get('short_dte', '?')} "
            f"L-DTE={meta.get('long_dte', '?')} "
            f"Costo=${_safe_metric(meta.get('cost')):.0f}"
        )
    if strategy == "sintetico":
        return f"Costo=${_safe_metric(meta.get('net_cost')):.0f} K={_safe_metric(meta.get('strike')):.0f}"
    return str(meta)


def _render_discoveries(opps: list[dscmod.Opportunity], console: Console, plain: bool) -> None:
    by_root: dict[str, list[dscmod.Opportunity]] = {}
    for o in opps:
        by_root.setdefault(o.root, []).append(o)

    for root in sorted(by_root):
        if plain:
            console.print(f"── {root} ──")
            for o in by_root[root]:
                label = dscmod.STRATEGY_LABELS.get(o.strategy, o.strategy)
                tickers = ", ".join(f"{l.ticker} {l.side} x{l.qty}" for l in o.legs)
                console.print(f"  [{label:14s}] ({o.confidence:.0f}) {tickers}")
                console.print(f"    {_summarize_metrics(o.strategy, o.metrics)}")
        else:
            table = Table(
                show_header=True,
                header_style="bold",
                title=f"🚀 {root}",
                title_style="bold cyan",
            )
            table.add_column("Estrategia", width=14, no_wrap=True)
            table.add_column("Conf", width=5)
            table.add_column("Side", width=8)
            table.add_column("Estructura", width=50)
            table.add_column("KPIs", width=45)

            for o in by_root[root]:
                label = dscmod.STRATEGY_LABELS.get(o.strategy, o.strategy)
                side_label = dscmod.SIDE_LABELS.get(o.side, o.side)
                tickers = ", ".join(f"{l.ticker}" for l in o.legs)
                summary = _summarize_metrics(o.strategy, o.metrics)

                conf_color = "green" if o.confidence >= 70 else "yellow" if o.confidence >= 40 else "red"
                table.add_row(
                    label,
                    f"[{conf_color}]{o.confidence:.0f}[/{conf_color}]",
                    side_label,
                    tickers,
                    summary,
                )

            console.print(table)


@app.command("journal-sync")
def journal_sync() -> None:
    """Sincroniza posiciones y órdenes desde PPI al SQLite local."""
    s = load_settings()
    ppi = connect_ppi(s)
    summary = journalmod.sync_journal(ppi, s)
    console.print("[bold]Sync[/bold]")
    console.print(JSON(json.dumps(summary, indent=2, default=str)))
    pnl = journalmod.summarize_pnl_proxy(s)
    console.print("\n[bold]Resumen valorizado (proxy)[/bold]")
    console.print(JSON(json.dumps(pnl, indent=2, default=str)))


@app.command("alerts-once")
def alerts_once(
    screening: Annotated[
        Optional[Path],
        typer.Option("--screening", help="YAML con bloque alerts (y reglas)"),
    ] = None,
) -> None:
    """Evalúa alertas una vez (vencimiento cercano, etc.) y envía si corresponde."""
    s = load_settings()
    sent = run_alerts_once(s, screening_path=screening)
    for m in sent:
        console.print(m)


@app.command("place-order")
def place_order_cmd(
    ticker: Annotated[str, typer.Argument(help="Ticker de la opción, ej. GFGC6200MY")],
    side: Annotated[str, typer.Argument(help="COMPRA o VENTA")],
    quantity: Annotated[int, typer.Argument(help="Cantidad de contratos")],
    price: Annotated[float, typer.Argument(help="Precio límite de la prima (por unidad / convención PPI)")],
    settlement: Annotated[str, typer.Option("--settlement", help="Plazo de liquidación")] = "A-48HS",
    send_live: Annotated[
        bool,
        typer.Option(
            "--send-live",
            help="Enviar orden real (requiere ALLOW_LIVE_ORDERS=true). Sin este flag solo simula.",
        ),
    ] = False,
) -> None:
    """Coloca orden límite. Por defecto [yellow]dry-run[/yellow] (no confirma en PPI)."""
    side_u = side.upper()
    if side_u not in ("COMPRA", "VENTA"):
        err.print("[red]side debe ser COMPRA o VENTA[/red]")
        raise typer.Exit(code=1)
    s = load_settings()
    ppi = connect_ppi(s)
    req = ordersmod.LimitOrderRequest(
        ticker=ticker.upper(),
        side=side_u,
        quantity=quantity,
        limit_price=price,
        settlement=settlement,
    )
    res = ordersmod.place_limit_order(ppi, s, req, dry_run=not send_live)
    console.print(JSON(json.dumps(res, indent=2, default=str)))


@app.command()
def interactive(
    watch: Annotated[
        Optional[int],
        typer.Option(
            "--watch",
            "-w",
            help="Segundos entre cada chain automático al abrir (ej. 300). Sin esto: manual; tecla w usa 300s por defecto.",
        ),
    ] = None,
) -> None:
    """Abre la app interactiva en la terminal (queda abierta; teclas c/s/j/a/l/w/?/q)."""
    from arg_options.tui_app import run_interactive

    interval = float(watch) if watch is not None and watch > 0 else None
    run_interactive(watch_interval_s=interval)


@app.command()
def version() -> None:
    """Muestra la versión instalada del paquete."""
    try:
        console.print(pkg_version("arg-options"))
    except Exception:
        from arg_options import __version__

        console.print(__version__)


def main() -> None:
    """Punto de entrada para `python -m arg_options` y scripts."""
    app()


if __name__ == "__main__":
    main()
