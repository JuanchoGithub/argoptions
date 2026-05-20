from __future__ import annotations

import typer

app = typer.Typer(help="argoptions — BYMA options trading via PPI")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    prod: bool = typer.Option(False, "--prod", help="Run in production mode"),
    watch: float = typer.Option(
        0.0, "--watch", help="Auto-refresh interval in seconds"
    ),
) -> None:
    """Launch the TUI. Defaults to test (sandbox) mode."""
    if ctx.invoked_subcommand is not None:
        return
    mode = "production" if prod else "test"
    from arg_options.ui.tui_app import ArgOptionsApp

    tui = ArgOptionsApp(mode=mode, watch_interval_s=watch if watch > 0 else None)
    tui.run()


@app.command()
def chain(
    prod: bool = typer.Option(False, "--prod"),
) -> None:
    """Build option chain and save to parquet."""
    from arg_options.config.settings import load_settings
    from arg_options.broker import create_broker
    from arg_options.core.chain import build_full_chain, persist_chain

    mode = "production" if prod else "test"
    config = load_settings(mode)
    broker = create_broker(config)
    broker.connect()
    rows = build_full_chain(broker, config)
    count, ts = persist_chain(rows, config)
    print(f"Chain saved: {count} rows at {ts}")


@app.command()
def screen(
    prod: bool = typer.Option(False, "--prod"),
    stored: bool = typer.Option(False, "--stored", help="Use latest stored chain data instead of live API"),
) -> None:
    """Run screening with saved config."""
    from arg_options.services.screening_service import ScreeningService
    
    mode = "production" if prod else "test"
    service = ScreeningService(mode=mode, use_stored=stored)
    df = service.run_screening()
    stats = service.get_screening_stats(df)
    
    print(f"Screen results: {stats['total_rows']} rows")
    if not df.empty:
        print(df.to_string())


@app.command()
def status(
    prod: bool = typer.Option(False, "--prod"),
) -> None:
    """Show account status, positions, balances."""
    from arg_options.config.settings import load_settings
    from arg_options.broker import create_broker

    mode = "production" if prod else "test"
    config = load_settings(mode)
    broker = create_broker(config)
    broker.connect()
    accounts = broker.account.get_accounts()
    for acc in accounts:
        print(f"Account: {acc.account_number} - {acc.name}")
        balances = broker.account.get_available_balance(acc.account_number)
        for b in balances:
            print(f"  {b.name}: {b.symbol} {b.amount} ({b.settlement})")


@app.command()
def orders(
    prod: bool = typer.Option(False, "--prod"),
) -> None:
    """Show active orders."""
    from arg_options.config.settings import load_settings
    from arg_options.broker import create_broker

    mode = "production" if prod else "test"
    config = load_settings(mode)
    broker = create_broker(config)
    broker.connect()
    active = broker.orders.get_active_orders(config.account_number)
    if not active:
        print("No active orders")
        return
    for o in active:
        print(
            f"#{o.id} {o.ticker} {o.operation} qty={o.quantity} "
            f"price={o.price} status={o.status}"
        )


@app.command()
def chain(
    prod: bool = typer.Option(False, "--prod"),
) -> None:
    """Build option chain and save to parquet."""
    from arg_options.services.chain_service import ChainService
    
    mode = "production" if prod else "test"
    service = ChainService(mode=mode)
    count, ts = service.build_and_save_chain()
    print(f"Chain saved: {count} rows at {ts}")


@app.command()
def screen(
    prod: bool = typer.Option(False, "--prod"),
    stored: bool = typer.Option(False, "--stored", help="Use latest stored chain data instead of live API"),
) -> None:
    """Run screening with saved config."""
    from arg_options.services.screening_service import ScreeningService
    
    mode = "production" if prod else "test"
    service = ScreeningService(mode=mode, use_stored=stored)
    df = service.run_screening()
    stats = service.get_screening_stats(df)
    
    print(f"Screen results: {stats['total_rows']} rows")
    if not df.empty:
        print(df.to_string())


@app.command()
def status(
    prod: bool = typer.Option(False, "--prod"),
) -> None:
    """Show account status, positions, balances."""
    from arg_options.services.account_service import AccountService
    
    mode = "production" if prod else "test"
    service = AccountService(mode=mode)
    results = service.get_account_status()
    for res in results:
        acc = res["account"]
        print(f"Account: {acc.account_number} - {acc.name}")
        for balance in res["balances"]:
            print(f"  {balance.name}: {balance.symbol} {balance.amount} ({balance.settlement})")


@app.command()
def orders(
    prod: bool = typer.Option(False, "--prod"),
) -> None:
    """Show active orders."""
    from arg_options.services.account_service import AccountService
    
    mode = "production" if prod else "test"
    service = AccountService(mode=mode)
    active = service.get_active_orders()
    if not active:
        print("No active orders")
        return
    for o in active:
        print(
            f"#{o.id} {o.ticker} {o.operation} qty={o.quantity} "
            f"price={o.price} status={o.status}"
        )


@app.command()
def journal(
    prod: bool = typer.Option(False, "--prod"),
) -> None:
    """Sync and show journal / P&L."""
    from arg_options.services.journal_service import JournalService
    
    mode = "production" if prod else "test"
    service = JournalService(mode=mode)
    summary = service.sync_and_summarize()
    print(summary)


@app.command()
def cancel(
    order_id: int = typer.Argument(
        None, help="Order ID to cancel (omit for mass cancel)"
    ),
    all: bool = typer.Option(False, "--all", help="Cancel all active orders"),
    prod: bool = typer.Option(False, "--prod"),
) -> None:
    """Cancel an order or all orders."""
    from arg_options.services.account_service import AccountService
    
    mode = "production" if prod else "test"
    service = AccountService(mode=mode)
    result = service.cancel_orders(order_id=order_id, all_orders=all)
    print(result)


@app.command()
def run(
    prod: bool = typer.Option(False, "--prod"),
    once: bool = typer.Option(False, "--once", help="Run one cycle then exit"),
) -> None:
    """Run the automation engine."""
    from arg_options.engine.scheduler import TradingEngine, run_once

    mode = "production" if prod else "test"
    if once:
        run_once(mode)
    else:
        engine = TradingEngine(mode)
        try:
            engine.start()
        except KeyboardInterrupt:
            engine.stop()
            print("\nEngine stopped")


if __name__ == "__main__":
    app()
