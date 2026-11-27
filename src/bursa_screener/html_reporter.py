"""
HTML Report Generator — creates a beautiful, beginner-friendly HTML report.

Designed for NON-TRADERS to understand:
- Clear traffic light system (green/yellow/red)
- Simple action recommendations
- Plain English explanations for every metric
- Visual gauges and progress bars
- Quick verdict cards with key takeaways
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from .ranker import StockResult

# News fetcher integration
try:
    from . import news_fetcher
    NEWS_AVAILABLE = True
except ImportError:
    NEWS_AVAILABLE = False

# i3investor integration
try:
    from . import i3investor_fetcher
    I3_AVAILABLE = True
except ImportError:
    I3_AVAILABLE = False


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
        return '<span class="na">—</span>'
    return f"{val:,.{decimals}f}{suffix}"


def _format_return(val: float | None) -> str:
    if val is None:
        return '<span class="na">—</span>'
    color = "#22c55e" if val > 0 else "#ef4444" if val < 0 else "#9ca3af"
    return f'<span style="color: {color}">{val:+.1f}%</span>'


def _get_verdict_text(r: StockResult) -> dict:
    """Generate beginner-friendly verdict text for a stock."""
    cls = r.classification
    fs = r.fundamental_score
    ts = r.technical_score
    
    if cls == "READY TO BUY":
        return {
            "action": "✅ Consider Buying",
            "action_color": "#22c55e",
            "summary": "Strong company + Price going up",
            "detail": "This stock passes both quality checks. The business is financially healthy AND the stock price is trending upward. This is the ideal combination.",
            "next_step": "Research further: Read recent news, check if the price is at a good entry point, consider your overall portfolio.",
        }
    elif cls == "EARLY RE-RATING":
        return {
            "action": "👀 Watch Closely",
            "action_color": "#eab308",
            "summary": "Strong company, but price hasn't caught up yet",
            "detail": "The business fundamentals are solid, but the stock price hasn't started its upward trend yet. This could be an early opportunity OR a 'value trap'.",
            "next_step": "Add to watchlist. Wait for price to break above resistance with increased trading volume before considering entry.",
        }
    elif cls == "WATCHLIST":
        return {
            "action": "📋 Monitor Only",
            "action_color": "#3b82f6",
            "summary": "Average company, needs improvement",
            "detail": "The fundamentals are okay but not outstanding. Wait for better earnings growth or a more attractive valuation before getting interested.",
            "next_step": "Check back in 1-2 quarters. Look for improving earnings reports or sector tailwinds.",
        }
    else:  # REJECT
        return {
            "action": "⛔ Avoid",
            "action_color": "#ef4444",
            "summary": "Warning signs detected",
            "detail": "Red flags found: weak financials, declining earnings, or high debt. Even if the price looks cheap, there's usually a good reason.",
            "next_step": "Skip this stock. Focus your time on better opportunities.",
        }


def _get_metric_explanation(metric: str, value: float | None, r: StockResult) -> str:
    """Generate plain English explanation for each metric."""
    if value is None:
        return "Data not available"
    
    explanations = {
        "pe": {
            "low": f"Trading at {value:.1f}x earnings — relatively cheap for its sector",
            "medium": f"Trading at {value:.1f}x earnings — fairly valued",
            "high": f"Trading at {value:.1f}x earnings — premium valuation, needs strong growth to justify",
            "negative": "Company is losing money (negative earnings)",
        },
        "roe": {
            "excellent": f"ROE of {value:.1f}% — excellent, management is very efficient with shareholder money",
            "good": f"ROE of {value:.1f}% — good profitability",
            "average": f"ROE of {value:.1f}% — average, room for improvement",
            "poor": f"ROE of {value:.1f}% — poor, company struggles to generate profits",
        },
        "gearing": {
            "cash": f"Net cash position ({value:.2f}) — company has more cash than debt, very safe",
            "low": f"Low debt ({value:.2f}) — healthy balance sheet",
            "moderate": f"Moderate debt ({value:.2f}) — acceptable but monitor",
            "high": f"High debt ({value:.2f}) — risky, vulnerable if business slows down",
        },
        "eps_growth": {
            "excellent": f"Earnings grew {value:+.1f}% — excellent growth, company expanding profits rapidly",
            "good": f"Earnings grew {value:+.1f}% — solid growth",
            "slow": f"Earnings grew {value:+.1f}% — slow growth",
            "negative": f"Earnings declined {value:+.1f}% — warning sign, profits shrinking",
        },
    }
    
    # PE explanation
    if metric == "pe":
        if value < 0:
            return explanations["pe"]["negative"]
        elif value < 10:
            return explanations["pe"]["low"]
        elif value < 20:
            return explanations["pe"]["medium"]
        else:
            return explanations["pe"]["high"]
    
    # ROE explanation
    elif metric == "roe":
        if value >= 15:
            return explanations["roe"]["excellent"]
        elif value >= 10:
            return explanations["roe"]["good"]
        elif value >= 5:
            return explanations["roe"]["average"]
        else:
            return explanations["roe"]["poor"]
    
    # Gearing explanation
    elif metric == "gearing":
        if value < 0:
            return explanations["gearing"]["cash"]
        elif value < 0.3:
            return explanations["gearing"]["low"]
        elif value < 0.7:
            return explanations["gearing"]["moderate"]
        else:
            return explanations["gearing"]["high"]
    
    # EPS growth explanation
    elif metric == "eps_growth":
        if value >= 25:
            return explanations["eps_growth"]["excellent"]
        elif value >= 10:
            return explanations["eps_growth"]["good"]
        elif value >= 0:
            return explanations["eps_growth"]["slow"]
        else:
            return explanations["eps_growth"]["negative"]
    
    return ""


def _get_score_gauge_html(score: int, max_score: int, label: str, color: str) -> str:
    """Generate a visual score gauge."""
    pct = min(100, (score / max_score) * 100) if max_score > 0 else 0
    return f'''
        <div class="gauge-container">
            <div class="gauge-label">{label}</div>
            <div class="gauge-bar">
                <div class="gauge-fill" style="width: {pct:.0f}%; background: {color};"></div>
            </div>
            <div class="gauge-value">{score}/{max_score}</div>
        </div>
    '''


def _generate_llm_prompt(r: StockResult, report_date: str, news_data: dict | None = None, i3_sentiment = None) -> str:
    """
    Generate a comprehensive, industry-standard LLM prompt for deep stock analysis.
    
    Includes ALL available data from yfinance, KLSE Screener, analyst consensus, i3investor, and recent news.
    Structured for professional investment analysis with clear sections and context.
    
    Args:
        r: StockResult object with fundamental and technical data
        report_date: Date string for the report
        news_data: Optional dict from news_fetcher.fetch_all_news() containing recent news
        i3_sentiment: Optional I3Sentiment from i3investor_fetcher
    """
    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 1: BASIC COMPANY INFORMATION
    # ═══════════════════════════════════════════════════════════════════════════
    ticker = r.ticker
    name = r.long_name or "Unknown"
    price = r.tech.price
    classification = r.classification
    sector = r.fund.klse_sector or r.fund.sector or "Unknown"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 2: SCREENING SCORES (Our Proprietary Analysis)
    # ═══════════════════════════════════════════════════════════════════════════
    fund_score = r.fundamental_score
    fund_max = r.fund.max_score
    tech_score = r.technical_score
    total_score = r.total_score
    
    # Fundamental score breakdown
    eq_score = r.fund.score_earnings_quality
    eg_score = r.fund.score_earnings_growth
    roe_score = r.fund.score_roe
    fh_score = r.fund.score_financial_health
    val_score = r.fund.score_valuation
    cf_score = r.fund.score_cashflow
    div_score = r.fund.score_dividends
    imp_score = r.fund.score_improving
    
    # Technical score breakdown
    ma20_score = r.tech.score_20ma
    ma50_score = r.tech.score_50ma
    ma200_score = r.tech.score_200ma
    rsi_score = r.tech.score_rsi
    macd_score = r.tech.score_macd
    vol_score = r.tech.score_volume
    breakout_score = r.tech.score_breakout
    support_score = r.tech.score_support
    rs_score = r.tech.score_rs
    pos52_score = r.tech.score_52wk
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 3: FUNDAMENTAL DATA
    # ═══════════════════════════════════════════════════════════════════════════
    # Valuation metrics
    pe = r.fund.klse_pe if r.fund.klse_pe else r.fund.pe_ttm
    pe_str = f"{pe:.2f}" if pe else "N/A"
    forward_pe = f"{r.fund.forward_pe:.2f}" if r.fund.forward_pe else "N/A"
    pb = r.fund.klse_pb if r.fund.klse_pb else r.fund.pb
    pb_str = f"{pb:.2f}" if pb else "N/A"
    
    # Profitability metrics
    roe = r.fund.klse_roe if r.fund.klse_roe else r.fund.roe_pct
    roe_str = f"{roe:.2f}%" if roe else "N/A"
    
    # Financial health
    gearing = f"{r.fund.net_gearing:.2f}" if r.fund.net_gearing is not None else "N/A"
    
    # Dividend
    div_yield = r.fund.klse_div_yield if r.fund.klse_div_yield else r.fund.div_yield_pct
    div_yield_str = f"{div_yield:.2f}%" if div_yield else "N/A"
    
    # Growth metrics
    eps_growth = f"{r.fund.earnings_growth_pct:+.2f}%" if r.fund.earnings_growth_pct else "N/A"
    rev_growth = f"{r.fund.revenue_growth_pct:+.2f}%" if r.fund.revenue_growth_pct else "N/A"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 4: TECHNICAL DATA
    # ═══════════════════════════════════════════════════════════════════════════
    ma20 = f"{r.tech.ma20:.4f}" if r.tech.ma20 else "N/A"
    ma50 = f"{r.tech.ma50:.4f}" if r.tech.ma50 else "N/A"
    ma200 = f"{r.tech.ma200:.4f}" if r.tech.ma200 else "N/A"
    rsi = f"{r.tech.rsi_val:.1f}" if r.tech.rsi_val else "N/A"
    macd_val = f"{r.tech.macd_val:.4f}" if r.tech.macd_val else "N/A"
    macd_signal = f"{r.tech.macd_signal:.4f}" if r.tech.macd_signal else "N/A"
    vol_ratio = f"{r.tech.volume_ratio:.2f}x" if r.tech.volume_ratio else "N/A"
    adv_30d = f"{r.tech.adv_30d:,.0f}" if r.tech.adv_30d else "N/A"
    week_return = f"{r.tech.week_return:+.2f}%" if r.tech.week_return else "N/A"
    month_return = f"{r.tech.month_return:+.2f}%" if r.tech.month_return else "N/A"
    tech_status = r.tech.status or "Unknown"
    rs_ratio = f"{r.tech.rs_ratio:.2f}" if r.tech.rs_ratio else "N/A"
    pct_52wk_low = f"{r.tech.pct_from_52wk_low:+.1f}%" if r.tech.pct_from_52wk_low else "N/A"
    pct_52wk_high = f"-{r.tech.pct_from_52wk_high:.1f}%" if r.tech.pct_from_52wk_high else "N/A"
    
    # MA analysis
    price_vs_ma20 = "ABOVE" if r.tech.price > r.tech.ma20 else "BELOW" if r.tech.ma20 else "N/A"
    price_vs_ma50 = "ABOVE" if r.tech.price > r.tech.ma50 else "BELOW" if r.tech.ma50 else "N/A"
    price_vs_ma200 = "ABOVE" if r.tech.price > r.tech.ma200 else "BELOW" if r.tech.ma200 else "N/A"
    
    # MACD analysis
    macd_bullish = "BULLISH (MACD > Signal)" if r.tech.macd_val > r.tech.macd_signal else "BEARISH (MACD < Signal)"
    macd_zone = "POSITIVE TERRITORY" if r.tech.macd_val > 0 else "NEGATIVE TERRITORY"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 5: KLSE SCREENER DATA (Malaysian stocks)
    # ═══════════════════════════════════════════════════════════════════════════
    klse_section = ""
    quarterly_section = ""
    institutional_section = ""
    
    if r.fund.has_klse_data:
        # Quarterly data
        qoq = f"{r.fund.latest_qoq:+.2f}%" if r.fund.latest_qoq is not None else "N/A"
        yoy = f"{r.fund.latest_yoy:+.2f}%" if r.fund.latest_yoy is not None else "N/A"
        
        # Enhanced scores from KLSE
        mom_score = r.fund.score_earnings_momentum
        cons_score = r.fund.score_earnings_consistency
        inst_score = r.fund.score_institutional_flow
        insider_score = r.fund.score_insider_trading
        
        # Format KLSE values with None handling
        klse_pe_str = f"{r.fund.klse_pe:.2f}x" if r.fund.klse_pe is not None else "N/A"
        klse_roe_str = f"{r.fund.klse_roe:.2f}%" if r.fund.klse_roe is not None else "N/A"
        klse_pb_str = f"{r.fund.klse_pb:.2f}x" if r.fund.klse_pb is not None else "N/A"
        klse_div_yield_str = f"{r.fund.klse_div_yield:.2f}%" if r.fund.klse_div_yield is not None else "N/A"
        klse_sector_str = r.fund.klse_sector if r.fund.klse_sector is not None else "N/A"
        
        klse_section = f"""
