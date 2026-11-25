"""
Reporter — renders the screening results to the terminal (rich tables)
and exports to CSV and HTML.

Output sections:
    1. Run summary (ticker count, timestamp, data source warnings)
    2. Full screening table (all stocks, sorted by classification)
    3. READY TO BUY panel
    4. EARLY RE-RATING panel
    5. WATCHLIST summary
    6. Flags & data quality warnings
"""

from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from .ranker import StockResult
from .html_reporter import generate_html_report

console = Console()

# colour map per classification
CLASS_STYLE = {
    "READY TO BUY":    "bold green",
    "EARLY RE-RATING": "bold yellow",
    "WATCHLIST":       "cyan",
    "REJECT":          "dim red",
}


def _fmt(val: str | None, style: str = "") -> str:
    if val is None:
        return "[dim]N/A[/dim]"
    return f"[{style}]{val}[/{style}]" if style else val


def print_summary(results: list[StockResult], universe_size: int, elapsed: float) -> None:
    ready      = [r for r in results if r.classification == "READY TO BUY"]
    early      = [r for r in results if r.classification == "EARLY RE-RATING"]
    watchlist  = [r for r in results if r.classification == "WATCHLIST"]
    rejected   = [r for r in results if r.classification == "REJECT"]
    
    # Check if any stock has FMP, KLSE, or Analyst data
    has_fmp = any(r.fund.has_fmp_data for r in results)
    has_klse = any(r.fund.has_klse_data for r in results)
    has_analyst = any(r.fund.has_analyst_data for r in results)
    klse_count = sum(1 for r in results if r.fund.has_klse_data)
    analyst_count = sum(1 for r in results if r.fund.has_analyst_data)
    
    # Build data sources status line
    sources = ["yfinance (15-min delayed)"]
    if has_analyst:
        sources.append(f"[green]Analyst targets ({analyst_count} stocks)[/green]")
    if has_klse:
        sources.append(f"[green]KLSE Screener ({klse_count} stocks)[/green]")
    else:
        sources.append("[dim]KLSE Screener disabled[/dim]")
    if has_fmp:
        sources.append("[green]+ FMP earnings surprises[/green]")
    else:
        sources.append("[dim]FMP disabled[/dim]")

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    summary = (
        f"[bold]Bursa Malaysia Screener — Level 1[/bold]  |  {ts}\n\n"
        f"Universe: [bold]{universe_size}[/bold] tickers scanned in {elapsed:.1f}s\n"
        f"  🟢 READY TO BUY   : [bold green]{len(ready)}[/bold green]\n"
        f"  🟡 EARLY RE-RATING: [bold yellow]{len(early)}[/bold yellow]\n"
        f"  🔵 WATCHLIST      : [bold cyan]{len(watchlist)}[/bold cyan]\n"
        f"  🔴 REJECT         : [dim red]{len(rejected)}[/dim red]\n\n"
        f"[dim]Data: {' • '.join(sources)} — Core EPS normalization requires Level 2 LLM analysis[/dim]"
    )
    console.print(Panel(summary, border_style="blue", padding=(1, 2)))


