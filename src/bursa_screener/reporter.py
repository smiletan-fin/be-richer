"""
Reporter — renders the screening results to the terminal (rich tables)
and exports to CSV.

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

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    summary = (
        f"[bold]Bursa Malaysia Screener — Level 1[/bold]  |  {ts}\n\n"
        f"Universe: [bold]{universe_size}[/bold] tickers scanned in {elapsed:.1f}s\n"
        f"  🟢 READY TO BUY   : [bold green]{len(ready)}[/bold green]\n"
        f"  🟡 EARLY RE-RATING: [bold yellow]{len(early)}[/bold yellow]\n"
        f"  🔵 WATCHLIST      : [bold cyan]{len(watchlist)}[/bold cyan]\n"
        f"  🔴 REJECT         : [dim red]{len(rejected)}[/dim red]\n\n"
        f"[dim]Data: yfinance (15-min delayed) — Core EPS normalization requires Level 2 LLM analysis[/dim]"
    )
    console.print(Panel(summary, border_style="blue", padding=(1, 2)))


def print_screening_table(results: list[StockResult], show_rejected: bool = False) -> None:
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
        ("Fund/60",     "right", 7),
        ("Tech/20",     "right", 7),
        ("Total",       "right", 6),
        ("PE",          "right", 6),
        ("PB",          "right", 5),
        ("ROE",         "right", 6),
        ("NetGear",     "right", 8),
        ("DivYld",      "right", 7),
        ("RSI",         "right", 5),
        ("VolRatio",    "right", 8),
        ("WkRet",       "right", 7),
        ("Tech Status", "left",  20),
        ("Class",       "left",  16),
    ]

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

        table.add_row(
            f"[bold]{row['ticker']}[/bold]",
            row["name"],
            row["price"],
            row["fundamental"],
            row["technical"],
            row["total"],
            row["pe_ttm"],
            row["pb"],
            row["roe"],
            row["net_gearing"],
            row["div_yield"],
            row["rsi"],
            row["vol_ratio"],
            wk_str,
            row["tech_status"],
            f"[{style}]{emoji} {cls}[/{style}]",
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
        flags = r.fund.flags[:3]  # top 3 flags only

        lines.append(f"[bold]{r.ticker}[/bold]  {r.long_name or ''}")
        lines.append(
            f"  Scores: Fund=[bold]{r.fundamental_score}/60[/bold]  "
            f"Tech=[bold]{r.technical_score}/20[/bold]  "
            f"Total=[bold]{r.total_score}[/bold]"
        )
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
) -> None:
    """Master print function — call this from main."""
    print_summary(results, universe_size, elapsed)
    print_screening_table(results, show_rejected=show_rejected)
    print_group_panel(results, "READY TO BUY")
    print_group_panel(results, "EARLY RE-RATING")
    print_group_panel(results, "WATCHLIST")
    print_flags_warnings(results)

    if export:
        csv_path = export_csv(results)
        console.print(f"\n[dim]📁 Results exported: {csv_path}[/dim]\n")