## KLSE SCREENER DATA (Malaysian Market Source)

**Data Accuracy Note:** KLSE Screener provides more accurate fundamental data for Malaysian stocks than Yahoo Finance. Use these values as the primary reference.

**Enhanced Fundamentals (from KLSE Screener):**
| Metric | Value |
|--------|-------|
| PE Ratio | {klse_pe_str} | 
| ROE | {klse_roe_str} |
| P/B Ratio | {klse_pb_str} |
| Dividend Yield | {klse_div_yield_str} |
| Sector | {klse_sector_str} |

**Latest Quarter Performance:**
| Metric | Value | Interpretation |
|--------|-------|----------------|
| QoQ Growth | {qoq} | {"📈 Positive" if r.fund.latest_qoq and r.fund.latest_qoq > 0 else "📉 Negative" if r.fund.latest_qoq else "N/A"} |
| YoY Growth | {yoy} | {"📈 Positive" if r.fund.latest_yoy and r.fund.latest_yoy > 0 else "📉 Negative" if r.fund.latest_yoy else "N/A"} |

**KLSE Enhanced Scores:**
| Factor | Score | Max | Interpretation |
|--------|-------|-----|----------------|
| Earnings Momentum | {mom_score if mom_score is not None else "N/A"} | 5 | {"Strong acceleration" if mom_score is not None and mom_score >= 4 else "Good momentum" if mom_score is not None and mom_score >= 3 else "Moderate" if mom_score is not None and mom_score >= 2 else "Weak" if mom_score is not None else "N/A"} |
| Earnings Consistency | {cons_score if cons_score is not None else "N/A"} | 3 | {f"{cons_score}+ consecutive growth quarters" if cons_score is not None and cons_score > 0 else "Inconsistent" if cons_score is not None else "N/A"} |
| Institutional Flow | {inst_score if inst_score is not None else "N/A"} | 3 | {"Net institutional buying" if inst_score is not None and inst_score >= 2 else "Mixed activity" if inst_score is not None and inst_score == 1 else "Net selling or neutral" if inst_score is not None else "N/A"} |
| Insider Trading | {insider_score if insider_score is not None else "N/A"} | 3 | {"Directors buying" if insider_score is not None and insider_score >= 2 else "Mixed" if insider_score is not None and insider_score >= 0 else "Directors selling (warning)" if insider_score is not None else "N/A"} |
"""
        
        # Detailed quarterly history
        if r.fund._raw_quarterly and len(r.fund._raw_quarterly) > 0:
            quarterly_rows = []
            for q in r.fund._raw_quarterly[:6]:  # Last 6 quarters
                q_date = q.get('q_date', 'N/A')
                q_eps = q.get('eps', 'N/A')
                q_rev = q.get('revenue', 0)
                q_profit = q.get('net_profit', 0)
                q_qoq = q.get('qoq', 'N/A')
                q_yoy = q.get('yoy', 'N/A')
                q_roe = q.get('roe', 'N/A')
                q_dps = q.get('dps', 0)
                
                # Format revenue and profit (convert to millions/billions)
                def fmt_num(n):
                    if n >= 1e9:
                        return f"RM {n/1e9:.2f}B"
                    elif n >= 1e6:
                        return f"RM {n/1e6:.1f}M"
                    return f"RM {n:,.0f}"
                
                quarterly_rows.append(f"| {q_date} | {q_eps} sen | {fmt_num(q_rev)} | {fmt_num(q_profit)} | {q_qoq}% | {q_yoy}% | {q_roe}% | {q_dps} sen |")
            
            quarterly_section = f"""
**Quarterly Financial History (Last 6 Quarters):**
| Quarter End | EPS | Revenue | Net Profit | QoQ% | YoY% | ROE | DPS |
|-------------|-----|---------|------------|------|------|-----|-----|
{chr(10).join(quarterly_rows)}
"""
        
        # Institutional activity
        if r.fund._raw_shareholding and len(r.fund._raw_shareholding) > 0:
            inst_data = _format_institutional_activity(r)
            if inst_data["has_data"]:
                net_status = "NET BUYING 🟢" if inst_data["summary"]["net_buying"] else "NET SELLING 🔴"
                acquired = inst_data["summary"]["total_acquired"]
                disposed = inst_data["summary"]["total_disposed"]
                
                txn_rows = []
                for txn in inst_data["transactions"][:8]:  # Last 8 transactions
                    action = "🟢 Acquired" if txn["is_buying"] else "🔴 Disposed"
                    txn_rows.append(f"| {txn['date']} | {txn['institution']} | {action} | {txn['shares']} |")
                
                institutional_section = f"""
**Institutional Activity ({net_status}):**
- **Total Shares Acquired:** {acquired:,}
- **Total Shares Disposed:** {disposed:,}
- **Net Change:** {acquired - disposed:+,} shares
- **Active Institutions:** {', '.join(inst_data['summary']['active_institutions'])}

**Recent Institutional Transactions:**
| Date | Institution | Action | Shares |
|------|-------------|--------|--------|
{chr(10).join(txn_rows)}

**What This Means:**
- EPF (Employees Provident Fund), KWAP (Retirement Fund), PNB (Permodalan Nasional) are government-linked institutional investors with professional research teams
- Net institutional buying = Strong confidence signal from "smart money"
- Net institutional selling = Caution warranted
"""
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 6: ANALYST CONSENSUS
    # ═══════════════════════════════════════════════════════════════════════════
    analyst_section = ""
    if r.fund.has_analyst_data and r.fund.analyst_target_mean:
        target = f"RM {r.fund.analyst_target_mean:.2f}"
        upside = r.fund.analyst_target_upside
        upside_str = f"{upside:+.2f}%" if upside else "N/A"
        rec = r.fund.analyst_recommendation or "N/A"
        num_analysts = r.fund.analyst_count or "N/A"
        
        analyst_section = f"""
## ANALYST CONSENSUS

| Metric | Value |
|--------|-------|
| Mean Target Price | {target} |
| Upside/Downside | {upside_str} |
| Current Price | RM {price:.2f} |
| Recommendation | {rec.upper()} |
| Number of Analysts | {num_analysts} |

