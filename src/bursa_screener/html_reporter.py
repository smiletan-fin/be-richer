"""
HTML Report Generator — creates a beautiful, self-contained HTML report.

Generates a responsive, dark-themed HTML report with:
- Summary cards showing classification counts
- Interactive sortable tables
- Color-coded classifications
- Mobile-friendly design
- No external dependencies (all CSS/JS inline)
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from .ranker import StockResult


def _get_class_color(classification: str) -> tuple[str, str]:
    """Return (background, text) colors for classification."""
    colors = {
        "READY TO BUY": ("#22c55e", "#000"),
        "EARLY RE-RATING": ("#eab308", "#000"),
        "WATCHLIST": ("#3b82f6", "#fff"),
        "REJECT": ("#ef4444", "#fff"),
    }
    return colors.get(classification, ("#6b7280", "#fff"))


def _get_class_emoji(classification: str) -> str:
    return {
        "READY TO BUY": "🟢",
        "EARLY RE-RATING": "🟡",
        "WATCHLIST": "🔵",
        "REJECT": "🔴",
    }.get(classification, "⚪")


def _format_value(val: float | None, suffix: str = "", decimals: int = 2) -> str:
    if val is None:
        return '<span class="na">N/A</span>'
    return f"{val:,.{decimals}f}{suffix}"


def _format_return(val: float | None) -> str:
    if val is None:
        return '<span class="na">N/A</span>'
    color = "#22c55e" if val > 0 else "#ef4444" if val < 0 else "#9ca3af"
    return f'<span style="color: {color}">{val:+.1f}%</span>'


def generate_html_report(
    results: list[StockResult],
    universe_size: int,
    elapsed: float,
    tier: str = "klci",
    show_rejected: bool = False,
    output_dir: str = "results",
) -> str:
    """
    Generate a self-contained HTML report.
    
    Returns the file path of the generated report.
    """
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now()
    ts_str = ts.strftime("%Y%m%d_%H%M")
    path = Path(output_dir) / f"bursa_screen_{ts_str}.html"
    
    # Count classifications
    ready = [r for r in results if r.classification == "READY TO BUY"]
    early = [r for r in results if r.classification == "EARLY RE-RATING"]
    watchlist = [r for r in results if r.classification == "WATCHLIST"]
    rejected = [r for r in results if r.classification == "REJECT"]
    
    # Filter results for display
    display_results = results if show_rejected else [r for r in results if r.classification != "REJECT"]
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bursa Malaysia Screener Report - {ts.strftime("%Y-%m-%d %H:%M")}</title>
    <style>
        :root {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-tertiary: #334155;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --border: #475569;
            --green: #22c55e;
            --yellow: #eab308;
            --blue: #3b82f6;
            --red: #ef4444;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }}
        
        h1 {{
            font-size: 2rem;
            margin-bottom: 10px;
            color: var(--text-primary);
        }}
        
        .subtitle {{
            color: var(--text-secondary);
            font-size: 0.95rem;
        }}
        
        .meta {{
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 15px;
            flex-wrap: wrap;
        }}
        
        .meta-item {{
            background: var(--bg-secondary);
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 0.85rem;
        }}
        
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        
        .card {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            border: 1px solid var(--border);
            transition: transform 0.2s;
        }}
        
        .card:hover {{
            transform: translateY(-2px);
        }}
        
        .card-emoji {{
            font-size: 2rem;
            margin-bottom: 10px;
        }}
        
        .card-count {{
            font-size: 2.5rem;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .card-label {{
            color: var(--text-secondary);
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .card.ready .card-count {{ color: var(--green); }}
        .card.early .card-count {{ color: var(--yellow); }}
        .card.watchlist .card-count {{ color: var(--blue); }}
        .card.reject .card-count {{ color: var(--red); }}
        
        .section {{
            margin-bottom: 30px;
        }}
        
        .section-title {{
            font-size: 1.3rem;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border);
        }}
        
        .table-container {{
            overflow-x: auto;
            border-radius: 12px;
            border: 1px solid var(--border);
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}
        
        th {{
            background: var(--bg-tertiary);
            padding: 12px 10px;
            text-align: left;
            font-weight: 600;
            color: var(--text-primary);
            white-space: nowrap;
            cursor: pointer;
            user-select: none;
            position: sticky;
            top: 0;
        }}
        
        th:hover {{
            background: #3d4f69;
        }}
        
        th::after {{
            content: ' ↕';
            opacity: 0.3;
            font-size: 0.8em;
        }}
        
        th.sort-asc::after {{
            content: ' ↑';
            opacity: 1;
        }}
        
        th.sort-desc::after {{
            content: ' ↓';
            opacity: 1;
        }}
        
        td {{
            padding: 10px;
            border-top: 1px solid var(--border);
            white-space: nowrap;
        }}
        
        tr:hover {{
            background: var(--bg-secondary);
        }}
        
        .ticker {{
            font-weight: 600;
            color: var(--blue);
        }}
        
        .name {{
            color: var(--text-secondary);
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .score {{
            font-weight: 600;
        }}
        
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
        }}
        
        .badge-ready {{ background: var(--green); color: #000; }}
        .badge-early {{ background: var(--yellow); color: #000; }}
        .badge-watchlist {{ background: var(--blue); color: #fff; }}
        .badge-reject {{ background: var(--red); color: #fff; }}
        
        .na {{
            color: var(--text-muted);
            font-style: italic;
        }}
        
        .highlight-section {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid var(--border);
        }}
        
        .highlight-title {{
            font-size: 1.1rem;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .stock-card {{
            background: var(--bg-tertiary);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 10px;
        }}
        
        .stock-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        
        .stock-name {{
            font-weight: 600;
        }}
        
        .stock-scores {{
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }}
        
        .stock-metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 10px;
            margin-top: 10px;
            font-size: 0.85rem;
        }}
        
        .metric {{
            background: var(--bg-secondary);
            padding: 8px;
            border-radius: 6px;
        }}
        
        .metric-label {{
            color: var(--text-muted);
            font-size: 0.75rem;
        }}
        
        .metric-value {{
            font-weight: 600;
        }}
        
        footer {{
            text-align: center;
            padding: 20px;
            color: var(--text-muted);
            font-size: 0.85rem;
            border-top: 1px solid var(--border);
            margin-top: 30px;
        }}
        
        @media (max-width: 768px) {{
            body {{
                padding: 10px;
            }}
            
            h1 {{
                font-size: 1.5rem;
            }}
            
            .summary-cards {{
                grid-template-columns: repeat(2, 1fr);
            }}
            
            table {{
                font-size: 0.8rem;
            }}
            
            th, td {{
                padding: 8px 6px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 Bursa Malaysia Stock Screener</h1>
            <p class="subtitle">Level 1 Automated Screening Report</p>
            <div class="meta">
                <span class="meta-item">📅 {ts.strftime("%Y-%m-%d %H:%M")}</span>
                <span class="meta-item">📈 Tier: {tier.upper()}</span>
                <span class="meta-item">🔍 {universe_size} stocks scanned</span>
                <span class="meta-item">⏱️ {elapsed:.1f}s</span>
            </div>
        </header>
        
        <section class="summary-cards">
            <div class="card ready">
                <div class="card-emoji">🟢</div>
                <div class="card-count">{len(ready)}</div>
                <div class="card-label">Ready to Buy</div>
            </div>
            <div class="card early">
                <div class="card-emoji">🟡</div>
                <div class="card-count">{len(early)}</div>
                <div class="card-label">Early Re-Rating</div>
            </div>
            <div class="card watchlist">
                <div class="card-emoji">🔵</div>
                <div class="card-count">{len(watchlist)}</div>
                <div class="card-label">Watchlist</div>
            </div>
            <div class="card reject">
                <div class="card-emoji">🔴</div>
                <div class="card-count">{len(rejected)}</div>
                <div class="card-label">Reject</div>
            </div>
        </section>
'''
    
    # Ready to Buy highlight section
    if ready:
        html += '''
        <section class="highlight-section">
            <div class="highlight-title">🟢 Ready to Buy — Top Picks</div>
'''
        for r in ready[:5]:
            html += f'''
            <div class="stock-card">
                <div class="stock-header">
                    <span class="stock-name">{r.ticker} — {r.long_name or "N/A"}</span>
                    <span class="badge badge-ready">READY TO BUY</span>
                </div>
                <div class="stock-scores">
                    <span>Fund: <strong>{r.fundamental_score}/60</strong></span>
                    <span>Tech: <strong>{r.technical_score}/20</strong></span>
                    <span>Total: <strong>{r.total_score}</strong></span>
                </div>
                <div class="stock-metrics">
                    <div class="metric">
                        <div class="metric-label">Price</div>
                        <div class="metric-value">RM {r.tech.price:.3f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">PE (TTM)</div>
                        <div class="metric-value">{_format_value(r.fund.pe_ttm, "x", 1)}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">ROE</div>
                        <div class="metric-value">{_format_value(r.fund.roe_pct, "%", 1)}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Div Yield</div>
                        <div class="metric-value">{_format_value(r.fund.div_yield_pct, "%", 1)}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Week Return</div>
                        <div class="metric-value">{_format_return(r.tech.week_return)}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">RSI</div>
                        <div class="metric-value">{r.tech.rsi_val:.0f}</div>
                    </div>
                </div>
            </div>
'''
        html += '''
        </section>
'''

    # Early Re-Rating highlight section
    if early:
        html += '''
        <section class="highlight-section">
            <div class="highlight-title">🟡 Early Re-Rating — Watch for Breakout</div>
'''
        for r in early[:5]:
            html += f'''
            <div class="stock-card">
                <div class="stock-header">
                    <span class="stock-name">{r.ticker} — {r.long_name or "N/A"}</span>
                    <span class="badge badge-early">EARLY RE-RATING</span>
                </div>
                <div class="stock-scores">
                    <span>Fund: <strong>{r.fundamental_score}/60</strong></span>
                    <span>Tech: <strong>{r.technical_score}/20</strong></span>
                    <span>Total: <strong>{r.total_score}</strong></span>
                </div>
                <div class="stock-metrics">
                    <div class="metric">
                        <div class="metric-label">Price</div>
                        <div class="metric-value">RM {r.tech.price:.3f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">PE (TTM)</div>
                        <div class="metric-value">{_format_value(r.fund.pe_ttm, "x", 1)}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Tech Status</div>
                        <div class="metric-value">{r.tech.status}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Vol Ratio</div>
                        <div class="metric-value">{r.tech.volume_ratio:.2f}x</div>
                    </div>
                </div>
            </div>
'''
        html += '''
        </section>
'''

    # Full table
    html += '''
        <section class="section">
            <h2 class="section-title">📋 Full Screening Results</h2>
            <div class="table-container">
                <table id="resultsTable">
                    <thead>
                        <tr>
                            <th data-sort="string">Ticker</th>
                            <th data-sort="string">Name</th>
                            <th data-sort="number">Price</th>
                            <th data-sort="number">Fund</th>
                            <th data-sort="number">Tech</th>
                            <th data-sort="number">Total</th>
                            <th data-sort="number">PE</th>
                            <th data-sort="number">PB</th>
                            <th data-sort="number">ROE</th>
                            <th data-sort="number">Gearing</th>
                            <th data-sort="number">Div%</th>
                            <th data-sort="number">RSI</th>
                            <th data-sort="number">Wk Ret</th>
                            <th data-sort="string">Class</th>
                        </tr>
                    </thead>
                    <tbody>
'''
    
    for r in display_results:
        bg_color, text_color = _get_class_color(r.classification)
        badge_class = {
            "READY TO BUY": "badge-ready",
            "EARLY RE-RATING": "badge-early",
            "WATCHLIST": "badge-watchlist",
            "REJECT": "badge-reject",
        }.get(r.classification, "")
        
        html += f'''
                        <tr>
                            <td class="ticker">{r.ticker}</td>
                            <td class="name">{(r.long_name or "")[:25]}</td>
                            <td>{r.tech.price:.3f}</td>
                            <td class="score">{r.fundamental_score}</td>
                            <td class="score">{r.technical_score}</td>
                            <td class="score">{r.total_score}</td>
                            <td>{_format_value(r.fund.pe_ttm, "", 1)}</td>
                            <td>{_format_value(r.fund.pb, "", 2)}</td>
                            <td>{_format_value(r.fund.roe_pct, "", 1)}</td>
                            <td>{_format_value(r.fund.net_gearing, "", 2)}</td>
                            <td>{_format_value(r.fund.div_yield_pct, "", 1)}</td>
                            <td>{r.tech.rsi_val:.0f}</td>
                            <td>{_format_return(r.tech.week_return)}</td>
                            <td><span class="badge {badge_class}">{_get_class_emoji(r.classification)} {r.classification}</span></td>
                        </tr>
'''
    
    html += '''
                    </tbody>
                </table>
            </div>
        </section>
        
        <footer>
            <p>Generated by Be Richer — Bursa Malaysia Stock Screener</p>
            <p>Data source: Yahoo Finance (15-min delayed) • Core EPS normalization requires Level 2 LLM analysis</p>
        </footer>
    </div>
    
    <script>
        // Simple table sorting
        document.querySelectorAll('th[data-sort]').forEach(th => {
            th.addEventListener('click', () => {
                const table = th.closest('table');
                const tbody = table.querySelector('tbody');
                const rows = Array.from(tbody.querySelectorAll('tr'));
                const colIndex = Array.from(th.parentNode.children).indexOf(th);
                const sortType = th.dataset.sort;
                const isAsc = th.classList.contains('sort-asc');
                
                // Remove sort classes from all headers
                table.querySelectorAll('th').forEach(h => {
                    h.classList.remove('sort-asc', 'sort-desc');
                });
                
                // Sort rows
                rows.sort((a, b) => {
                    let aVal = a.children[colIndex].textContent.trim();
                    let bVal = b.children[colIndex].textContent.trim();
                    
                    if (sortType === 'number') {
                        aVal = parseFloat(aVal.replace(/[^0-9.-]/g, '')) || 0;
                        bVal = parseFloat(bVal.replace(/[^0-9.-]/g, '')) || 0;
                        return isAsc ? bVal - aVal : aVal - bVal;
                    }
                    return isAsc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
                });
                
                // Update classes and DOM
                th.classList.add(isAsc ? 'sort-desc' : 'sort-asc');
                rows.forEach(row => tbody.appendChild(row));
            });
        });
    </script>
</body>
</html>
'''
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    
    return str(path)
