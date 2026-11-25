"""
Screener orchestrator — ties all Level 1 modules together.

Usage (from project root with venv active):

    python -m bursa_screener
    python -m bursa_screener --tier broad
    python -m bursa_screener --tier broad --show-rejected
    python -m bursa_screener --tickers 1155.KL 5347.KL 1023.KL
    python -m bursa_screener --no-cache  # bypass cache
    python -m bursa_screener --clear-cache  # clear all cached data
    python -m bursa_screener --check  # check Yahoo Finance connectivity
    python -m bursa_screener --cache-stats  # show cache statistics

Or via CLI entry point:
    be-richer --tier broad
    bursa-screener --tier klci
"""

from __future__ import annotations

import argparse
import time

from rich.console import Console

from .data_fetcher import batch_fetch, clear_cache, check_yahoo_connectivity, get_cache_stats
from .fundamentals import score_fundamentals
from .ranker import build_results
from .reporter import print_all
from .technicals import score_technicals
from .universe import get_universe

console = Console()


def run(
    tier: str = "klci",
    tickers: list[str] | None = None,
    show_rejected: bool = False,
    export: bool = True,
    refresh_universe: bool = False,
    use_cache: bool = True,
    skip_connectivity_check: bool = False,
) -> None:
    universe = tickers if tickers else get_universe(tier, force_refresh=refresh_universe)

    cache_status = "[green]cache enabled[/green]" if use_cache else "[yellow]cache disabled[/yellow]"
    console.print(
        f"\n[bold blue]🔍 Bursa Malaysia Level 1 Screener[/bold blue]  "
        f"({len(universe)} tickers, tier={tier if not tickers else 'custom'}, {cache_status})\n"
    )

    # Quick connectivity check (unless using cache only)
    if not skip_connectivity_check:
        console.print("[dim]Checking Yahoo Finance connectivity…[/dim]")
        conn = check_yahoo_connectivity()
        if conn["rate_limited"]:
            console.print(f"[bold yellow]⚠ {conn['message']}[/bold yellow]")
            console.print("[yellow]Will attempt to use cached data where available.[/yellow]\n")
        elif not conn["ok"]:
            console.print(f"[yellow]⚠ {conn['message']}[/yellow]\n")
        else:
            console.print(f"[green]✓ {conn['message']}[/green]\n")

    start = time.time()

    # ── Step 1: fetch data ────────────────────────────────────────────────────
    console.print("[dim]Fetching price history and fundamentals…[/dim]")
    console.print("[dim](This may take a while due to Yahoo Finance rate limits)[/dim]")
    raw_data = batch_fetch(universe, period="6mo", throttle=0.5, use_cache=use_cache)

    # Count successful fetches
    price_success = sum(1 for d in raw_data.values() if d["price_df"] is not None)
    fund_success = sum(1 for d in raw_data.values() if d["fundamentals"].get("price") is not None)
    console.print(f"[dim]Fetched: {price_success}/{len(universe)} prices, {fund_success}/{len(universe)} fundamentals[/dim]")
    
    if price_success == 0 and fund_success == 0:
        console.print(
            "\n[bold red]⚠ No data fetched![/bold red] "
            "Yahoo Finance may be rate-limiting your IP.\n"
            "Options:\n"
            "  1. Wait 15-30 minutes and try again\n"
            "  2. Run from a different network/IP\n"
            "  3. If you have cached data, it will be used automatically\n"
        )

    # ── Step 2: score each stock ──────────────────────────────────────────────
    console.print("[dim]Scoring technicals and fundamentals…[/dim]")
    fund_scores = {}
    tech_scores = {}

    for ticker, data in raw_data.items():
        fund_scores[ticker] = score_fundamentals(ticker, data["fundamentals"])
        tech_scores[ticker] = score_technicals(ticker, data["price_df"])

    # ── Step 3: rank and classify ─────────────────────────────────────────────
    results = build_results(raw_data, fund_scores, tech_scores)

    elapsed = time.time() - start

    # ── Step 4: report ────────────────────────────────────────────────────────
    print_all(results, len(universe), elapsed, show_rejected=show_rejected, export=export)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Be Richer - Bursa Malaysia Level 1 Stock Screener",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  be-richer
  be-richer --tier broad
  be-richer --tickers 1155.KL 5347.KL 4715.KL
  be-richer --tier broad --show-rejected --no-export
  be-richer --refresh-universe
  be-richer --no-cache  # bypass cache (always fetch fresh)
  be-richer --clear-cache  # clear all cached data
  be-richer --check  # check Yahoo Finance connectivity
  be-richer --cache-stats  # show cache statistics
        """,
    )
    parser.add_argument(
        "--tier",
        choices=["klci", "broad", "full"],
        default="klci",
        help="Stock universe tier (default: klci)",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        metavar="TICKER",
        help="Override universe with specific tickers (e.g. 1155.KL 5347.KL)",
    )
    parser.add_argument(
        "--show-rejected",
        action="store_true",
        default=False,
        help="Include REJECT stocks in the output table",
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        default=False,
        help="Skip CSV export",
    )
    parser.add_argument(
        "--refresh-universe",
        action="store_true",
        default=False,
        help="Force refresh KLCI constituents from yfinance (ignores cache)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        default=False,
        help="Bypass cache and fetch fresh data from Yahoo Finance",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        default=False,
        help="Clear all cached data before running",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        default=False,
        help="Check Yahoo Finance connectivity and exit",
    )
    parser.add_argument(
        "--cache-stats",
        action="store_true",
        default=False,
        help="Show cache statistics and exit",
    )

    args = parser.parse_args()
    
    # Check connectivity only
    if args.check:
        console.print("\n[bold]Checking Yahoo Finance connectivity…[/bold]")
        conn = check_yahoo_connectivity()
        if conn["ok"]:
            console.print(f"[green]✓ {conn['message']}[/green]")
        elif conn["rate_limited"]:
            console.print(f"[bold red]✗ Rate Limited[/bold red]")
            console.print(f"[yellow]{conn['message']}[/yellow]")
        else:
            console.print(f"[red]✗ {conn['message']}[/red]")
        return
    
    # Show cache stats only
    if args.cache_stats:
        stats = get_cache_stats()
        console.print("\n[bold]Cache Statistics[/bold]")
        console.print(f"  Price files: {stats['prices_count']}")
        console.print(f"  Fundamentals files: {stats['fundamentals_count']}")
        console.print(f"  Total size: {stats['total_size_mb']} MB")
        if stats['oldest_file']:
            console.print(f"  Oldest: {stats['oldest_file']}")
        if stats['newest_file']:
            console.print(f"  Newest: {stats['newest_file']}")
        return
    
    # Clear cache if requested
    if args.clear_cache:
        deleted = clear_cache()
        console.print(f"[yellow]Cleared {deleted} cached files[/yellow]")
    
    run(
        tier=args.tier,
        tickers=args.tickers,
        show_rejected=args.show_rejected,
        export=not args.no_export,
        refresh_universe=args.refresh_universe,
        use_cache=not args.no_cache,
    )


if __name__ == "__main__":
    main()