**Interpretation:**
- Target implies stock is {"UNDERVALUED by analysts" if upside and upside > 10 else "FAIRLY VALUED" if upside and -10 <= upside <= 10 else "OVERVALUED vs targets" if upside else "N/A"}
- Analyst consensus: {rec.upper() if rec else "N/A"}
"""
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 7: FLAGS AND WARNINGS
    # ═══════════════════════════════════════════════════════════════════════════
    flags_section = ""
    if r.fund.flags:
        positive_flags = [f for f in r.fund.flags if any(p in f for p in ["✓", "Net cash", "Strong", "buying", "📈", "🚀"])]
        warning_flags = [f for f in r.fund.flags if any(w in f for w in ["⚠", "Negative", "High", "Declining", "selling"])]
        neutral_flags = [f for f in r.fund.flags if f not in positive_flags and f not in warning_flags]
        
        flags_section = """
## FLAGS AND SIGNALS
"""
        if positive_flags:
            flags_section += "\n**🟢 Positive Signals:**\n" + "\n".join([f"- {f}" for f in positive_flags])
        if warning_flags:
            flags_section += "\n\n**🔴 Warning Signals:**\n" + "\n".join([f"- {f}" for f in warning_flags])
        if neutral_flags:
            flags_section += "\n\n**ℹ️ Notes:**\n" + "\n".join([f"- {f}" for f in neutral_flags])
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 8: RECENT NEWS (if available)
    # ═══════════════════════════════════════════════════════════════════════════
    news_section = ""
    if news_data and NEWS_AVAILABLE:
        news_section = news_fetcher.format_news_for_prompt(news_data, max_items=10)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 9: i3investor SENTIMENT (Malaysian stocks)
    # ═══════════════════════════════════════════════════════════════════════════
    i3_section = ""
    if i3_sentiment and I3_AVAILABLE:
        i3_section = i3investor_fetcher.format_i3_for_prompt(i3_sentiment, limit=8)
        i3_score = i3investor_fetcher.get_i3_sentiment_score(i3_sentiment)
        i3_section += f"\n**Community Sentiment Score:** {i3_score['score']}/10 ({i3_score['signal']})\n"
        i3_section += f"**Details:** {i3_score['details']}\n"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # BUILD THE COMPLETE PROMPT
    # ═══════════════════════════════════════════════════════════════════════════
    prompt = f"""You are a professional equity research analyst. Analyze this Malaysian stock using the comprehensive data provided below and produce a detailed investment analysis report.

══════════════════════════════════════════════════════════════════════════════
STOCK ANALYSIS REQUEST
══════════════════════════════════════════════════════════════════════════════

**Company:** {name}
**Ticker:** {ticker} (Bursa Malaysia)
**Sector:** {sector}
**Current Price:** RM {price:.2f}
**Analysis Date:** {report_date}
**Screener Classification:** {classification}

---

## SCREENING SCORES (Proprietary Multi-Factor Model)

**Overall Assessment:**
| Score Type | Score | Maximum | Percentage |
|------------|-------|---------|------------|
| Fundamental Score | {fund_score} | {fund_max} | {fund_score/fund_max*100:.1f}% |
| Technical Score | {tech_score} | 25 | {tech_score/25*100:.1f}% |
| **TOTAL SCORE** | **{total_score}** | **{fund_max + 25}** | **{total_score/(fund_max+25)*100:.1f}%** |

**Fundamental Score Breakdown (Max {fund_max} pts):**
| Factor | Score | Max | Category |
|--------|-------|-----|----------|
| Earnings Quality | {eq_score} | 10 | Quality |
| Earnings Growth | {eg_score} | 10 | Growth |
| Return on Equity | {roe_score} | 10 | Profitability |
| Financial Health | {fh_score} | 10 | Safety |
| Valuation | {val_score} | 12 | Value |
| Cash Flow | {cf_score} | 5 | Quality |
| Dividends | {div_score} | 3 | Income |
| Improving Fundamentals | {imp_score} | 5 | Momentum |
| {"Analyst Target | " + str(r.fund.score_analyst_target) + " | 5 | Consensus |" if r.fund.has_analyst_data else ""}
| {"Earnings Momentum | " + str(r.fund.score_earnings_momentum) + " | 5 | KLSE Enhanced |" if r.fund.has_klse_data else ""}
| {"Earnings Consistency | " + str(r.fund.score_earnings_consistency) + " | 3 | KLSE Enhanced |" if r.fund.has_klse_data else ""}
| {"Institutional Flow | " + str(r.fund.score_institutional_flow) + " | 3 | KLSE Enhanced |" if r.fund.has_klse_data else ""}
| {"Insider Trading | " + str(r.fund.score_insider_trading) + " | 3 | KLSE Enhanced |" if r.fund.has_klse_data else ""}

**Technical Score Breakdown (Max 25 pts):**
| Factor | Score | Max | Interpretation |
|--------|-------|-----|----------------|
| 20-Day MA | {ma20_score} | 3 | {"Bullish" if ma20_score >= 2 else "Neutral" if ma20_score == 1 else "Bearish"} |
| 50-Day MA | {ma50_score} | 3 | {"Bullish" if ma50_score >= 2 else "Neutral" if ma50_score == 1 else "Bearish"} |
| 200-Day MA | {ma200_score} | 3 | {"Bullish" if ma200_score >= 2 else "Neutral" if ma200_score == 1 else "Bearish"} |
| RSI (14) | {rsi_score} | 2 | {"Bullish" if rsi_score >= 1 else "Weak"} |
| MACD | {macd_score} | 2 | {"Bullish" if macd_score >= 1 else "Bearish"} |
| Volume | {vol_score} | 3 | {"Strong accumulation" if vol_score >= 2 else "Normal" if vol_score == 1 else "Weak"} |
| Breakout Pattern | {breakout_score} | 2 | {"Near highs" if breakout_score >= 1 else "No pattern"} |
| Support Holding | {support_score} | 2 | {"Strong support" if support_score >= 1 else "Breaking down"} |
| Relative Strength | {rs_score} | 3 | {"Outperforming" if rs_score >= 2 else "In-line" if rs_score == 1 else "Underperforming"} |
| 52-Week Position | {pos52_score} | 2 | {"Sweet spot" if pos52_score >= 1 else "Poor position"} |

**Technical Status:** {tech_status}

---

## FUNDAMENTAL DATA

**Valuation Metrics:**
| Metric | Value | Sector Benchmark | Assessment |
|--------|-------|------------------|------------|
| P/E Ratio (TTM) | {pe_str}x | ~12-15x (Banks) | {"Undervalued" if pe and pe < 12 else "Fair" if pe and pe <= 18 else "Premium" if pe else "N/A"} |
| Forward P/E | {forward_pe}x | - | - |
| P/B Ratio | {pb_str}x | ~1.0-1.5x (Banks) | {"Undervalued" if pb and pb < 1.0 else "Fair" if pb and pb <= 1.5 else "Premium" if pb else "N/A"} |

**Profitability Metrics:**
| Metric | Value | Good Threshold | Assessment |
|--------|-------|----------------|------------|
| Return on Equity (ROE) | {roe_str} | >15% | {"Excellent" if roe and roe >= 15 else "Good" if roe and roe >= 10 else "Average" if roe and roe >= 5 else "Poor" if roe else "N/A"} |
| EPS Growth (YoY) | {eps_growth} | >15% | {"Strong" if r.fund.earnings_growth_pct and r.fund.earnings_growth_pct >= 15 else "Moderate" if r.fund.earnings_growth_pct and r.fund.earnings_growth_pct > 0 else "Negative" if r.fund.earnings_growth_pct else "N/A"} |
| Revenue Growth (YoY) | {rev_growth} | >10% | {"Strong" if r.fund.revenue_growth_pct and r.fund.revenue_growth_pct >= 10 else "Moderate" if r.fund.revenue_growth_pct and r.fund.revenue_growth_pct > 0 else "Negative" if r.fund.revenue_growth_pct else "N/A"} |

**Financial Health:**
| Metric | Value | Risk Level |
|--------|-------|------------|
| Net Gearing (D/E) | {gearing} | {"Low Risk (Net Cash)" if r.fund.net_gearing and r.fund.net_gearing < 0 else "Low Risk" if r.fund.net_gearing and r.fund.net_gearing < 0.3 else "Moderate" if r.fund.net_gearing and r.fund.net_gearing < 0.7 else "High Risk" if r.fund.net_gearing else "N/A"} |
| Dividend Yield | {div_yield_str} | {"High yield" if div_yield and div_yield > 5 else "Good yield" if div_yield and div_yield > 3 else "Low yield" if div_yield else "N/A"} |

---

## TECHNICAL DATA

**Price vs Moving Averages:**
| Moving Average | Value | Price Position | Trend Signal |
|----------------|-------|----------------|--------------|
| Current Price | RM {price:.4f} | - | - |
| 20-Day MA | {ma20} | {price_vs_ma20} | {"Bullish" if price_vs_ma20 == "ABOVE" else "Bearish"} |
| 50-Day MA | {ma50} | {price_vs_ma50} | {"Bullish" if price_vs_ma50 == "ABOVE" else "Bearish"} |
| 200-Day MA | {ma200} | {price_vs_ma200} | {"Bullish" if price_vs_ma200 == "ABOVE" else "Bearish"} |

