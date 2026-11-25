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
        /* Strategy section styles */
        .strategy-section {{
            background: linear-gradient(135deg, var(--bg-secondary) 0%, #1a2744 100%);
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 30px;
            border: 1px solid var(--border);
        }}
        
        .strategy-title {{
            font-size: 1.4rem;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .strategy-intro {{
            color: var(--text-secondary);
            margin-bottom: 25px;
            line-height: 1.8;
            font-size: 1rem;
        }}
        
        .scoring-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 25px;
        }}
        
        .score-box {{
            background: var(--bg-tertiary);
            border-radius: 12px;
            padding: 20px;
            border-left: 4px solid var(--blue);
        }}
        
        .score-box.fundamental {{
            border-left-color: #8b5cf6;
        }}
        
        .score-box.technical {{
            border-left-color: #06b6d4;
        }}
        
        .score-box-title {{
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .score-box-subtitle {{
            color: var(--text-muted);
            font-size: 0.85rem;
            margin-bottom: 15px;
        }}
        
        .factor-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        
        .factor-list li {{
            padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.9rem;
        }}
        
        .factor-list li:last-child {{
            border-bottom: none;
        }}
        
        .factor-name {{
            color: var(--text-secondary);
        }}
        
        .factor-points {{
            color: var(--text-muted);
            font-size: 0.8rem;
        }}
        
        .category-explainer {{
            margin-top: 25px;
        }}
        
        .category-explainer-title {{
            font-size: 1.1rem;
            margin-bottom: 15px;
        }}
        
        .category-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 15px;
        }}
        
        .category-card {{
            background: var(--bg-tertiary);
            border-radius: 10px;
            padding: 15px;
            border-left: 4px solid;
        }}
        
        .category-card.ready {{
            border-left-color: var(--green);
        }}
        
        .category-card.early {{
            border-left-color: var(--yellow);
        }}
        
        .category-card.watchlist {{
            border-left-color: var(--blue);
        }}
        
        .category-card.reject {{
            border-left-color: var(--red);
        }}
        
        .category-card-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 10px;
            font-weight: 600;
        }}
        
        .category-card-criteria {{
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 8px;
            padding: 6px 10px;
            background: rgba(0,0,0,0.2);
            border-radius: 6px;
            font-family: monospace;
        }}
        
        .category-card-desc {{
            font-size: 0.9rem;
            color: var(--text-secondary);
            line-height: 1.6;
        }}
        
        .analogy-box {{
            background: rgba(59, 130, 246, 0.1);
            border: 1px solid rgba(59, 130, 246, 0.3);
            border-radius: 10px;
            padding: 15px;
            margin-top: 20px;
        }}
        
        .analogy-title {{
            font-size: 0.95rem;
            font-weight: 600;
            margin-bottom: 10px;
            color: var(--blue);
        }}
        
        .analogy-text {{
            font-size: 0.9rem;
            color: var(--text-secondary);
            line-height: 1.7;
        }}
        
        .toggle-btn {{
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            color: var(--text-primary);
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 15px;
            transition: background 0.2s;
        }}
        
        .toggle-btn:hover {{
            background: var(--bg-secondary);
        }}
        
        .collapsible {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
        }}
        
        .collapsible.expanded {{
            max-height: 2000px;
        }}
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
            overflow-y: visible;
            position: relative;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}
        
        thead {{
            position: relative;
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
            position: relative;
        }}
        
        /* Custom tooltip styles - positioned above to avoid clipping */
        th[title] {{
            cursor: help;
        }}
        
        th[title]:hover::before {{
            content: attr(title);
            position: fixed;
            background: #0f172a;
            color: #f1f5f9;
            padding: 14px 18px;
            border-radius: 10px;
            font-size: 0.85rem;
            font-weight: 400;
            white-space: pre-line;
            min-width: 250px;
            max-width: 320px;
            z-index: 9999;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
            border: 1px solid var(--border);
            line-height: 1.6;
            text-align: left;
            pointer-events: none;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
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
        
        <!-- Strategy Explanation Section -->
        <section class="strategy-section">
            <h2 class="strategy-title">📚 How This Screener Works</h2>
            
            <p class="strategy-intro">
                This screener analyzes stocks using an <strong>industry-standard 90-point scoring system</strong> that combines 
                financial quality (fundamentals) with price momentum (technicals). Think of it like checking 
                both the engine AND the speedometer before buying a car — you want a quality vehicle that's 
                also moving in the right direction. This methodology is aligned with proven frameworks like 
                CAN SLIM, Piotroski F-Score, and Minervini's SEPA.
            </p>
            
            <button class="toggle-btn" onclick="toggleStrategy()">
                <span id="toggle-icon">▶</span> Show Detailed Scoring Breakdown
            </button>
            
            <div id="strategy-details" class="collapsible">
                <div class="scoring-grid">
                    <div class="score-box fundamental">
                        <div class="score-box-title">
                            <span>💰</span> Fundamental Score (65 points)
                        </div>
                        <div class="score-box-subtitle">
                            "Is this a quality business?" — Measures company health, growth & value
                        </div>
                        <ul class="factor-list">
                            <li>
                                <span class="factor-name">📈 Earnings Quality</span>
                                <span class="factor-points">10 pts</span>
                            </li>
                            <li>
                                <span class="factor-name">🚀 Earnings Growth (NEW)</span>
                                <span class="factor-points">10 pts</span>
                            </li>
                            <li>
                                <span class="factor-name">💵 Return on Equity (ROE)</span>
                                <span class="factor-points">10 pts</span>
                            </li>
                            <li>
                                <span class="factor-name">🏦 Financial Health (Debt levels)</span>
                                <span class="factor-points">10 pts</span>
                            </li>
                            <li>
                                <span class="factor-name">🏷️ Valuation (PE & PB vs sector)</span>
                                <span class="factor-points">12 pts</span>
                            </li>
                            <li>
                                <span class="factor-name">💸 Cash Flow</span>
                                <span class="factor-points">5 pts</span>
                            </li>
                            <li>
                                <span class="factor-name">🎁 Dividends</span>
                                <span class="factor-points">3 pts</span>
                            </li>
                            <li>
                                <span class="factor-name">📊 Improving Fundamentals (NEW)</span>
                                <span class="factor-points">5 pts</span>
                            </li>
                        </ul>
                    </div>
                    
                    <div class="score-box technical">
                        <div class="score-box-title">
                            <span>📊</span> Technical Score (25 points)
                        </div>
                        <div class="score-box-subtitle">
                            "Is the price going up?" — Measures momentum, trend & relative strength
                        </div>
                        <ul class="factor-list">
                            <li>
                                <span class="factor-name">📉 Price vs 20-day average</span>
                                <span class="factor-points">3 pts</span>
                            </li>
                            <li>
                                <span class="factor-name">📉 Price vs 50-day average</span>
                                <span class="factor-points">3 pts</span>
                            </li>
                            <li>
                                <span class="factor-name">📉 Price vs 200-day average</span>
                                <span class="factor-points">3 pts</span>
                            </li>
                            <li>
                                <span class="factor-name">🎯 RSI (Momentum indicator)</span>
                                <span class="factor-points">2 pts</span>
                            </li>
                            <li>
                                <span class="factor-name">📶 MACD (Trend direction)</span>
                                <span class="factor-points">2 pts</span>
                            </li>
                            <li>
                                <span class="factor-name">📊 Trading Volume</span>
                                <span class="factor-points">3 pts</span>
                            </li>
                            <li>
                                <span class="factor-name">🚀 Breakout Pattern</span>
                                <span class="factor-points">2 pts</span>
                            </li>
                            <li>
                                <span class="factor-name">🛡️ Support Level</span>
                                <span class="factor-points">2 pts</span>
                            </li>
                            <li>
                                <span class="factor-name">💪 Relative Strength (NEW)</span>
                                <span class="factor-points">3 pts</span>
                            </li>
                            <li>
                                <span class="factor-name">📍 52-Week Position (NEW)</span>
                                <span class="factor-points">2 pts</span>
                            </li>
                        </ul>
                    </div>
                </div>
                
                <div class="category-explainer">
                    <h3 class="category-explainer-title">🏷️ What Each Category Means</h3>
                    
                    <div class="category-cards">
                        <div class="category-card ready">
                            <div class="category-card-header">
                                🟢 Ready to Buy
                            </div>
                            <div class="category-card-criteria">
                                Fundamental ≥ 52/65 AND Technical ≥ 18/25
                            </div>
                            <div class="category-card-desc">
                                <strong>The sweet spot!</strong> These stocks are both financially strong 
                                AND showing positive price momentum. The business is healthy, growing, and the 
                                market is already recognizing its value. Consider these for immediate 
                                research and potential entry.
                            </div>
                        </div>
                        
                        <div class="category-card early">
                            <div class="category-card-header">
                                🟡 Early Re-Rating
                            </div>
                            <div class="category-card-criteria">
                                Fundamental ≥ 52/65 AND Technical 12-17/25
                            </div>
                            <div class="category-card-desc">
                                <strong>Hidden gems in transition!</strong> Great fundamentals but price 
                                hasn't fully caught up yet. These could be early-stage turnarounds. 
                                Watch for increasing volume, relative strength improvement, and price breakouts.
                            </div>
                        </div>
                        
                        <div class="category-card watchlist">
                            <div class="category-card-header">
                                🔵 Watchlist
                            </div>
                            <div class="category-card-criteria">
                                Fundamental 40-51/65
                            </div>
                            <div class="category-card-desc">
                                <strong>Keep an eye on these.</strong> Decent fundamentals but not 
                                outstanding. Could improve with better earnings growth or if valuation 
                                becomes more attractive. Monitor for upgrades.
                            </div>
                        </div>
                        
                        <div class="category-card reject">
                            <div class="category-card-header">
                                🔴 Reject
                            </div>
                            <div class="category-card-criteria">
                                Fundamental &lt; 40/65 OR red flags present
                            </div>
                            <div class="category-card-desc">
                                <strong>Avoid for now.</strong> Weak fundamentals, negative earnings growth, 
                                high debt, or other warning signs. Even if the price looks cheap, 
                                there's usually a reason. These often become "value traps."
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="analogy-box">
                    <div class="analogy-title">💡 Simple Analogy: Buying a Used Car</div>
                    <div class="analogy-text">
                        <strong>Fundamental Score</strong> = Checking the engine, brakes, and service history. 
                        Is this a reliable car?<br><br>
                        <strong>Technical Score</strong> = Checking if the car is accelerating or slowing down. 
                        Is it gaining momentum?<br><br>
                        <strong>🟢 Ready to Buy</strong> = Great engine + accelerating = Buy with confidence<br>
                        <strong>🟡 Early Re-Rating</strong> = Great engine + just started moving = Promising, watch closely<br>
                        <strong>🔵 Watchlist</strong> = Okay engine = Wait for better conditions<br>
                        <strong>🔴 Reject</strong> = Engine problems = Don't buy, no matter how cheap
                    </div>
                </div>
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
                    <span>Fund: <strong>{r.fundamental_score}/65</strong></span>
                    <span>Tech: <strong>{r.technical_score}/25</strong></span>
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
                        <div class="metric-label">EPS Growth</div>
                        <div class="metric-value">{_format_return(r.fund.earnings_growth_pct)}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">RS Ratio</div>
                        <div class="metric-value">{r.tech.rs_ratio:.2f}x</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Week Return</div>
                        <div class="metric-value">{_format_return(r.tech.week_return)}</div>
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
                    <span>Fund: <strong>{r.fundamental_score}/65</strong></span>
                    <span>Tech: <strong>{r.technical_score}/25</strong></span>
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
                        <div class="metric-label">EPS Growth</div>
                        <div class="metric-value">{_format_return(r.fund.earnings_growth_pct)}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">RS Ratio</div>
                        <div class="metric-value">{r.tech.rs_ratio:.2f}x</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">52Wk Position</div>
                        <div class="metric-value">+{r.tech.pct_from_52wk_low:.0f}% / -{r.tech.pct_from_52wk_high:.0f}%</div>
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
            <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 15px;">
                💡 Hover over column headers for explanations
            </p>
            <div class="table-container">
                <table id="resultsTable">
                    <thead>
                        <tr>
                            <th data-sort="string" title="Stock ticker symbol on Bursa Malaysia">Ticker</th>
                            <th data-sort="string" title="Company name">Name</th>
                            <th data-sort="number" title="Current stock price in Malaysian Ringgit">Price</th>
                            <th data-sort="number" title="Fundamental Score (max 65 pts)&#10;Measures business quality: earnings, growth, ROE, debt, valuation&#10;Higher = stronger company financials">Fund</th>
                            <th data-sort="number" title="Technical Score (max 25 pts)&#10;Measures price momentum: trend, moving averages, volume&#10;Higher = stronger uptrend">Tech</th>
                            <th data-sort="number" title="Total Score = Fundamental + Technical&#10;Higher score = better overall candidate">Total</th>
                            <th data-sort="number" title="Price-to-Earnings Ratio (TTM)&#10;How much you pay for each RM1 of earnings&#10;Lower = cheaper (but compare within same sector)">PE</th>
                            <th data-sort="number" title="Price-to-Book Ratio&#10;Stock price vs company's net assets&#10;Below 1.0 = trading below book value">PB</th>
                            <th data-sort="number" title="Return on Equity (%)&#10;How efficiently the company uses shareholder money&#10;Higher = more profitable (above 15% is good)">ROE</th>
                            <th data-sort="number" title="Earnings Per Share Growth (YoY %)&#10;How fast profits are growing&#10;Above 25% is excellent (CAN SLIM standard)">EPS Gr</th>
                            <th data-sort="number" title="Net Gearing Ratio&#10;(Total Debt - Cash) / Equity&#10;Negative = net cash (good), Above 1.0 = high debt (risky)">Gearing</th>
                            <th data-sort="number" title="Dividend Yield (%)&#10;Annual dividend as % of stock price&#10;Higher = more income (but growth stocks may not pay)">Div%</th>
                            <th data-sort="number" title="Relative Strength Ratio&#10;Stock performance vs KLCI index (6 months)&#10;Above 1.0 = outperforming market">RS</th>
                            <th data-sort="number" title="Relative Strength Index (14-day)&#10;Momentum indicator: 0-100 scale&#10;50-70 = bullish, Above 70 = overbought, Below 30 = oversold">RSI</th>
                            <th data-sort="number" title="52-Week Position&#10;Format: +X% above low / -Y% below high&#10;Ideal: >25% above low AND within 25% of high">52Wk</th>
                            <th data-sort="number" title="Weekly Return (%)&#10;Price change over last 5 trading days&#10;Green = up, Red = down">Wk Ret</th>
                            <th data-sort="string" title="Classification based on scores&#10;🟢 Ready to Buy: Fund≥52 + Tech≥18&#10;🟡 Early Re-Rating: Fund≥52 + Tech 12-17&#10;🔵 Watchlist: Fund 40-51&#10;🔴 Reject: Fund<40 or red flags">Class</th>
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
        
        # Format 52-week position
        wk52_str = f"+{r.tech.pct_from_52wk_low:.0f}%/-{r.tech.pct_from_52wk_high:.0f}%"
        
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
                            <td>{_format_return(r.fund.earnings_growth_pct)}</td>
                            <td>{_format_value(r.fund.net_gearing, "", 2)}</td>
                            <td>{_format_value(r.fund.div_yield_pct, "", 1)}</td>
                            <td>{r.tech.rs_ratio:.2f}x</td>
                            <td>{r.tech.rsi_val:.0f}</td>
                            <td>{wk52_str}</td>
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
        // Toggle strategy section
        function toggleStrategy() {
            const details = document.getElementById('strategy-details');
            const icon = document.getElementById('toggle-icon');
            const btn = document.querySelector('.toggle-btn');
            
            if (details.classList.contains('expanded')) {
                details.classList.remove('expanded');
                icon.textContent = '▶';
                btn.innerHTML = '<span id="toggle-icon">▶</span> Show Detailed Scoring Breakdown';
            } else {
                details.classList.add('expanded');
                icon.textContent = '▼';
                btn.innerHTML = '<span id="toggle-icon">▼</span> Hide Detailed Scoring Breakdown';
            }
        }
        
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