def print_screening_table(results: list[StockResult], show_rejected: bool = False) -> None:
    # Check if any stock has FMP or KLSE or Analyst data
    has_fmp = any(r.fund.has_fmp_data for r in results)
    has_klse = any(r.fund.has_klse_data for r in results)
    has_analyst = any(r.fund.has_analyst_data for r in results)
    
    table = Table(
        title="📊 Full Screening Table",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold white on dark_blue",
        border_style="blue",
        row_styles=["", "dim"],
    )

    cols = [
        ("Ticker",      "left",  6),
        ("Name",        "left",  22),
        ("Price",       "right", 8),
        ("Fund",        "right", 7),
        ("Tech/25",     "right", 7),
        ("Total",       "right", 6),
        ("PE",          "right", 6),
        ("PB",          "right", 5),
        ("ROE",         "right", 6),
        ("EPSGrowth",   "right", 9),
    ]
    
    # Add Analyst target column if data available
    if has_analyst:
        cols.extend([
            ("Target",   "right", 8),
            ("Upside",   "right", 7),
        ])
    
    # Add Earnings Surprise column if FMP data available
    if has_fmp:
        cols.append(("EarnSurp", "right", 8))
    
    # Add KLSE enhanced columns if KLSE data available
    if has_klse:
        cols.extend([
            ("QoQ%",   "right", 7),
            ("YoY%",   "right", 7),
            ("Mom",    "right", 5),
            ("Inst",   "right", 5),
        ])
    
    cols.extend([
        ("NetGear",     "right", 8),
        ("DivYld",      "right", 7),
        ("RS Ratio",    "right", 8),
        ("RSI",         "right", 5),
        ("VolRatio",    "right", 8),
        ("WkRet",       "right", 7),
        ("Tech Status", "left",  20),
        ("Class",       "left",  16),
    ])

    for name, justify, min_width in cols:
        table.add_column(name, justify=justify, min_width=min_width, no_wrap=True)

    for r in results:
        if r.classification == "REJECT" and not show_rejected:
            continue

        row = r.as_row()
        cls   = r.classification
        style = CLASS_STYLE.get(cls, "")
        emoji = r.classification_emoji

        # colour week return
        wk = r.tech.week_return
        wk_str = f"[green]{wk:+.1f}%[/green]" if wk > 0 else f"[red]{wk:+.1f}%[/red]"
        
        # Build row data
        row_data = [
            f"[bold]{row['ticker']}[/bold]",
            row["name"],
            row["price"],
            row["fundamental"],
            row["technical"],
            row["total"],
            row["pe_ttm"],
            row["pb"],
            row["roe"],
            row["earnings_growth"],
        ]
        
        # Add analyst target if data available
        if has_analyst:
            upside_val = r.fund.analyst_target_upside
            upside_str = f"[green]{upside_val:+.1f}%[/green]" if upside_val and upside_val > 0 else (f"[red]{upside_val:+.1f}%[/red]" if upside_val and upside_val < 0 else "[dim]—[/dim]")
            row_data.extend([
                row["analyst_target"] if r.fund.has_analyst_data else "[dim]—[/dim]",
                upside_str if r.fund.has_analyst_data else "[dim]—[/dim]",
            ])
        
        # Add earnings surprise if FMP data available
        if has_fmp:
            row_data.append(row["earnings_surprise"])
        
        # Add KLSE columns if available
        if has_klse:
            # Format QoQ/YoY with colors
            qoq_val = r.fund.latest_qoq
            yoy_val = r.fund.latest_yoy
            qoq_str = f"[green]{qoq_val:+.1f}%[/green]" if qoq_val and qoq_val > 0 else (f"[red]{qoq_val:+.1f}%[/red]" if qoq_val and qoq_val < 0 else "[dim]—[/dim]")
            yoy_str = f"[green]{yoy_val:+.1f}%[/green]" if yoy_val and yoy_val > 0 else (f"[red]{yoy_val:+.1f}%[/red]" if yoy_val and yoy_val < 0 else "[dim]—[/dim]")
            
            row_data.extend([
                qoq_str if r.fund.has_klse_data else "[dim]—[/dim]",
                yoy_str if r.fund.has_klse_data else "[dim]—[/dim]",
                row["klse_momentum"],
                row["klse_institutional"],
            ])
        
        row_data.extend([
            row["net_gearing"],
            row["div_yield"],
            row["rs_ratio"],
            row["rsi"],
            row["vol_ratio"],
            wk_str,
            row["tech_status"],
            f"[{style}]{emoji} {cls}[/{style}]",
        ])

        table.add_row(
            *row_data,
            style=style if cls == "READY TO BUY" else "",
        )

    console.print(table)