**Momentum Indicators:**
| Indicator | Value | Zone | Signal |
|-----------|-------|------|--------|
| RSI (14-period) | {rsi} | {"Overbought" if r.tech.rsi_val and r.tech.rsi_val > 70 else "Bullish" if r.tech.rsi_val and r.tech.rsi_val > 50 else "Bearish" if r.tech.rsi_val and r.tech.rsi_val > 30 else "Oversold" if r.tech.rsi_val else "N/A"} | {"Caution" if r.tech.rsi_val and r.tech.rsi_val > 70 else "Buy" if r.tech.rsi_val and 50 <= r.tech.rsi_val <= 70 else "Neutral" if r.tech.rsi_val and 30 <= r.tech.rsi_val < 50 else "Potential bottom" if r.tech.rsi_val else "N/A"} |
| MACD Line | {macd_val} | {macd_zone} | {macd_bullish} |
| MACD Signal | {macd_signal} | - | - |

**Volume Analysis:**
| Metric | Value | Interpretation |
|--------|-------|----------------|
| 30-Day ADV | {adv_30d} shares | Average daily trading volume |
| Recent Volume Ratio | {vol_ratio} | {"Heavy accumulation" if r.tech.volume_ratio and r.tech.volume_ratio >= 1.5 else "Above average" if r.tech.volume_ratio and r.tech.volume_ratio >= 1.2 else "Normal" if r.tech.volume_ratio and r.tech.volume_ratio >= 0.8 else "Below average" if r.tech.volume_ratio else "N/A"} |

**Price Performance:**
| Period | Return | Assessment |
|--------|--------|------------|
| 1-Week | {week_return} | {"Strong" if r.tech.week_return and r.tech.week_return > 3 else "Positive" if r.tech.week_return and r.tech.week_return > 0 else "Negative" if r.tech.week_return else "N/A"} |
| 1-Month | {month_return} | {"Strong" if r.tech.month_return and r.tech.month_return > 5 else "Positive" if r.tech.month_return and r.tech.month_return > 0 else "Negative" if r.tech.month_return else "N/A"} |

**Relative Strength & Position:**
| Metric | Value | Assessment |
|--------|-------|------------|
| RS vs KLCI Index | {rs_ratio}x | {"Strong outperformance" if r.tech.rs_ratio and r.tech.rs_ratio >= 1.5 else "Outperforming" if r.tech.rs_ratio and r.tech.rs_ratio >= 1.2 else "In-line" if r.tech.rs_ratio and r.tech.rs_ratio >= 0.9 else "Underperforming" if r.tech.rs_ratio else "N/A"} |
| % Above 52-Week Low | {pct_52wk_low} | - |
| % Below 52-Week High | {pct_52wk_high} | - |
{klse_section}
{quarterly_section}
{institutional_section}
{analyst_section}
{flags_section}
{news_section}
{i3_section}

---

## ANALYSIS INSTRUCTIONS

Please provide a comprehensive investment analysis covering:

### 1. EXECUTIVE SUMMARY (2-3 sentences)
Summarize the key investment thesis in plain language.

### 2. BUSINESS QUALITY ASSESSMENT
- Evaluate profitability (ROE, margins)
- Assess earnings quality and growth trajectory
- Compare to sector peers
- Rate: Excellent / Good / Average / Poor

### 3. VALUATION ANALYSIS
- Is the stock cheap or expensive based on PE, PB?
- Compare to historical averages and sector benchmarks
- Calculate intrinsic value estimate if possible
- Rate: Undervalued / Fair Value / Overvalued

### 4. GROWTH ANALYSIS
- Analyze earnings and revenue growth trends
- Review quarterly progression (if KLSE data available)
- Assess sustainability of growth
- Rate: High Growth / Moderate Growth / Stable / Declining

### 5. FINANCIAL HEALTH & RISK ASSESSMENT
- Evaluate debt levels (gearing)
- Assess cash flow quality
- Identify key risk factors
- Rate: Low Risk / Medium Risk / High Risk

### 6. TECHNICAL ANALYSIS
- Trend direction (uptrend/downtrend/sideways)
- Key support and resistance levels
- Entry timing recommendation
- Rate: Bullish / Neutral / Bearish

### 7. INSTITUTIONAL & INSIDER ACTIVITY (if available)
- Interpret institutional buying/selling patterns
- What does smart money activity suggest?
- Any concerning insider selling?

### 8. CATALYST ASSESSMENT
- What could drive the stock higher in next 6-12 months?
- What risks could cause a decline?
- Any sector tailwinds or headwinds?

### 9. FINAL RECOMMENDATION
Provide a clear rating:
- **STRONG BUY** (High conviction, significant upside)
- **BUY** (Positive outlook, good risk/reward)
- **HOLD** (Fair value, wait for better entry)
- **SELL** (Overvalued or deteriorating fundamentals)
- **STRONG SELL** (Significant downside risk)

Include:
- Target price (12-month)
- Stop-loss level
- Position sizing recommendation (% of portfolio)

### 10. KEY QUESTIONS TO RESEARCH FURTHER
List 3-5 specific questions the investor should investigate before making a decision.

---

