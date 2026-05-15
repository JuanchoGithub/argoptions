"""App de terminal: cadena, pantalla, diario, alertas, órdenes (Typer + Rich)."""

from __future__ import annotations

import json
import logging
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.json import JSON
from rich.table import Table

from arg_options import chain as chainmod
from arg_options import journal as journalmod
from arg_options import orders as ordersmod
from arg_options import screen as screenmod
from arg_options.alerts import run_alerts_once
from arg_options.ppi_client import connect_ppi, ping_readonly
from arg_options.settings import load_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

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
