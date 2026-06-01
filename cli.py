#!/usr/bin/env python3
"""
Binance Futures Testnet Trading Bot — CLI Entry Point

Usage examples
--------------
  python cli.py place --symbol BTCUSDT --side BUY  --type MARKET     --quantity 0.001
  python cli.py place --symbol BTCUSDT --side SELL --type LIMIT       --quantity 0.001 --price 65000
  python cli.py place --symbol BTCUSDT --side BUY  --type STOP_LIMIT  --quantity 0.001 --price 64000 --stop-price 64500
  python cli.py interactive
"""

import logging
import os
import sys
from typing import Optional

import typer
from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from bot import setup_logging
from bot.client import BinanceAPIError, BinanceFuturesClient, NetworkError
from bot.orders import place_order
from bot.validators import ValidationError

# --------------------------------------------------------------------------
# Bootstrap
# --------------------------------------------------------------------------

load_dotenv()
setup_logging()
logger = logging.getLogger("trading_bot.cli")

app = typer.Typer(
    name="trading-bot",
    help="Place orders on Binance Futures Testnet (USDT-M).",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()

BANNER = "[bold blue]Binance Futures Testnet — Trading Bot[/bold blue]"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _build_client() -> BinanceFuturesClient:
    """Read credentials from env and return a configured client."""
    api_key = os.getenv("BINANCE_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_API_SECRET", "").strip()
    if not api_key or not api_secret:
        console.print(
            "[bold red]Error:[/bold red] BINANCE_API_KEY and BINANCE_API_SECRET "
            "must be set.\n"
            "Copy [cyan].env.example[/cyan] to [cyan].env[/cyan] and fill in your credentials."
        )
        raise typer.Exit(code=1)
    return BinanceFuturesClient(api_key=api_key, api_secret=api_secret)


def _print_request_summary(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: Optional[float] = None,
    stop_price: Optional[float] = None,
) -> None:
    table = Table(title="Order Request", box=box.ROUNDED, show_header=False, min_width=42)
    table.add_column("Field", style="cyan", width=14)
    table.add_column("Value", style="white")

    side_styled = f"[green]{side}[/green]" if side.upper() == "BUY" else f"[red]{side}[/red]"

    table.add_row("Symbol",     symbol.upper())
    table.add_row("Side",       side_styled)
    table.add_row("Type",       order_type.upper())
    table.add_row("Quantity",   str(quantity))
    if price is not None:
        table.add_row("Price",  str(price))
    if stop_price is not None:
        table.add_row("Stop Price", str(stop_price))
    console.print(table)


def _print_order_result(result: dict) -> None:
    table = Table(title="Order Response", box=box.ROUNDED, show_header=False, min_width=42)
    table.add_column("Field", style="cyan", width=14)
    table.add_column("Value", style="white")

    display_fields = [
        "orderId", "symbol", "side", "type", "status",
        "origQty", "executedQty", "avgPrice", "price",
        "stopPrice", "timeInForce", "updateTime",
    ]
    for field in display_fields:
        value = result.get(field)
        # Skip None, empty string, and uninformative "0" / "0.000" placeholders
        # for fields like avgPrice on a NEW limit order.
        if value is None or value == "":
            continue
        table.add_row(field, str(value))

    console.print(table)


def _run_place_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: Optional[float],
    stop_price: Optional[float],
) -> bool:
    """
    Core order placement with unified error handling.
    Returns True on success, False on failure.
    """
    try:
        result = place_order(
            client=client,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
        )
        console.print("\n[bold green]✓  Order placed successfully![/bold green]\n")
        _print_order_result(result)
        return True

    except ValidationError as exc:
        logger.warning("Validation error: %s", exc)
        console.print(f"\n[bold red]✗  Validation error:[/bold red] {exc}")

    except BinanceAPIError as exc:
        logger.error("Binance API error [%s]: %s", exc.code, exc.msg)
        console.print(
            f"\n[bold red]✗  Binance API error [{exc.code}]:[/bold red] {exc.msg}"
        )

    except NetworkError as exc:
        logger.error("Network error: %s", exc)
        console.print(f"\n[bold red]✗  Network error:[/bold red] {exc}")

    return False


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