def print_group_panel(results: list[StockResult], classification: str) -> None:
    group = [r for r in results if r.classification == classification]
    if not group:
        return

    style = CLASS_STYLE.get(classification, "white")
    emoji = {"READY TO BUY": "🟢", "EARLY RE-RATING": "🟡", "WATCHLIST": "🔵"}.get(classification, "")

    lines: list[str] = []
    for r in group[:5]:   # cap at 5 per spec
        fund_breakdown = r.fund.breakdown
        tech_detail    = r.tech.detail
        flags = r.fund.flags  # show all flags
        
        # Format earnings surprise info
        es_info = ""
        if r.fund.has_fmp_data:
            es_info = f"  EarnSurp=[bold]{r.fund.score_earnings_surprise}/5[/bold]"
        
        # Format analyst target info
        analyst_info = ""
        if r.fund.has_analyst_data and r.fund.analyst_target_mean:
            upside = r.fund.analyst_target_upside or 0
            upside_color = "green" if upside > 0 else "red"
            analyst_info = (
                f"  Analyst: Target=[bold]RM {r.fund.analyst_target_mean:.2f}[/bold] "
                f"([{upside_color}]{upside:+.1f}%[/{upside_color}] upside) "
                f"Score=[bold]{r.fund.score_analyst_target}/5[/bold]"
            )
        
        # Format KLSE enhanced info
        klse_info = ""
        if r.fund.has_klse_data:
            klse_info = (
                f"  KLSE=[bold]Mom={r.fund.score_earnings_momentum}/5 "
                f"Con={r.fund.score_earnings_consistency}/3 "
                f"Inst={r.fund.score_institutional_flow}/3[/bold]"
            )
            if r.fund.latest_qoq is not None or r.fund.latest_yoy is not None:
                qoq_str = f"QoQ: {r.fund.latest_qoq:+.1f}%" if r.fund.latest_qoq is not None else ""
                yoy_str = f"YoY: {r.fund.latest_yoy:+.1f}%" if r.fund.latest_yoy is not None else ""
                klse_info += f"\n  [dim]Latest Quarterly: {qoq_str}  {yoy_str}[/dim]"

        lines.append(f"[bold]{r.ticker}[/bold]  {r.long_name or ''}")
        lines.append(
            f"  Scores: Fund=[bold]{r.fundamental_score}/{r.fund.max_score}[/bold]  "
            f"Tech=[bold]{r.technical_score}/25[/bold]  "
            f"Total=[bold]{r.total_score}[/bold]{es_info}"
        )
        if analyst_info:
            lines.append(analyst_info)
        if klse_info:
            lines.append(klse_info)
        lines.append(f"  {fund_breakdown}")
        lines.append(
            f"  Price: {r.tech.price:.3f}  MA20: {r.tech.ma20:.3f}  "
            f"MA50: {r.tech.ma50:.3f}  RSI: {r.tech.rsi_val:.0f}  "
            f"Vol: {r.tech.volume_ratio:.2f}x"
        )
        lines.append(
            f"  Week: {r.tech.week_return:+.1f}%  "
            f"Month: {r.tech.month_return:+.1f}%  "
            f"Status: {r.tech.status}"
        )
        if flags:
            lines.append(f"  [dim]Flags: {' | '.join(flags)}[/dim]")

        if classification == "EARLY RE-RATING":
            lines.append(
                f"  [yellow]⚡ Watching for breakout confirmation with volume expansion[/yellow]"
            )

        lines.append("")

    console.print(
        Panel(
            "\n".join(lines),
            title=f"{emoji} {classification} ({len(group)} stocks)",
            border_style=style.replace("bold ", ""),
            padding=(1, 2),
        )
    )


def print_flags_warnings(results: list[StockResult]) -> None:
    flagged = [r for r in results if r.fund.flags or r.fund.error or r.tech.error]
    if not flagged:
        return

    lines = ["[bold]Data Quality & Risk Flags[/bold]\n"]
    for r in flagged[:15]:
        if r.fund.error:
            lines.append(f"  [red]{r.ticker}[/red]: {r.fund.error}")
        if r.tech.error:
            lines.append(f"  [red]{r.ticker}[/red]: {r.tech.error}")
        for flag in r.fund.flags:
            if any(kw in flag for kw in ["⚠", "High net", "Negative", "concern"]):
                lines.append(f"  [yellow]{r.ticker}[/yellow]: {flag}")

    if len(lines) > 1:
        console.print(Panel("\n".join(lines), title="⚠ Flags", border_style="yellow", padding=(1, 2)))


def export_csv(results: list[StockResult], output_dir: str = "results") -> str:
    """Export the screening table to CSV. Returns the file path."""
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    path = Path(output_dir) / f"bursa_screen_{ts}.csv"

    rows = [r.as_row() for r in results]
    if not rows:
        return str(path)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    return str(path)


def print_all(
    results: list[StockResult],
    universe_size: int,
    elapsed: float,
    show_rejected: bool = False,
    export: bool = True,
    export_html: bool = False,
    tier: str = "klci",
) -> dict[str, str | None]:
    """
    Master print function — call this from main.
    
    Returns dict with export paths: {"csv": path, "html": path}
    """
    print_summary(results, universe_size, elapsed)
    print_screening_table(results, show_rejected=show_rejected)
    print_group_panel(results, "READY TO BUY")
    print_group_panel(results, "EARLY RE-RATING")
    print_group_panel(results, "WATCHLIST")
    print_flags_warnings(results)

    exports: dict[str, str | None] = {"csv": None, "html": None}

    if export:
        csv_path = export_csv(results)
        exports["csv"] = csv_path
        console.print(f"\n[dim]📁 CSV exported: {csv_path}[/dim]")
    
    if export_html:
        html_path = generate_html_report(
            results=results,
            universe_size=universe_size,
            elapsed=elapsed,
            tier=tier,
            show_rejected=show_rejected,
        )
        exports["html"] = html_path
        console.print(f"[dim]📁 HTML exported: {html_path}[/dim]\n")
    elif export:
        console.print()
    
    return exports