**Note:** This analysis is based on quantitative data and recent news. The AI should acknowledge limitations and recommend additional qualitative research (management quality, competitive position, industry trends).
"""

    return prompt


def _escape_html(text: str) -> str:
    """Escape HTML special characters in prompt text."""
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _format_institutional_activity(r: StockResult) -> dict:
    """
    Format institutional activity data for display.
    
    Returns:
        {
            "has_data": bool,
            "transactions": [
                {
                    "date": "24 Nov 2026",
                    "institution": "KWAP",
                    "full_name": "KUMPULAN WANG PERSARAAN...",
                    "action": "Acquired" / "Disposed",
                    "shares": "216,600",
                    "shares_num": 216600,
                    "is_buying": True/False,
                }
            ],
            "summary": {
                "net_buying": True/False,
                "total_acquired": 1234567,
                "total_disposed": 567890,
                "active_institutions": ["EPF", "KWAP", "PNB"],
            }
        }
    """
    result = {
        "has_data": False,
        "transactions": [],
        "summary": {
            "net_buying": False,
            "total_acquired": 0,
            "total_disposed": 0,
            "active_institutions": [],
        }
    }
    
    if not r.fund.has_klse_data:
        return result
    
    # Get raw shareholding data from the KLSE data
    # Note: This requires access to the raw data, which we'll need to pass through
    shareholding = getattr(r.fund, '_raw_shareholding', None)
    if not shareholding:
        return result
    
    result["has_data"] = True
    
    # Institution short names mapping
    INSTITUTION_MAP = {
        "KWAP": "KWAP",
        "KUMPULAN WANG PERSARAAN": "KWAP",
        "EPF": "EPF",
        "EMPLOYEES PROVIDENT FUND": "EPF",
        "PNB": "PNB",
        "PERMODALAN NASIONAL": "PNB",
        "AMANAH SAHAM": "ASB/PNB",
        "AMANAHRAYA": "ASB/PNB",
        "TABUNG HAJI": "TH",
        "LEMBAGA TABUNG HAJI": "TH",
        "LEMBAGA TABUNG ANGKATAN TENTERA": "LTAT",
    }
    
    total_acquired = 0
    total_disposed = 0
    seen_institutions = set()
    
    for txn in shareholding[:8]:  # Last 8 transactions
        holder = txn.get("holder", "").upper()
        txn_type = txn.get("transaction_type", "").lower()
        shares_str = txn.get("shares", "0")
        date = txn.get("date", "")
        
        # Parse shares to number
        try:
            shares_num = int(shares_str.replace(",", ""))
        except (ValueError, AttributeError):
            shares_num = 0
        
        # Determine institution short name
        inst_short = None
        for key, short in INSTITUTION_MAP.items():
            if key in holder:
                inst_short = short
                break
        
        if not inst_short:
            # Unknown institution, use first few words
            inst_short = " ".join(holder.split()[:2])[:20]
        
        is_buying = "acquired" in txn_type or "bought" in txn_type
        
        if is_buying:
            total_acquired += shares_num
        else:
            total_disposed += shares_num
        
        seen_institutions.add(inst_short)
        
        result["transactions"].append({
            "date": date,
            "institution": inst_short,
            "full_name": txn.get("holder", "")[:50],
            "action": "Acquired" if is_buying else "Disposed",
            "shares": shares_str,
            "shares_num": shares_num,
            "is_buying": is_buying,
        })
    
    result["summary"]["total_acquired"] = total_acquired
    result["summary"]["total_disposed"] = total_disposed
    result["summary"]["net_buying"] = total_acquired > total_disposed
    result["summary"]["active_institutions"] = list(seen_institutions)
    
    return result


def generate_html_report(
    results: list[StockResult],
    universe_size: int,
    elapsed: float,
    tier: str = "klci",
    show_rejected: bool = False,
    output_dir: str = "results",
) -> str:
    """Generate a beginner-friendly HTML report."""
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
    
    # Check data sources
    has_klse = any(r.fund.has_klse_data for r in results)
    has_analyst = any(r.fund.has_analyst_data for r in results)
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stock Screener Report - {ts.strftime("%Y-%m-%d")}</title>
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
            --purple: #8b5cf6;
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 20px;
        }}
        
        .container {{ max-width: 1200px; margin: 0 auto; }}
        
        /* Header */
        header {{
            text-align: center;
            padding: 30px 20px;
            background: linear-gradient(135deg, var(--bg-secondary) 0%, #1a2744 100%);
            border-radius: 20px;
            margin-bottom: 30px;
        }}
        
        h1 {{ font-size: 2.2rem; margin-bottom: 10px; }}
        .subtitle {{ color: var(--text-secondary); font-size: 1.1rem; }}
        
        .meta-pills {{
            display: flex;
            justify-content: center;
            gap: 12px;
            margin-top: 20px;
            flex-wrap: wrap;
        }}
        
        .pill {{
            background: rgba(255,255,255,0.1);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.9rem;
        }}
        
        /* Quick Summary */
        .quick-summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        
        .summary-card {{
            background: var(--bg-secondary);
            border-radius: 16px;
            padding: 25px;
            text-align: center;
            border: 2px solid transparent;
            transition: transform 0.2s, border-color 0.2s;
        }}
        
        .summary-card:hover {{ transform: translateY(-4px); }}
        .summary-card.ready {{ border-color: var(--green); }}
        .summary-card.early {{ border-color: var(--yellow); }}
        .summary-card.watchlist {{ border-color: var(--blue); }}
        .summary-card.reject {{ border-color: var(--red); }}
        
        .card-icon {{ font-size: 3rem; margin-bottom: 15px; }}
        .card-count {{ font-size: 3rem; font-weight: 700; margin-bottom: 5px; }}
        .card-label {{ font-size: 1.1rem; color: var(--text-secondary); margin-bottom: 10px; }}
        .card-desc {{ font-size: 0.85rem; color: var(--text-muted); }}
        
        .summary-card.ready .card-count {{ color: var(--green); }}
        .summary-card.early .card-count {{ color: var(--yellow); }}
        .summary-card.watchlist .card-count {{ color: var(--blue); }}
        .summary-card.reject .card-count {{ color: var(--red); }}
        
        /* How to Read Section */
        .how-to-read {{
            background: linear-gradient(135deg, #1a365d 0%, var(--bg-secondary) 100%);
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 40px;
            border: 1px solid rgba(59, 130, 246, 0.3);
        }}
        
        .how-title {{
            font-size: 1.4rem;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .steps-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
        }}
        
        .step {{
            background: rgba(0,0,0,0.2);
            border-radius: 12px;
            padding: 20px;
        }}
        
        .step-number {{
            width: 36px;
            height: 36px;
            background: var(--blue);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            margin-bottom: 12px;
        }}
        
        .step-title {{ font-size: 1.1rem; font-weight: 600; margin-bottom: 8px; }}
        .step-desc {{ font-size: 0.9rem; color: var(--text-secondary); line-height: 1.6; }}
        
        /* Stock Cards */
        .stock-section {{
            margin-bottom: 40px;
        }}
        
        .section-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid var(--border);
        }}
        
        .section-icon {{ font-size: 1.8rem; }}
        .section-title {{ font-size: 1.5rem; font-weight: 600; }}
        .section-count {{
            background: var(--bg-tertiary);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.9rem;
        }}
        
        .stock-card {{
            background: var(--bg-secondary);
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 20px;
            border-left: 4px solid;
        }}
        
        .stock-card.ready {{ border-left-color: var(--green); }}
        .stock-card.early {{ border-left-color: var(--yellow); }}
        .stock-card.watchlist {{ border-left-color: var(--blue); }}
        .stock-card.reject {{ border-left-color: var(--red); }}
        
        .stock-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 15px;
        }}
        
        .stock-info h3 {{ font-size: 1.3rem; margin-bottom: 5px; }}
        .stock-info .ticker {{ color: var(--blue); font-weight: 600; }}
        .stock-info .name {{ color: var(--text-secondary); font-size: 0.95rem; }}
        
        .verdict-box {{
            padding: 12px 20px;
            border-radius: 10px;
            text-align: center;
        }}
        
        .verdict-action {{
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        
        .verdict-summary {{
            font-size: 0.85rem;
            opacity: 0.9;
        }}
        
        /* Score Gauges */
        .scores-section {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        
        .gauge-container {{
            background: var(--bg-tertiary);
            border-radius: 10px;
            padding: 15px;
        }}
        
        .gauge-label {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 8px;
        }}
        
        .gauge-bar {{
            height: 8px;
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 6px;
        }}
        
        .gauge-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s ease;
        }}
        
        .gauge-value {{
            font-size: 1.1rem;
            font-weight: 600;
        }}
        
        /* Key Metrics */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 12px;
            margin-bottom: 20px;
        }}
        
        .metric-card {{
            background: var(--bg-tertiary);
            border-radius: 10px;
            padding: 15px;
        }}
        
        .metric-label {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-bottom: 4px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        
        .metric-value {{
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 4px;
        }}
        
        .metric-explain {{
            font-size: 0.75rem;
            color: var(--text-secondary);
            line-height: 1.4;
        }}
        
        .metric-good {{ color: var(--green); }}
        .metric-warn {{ color: var(--yellow); }}
        .metric-bad {{ color: var(--red); }}
        
        /* Recommendation Box */
        .recommendation {{
            background: rgba(59, 130, 246, 0.1);
            border: 1px solid rgba(59, 130, 246, 0.3);
            border-radius: 12px;
            padding: 20px;
        }}
        
        .rec-title {{
            font-weight: 600;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .rec-text {{
            font-size: 0.9rem;
            color: var(--text-secondary);
            line-height: 1.6;
        }}
        
        /* Flags */
        .flags {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 15px;
        }}
        
        .flag {{
            background: var(--bg-tertiary);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.8rem;
        }}
        
        .flag.warning {{
            background: rgba(239, 68, 68, 0.2);
            color: #fca5a5;
        }}
        
        .flag.positive {{
            background: rgba(34, 197, 94, 0.2);
            color: #86efac;
        }}
        
        /* LLM Prompt Section */
        .llm-prompt-section {{
            margin-top: 20px;
            border-top: 1px solid var(--border);
            padding-top: 20px;
        }}
        
        .llm-prompt-toggle {{
            display: flex;
            align-items: center;
            gap: 10px;
            cursor: pointer;
            padding: 12px 16px;
            background: linear-gradient(135deg, #4c1d95 0%, #5b21b6 100%);
            border: none;
            border-radius: 10px;
            color: white;
            font-weight: 600;
            font-size: 0.95rem;
            transition: all 0.2s;
            width: 100%;
            justify-content: center;
        }}
        
        .llm-prompt-toggle:hover {{
            background: linear-gradient(135deg, #5b21b6 0%, #6d28d9 100%);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(91, 33, 182, 0.3);
        }}
        
        .llm-prompt-toggle .icon {{
            font-size: 1.2rem;
        }}
        
        .llm-prompt-content {{
            display: none;
            margin-top: 15px;
            background: var(--bg-tertiary);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid var(--border);
        }}
        
        .llm-prompt-content.show {{
            display: block;
        }}
        
        .llm-prompt-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            flex-wrap: wrap;
            gap: 10px;
        }}
        
        .llm-prompt-title {{
            font-weight: 600;
            color: var(--purple);
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .llm-prompt-actions {{
            display: flex;
            gap: 10px;
        }}
        
        .copy-btn {{
            padding: 8px 16px;
            background: var(--purple);
            border: none;
            border-radius: 8px;
            color: white;
            font-weight: 600;
            font-size: 0.85rem;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s;
        }}
        
        .copy-btn:hover {{
            background: #7c3aed;
            transform: translateY(-1px);
        }}
        
        .copy-btn.copied {{
            background: var(--green);
        }}
        
        .llm-prompt-text {{
            background: var(--bg-primary);
            border-radius: 8px;
            padding: 15px;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 0.8rem;
            line-height: 1.6;
            color: var(--text-secondary);
            max-height: 400px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-break: break-word;
        }}
        
        .llm-prompt-text::-webkit-scrollbar {{
            width: 8px;
        }}
        
        .llm-prompt-text::-webkit-scrollbar-track {{
            background: var(--bg-secondary);
            border-radius: 4px;
        }}
        
        .llm-prompt-text::-webkit-scrollbar-thumb {{
            background: var(--border);
            border-radius: 4px;
        }}
        
        .llm-tips {{
            margin-top: 15px;
            padding: 12px;
            background: rgba(139, 92, 246, 0.1);
            border-radius: 8px;
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}
        
        .llm-tips strong {{
            color: var(--purple);
        }}
        
        /* Institutional Activity Section */
        .institutional-section {{
            margin-top: 20px;
            background: var(--bg-tertiary);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid var(--border);
        }}
        
        .institutional-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            flex-wrap: wrap;
            gap: 10px;
        }}
        
        .institutional-title {{
            font-weight: 600;
            font-size: 1.1rem;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .institutional-summary {{
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }}
        
        .summary-pill {{
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }}
        
        .summary-pill.buying {{
            background: rgba(34, 197, 94, 0.2);
            color: #86efac;
        }}
        
        .summary-pill.selling {{
            background: rgba(239, 68, 68, 0.2);
            color: #fca5a5;
        }}
        
        .transaction-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        
        .transaction-table th {{
            padding: 10px 12px;
            text-align: left;
            font-size: 0.8rem;
            color: var(--text-muted);
            font-weight: 600;
            border-bottom: 1px solid var(--border);
        }}
        
        .transaction-table td {{
            padding: 10px 12px;
            font-size: 0.85rem;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }}
        
        .transaction-table tr:hover {{
            background: rgba(255,255,255,0.03);
        }}
        
        .txn-date {{
            color: var(--text-muted);
            white-space: nowrap;
        }}
        
        .txn-institution {{
            font-weight: 600;
            color: var(--blue);
        }}
        
        .txn-action {{
            font-weight: 600;
            white-space: nowrap;
        }}
        
        .txn-action.buy {{
            color: var(--green);
        }}
        
        .txn-action.sell {{
            color: var(--red);
        }}
        
        .txn-shares {{
            text-align: right;
            font-family: 'Monaco', monospace;
            font-size: 0.8rem;
        }}
        
        .institutional-note {{
            margin-top: 15px;
            padding: 10px;
            background: rgba(59, 130, 246, 0.1);
            border-radius: 8px;
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}
        
        /* Simple Table */
        .simple-table {{
            overflow-x: auto;
            margin-top: 30px;
        }}
        
        .simple-table table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        .simple-table th {{
            background: var(--bg-tertiary);
            padding: 15px 12px;
            text-align: left;
            font-weight: 600;
            font-size: 0.9rem;
            cursor: pointer;
            white-space: nowrap;
        }}
        
        .simple-table th:hover {{ background: #3d4f69; }}
        
        .simple-table td {{
            padding: 12px;
            border-bottom: 1px solid var(--border);
            font-size: 0.9rem;
        }}
        
        .simple-table tr:hover {{ background: var(--bg-secondary); }}
        
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        
        .badge-ready {{ background: var(--green); color: #000; }}
        .badge-early {{ background: var(--yellow); color: #000; }}
        .badge-watchlist {{ background: var(--blue); color: #fff; }}
        .badge-reject {{ background: var(--red); color: #fff; }}
        
        /* Tooltip */
        .info-tip {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 16px;
            height: 16px;
            background: var(--text-muted);
            border-radius: 50%;
            font-size: 10px;
            color: var(--bg-primary);
            cursor: help;
        }}
        
        /* Footer */
        footer {{
            text-align: center;
            padding: 30px;
            margin-top: 40px;
            border-top: 1px solid var(--border);
            color: var(--text-muted);
            font-size: 0.85rem;
        }}
        
        footer a {{ color: var(--blue); text-decoration: none; }}
        
        /* Responsive */
        @media (max-width: 768px) {{
            body {{ padding: 10px; }}
            h1 {{ font-size: 1.6rem; }}
            .stock-header {{ flex-direction: column; }}
            .metrics-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
        
        /* Print styles */
        @media print {{
            body {{ background: white; color: black; }}
            .stock-card {{ break-inside: avoid; }}
        }}
        
        /* Expand/Collapse Section Styles */
        .expandable-section {{
            margin-top: 10px;
        }}
        
        .expand-btn {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            width: 100%;
            padding: 15px 20px;
            margin-top: 10px;
            background: linear-gradient(135deg, var(--bg-tertiary) 0%, var(--bg-secondary) 100%);
            border: 1px dashed var(--border);
            border-radius: 12px;
            color: var(--text-secondary);
            font-weight: 600;
            font-size: 0.95rem;
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        
        .expand-btn:hover {{
            background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-tertiary) 100%);
            border-color: var(--blue);
            color: var(--blue);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
        }}
        
        .expand-btn .expand-icon {{
            transition: transform 0.3s ease;
            font-size: 0.9rem;
        }}
        
        .expand-btn.expanded .expand-icon {{
            transform: rotate(180deg);
        }}
        
        /* Flags expand styles */
        .flags-container {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 15px;
            align-items: center;
        }}
        
        .flags-toggle {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 0.8rem;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .flags-toggle:hover {{
            background: var(--bg-secondary);
            border-color: var(--blue);
            color: var(--blue);
        }}
        
        .flags-hidden {{
            display: none;
        }}
        
        .flags-hidden.show {{
            display: contents;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 Bursa Malaysia Stock Screener</h1>
            <p class="subtitle">Automated analysis to help you find quality stocks</p>
            <div class="meta-pills">
                <span class="pill">📅 {ts.strftime("%d %b %Y, %I:%M %p")}</span>
                <span class="pill">🔍 {universe_size} stocks analyzed</span>
                <span class="pill">⏱️ {elapsed:.0f} seconds</span>
                <span class="pill">📈 {tier.upper()}</span>
            </div>
        </header>
        
        <!-- Quick Summary Cards -->
        <section class="quick-summary">
            <div class="summary-card ready">
                <div class="card-icon">✅</div>
                <div class="card-count">{len(ready)}</div>
                <div class="card-label">Ready to Buy</div>
                <div class="card-desc">Strong company + Price going up. Best candidates!</div>
            </div>
            <div class="summary-card early">
                <div class="card-icon">👀</div>
                <div class="card-count">{len(early)}</div>
                <div class="card-label">Watch Closely</div>
                <div class="card-desc">Good company, price hasn't caught up yet.</div>
            </div>
            <div class="summary-card watchlist">
                <div class="card-icon">📋</div>
                <div class="card-count">{len(watchlist)}</div>
                <div class="card-label">Monitor</div>
                <div class="card-desc">Average. Wait for improvement.</div>
            </div>
            <div class="summary-card reject">
                <div class="card-icon">⛔</div>
                <div class="card-count">{len(rejected)}</div>
                <div class="card-label">Avoid</div>
                <div class="card-desc">Warning signs detected. Skip these.</div>
            </div>
        </section>
        
        <!-- How to Read This Report -->
        <section class="how-to-read">
            <h2 class="how-title">📖 How to Read This Report (60-second guide)</h2>
            <div class="steps-grid">
                <div class="step">
                    <div class="step-number">1</div>
                    <div class="step-title">Check the Color 🚦</div>
                    <div class="step-desc">
                        <strong>Green (✅)</strong> = Best candidates<br>
                        <strong>Yellow (👀)</strong> = Promising, needs confirmation<br>
                        <strong>Blue (📋)</strong> = Wait and watch<br>
                        <strong>Red (⛔)</strong> = Avoid
                    </div>
                </div>
                <div class="step">
                    <div class="step-number">2</div>
                    <div class="step-title">Look at Two Scores 📊</div>
                    <div class="step-desc">
                        <strong>Business Score</strong> = Is the company healthy?<br>
                        <strong>Momentum Score</strong> = Is the stock price going up?<br>
                        You want BOTH to be high.
                    </div>
                </div>
                <div class="step">
                    <div class="step-number">3</div>
                    <div class="step-title">Read the Verdict 📝</div>
                    <div class="step-desc">
                        Each stock has a plain-English explanation of why it's rated that way and what to do next.
                    </div>
                </div>
                <div class="step">
                    <div class="step-number">4</div>
                    <div class="step-title">Check the Flags ⚠️</div>
                    <div class="step-desc">
                        Warning flags highlight potential problems. Green flags show positive signs. These help you dig deeper.
                    </div>
                </div>
            </div>
        </section>
'''

    # Generate stock cards for each category
    def _generate_stock_card(r: StockResult, show_detail: bool = True, news_data: dict | None = None, i3_sentiment = None) -> str:
        verdict = _get_verdict_text(r)
        cls_lower = r.classification.lower().replace(" ", "-").replace("to-", "")
        badge_class = {
            "READY TO BUY": "badge-ready",
            "EARLY RE-RATING": "badge-early", 
            "WATCHLIST": "badge-watchlist",
            "REJECT": "badge-reject",
        }.get(r.classification, "badge-watchlist")
        
        # Determine metric colors
        pe_color = "metric-good" if r.fund.pe_ttm and 0 < r.fund.pe_ttm < 15 else ("metric-bad" if r.fund.pe_ttm and r.fund.pe_ttm < 0 else "")
        roe_color = "metric-good" if r.fund.roe_pct and r.fund.roe_pct >= 15 else ("metric-bad" if r.fund.roe_pct and r.fund.roe_pct < 5 else "")
        gearing_color = "metric-good" if r.fund.net_gearing and r.fund.net_gearing < 0.3 else ("metric-bad" if r.fund.net_gearing and r.fund.net_gearing > 0.7 else "")
        growth_color = "metric-good" if r.fund.earnings_growth_pct and r.fund.earnings_growth_pct > 10 else ("metric-bad" if r.fund.earnings_growth_pct and r.fund.earnings_growth_pct < 0 else "")
        
        # Analyst target
        analyst_html = ""
        if r.fund.has_analyst_data and r.fund.analyst_target_mean:
            upside = r.fund.analyst_target_upside or 0
            upside_color = "metric-good" if upside > 10 else ("metric-bad" if upside < -10 else "")
            analyst_html = f'''
                <div class="metric-card">
                    <div class="metric-label">🎯 Analyst Target</div>
                    <div class="metric-value">RM {r.fund.analyst_target_mean:.2f}</div>
                    <div class="metric-explain {upside_color}">{upside:+.1f}% from current price</div>
                </div>
            '''
        
        # KLSE quarterly data
        klse_html = ""
        if r.fund.has_klse_data and (r.fund.latest_qoq is not None or r.fund.latest_yoy is not None):
            qoq = r.fund.latest_qoq or 0
            yoy = r.fund.latest_yoy or 0
            qoq_color = "metric-good" if qoq > 5 else ("metric-bad" if qoq < -5 else "")
            yoy_color = "metric-good" if yoy > 10 else ("metric-bad" if yoy < -10 else "")
            klse_html = f'''
                <div class="metric-card">
                    <div class="metric-label">📈 Quarterly Growth</div>
                    <div class="metric-value {qoq_color}">{qoq:+.1f}% QoQ</div>
                    <div class="metric-explain {yoy_color}">{yoy:+.1f}% vs last year</div>
                </div>
            '''
        
        # Generate flags with expand functionality
        flags_html = ""
        if r.fund.flags:
            # Generate unique ID for this stock's flags
            flags_id = f"flags-{r.ticker.replace('.', '_')}"
            
            # Visible flags (first 3)
            visible_items = []
            for flag in r.fund.flags[:3]:
                is_warning = any(w in flag for w in ["⚠", "Negative", "High", "Declining", "selling"])
                is_positive = any(p in flag for p in ["✓", "Net cash", "Strong", "buying", "📈", "🚀"])
                css_class = "warning" if is_warning else ("positive" if is_positive else "")
                visible_items.append(f'<span class="flag {css_class}">{flag}</span>')
            
            # Hidden flags (rest)
            hidden_items = []
            for flag in r.fund.flags[3:]:
                is_warning = any(w in flag for w in ["⚠", "Negative", "High", "Declining", "selling"])
                is_positive = any(p in flag for p in ["✓", "Net cash", "Strong", "buying", "📈", "🚀"])
                css_class = "warning" if is_warning else ("positive" if is_positive else "")
                hidden_items.append(f'<span class="flag {css_class}">{flag}</span>')
            
            # Build HTML
            if len(r.fund.flags) > 3:
                remaining = len(r.fund.flags) - 3
                flags_html = f'''<div class="flags-container">
                    {"".join(visible_items)}
                    <span class="flags-hidden" id="{flags_id}">{"".join(hidden_items)}</span>
                    <button class="flags-toggle" onclick="toggleFlags('{flags_id}', this)">
                        <span>▼</span> +{remaining} more
                    </button>
                </div>'''
            else:
                flags_html = f'<div class="flags">{"".join(visible_items)}</div>'
        
        # Generate institutional activity section
        institutional_html = ""
        if r.fund.has_klse_data and r.fund._raw_shareholding:
            inst_data = _format_institutional_activity(r)
            if inst_data["has_data"] and len(inst_data["transactions"]) > 0:
                # Generate summary pills
                net_status = "buying" if inst_data["summary"]["net_buying"] else "selling"
                net_label = "🟢 Net Buying" if inst_data["summary"]["net_buying"] else "🔴 Net Selling"
                acquired = inst_data["summary"]["total_acquired"]
                disposed = inst_data["summary"]["total_disposed"]
                
                # Format large numbers
                def fmt_shares(n):
                    if n >= 1_000_000:
                        return f"{n/1_000_000:.1f}M"
                    elif n >= 1_000:
                        return f"{n/1_000:.0f}K"
                    return str(n)
                
                # Generate transaction rows
                txn_rows = ""
                for txn in inst_data["transactions"][:6]:  # Show up to 6 transactions
                    action_class = "buy" if txn["is_buying"] else "sell"
                    action_icon = "🟢" if txn["is_buying"] else "🔴"
                    txn_rows += f'''
                        <tr>
                            <td class="txn-date">{txn["date"]}</td>
                            <td class="txn-institution" title="{txn["full_name"]}">{txn["institution"]}</td>
                            <td class="txn-action {action_class}">{action_icon} {txn["action"]}</td>
                            <td class="txn-shares">{txn["shares"]}</td>
                        </tr>
                    '''
                
                institutional_html = f'''
            <div class="institutional-section">
                <div class="institutional-header">
                    <div class="institutional-title">
                        <span>🏦</span>
                        <span>Smart Money Activity (EPF, KWAP, PNB...)</span>
                    </div>
                    <div class="institutional-summary">
                        <span class="summary-pill {net_status}">{net_label}</span>
                    </div>
                </div>
                <table class="transaction-table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Institution</th>
                            <th>Action</th>
                            <th style="text-align: right;">Shares</th>
                        </tr>
                    </thead>
                    <tbody>
                        {txn_rows}
                    </tbody>
                </table>
                <div class="institutional-note">
                    💡 <strong>What this means:</strong> EPF (Employees Provident Fund), KWAP (Retirement Fund), and PNB (Permodalan Nasional) are institutional investors with professional research teams. 
                    When they buy, it often signals confidence in the company. Net buying = bullish signal; Net selling = caution.
                </div>
            </div>
            '''
        
        card_html = f'''
        <div class="stock-card {cls_lower.split('-')[0] if '-' not in cls_lower else cls_lower.replace('early-re-rating', 'early').replace('ready-buy', 'ready')}">
            <div class="stock-header">
                <div class="stock-info">
                    <h3><span class="ticker">{r.ticker}</span></h3>
                    <div class="name">{r.long_name or "Unknown"}</div>
                    <div style="margin-top: 8px; font-size: 1.2rem; font-weight: 600;">RM {r.tech.price:.2f}</div>
                </div>
                <div class="verdict-box" style="background: {verdict['action_color']}20; border: 1px solid {verdict['action_color']};">
                    <div class="verdict-action" style="color: {verdict['action_color']}">{verdict['action']}</div>
                    <div class="verdict-summary">{verdict['summary']}</div>
                </div>
            </div>
            
            <div class="scores-section">
                {_get_score_gauge_html(r.fundamental_score, r.fund.max_score, "💼 Business Health", "#8b5cf6")}
                {_get_score_gauge_html(r.technical_score, 25, "📈 Price Momentum", "#06b6d4")}
                {_get_score_gauge_html(r.total_score, r.fund.max_score + 25, "🏆 Overall Score", "#22c55e")}
            </div>
            
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">💰 PE Ratio</div>
                    <div class="metric-value {pe_color}">{_format_value(r.fund.pe_ttm, "x", 1)}</div>
                    <div class="metric-explain">{_get_metric_explanation("pe", r.fund.pe_ttm, r)}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">📊 Return on Equity</div>
                    <div class="metric-value {roe_color}">{_format_value(r.fund.roe_pct, "%", 1)}</div>
                    <div class="metric-explain">{_get_metric_explanation("roe", r.fund.roe_pct, r)}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">🏦 Debt Level</div>
                    <div class="metric-value {gearing_color}">{_format_value(r.fund.net_gearing, "", 2)}</div>
                    <div class="metric-explain">{_get_metric_explanation("gearing", r.fund.net_gearing, r)}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">🚀 Earnings Growth</div>
                    <div class="metric-value {growth_color}">{_format_return(r.fund.earnings_growth_pct)}</div>
                    <div class="metric-explain">{_get_metric_explanation("eps_growth", r.fund.earnings_growth_pct, r)}</div>
                </div>
                {analyst_html}
                {klse_html}
            </div>
            
            <div class="recommendation">
                <div class="rec-title">💡 What This Means For You</div>
                <div class="rec-text">
                    {verdict['detail']}<br><br>
                    <strong>Next step:</strong> {verdict['next_step']}
                </div>
            </div>
            
            {institutional_html}
            
            {flags_html}
            
            <!-- LLM Deep Analysis Prompt -->
            <div class="llm-prompt-section">
                <button class="llm-prompt-toggle" onclick="togglePrompt('{r.ticker.replace('.', '_')}')">
                    <span class="icon">🤖</span>
                    <span>Get AI Deep Analysis Prompt</span>
                    <span class="icon">▼</span>
                </button>
                <div id="prompt-{r.ticker.replace('.', '_')}" class="llm-prompt-content">
                    <div class="llm-prompt-header">
                        <div class="llm-prompt-title">
                            <span>🤖</span>
                            <span>Copy this prompt to ChatGPT, Claude, or any AI assistant</span>
                        </div>
                        <div class="llm-prompt-actions">
                            <button class="copy-btn" onclick="copyPrompt('{r.ticker.replace('.', '_')}')">
                                <span>📋</span>
                                <span>Copy Prompt</span>
                            </button>
                        </div>
                    </div>
                    <div class="llm-prompt-text" id="prompt-text-{r.ticker.replace('.', '_')}">{_escape_html(_generate_llm_prompt(r, ts.strftime("%Y-%m-%d"), news_data, i3_sentiment))}</div>
                    <div class="llm-tips">
                        <strong>💡 Tip:</strong> Paste this prompt into ChatGPT, Claude, Gemini, or any AI assistant for a detailed investment analysis. 
                        The AI will analyze fundamentals, valuation, technicals, and provide actionable recommendations.
                    </div>
                </div>
            </div>
        </div>
        '''
        return card_html

    # Ready to Buy section
    # ═══════════════════════════════════════════════════════════════════════════
    # NEWS FETCHING - Fetch news for non-REJECT stocks to include in AI prompts
    # Only fetch for Ready to Buy, Early Re-Rating, and Watchlist to minimize API calls
    # ═══════════════════════════════════════════════════════════════════════════
    news_cache: dict[str, dict] = {}  # Cache news data by ticker
    i3_cache: dict = {}  # Cache i3investor data by ticker
    
    def _get_news_for_stock(ticker: str) -> dict | None:
        """Fetch and cache news for a stock."""
        if not NEWS_AVAILABLE:
            return None
        if ticker in news_cache:
            return news_cache[ticker]
        try:
            news_data = news_fetcher.fetch_all_news(ticker, use_cache=True)
            news_cache[ticker] = news_data
            return news_data
        except Exception:
            return None
    
    def _get_i3_for_stock(ticker: str):
        """Fetch and cache i3investor sentiment for a stock."""
        if not I3_AVAILABLE:
            return None
        if ticker in i3_cache:
            return i3_cache[ticker]
        try:
            i3_data = i3investor_fetcher.fetch_i3investor_sentiment(ticker)
            i3_cache[ticker] = i3_data
            return i3_data
        except Exception:
            return None
    
    if ready:
        html += f'''
        <section class="stock-section">
            <div class="section-header">
                <span class="section-icon">✅</span>
                <span class="section-title">Ready to Buy</span>
                <span class="section-count">{len(ready)} stocks</span>
            </div>
'''
        # Show first 5 cards
        for r in ready[:5]:
            stock_news = _get_news_for_stock(r.ticker)
            stock_i3 = _get_i3_for_stock(r.ticker)
            html += _generate_stock_card(r, news_data=stock_news, i3_sentiment=stock_i3)
        
        # If more than 5, add expandable section
        if len(ready) > 5:
            remaining_count = len(ready) - 5
            html += f'''
            <div class="expandable-section" id="ready-expanded" style="display: none;">
'''
            for r in ready[5:]:
                stock_news = _get_news_for_stock(r.ticker)
                stock_i3 = _get_i3_for_stock(r.ticker)
                html += _generate_stock_card(r, news_data=stock_news, i3_sentiment=stock_i3)
            html += '''
            </div>
            <button class="expand-btn" onclick="toggleExpandSection('ready-expanded', this)">
                <span class="expand-icon">▼</span>
                <span class="expand-text">Show {remaining} more stocks</span>
            </button>
'''.replace('{remaining}', str(remaining_count))
        html += '''
        </section>
'''

    # Early Re-Rating section
    if early:
        html += f'''
        <section class="stock-section">
            <div class="section-header">
                <span class="section-icon">👀</span>
                <span class="section-title">Watch Closely</span>
                <span class="section-count">{len(early)} stocks</span>
            </div>
'''
        # Show first 5 cards
        for r in early[:5]:
            stock_news = _get_news_for_stock(r.ticker)
            stock_i3 = _get_i3_for_stock(r.ticker)
            html += _generate_stock_card(r, news_data=stock_news, i3_sentiment=stock_i3)
        
        # If more than 5, add expandable section
        if len(early) > 5:
            remaining_count = len(early) - 5
            html += f'''
            <div class="expandable-section" id="early-expanded" style="display: none;">
'''
            for r in early[5:]:
                stock_news = _get_news_for_stock(r.ticker)
                stock_i3 = _get_i3_for_stock(r.ticker)
                html += _generate_stock_card(r, news_data=stock_news, i3_sentiment=stock_i3)
            html += '''
            </div>
            <button class="expand-btn" onclick="toggleExpandSection('early-expanded', this)">
                <span class="expand-icon">▼</span>
                <span class="expand-text">Show {remaining} more stocks</span>
            </button>
'''.replace('{remaining}', str(remaining_count))
        html += '''
        </section>
'''

    # Watchlist section
    if watchlist:
        html += f'''
        <section class="stock-section">
            <div class="section-header">
                <span class="section-icon">📋</span>
                <span class="section-title">Monitor Only</span>
                <span class="section-count">{len(watchlist)} stocks</span>
            </div>
'''
        # Show first 3 cards
        for r in watchlist[:3]:
            stock_news = _get_news_for_stock(r.ticker)
            stock_i3 = _get_i3_for_stock(r.ticker)
            html += _generate_stock_card(r, news_data=stock_news, i3_sentiment=stock_i3)
        
        # If more than 3, add expandable section
        if len(watchlist) > 3:
            remaining_count = len(watchlist) - 3
            html += f'''
            <div class="expandable-section" id="watchlist-expanded" style="display: none;">
'''
            for r in watchlist[3:]:
                stock_news = _get_news_for_stock(r.ticker)
                stock_i3 = _get_i3_for_stock(r.ticker)
                html += _generate_stock_card(r, news_data=stock_news, i3_sentiment=stock_i3)
            html += '''
            </div>
            <button class="expand-btn" onclick="toggleExpandSection('watchlist-expanded', this)">
                <span class="expand-icon">▼</span>
                <span class="expand-text">Show {remaining} more stocks</span>
            </button>
'''.replace('{remaining}', str(remaining_count))
        html += '''
        </section>
'''

    # Simple summary table
    html += '''
        <section class="simple-table">
            <h2 style="margin-bottom: 20px;">📋 All Stocks Summary</h2>
            <p style="color: var(--text-muted); margin-bottom: 15px; font-size: 0.9rem;">
                Click any column header to sort. Scroll right for more data →
            </p>
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Name</th>
                        <th>Price (RM)</th>
                        <th>Business Score</th>
                        <th>Momentum</th>
                        <th>PE</th>
                        <th>ROE %</th>
                        <th>Debt</th>
                        <th>Week %</th>
'''
    if has_analyst:
        html += '<th>Analyst Target</th>'
    html += '''
                        <th>Verdict</th>
                    </tr>
                </thead>
                <tbody>
'''
    
    for r in display_results:
        badge_class = {
            "READY TO BUY": "badge-ready",
            "EARLY RE-RATING": "badge-early",
            "WATCHLIST": "badge-watchlist",
            "REJECT": "badge-reject",
        }.get(r.classification, "badge-watchlist")
        
        analyst_cell = ""
        if has_analyst:
            if r.fund.has_analyst_data and r.fund.analyst_target_mean:
                upside = r.fund.analyst_target_upside or 0
                analyst_cell = f'<td>RM {r.fund.analyst_target_mean:.2f} ({upside:+.0f}%)</td>'
            else:
                analyst_cell = '<td style="color: var(--text-muted);">—</td>'
        
        html += f'''
                    <tr>
                        <td style="font-weight: 600; color: var(--blue);">{r.ticker}</td>
                        <td style="max-width: 150px; overflow: hidden; text-overflow: ellipsis;">{(r.long_name or "")[:20]}</td>
                        <td>{r.tech.price:.2f}</td>
                        <td>{r.fundamental_score}/{r.fund.max_score}</td>
                        <td>{r.technical_score}/25</td>
                        <td>{_format_value(r.fund.pe_ttm, "", 1)}</td>
                        <td>{_format_value(r.fund.roe_pct, "", 1)}</td>
                        <td>{_format_value(r.fund.net_gearing, "", 2)}</td>
                        <td>{_format_return(r.tech.week_return)}</td>
                        {analyst_cell}
                        <td><span class="badge {badge_class}">{_get_class_emoji(r.classification)} {r.classification.split()[0]}</span></td>
                    </tr>
'''
    
    html += '''
                </tbody>
            </table>
        </section>
        
        <footer>
            <p><strong>Be Richer</strong> — Bursa Malaysia Stock Screener</p>
            <p style="margin: 10px 0;">
                Data sources: Yahoo Finance (15-min delayed) • KLSE Screener (quarterly data) • Analyst consensus
            </p>
            <p style="font-size: 0.8rem; color: var(--text-muted);">
                ⚠️ This is an automated screening tool for educational purposes. 
                Always do your own research before investing. Past performance doesn't guarantee future results.
            </p>
        </footer>
    </div>
    
    <script>
        // Toggle LLM prompt visibility
        function togglePrompt(tickerId) {
            const content = document.getElementById('prompt-' + tickerId);
            const btn = content.previousElementSibling;
            if (content.classList.contains('show')) {
                content.classList.remove('show');
                btn.querySelector('.icon:last-child').textContent = '▼';
            } else {
                content.classList.add('show');
                btn.querySelector('.icon:last-child').textContent = '▲';
            }
        }
        
        // Copy prompt to clipboard
        function copyPrompt(tickerId) {
            const textElement = document.getElementById('prompt-text-' + tickerId);
            const btn = event.currentTarget;
            const text = textElement.textContent;
            
            navigator.clipboard.writeText(text).then(() => {
                btn.classList.add('copied');
                btn.querySelector('span:last-child').textContent = 'Copied!';
                setTimeout(() => {
                    btn.classList.remove('copied');
                    btn.querySelector('span:last-child').textContent = 'Copy Prompt';
                }, 2000);
            }).catch(err => {
                // Fallback for older browsers
                const textarea = document.createElement('textarea');
                textarea.value = text;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                btn.classList.add('copied');
                btn.querySelector('span:last-child').textContent = 'Copied!';
                setTimeout(() => {
                    btn.classList.remove('copied');
                    btn.querySelector('span:last-child').textContent = 'Copy Prompt';
                }, 2000);
            });
        }
        
        // Simple table sorting
        document.querySelectorAll('th').forEach((th, idx) => {
            th.addEventListener('click', () => {
                const table = th.closest('table');
                const tbody = table.querySelector('tbody');
                const rows = Array.from(tbody.querySelectorAll('tr'));
                const isAsc = th.dataset.sorted === 'asc';
                
                // Clear all sorted states
                table.querySelectorAll('th').forEach(h => delete h.dataset.sorted);
                th.dataset.sorted = isAsc ? 'desc' : 'asc';
                
                rows.sort((a, b) => {
                    let aVal = a.children[idx].textContent.trim();
                    let bVal = b.children[idx].textContent.trim();
                    
                    // Try numeric comparison
                    const aNum = parseFloat(aVal.replace(/[^0-9.-]/g, ''));
                    const bNum = parseFloat(bVal.replace(/[^0-9.-]/g, ''));
                    
                    if (!isNaN(aNum) && !isNaN(bNum)) {
                        return isAsc ? bNum - aNum : aNum - bNum;
                    }
                    return isAsc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
                });
                
                rows.forEach(row => tbody.appendChild(row));
            });
        });
        
        // Toggle expand/collapse for card sections
        function toggleExpandSection(sectionId, btn) {
            const section = document.getElementById(sectionId);
            const textSpan = btn.querySelector('.expand-text');
            
            if (section.style.display === 'none') {
                section.style.display = 'block';
                btn.classList.add('expanded');
                textSpan.textContent = 'Show less';
            } else {
                section.style.display = 'none';
                btn.classList.remove('expanded');
                // Restore original text from data attribute or default
                const originalCount = btn.dataset.originalCount || '';
                textSpan.textContent = 'Show ' + originalCount + ' more stocks';
            }
        }
        
        // Initialize expand buttons with original count
        document.querySelectorAll('.expand-btn').forEach(btn => {
            const textSpan = btn.querySelector('.expand-text');
            if (textSpan) {
                const match = textSpan.textContent.match(/Show (\\d+) more/);
                if (match) {
                    btn.dataset.originalCount = match[1];
                }
            }
        });
        
        // Toggle flags expand/collapse
        function toggleFlags(flagsId, btn) {
            const hiddenFlags = document.getElementById(flagsId);
            if (hiddenFlags.classList.contains('show')) {
                hiddenFlags.classList.remove('show');
                btn.innerHTML = '<span>▼</span> Show more';
            } else {
                hiddenFlags.classList.add('show');
                btn.innerHTML = '<span>▲</span> Show less';
            }
        }
    </script>
</body>
</html>
'''
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    
    return str(path)