@app.command()
def place(
    symbol: str = typer.Option(..., "--symbol", "-s", help="Trading pair, e.g. BTCUSDT"),
    side: str = typer.Option(..., "--side", help="BUY or SELL"),
    order_type: str = typer.Option(..., "--type", "-t", help="MARKET | LIMIT | STOP_LIMIT"),
    quantity: float = typer.Option(..., "--quantity", "-q", help="Number of contracts"),
    price: Optional[float] = typer.Option(None, "--price", "-p", help="Limit/stop-limit price"),
    stop_price: Optional[float] = typer.Option(None, "--stop-price", help="Trigger price for STOP_LIMIT"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate order without hitting the API"),   # <-- add this
):
    console.print(Panel(BANNER, expand=False))

    if dry_run:
        console.print("[yellow bold]⚠  DRY RUN — no real order will be placed[/yellow bold]\n")

    _print_request_summary(symbol, side, order_type, quantity, price, stop_price)

    client = _build_client()
    try:
        result = place_order(
            client=client,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            dry_run=dry_run,        # <-- pass it through
        )
        label = "Order Placed" if dry_run else "Order placed successfully!"
        console.print(f"\n[bold green]✓  {label}[/bold green]\n")
        _print_order_result(result)

    except ValidationError as exc:
        console.print(f"\n[bold red]✗  Validation error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    except BinanceAPIError as exc:
        console.print(f"\n[bold red]✗  Binance API error [{exc.code}]:[/bold red] {exc.msg}")
        raise typer.Exit(code=1)
    except NetworkError as exc:
        console.print(f"\n[bold red]✗  Network error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    finally:
        client.close()

@app.command()
def interactive() -> None:
    """
    [Bonus] Menu-driven interactive order placement session.

    Prompts for all fields, shows a confirmation before submitting,
    and loops until you choose to quit.
    """
    console.print(Panel(f"{BANNER} — [italic]Interactive Mode[/italic]", expand=False))

    client = _build_client()

    ORDER_TYPE_MAP = {"1": "MARKET", "2": "LIMIT", "3": "STOP_LIMIT"}

    try:
        while True:
            console.print("\n[bold cyan]Select order type:[/bold cyan]")
            console.print("  [1]  Market Order")
            console.print("  [2]  Limit Order")
            console.print("  [3]  Stop-Limit Order  [yellow](bonus)[/yellow]")
            console.print("  [q]  Quit")

            choice = typer.prompt("\nEnter choice", default="q").strip().lower()

            if choice == "q":
                console.print("\n[yellow]Session ended. Goodbye![/yellow]")
                break

            if choice not in ORDER_TYPE_MAP:
                console.print("[red]Invalid choice — enter 1, 2, 3, or q.[/red]")
                continue

            order_type = ORDER_TYPE_MAP[choice]

            # --- Collect inputs with inline validation feedback ---
            symbol = _prompt_validated(
                "Symbol (e.g. BTCUSDT)", str,
                lambda v: v.strip().upper() if v.strip().isalnum() and v.strip()
                          else (_ for _ in ()).throw(ValueError("Must be alphanumeric")),
            )
            side = _prompt_validated(
                "Side (BUY / SELL)", str,
                lambda v: v.strip().upper() if v.strip().upper() in {"BUY", "SELL"}
                          else (_ for _ in ()).throw(ValueError("Must be BUY or SELL")),
            )
            quantity = _prompt_validated(
                "Quantity", float,
                lambda v: v if v > 0 else (_ for _ in ()).throw(ValueError("Must be > 0")),
            )

            price: Optional[float] = None
            stop_price: Optional[float] = None

            if order_type in ("LIMIT", "STOP_LIMIT"):
                price = _prompt_validated(
                    "Limit price", float,
                    lambda v: v if v > 0 else (_ for _ in ()).throw(ValueError("Must be > 0")),
                )

            if order_type == "STOP_LIMIT":
                stop_price = _prompt_validated(
                    "Stop / trigger price", float,
                    lambda v: v if v > 0 else (_ for _ in ()).throw(ValueError("Must be > 0")),
                )

            # --- Show summary and confirm ---
            console.print()
            _print_request_summary(symbol, side, order_type, quantity, price, stop_price)
            if not typer.confirm("\nSubmit order?"):
                console.print("[yellow]Cancelled.[/yellow]")
                continue

            _run_place_order(client, symbol, side, order_type, quantity, price, stop_price)

    finally:
        client.close()


# --------------------------------------------------------------------------
# Internal prompt helper (used only in interactive mode)
# --------------------------------------------------------------------------

def _prompt_validated(label: str, cast, validator):
    """Loop until the user enters a valid value."""
    while True:
        raw = typer.prompt(label)
        try:
            value = cast(raw)
            return validator(value)
        except (ValueError, TypeError) as exc:
            console.print(f"  [red]Invalid input:[/red] {exc}")


# --------------------------------------------------------------------------
# Entry-point
# --------------------------------------------------------------------------

if __name__ == "__main__":
    app()
