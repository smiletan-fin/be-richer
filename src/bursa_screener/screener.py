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
    python -m bursa_screener --analyze 1155.KL  # deep analyze a single stock

Or via CLI entry point:
    be-richer --tier broad
    bursa-screener --tier klci
    be-richer --analyze MAYBANK  # analyze a single stock
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

# FMP integration (optional - US stocks only)
try:
    from . import fmp_fetcher
    FMP_AVAILABLE = True
except ImportError:
    FMP_AVAILABLE = False

# KLSE Screener integration (primary for Malaysian stocks)
try:
    from . import klse_fetcher
    KLSE_AVAILABLE = True
except ImportError:
    KLSE_AVAILABLE = False

# Stock analyzer for single-stock deep analysis
try:
    from . import stock_analyzer
    ANALYZER_AVAILABLE = True
except ImportError:
    ANALYZER_AVAILABLE = False

console = Console()


def run(
    tier: str = "klci",
    tickers: list[str] | None = None,
    sector: str | None = None,
    show_rejected: bool = False,
    export: bool = True,
    export_html: bool = False,
    refresh_universe: bool = False,
    use_cache: bool = True,
    skip_connectivity_check: bool = False,
    use_fmp: bool = False,  # Disabled by default - no coverage for Malaysian stocks
) -> dict[str, str | None]:
    """
    Run the screener and return export paths.
    
    Returns dict with paths: {"csv": path, "html": path}
    """
    universe = tickers if tickers else get_universe(tier, force_refresh=refresh_universe, sector=sector)
    
    # Build tier description
    tier_desc = tier if not tickers else "custom"
    if sector:
        tier_desc = f"{tier_desc} ({sector})"

    cache_status = "[green]cache enabled[/green]" if use_cache else "[yellow]cache disabled[/yellow]"
    console.print(
        f"\n[bold blue]🔍 Bursa Malaysia Level 1 Screener[/bold blue]  "
        f"({len(universe)} tickers, tier={tier_desc}, {cache_status})\n"
    )

    # Check FMP status
    fmp_enabled = False
    if use_fmp and FMP_AVAILABLE:
        fmp_status = fmp_fetcher.check_api_status()
        if fmp_status["configured"]:
            if fmp_status["connected"]:
                console.print(f"[green]✓ FMP API: {fmp_status['message']}[/green]")
                fmp_enabled = True
            else:
                console.print(f"[yellow]⚠ FMP API configured but: {fmp_status['message']}[/yellow]")
        else:
            console.print("[dim]ℹ FMP API not configured (earnings surprises disabled)[/dim]")

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

    # ── Step 1b: fetch FMP data (if enabled - US stocks only) ──────────────────
    fmp_data_map = {}
    if fmp_enabled:
        console.print("[dim]Fetching FMP earnings data…[/dim]")
        fmp_success = 0
        for ticker in universe:
            fmp_data = fmp_fetcher.get_fmp_enhanced_data(ticker, use_cache=use_cache)
            fmp_data_map[ticker] = fmp_data
            if fmp_data.get("has_fmp_data"):
                fmp_success += 1
        console.print(f"[dim]FMP data: {fmp_success}/{len(universe)} stocks with earnings surprise data[/dim]")

    # ── Step 1c: fetch KLSE data (Malaysian stocks - primary enhancement) ─────
    klse_data_map = {}
    klse_enabled = False
    if KLSE_AVAILABLE:
        # Check if we have Malaysian stocks
        klse_tickers = [t for t in universe if t.upper().endswith(".KL")]
        if klse_tickers:
            klse_status = klse_fetcher.check_status()
            if klse_status["connected"]:
                console.print(f"[green]✓ KLSE Screener: {klse_status['message']}[/green]")
                klse_enabled = True
                console.print(f"[dim]Fetching KLSE quarterly data for {len(klse_tickers)} Malaysian stocks…[/dim]")
                klse_success = 0
                for ticker in klse_tickers:
                    klse_data = klse_fetcher.get_klse_enhanced_data(ticker, use_cache=use_cache)
                    klse_data_map[ticker] = klse_data
                    if klse_data.get("has_klse_data"):
                        klse_success += 1
                console.print(f"[dim]KLSE data: {klse_success}/{len(klse_tickers)} stocks with quarterly/shareholding data[/dim]")
            else:
                console.print(f"[yellow]⚠ KLSE Screener: {klse_status['message']}[/yellow]")

    # ── Step 2: score each stock ──────────────────────────────────────────────
    console.print("[dim]Scoring technicals and fundamentals…[/dim]")
    fund_scores = {}
    tech_scores = {}

    for ticker, data in raw_data.items():
        fmp_data = fmp_data_map.get(ticker) if fmp_enabled else None
        klse_data = klse_data_map.get(ticker) if klse_enabled else None
        fund_scores[ticker] = score_fundamentals(ticker, data["fundamentals"], fmp_data, klse_data)
        tech_scores[ticker] = score_technicals(ticker, data["price_df"])

    # ── Step 3: rank and classify ─────────────────────────────────────────────
    results = build_results(raw_data, fund_scores, tech_scores)

    elapsed = time.time() - start

    # ── Step 4: report ────────────────────────────────────────────────────────
    return print_all(
        results, 
        len(universe), 
        elapsed, 
        show_rejected=show_rejected, 
        export=export,
        export_html=export_html,
        tier=tier if not tickers else "custom",
    )


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
  be-richer --sector banking  # filter by sector
  be-richer --tier klci --sector technology
  be-richer --list-sectors  # show available sectors
  be-richer --refresh-universe
  be-richer --no-cache  # bypass cache (always fetch fresh)
  be-richer --clear-cache  # clear all cached data
  be-richer --check  # check Yahoo Finance connectivity
  be-richer --cache-stats  # show cache statistics
  
  # Single stock deep analysis:
  be-richer --analyze 1155.KL  # analyze Maybank
  be-richer --analyze MAYBANK  # same as above (auto-resolves to 1155.KL)
  be-richer --analyze CIMB --output ./my-reports  # custom output directory
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
        "--sector",
        type=str,
        metavar="SECTOR",
        help="Filter by sector (e.g. banking, technology, plantation, property)",
    )
    parser.add_argument(
        "--list-sectors",
        action="store_true",
        default=False,
        help="List available sectors and exit",
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
        "--html",
        action="store_true",
        default=False,
        help="Generate HTML report (in addition to CSV)",
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
        "--fmp",
        action="store_true",
        default=False,
        help="Enable FMP earnings surprise data (US stocks only, requires FMP_API_KEY)",
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
    parser.add_argument(
        "--analyze",
        type=str,
        metavar="TICKER",
        help="Deep analyze a single stock (e.g., --analyze 1155.KL or --analyze MAYBANK)",
    )
    parser.add_argument(
        "--output",
        type=str,
        metavar="DIR",
        help="Output directory for analysis files (default: results/)",
    )

    args = parser.parse_args()
    
    # Single stock analysis mode
    if args.analyze:
        if not ANALYZER_AVAILABLE:
            console.print("[red]Error: Stock analyzer module not available[/red]")
            return
        
        analysis = stock_analyzer.analyze_stock(
            args.analyze,
            use_cache=not args.no_cache,
            verbose=True,
        )
        
        # Print summary to console
        stock_analyzer.print_analysis(analysis)
        
        # Save outputs
        output_dir = args.output or "results"
        paths = stock_analyzer.save_analysis(analysis, output_dir)
        
        console.print("\n[bold]📁 Files Generated:[/bold]")
        console.print(f"  Report:    {paths['report']}")
        console.print(f"  AI Prompt: {paths['prompt']}")
        console.print(f"  JSON Data: {paths['json']}")
        
        console.print("\n[bold cyan]💡 Next Steps:[/bold cyan]")
        console.print(f"  1. Read the report: [dim]{paths['report']}[/dim]")
        console.print(f"  2. Copy the AI prompt to ChatGPT/Claude for deeper analysis")
        console.print(f"  3. Research recent news and announcements for {args.analyze}")
        
        return
    
    # List available sectors
    if args.list_sectors:
        from .universe import list_available_sectors
        sectors = list_available_sectors()
        if sectors:
            console.print("\n[bold]Available Sectors[/bold]")
            for s in sectors:
                aliases = ", ".join(s.get("aliases", []))
                console.print(f"  [cyan]{s['name']}[/cyan]: {aliases}")
        else:
            console.print("[yellow]KLSE Screener not available - cannot list sectors[/yellow]")
        return
    
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
        sector=args.sector,
        show_rejected=args.show_rejected,
        export=not args.no_export,
        export_html=args.html,
        refresh_universe=args.refresh_universe,
        use_cache=not args.no_cache,
        use_fmp=args.fmp,
    )


if __name__ == "__main__":
    main()
