"""
Stock Analyzer — Deep analysis of a single stock with comprehensive data gathering.

Provides:
1. Full data retrieval from all sources (yfinance, KLSE Screener, analyst data)
2. Detailed scoring breakdown with explanations
3. Industry-standard AI prompt generation for further analysis
4. Buy/Sell/Hold recommendation framework

Usage:
    python -m bursa_screener --analyze 1155.KL
    python -m bursa_screener --analyze MAYBANK --output report.md

Or programmatically:
    from bursa_screener.stock_analyzer import analyze_stock
    result = analyze_stock("1155.KL")
    print(result["prompt"])  # AI-ready prompt
    print(result["report"])  # Markdown report
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from .data_fetcher import fetch_price_history, fetch_fundamentals
from .fundamentals import score_fundamentals, FundamentalScore
from .technicals import score_technicals, TechnicalScore
from .ranker import StockResult

# KLSE Screener integration
try:
    from . import klse_fetcher
    KLSE_AVAILABLE = True
except ImportError:
    KLSE_AVAILABLE = False

console = Console()


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class StockAnalysis:
    """Complete analysis result for a single stock."""
    ticker: str
    name: str | None
    analysis_date: str
    
    # Raw data
    fundamentals: dict[str, Any]
    price_data_available: bool
    klse_data: dict[str, Any] | None
    
    # Scores
    fund_score: FundamentalScore
    tech_score: TechnicalScore
    result: StockResult
    
    # Generated content
    report_markdown: str = ""
    ai_prompt: str = ""
    summary: dict = field(default_factory=dict)
    
    @property
    def classification(self) -> str:
        return self.result.classification
    
    @property
    def total_score(self) -> int:
        return self.result.total_score
    
    @property
    def recommendation(self) -> str:
        """Generate buy/hold/sell recommendation."""
        cls = self.classification
        fs = self.fund_score.total
        ts = self.tech_score.total
        
        if cls == "READY TO BUY" and fs >= 55 and ts >= 20:
            return "STRONG BUY"
        elif cls == "READY TO BUY":
            return "BUY"
        elif cls == "EARLY RE-RATING" and fs >= 55:
            return "ACCUMULATE"
        elif cls == "EARLY RE-RATING":
            return "HOLD - Wait for Confirmation"
        elif cls == "WATCHLIST":
            return "HOLD - Monitor"
        else:
            return "AVOID"


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ANALYSIS FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_stock(
    ticker: str,
    use_cache: bool = True,
    verbose: bool = True,
) -> StockAnalysis:
    """
    Perform comprehensive analysis on a single stock.
    
    Args:
        ticker: Stock ticker (e.g., "1155.KL" or "MAYBANK")
        use_cache: Whether to use cached data
        verbose: Print progress to console
    
    Returns:
        StockAnalysis object with all data and generated content
    """
    # Normalize ticker format
    ticker = _normalize_ticker(ticker)
    analysis_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    if verbose:
        console.print(f"\n[bold blue]📊 Analyzing {ticker}...[/bold blue]\n")
    
    # ── Step 1: Fetch price data ──────────────────────────────────────────────
    if verbose:
        console.print("[dim]Fetching price history...[/dim]")
    price_df = fetch_price_history(ticker, period="1y", use_cache=use_cache)
    price_data_available = price_df is not None and len(price_df) >= 20
    
    if not price_data_available and verbose:
        console.print("[yellow]⚠ Limited price data available[/yellow]")
    
    # ── Step 2: Fetch fundamentals ────────────────────────────────────────────
    if verbose:
        console.print("[dim]Fetching fundamental data...[/dim]")
    fundamentals = fetch_fundamentals(ticker, use_cache=use_cache)
    
    # ── Step 3: Fetch KLSE data (Malaysian stocks) ────────────────────────────
    klse_data = None
    if KLSE_AVAILABLE and ticker.upper().endswith(".KL"):
        if verbose:
            console.print("[dim]Fetching KLSE Screener data...[/dim]")
        klse_data = klse_fetcher.get_klse_enhanced_data(ticker, use_cache=use_cache)
        if klse_data.get("has_klse_data") and verbose:
            console.print("[green]✓ KLSE quarterly data available[/green]")
    
    # ── Step 4: Score the stock ───────────────────────────────────────────────
    if verbose:
        console.print("[dim]Calculating scores...[/dim]")
    
    fund_score = score_fundamentals(ticker, fundamentals, None, klse_data)
    tech_score = score_technicals(ticker, price_df)
    
    # Build StockResult
    result = StockResult(
        ticker=ticker,
        long_name=fundamentals.get("long_name"),
        fund=fund_score,
        tech=tech_score,
    )
    
    # ── Step 5: Create analysis object ────────────────────────────────────────
    analysis = StockAnalysis(
        ticker=ticker,
        name=fundamentals.get("long_name"),
        analysis_date=analysis_date,
        fundamentals=fundamentals,
        price_data_available=price_data_available,
        klse_data=klse_data,
        fund_score=fund_score,
        tech_score=tech_score,
        result=result,
    )
    
    # ── Step 6: Generate summary ──────────────────────────────────────────────
    analysis.summary = _generate_summary(analysis)
    
    # ── Step 7: Generate report and prompt ────────────────────────────────────
    if verbose:
        console.print("[dim]Generating analysis report...[/dim]")
    
    analysis.report_markdown = _generate_report_markdown(analysis)
    analysis.ai_prompt = _generate_comprehensive_ai_prompt(analysis)
    
    if verbose:
        console.print(f"\n[bold green]✓ Analysis complete for {ticker}[/bold green]\n")
    
    return analysis


def _normalize_ticker(ticker: str) -> str:
    """Normalize ticker format to Bursa Malaysia format."""
    ticker = ticker.upper().strip()
    
    # Common name mappings
    NAME_MAP = {
        "MAYBANK": "1155.KL",
        "CIMB": "1023.KL",
        "PBBANK": "1295.KL",
        "TENAGA": "5347.KL",
        "IHH": "5225.KL",
        "PCHEM": "5183.KL",
        "PETRONAS": "5183.KL",
        "AXIATA": "6888.KL",
        "DIGI": "6947.KL",
        "MAXIS": "6012.KL",
        "GENTING": "3182.KL",
        "GENM": "4715.KL",
        "TOPGLOVE": "7113.KL",
        "HARTALEGA": "5168.KL",
        "NESTLE": "4707.KL",
        "HLBANK": "5819.KL",
        "RHBBANK": "1066.KL",
        "AMBANK": "1015.KL",
    }
    
    if ticker in NAME_MAP:
        return NAME_MAP[ticker]
    
    # Add .KL suffix if not present
    if not ticker.endswith(".KL"):
        ticker = f"{ticker}.KL"
    
    return ticker


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_summary(analysis: StockAnalysis) -> dict:
    """Generate a summary dict of key metrics."""
    r = analysis.result
    f = analysis.fund_score
    t = analysis.tech_score
    
    # Determine strengths and weaknesses
    strengths = []
    weaknesses = []
    
    # Check fundamentals
    if f.score_earnings_quality >= 7:
        strengths.append("Strong earnings quality")
    if f.score_earnings_growth >= 8:
        strengths.append("Excellent earnings growth")
    if f.score_roe >= 8:
        strengths.append("High return on equity")
    if f.score_financial_health >= 8:
        strengths.append("Strong balance sheet")
    if f.score_valuation >= 9:
        strengths.append("Attractive valuation")
    
    if f.score_earnings_quality <= 3:
        weaknesses.append("Poor earnings quality")
    if f.score_earnings_growth <= 2:
        weaknesses.append("Weak/negative earnings growth")
    if f.score_roe <= 3:
        weaknesses.append("Low return on equity")
    if f.score_financial_health <= 3:
        weaknesses.append("High debt concerns")
    if f.score_valuation <= 4:
        weaknesses.append("Expensive valuation")
    
    # Check technicals
    if t.total >= 20:
        strengths.append("Strong uptrend with momentum")
    elif t.total >= 15:
        strengths.append("Positive price momentum")
    
    if t.total <= 8:
        weaknesses.append("Weak price action / downtrend")
    if t.score_volume == 0:
        weaknesses.append("Low trading volume")
    
    # KLSE-specific
    if f.has_klse_data:
        if f.score_institutional_flow >= 2:
            strengths.append("Institutional buying detected")
        if f.score_insider_trading >= 2:
            strengths.append("Director/insider buying")
        if f.score_earnings_consistency >= 2:
            strengths.append("Consistent quarterly growth")
        
        if f.score_institutional_flow == 0 and f._raw_shareholding:
            weaknesses.append("Institutional selling pressure")
        if f.score_insider_trading < 0:
            weaknesses.append("Insider selling detected")
    
    return {
        "recommendation": analysis.recommendation,
        "classification": analysis.classification,
        "fundamental_score": f"{f.total}/{f.max_score}",
        "technical_score": f"{t.total}/25",
        "total_score": r.total_score,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "risk_level": _assess_risk(analysis),
        "conviction": _assess_conviction(analysis),
    }


def _assess_risk(analysis: StockAnalysis) -> str:
    """Assess overall risk level."""
    f = analysis.fund_score
    
    risk_score = 0
    
    # Financial health risk
    if f.net_gearing is not None:
        if f.net_gearing > 1.0:
            risk_score += 3
        elif f.net_gearing > 0.5:
            risk_score += 1
        elif f.net_gearing < 0:
            risk_score -= 1  # Net cash is safer
    
    # Earnings risk
    if f.earnings_growth_pct is not None and f.earnings_growth_pct < -10:
        risk_score += 2
    
    # Valuation risk
    if f.pe_ttm is not None:
        if f.pe_ttm > 30:
            risk_score += 2
        elif f.pe_ttm < 0:
            risk_score += 3  # Loss-making
    
    # Technical risk
    if analysis.tech_score.total < 10:
        risk_score += 1
    
    if risk_score <= 0:
        return "LOW"
    elif risk_score <= 2:
        return "MODERATE"
    elif risk_score <= 4:
        return "HIGH"
    else:
        return "VERY HIGH"


def _assess_conviction(analysis: StockAnalysis) -> str:
    """Assess conviction level for the recommendation."""
    f = analysis.fund_score
    t = analysis.tech_score
    
    fund_pct = f.total / f.max_score * 100
    tech_pct = t.total / 25 * 100
    
    # Both scores need to be aligned
    if fund_pct >= 75 and tech_pct >= 70:
        return "HIGH"
    elif fund_pct >= 65 and tech_pct >= 55:
        return "MEDIUM"
    elif fund_pct >= 55 or tech_pct >= 60:
        return "LOW"
    else:
        return "VERY LOW"


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_report_markdown(analysis: StockAnalysis) -> str:
    """Generate a comprehensive markdown report."""
    r = analysis.result
    f = analysis.fund_score
    t = analysis.tech_score
    s = analysis.summary
    fundamentals = analysis.fundamentals
    
    # Header
    report = f"""# 📊 Stock Analysis Report: {analysis.ticker}

**Company:** {analysis.name or 'N/A'}  
**Sector:** {f.klse_sector or f.sector or 'N/A'}  
**Analysis Date:** {analysis.analysis_date}  

---

## 🎯 Executive Summary

| Metric | Value |
|--------|-------|
| **Recommendation** | **{s['recommendation']}** |
| **Classification** | {s['classification']} |
| **Risk Level** | {s['risk_level']} |
| **Conviction** | {s['conviction']} |
| **Fundamental Score** | {s['fundamental_score']} |
| **Technical Score** | {s['technical_score']} |

"""

    # Key strengths and weaknesses
    if s['strengths']:
        report += "### ✅ Key Strengths\n"
        for strength in s['strengths']:
            report += f"- {strength}\n"
        report += "\n"
    
    if s['weaknesses']:
        report += "### ⚠️ Key Concerns\n"
        for weakness in s['weaknesses']:
            report += f"- {weakness}\n"
        report += "\n"
    
    # Helper function for safe formatting
    def _fmt(val, fmt_str=".2f", suffix="", prefix="", default="N/A"):
        """Safely format a value that might be None."""
        if val is None:
            return default
        try:
            return f"{prefix}{val:{fmt_str}}{suffix}"
        except (ValueError, TypeError):
            return str(val) if val else default
    
    # Price information
    pe_val = f.klse_pe if f.klse_pe is not None else f.pe_ttm
    pb_val = f.klse_pb if f.klse_pb is not None else f.pb
    div_val = f.klse_div_yield if f.klse_div_yield is not None else f.div_yield_pct
    
    # Safe price display
    price_display = f"RM {t.price:.3f}" if t.price is not None else "N/A"
    
    report += f"""---

## 💰 Price & Valuation

| Metric | Value | Assessment |
|--------|-------|------------|
| **Current Price** | {price_display} | - |
| **PE Ratio** | {_fmt(pe_val, '.1f', 'x')} | {_assess_pe(f.pe_ttm)} |
| **P/B Ratio** | {_fmt(pb_val, '.2f', 'x')} | {_assess_pb(f.pb)} |
| **Dividend Yield** | {_fmt(div_val, '.2f', '%')} | {_assess_div_yield(f.div_yield_pct)} |
| **52-Week Range** | {_fmt(t.pct_from_52wk_low, '+.1f', '% from low')} / {_fmt(t.pct_from_52wk_high, '.1f', '% from high', '-')} | - |

"""
    
    # Analyst targets
    if f.has_analyst_data and f.analyst_target_mean:
        report += f"""### 🎯 Analyst Targets

| Metric | Value |
|--------|-------|
| Mean Target | RM {_fmt(f.analyst_target_mean, '.2f')} |
| Upside/Downside | {_fmt(f.analyst_target_upside, '+.1f', '%')} |
| Recommendation | {f.analyst_recommendation.upper() if f.analyst_recommendation else 'N/A'} |
| Number of Analysts | {f.analyst_count or 'N/A'} |

"""
    
    # Fundamental breakdown
    report += f"""---

## 📈 Fundamental Analysis ({f.total}/{f.max_score} points)

### Score Breakdown

| Factor | Score | Max | Assessment |
|--------|-------|-----|------------|
| Earnings Quality | {f.score_earnings_quality} | 10 | {_score_assessment(f.score_earnings_quality, 10)} |
| Earnings Growth | {f.score_earnings_growth} | 10 | {_score_assessment(f.score_earnings_growth, 10)} |
| Return on Equity | {f.score_roe} | 10 | {_score_assessment(f.score_roe, 10)} |
| Financial Health | {f.score_financial_health} | 10 | {_score_assessment(f.score_financial_health, 10)} |
| Valuation | {f.score_valuation} | 12 | {_score_assessment(f.score_valuation, 12)} |
| Cash Flow | {f.score_cashflow} | 5 | {_score_assessment(f.score_cashflow, 5)} |
| Dividends | {f.score_dividends} | 3 | {_score_assessment(f.score_dividends, 3)} |
| Improving Fundamentals | {f.score_improving} | 5 | {_score_assessment(f.score_improving, 5)} |
"""
    
    if f.has_analyst_data:
        report += f"| Analyst Target | {f.score_analyst_target} | 5 | {_score_assessment(f.score_analyst_target, 5)} |\n"
    
    if f.has_klse_data:
        report += f"""| Earnings Momentum | {f.score_earnings_momentum} | 5 | {_score_assessment(f.score_earnings_momentum, 5)} |
| Earnings Consistency | {f.score_earnings_consistency} | 3 | {_score_assessment(f.score_earnings_consistency, 3)} |
| Institutional Flow | {f.score_institutional_flow} | 3 | {_score_assessment(f.score_institutional_flow, 3)} |
| Insider Trading | {f.score_insider_trading} | 3 | {_score_assessment(f.score_insider_trading, 3)} |
"""
    
    report += "\n"
    
    # Key metrics detail
    report += f"""### Key Metrics

| Metric | Value | Industry Benchmark |
|--------|-------|-------------------|
| ROE | {_fmt(f.roe_pct, '.1f', '%')} | >15% is excellent |
| Net Gearing | {_fmt(f.net_gearing, '.2f', 'x')} | <0.5 is healthy |
| Earnings Growth | {_fmt(f.earnings_growth_pct, '+.1f', '%')} | >15% is good |
| Revenue Growth | {_fmt(f.revenue_growth_pct, '+.1f', '%')} | >10% is good |

"""
    
    # KLSE quarterly data
    if f.has_klse_data and f._raw_quarterly:
        report += """### 📊 Quarterly Performance (Last 4 Quarters)

| Quarter | EPS (sen) | QoQ% | YoY% |
|---------|-----------|------|------|
"""
        for q in f._raw_quarterly[:4]:
            report += f"| {q.get('q_date', 'N/A')} | {q.get('eps', 'N/A')} | {q.get('qoq', 'N/A')}% | {q.get('yoy', 'N/A')}% |\n"
        report += "\n"
    
    # Technical analysis
    # Safe values for technical display
    ma20_display = f"{t.ma20:.3f}" if t.ma20 is not None else "N/A"
    ma50_display = f"{t.ma50:.3f}" if t.ma50 is not None else "N/A"
    ma200_display = f"{t.ma200:.3f}" if t.ma200 is not None else "N/A"
    rsi_display = f"{t.rsi_val:.0f}" if t.rsi_val is not None else "N/A"
    volume_ratio_display = f"{t.volume_ratio:.1f}" if t.volume_ratio is not None else "N/A"
    rs_ratio_display = f"{t.rs_ratio:.2f}" if t.rs_ratio is not None else "N/A"
    week_return_display = f"{t.week_return:+.2f}" if t.week_return is not None else "N/A"
    month_return_display = f"{t.month_return:+.2f}" if t.month_return is not None else "N/A"
    
    # Safe comparisons
    above_ma20 = "Above" if t.price and t.ma20 and t.price > t.ma20 else "Below"
    above_ma50 = "Above" if t.price and t.ma50 and t.price > t.ma50 else "Below"
    above_ma200 = "Above" if t.price and t.ma200 and t.price > t.ma200 else "Below"
    macd_status = "Bullish" if t.macd_val is not None and t.macd_signal is not None and t.macd_val > t.macd_signal else "Bearish"
    
    report += f"""---

## 📉 Technical Analysis ({t.total}/25 points)

**Status:** {t.status or 'N/A'}

### Score Breakdown

| Factor | Score | Max | Assessment |
|--------|-------|-----|------------|
| 20-Day MA | {t.score_20ma} | 3 | {above_ma20} MA ({ma20_display}) |
| 50-Day MA | {t.score_50ma} | 3 | {above_ma50} MA ({ma50_display}) |
| 200-Day MA | {t.score_200ma} | 3 | {above_ma200} MA ({ma200_display}) |
| RSI ({rsi_display}) | {t.score_rsi} | 2 | {_assess_rsi(t.rsi_val)} |
| MACD | {t.score_macd} | 2 | {macd_status} |
| Volume | {t.score_volume} | 3 | {volume_ratio_display}x avg volume |
| Breakout Pattern | {t.score_breakout} | 2 | {_score_assessment(t.score_breakout, 2)} |
| Support Holding | {t.score_support} | 2 | {_score_assessment(t.score_support, 2)} |
| Relative Strength | {t.score_rs} | 3 | {rs_ratio_display}x vs KLCI |
| 52-Week Position | {t.score_52wk} | 2 | {_score_assessment(t.score_52wk, 2)} |

### Price Performance

| Period | Return |
|--------|--------|
| 1 Week | {week_return_display}% |
| 1 Month | {month_return_display}% |

"""
    
    # Flags
    if f.flags:
        report += "---\n\n## 🚩 Flags & Signals\n\n"
        
        positive = [fl for fl in f.flags if any(p in fl for p in ["✓", "Net cash", "Strong", "buying", "📈", "🚀"])]
        warning = [fl for fl in f.flags if any(w in fl for w in ["⚠", "Negative", "High", "Declining", "selling"])]
        other = [fl for fl in f.flags if fl not in positive and fl not in warning]
        
        if positive:
            report += "### ✅ Positive\n"
            for fl in positive:
                report += f"- {fl}\n"
            report += "\n"
        
        if warning:
            report += "### ⚠️ Warnings\n"
            for fl in warning:
                report += f"- {fl}\n"
            report += "\n"
        
        if other:
            report += "### ℹ️ Notes\n"
            for fl in other:
                report += f"- {fl}\n"
            report += "\n"
    
    # Footer
    report += f"""---

## 📋 Action Items

Based on this analysis, here are suggested next steps:

1. **Review the AI Analysis Prompt** - Copy the generated prompt to ChatGPT/Claude for deeper insights
2. **Check Recent News** - Look for company announcements, earnings reports, or sector news
3. **Review Peer Comparison** - Compare metrics with industry peers
4. **Set Price Alerts** - Monitor key support/resistance levels
5. **Position Sizing** - If buying, consider risk-appropriate position size

---

*Report generated by Be Richer Stock Screener*  
*Analysis Date: {analysis.analysis_date}*  
*Disclaimer: This is not financial advice. Always do your own research before investing.*
"""
    
    return report


def _score_assessment(score: int, max_score: int) -> str:
    """Generate assessment text for a score."""
    pct = score / max_score * 100
    if pct >= 80:
        return "🟢 Excellent"
    elif pct >= 60:
        return "🟡 Good"
    elif pct >= 40:
        return "🟠 Average"
    else:
        return "🔴 Weak"


def _assess_pe(pe: float | None) -> str:
    if pe is None:
        return "N/A"
    if pe < 0:
        return "🔴 Loss-making"
    if pe < 10:
        return "🟢 Cheap"
    if pe < 15:
        return "🟡 Fair"
    if pe < 25:
        return "🟠 Premium"
    return "🔴 Expensive"


def _assess_pb(pb: float | None) -> str:
    if pb is None:
        return "N/A"
    if pb < 1.0:
        return "🟢 Below book value"
    if pb < 1.5:
        return "🟡 Fair"
    if pb < 3.0:
        return "🟠 Premium"
    return "🔴 Expensive"


def _assess_div_yield(dy: float | None) -> str:
    if dy is None:
        return "No dividend"
    if dy >= 5:
        return "🟢 High yield"
    if dy >= 3:
        return "🟡 Good yield"
    if dy >= 1:
        return "🟠 Modest"
    return "⚪ Low"


def _assess_rsi(rsi: float | None) -> str:
    if rsi is None:
        return "N/A"
    if rsi > 70:
        return "🟠 Overbought"
    if rsi >= 50:
        return "🟢 Bullish"
    if rsi >= 30:
        return "🟡 Neutral"
    return "🔴 Oversold"


# ═══════════════════════════════════════════════════════════════════════════════
# AI PROMPT GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_comprehensive_ai_prompt(analysis: StockAnalysis) -> str:
    """
    Generate a comprehensive, industry-standard AI prompt for deep stock analysis.
    
    This prompt includes:
    - All quantitative data available
    - Clear analysis framework
    - Specific questions to answer
    - Output format requirements
    """
    r = analysis.result
    f = analysis.fund_score
    t = analysis.tech_score
    fundamentals = analysis.fundamentals
    
    # Helper function for safe formatting of potentially None values
    def _safe(val, fmt=".2f", suffix="", prefix="", default="N/A"):
        """Safely format a value that might be None."""
        if val is None:
            return default
        try:
            if fmt.endswith("f"):
                return f"{prefix}{val:{fmt}}{suffix}"
            elif "," in fmt:
                return f"{prefix}{val:{fmt}}{suffix}"
            else:
                return f"{prefix}{val:{fmt}}{suffix}"
        except (ValueError, TypeError):
            return str(val) if val else default
    
    def _safe_int(val, default="N/A"):
        """Safely format an integer with commas."""
        if val is None:
            return default
        try:
            return f"{int(val):,}"
        except (ValueError, TypeError):
            return str(val) if val else default
    
    # Basic info
    ticker = analysis.ticker
    name = analysis.name or "Unknown"
    sector = f.klse_sector or f.sector or "Unknown"
    price = t.price if t.price else 0.0
    
    # Build data sections
    prompt = f"""You are a senior equity research analyst with 15+ years of experience analyzing Malaysian stocks. Your task is to provide a comprehensive investment analysis based on the data provided below.

═══════════════════════════════════════════════════════════════════════════════
                        STOCK ANALYSIS REQUEST
═══════════════════════════════════════════════════════════════════════════════

COMPANY OVERVIEW
────────────────────────────────────────────────────────────────────────────────
Company Name: {name}
Ticker: {ticker} (Bursa Malaysia)
Sector: {sector}
Industry: {fundamentals.get('industry', 'N/A')}
Current Price: RM {_safe(price, '.3f')}
Market Cap: RM {_safe((fundamentals.get('market_cap') or 0)/1e9, '.2f')} billion
Analysis Date: {analysis.analysis_date}

═══════════════════════════════════════════════════════════════════════════════
                        SCREENING RESULTS
═══════════════════════════════════════════════════════════════════════════════

CLASSIFICATION: {r.classification}
PRELIMINARY RECOMMENDATION: {analysis.recommendation}

SCORING SUMMARY:
┌─────────────────────────┬─────────┬─────────┬────────────┐
│ Category                │ Score   │ Maximum │ Percentage │
├─────────────────────────┼─────────┼─────────┼────────────┤
│ Fundamental Score       │ {f.total:>7} │ {f.max_score:>7} │ {f.total/f.max_score*100:>9.1f}% │
│ Technical Score         │ {t.total:>7} │      25 │ {t.total/25*100:>9.1f}% │
│ TOTAL SCORE             │ {r.total_score:>7} │ {f.max_score+25:>7} │ {r.total_score/(f.max_score+25)*100:>9.1f}% │
└─────────────────────────┴─────────┴─────────┴────────────┘

═══════════════════════════════════════════════════════════════════════════════
                     FUNDAMENTAL DATA (Business Quality)
═══════════════════════════════════════════════════════════════════════════════

FUNDAMENTAL SCORE BREAKDOWN ({f.total}/{f.max_score} points):

A. EARNINGS QUALITY ({f.score_earnings_quality}/10)
   - PE Ratio (TTM): {_safe(f.pe_ttm, '.2f', 'x')} (Sector benchmark: ~15x)
   - Forward PE: {_safe(f.forward_pe, '.2f', 'x')}
   - Interpretation: {"Undervalued" if f.pe_ttm and f.pe_ttm < 12 else "Fair value" if f.pe_ttm and f.pe_ttm < 18 else "Premium" if f.pe_ttm else "N/A"}

B. EARNINGS GROWTH ({f.score_earnings_growth}/10)
   - YoY Earnings Growth: {_safe(f.earnings_growth_pct, '+.1f', '%')}
   - YoY Revenue Growth: {_safe(f.revenue_growth_pct, '+.1f', '%')}
   - CAN SLIM Threshold: 25%+ ({"PASS ✓" if f.earnings_growth_pct and f.earnings_growth_pct >= 25 else "BELOW"})

C. RETURN ON EQUITY ({f.score_roe}/10)
   - ROE: {_safe(f.roe_pct, '.1f', '%')}
   - Buffett's Threshold: 15%+ ({"PASS ✓" if f.roe_pct and f.roe_pct >= 15 else "BELOW"})

D. FINANCIAL HEALTH ({f.score_financial_health}/10)
   - Net Gearing: {_safe(f.net_gearing, '.2f', 'x')}
   - Total Debt: RM {_safe((fundamentals.get('total_debt') or 0)/1e6, '.1f')}M
   - Total Cash: RM {_safe((fundamentals.get('total_cash') or 0)/1e6, '.1f')}M
   - Assessment: {"NET CASH ✓" if f.net_gearing is not None and f.net_gearing < 0 else "LOW DEBT ✓" if f.net_gearing is not None and f.net_gearing < 0.3 else "MODERATE DEBT" if f.net_gearing is not None and f.net_gearing < 0.7 else "HIGH DEBT ⚠" if f.net_gearing is not None else "N/A"}

E. VALUATION ({f.score_valuation}/12)
   - PE Ratio: {_safe(f.pe_ttm, '.2f', 'x')}
   - P/B Ratio: {_safe(f.pb, '.2f', 'x')}
   - Dividend Yield: {_safe(f.div_yield_pct, '.2f', '%')}

F. CASH FLOW ({f.score_cashflow}/5)
   - Operating Cash Flow: RM {_safe((fundamentals.get('operating_cash_flow') or 0)/1e6, '.1f')}M
   - FCF Yield: {"Positive" if (fundamentals.get('operating_cash_flow') or 0) > 0 else "Negative ⚠"}

G. DIVIDENDS ({f.score_dividends}/3)
   - Dividend Yield: {_safe(f.div_yield_pct, '.2f', '%')}
   - {"High yield (>5%)" if f.div_yield_pct and f.div_yield_pct >= 5 else "Good yield (3-5%)" if f.div_yield_pct and f.div_yield_pct >= 3 else "Modest/No dividend"}

H. IMPROVING FUNDAMENTALS ({f.score_improving}/5)
   - Piotroski-style momentum checks
"""

    # Add analyst data if available
    if f.has_analyst_data and f.analyst_target_mean:
        prompt += f"""
I. ANALYST CONSENSUS ({f.score_analyst_target}/5)
   - Mean Target Price: RM {_safe(f.analyst_target_mean, '.2f')}
   - Current Price: RM {_safe(price, '.2f')}
   - Implied Upside: {_safe(f.analyst_target_upside, '+.1f', '%')}
   - Recommendation: {f.analyst_recommendation.upper() if f.analyst_recommendation else 'N/A'}
   - Number of Analysts: {f.analyst_count or 'N/A'}
"""

    # Add KLSE data if available
    if f.has_klse_data:
        prompt += f"""
═══════════════════════════════════════════════════════════════════════════════
                   KLSE SCREENER DATA (Malaysian Market Source)
═══════════════════════════════════════════════════════════════════════════════

Note: KLSE Screener data is more accurate for Malaysian stocks than global data providers.

ENHANCED FUNDAMENTALS:
   - PE Ratio (KLSE): {_safe(f.klse_pe, '.2f', 'x')}
   - ROE (KLSE): {_safe(f.klse_roe, '.2f', '%')}
   - P/B (KLSE): {_safe(f.klse_pb, '.2f', 'x')}
   - Dividend Yield (KLSE): {_safe(f.klse_div_yield, '.2f', '%')}
   - Sector: {f.klse_sector or 'N/A'}

QUARTERLY PERFORMANCE:
   - Latest QoQ Growth: {_safe(f.latest_qoq, '+.1f', '%')}
   - Latest YoY Growth: {_safe(f.latest_yoy, '+.1f', '%')}

ENHANCED SCORES:
   J. Earnings Momentum: {f.score_earnings_momentum}/5 (QoQ/YoY acceleration)
   K. Earnings Consistency: {f.score_earnings_consistency}/3 (Consecutive growth quarters)
   L. Institutional Flow: {f.score_institutional_flow}/3 (EPF/KWAP/PNB activity)
   M. Insider Trading: {f.score_insider_trading}/3 (Director transactions)
"""

        # Add quarterly history
        if f._raw_quarterly and len(f._raw_quarterly) > 0:
            prompt += """
QUARTERLY HISTORY (Last 6 Quarters):
┌────────────┬──────────┬──────────┬──────────┬─────────┐
│ Quarter    │ EPS(sen) │ QoQ%     │ YoY%     │ ROE%    │
├────────────┼──────────┼──────────┼──────────┼─────────┤
"""
            for q in f._raw_quarterly[:6]:
                prompt += f"│ {q.get('q_date', 'N/A'):10} │ {str(q.get('eps', 'N/A')):>8} │ {str(q.get('qoq', 'N/A'))+('%' if q.get('qoq') else ''):>8} │ {str(q.get('yoy', 'N/A'))+('%' if q.get('yoy') else ''):>8} │ {str(q.get('roe', 'N/A'))+('%' if q.get('roe') else ''):>7} │\n"
            prompt += "└────────────┴──────────┴──────────┴──────────┴─────────┘\n"

        # Add institutional activity
        if f._raw_shareholding and len(f._raw_shareholding) > 0:
            prompt += """
INSTITUTIONAL ACTIVITY (Recent Transactions):
"""
            for txn in f._raw_shareholding[:5]:
                action = "ACQUIRED" if 'acquired' in str(txn.get('type', '')).lower() else "DISPOSED"
                # Handle shares formatting safely - could be int, float, or string
                shares_val = txn.get('shares')
                if isinstance(shares_val, (int, float)) and shares_val > 0:
                    shares_str = f"{int(shares_val):,}"
                else:
                    shares_str = str(shares_val) if shares_val else "N/A"
                name_str = str(txn.get('name', 'Unknown'))[:30]
                prompt += f"   - {txn.get('date', 'N/A')}: {name_str} {action} {shares_str} shares\n"

    # Technical data
    prompt += f"""
═══════════════════════════════════════════════════════════════════════════════
                     TECHNICAL DATA (Timing & Momentum)
═══════════════════════════════════════════════════════════════════════════════

TECHNICAL SCORE BREAKDOWN ({t.total}/25 points):

TREND ANALYSIS:
   - Price: RM {_safe(price, '.4f')}
   - 20-Day MA: RM {_safe(t.ma20, '.4f')} (Price is {"ABOVE ✓" if price and t.ma20 and price > t.ma20 else "BELOW ✗"}) - Score: {t.score_20ma}/3
   - 50-Day MA: RM {_safe(t.ma50, '.4f')} (Price is {"ABOVE ✓" if price and t.ma50 and price > t.ma50 else "BELOW ✗"}) - Score: {t.score_50ma}/3
   - 200-Day MA: RM {_safe(t.ma200, '.4f')} (Price is {"ABOVE ✓" if price and t.ma200 and price > t.ma200 else "BELOW ✗"}) - Score: {t.score_200ma}/3
   - Trend Status: {t.status or 'N/A'}

MOMENTUM INDICATORS:
   - RSI (14-period): {_safe(t.rsi_val, '.1f')} ({"Overbought >70" if t.rsi_val and t.rsi_val > 70 else "Bullish 50-70 ✓" if t.rsi_val and t.rsi_val >= 50 else "Neutral 30-50" if t.rsi_val and t.rsi_val >= 30 else "Oversold <30" if t.rsi_val else "N/A"}) - Score: {t.score_rsi}/2
   - MACD: {_safe(t.macd_val, '.4f')}
   - MACD Signal: {_safe(t.macd_signal, '.4f')}
   - MACD Status: {"BULLISH (MACD > Signal) ✓" if t.macd_val is not None and t.macd_signal is not None and t.macd_val > t.macd_signal else "BEARISH (MACD < Signal) ✗"} - Score: {t.score_macd}/2

VOLUME ANALYSIS:
   - 30-Day ADV: {_safe_int(t.adv_30d)} shares
   - Recent Volume Ratio: {_safe(t.volume_ratio, '.2f', 'x')}
   - Volume Assessment: {"Heavy accumulation ✓" if t.volume_ratio and t.volume_ratio >= 1.5 else "Above average" if t.volume_ratio and t.volume_ratio >= 1.2 else "Normal" if t.volume_ratio and t.volume_ratio >= 0.8 else "Below average" if t.volume_ratio else "N/A"} - Score: {t.score_volume}/3

PRICE PERFORMANCE:
   - 1-Week Return: {_safe(t.week_return, '+.2f', '%')}
   - 1-Month Return: {_safe(t.month_return, '+.2f', '%')}

RELATIVE STRENGTH (vs KLCI):
   - RS Ratio: {_safe(t.rs_ratio, '.2f', 'x')} ({"OUTPERFORMING ✓" if t.rs_ratio and t.rs_ratio >= 1.2 else "AT PAR" if t.rs_ratio and t.rs_ratio >= 1.0 else "UNDERPERFORMING ✗" if t.rs_ratio else "N/A"}) - Score: {t.score_rs}/3

52-WEEK POSITION (Minervini Template):
   - Above 52-Week Low: {_safe(t.pct_from_52wk_low, '+.1f', '%')} (Need >25%: {"✓" if t.pct_from_52wk_low and t.pct_from_52wk_low >= 25 else "✗"})
   - Below 52-Week High: {_safe(t.pct_from_52wk_high, '.1f', '%')} (Need <25%: {"✓" if t.pct_from_52wk_high is not None and t.pct_from_52wk_high <= 25 else "✗"})
   - In "Sweet Spot": {"YES ✓" if t.pct_from_52wk_low and t.pct_from_52wk_high is not None and t.pct_from_52wk_low >= 25 and t.pct_from_52wk_high <= 25 else "NO"} - Score: {t.score_52wk}/2

PATTERN RECOGNITION:
   - Breakout Pattern: {t.score_breakout}/2
   - Support Holding: {t.score_support}/2
"""

    # Flags
    if f.flags:
        prompt += """
═══════════════════════════════════════════════════════════════════════════════
                        FLAGS AND SIGNALS
═══════════════════════════════════════════════════════════════════════════════

"""
        positive = [fl for fl in f.flags if any(p in fl for p in ["✓", "Net cash", "Strong", "buying", "📈", "🚀"])]
        warning = [fl for fl in f.flags if any(w in fl for w in ["⚠", "Negative", "High", "Declining", "selling"])]
        other = [fl for fl in f.flags if fl not in positive and fl not in warning]
        
        if positive:
            prompt += "🟢 POSITIVE SIGNALS:\n"
            for fl in positive:
                prompt += f"   • {fl}\n"
        
        if warning:
            prompt += "\n🔴 WARNING SIGNALS:\n"
            for fl in warning:
                prompt += f"   • {fl}\n"
        
        if other:
            prompt += "\nℹ️  NOTES:\n"
            for fl in other:
                prompt += f"   • {fl}\n"

    # Analysis instructions
    prompt += """
═══════════════════════════════════════════════════════════════════════════════
                      ANALYSIS REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

Based on all the data provided above, please provide a comprehensive investment analysis covering the following sections:

─────────────────────────────────────────────────────────────────────────────
1. EXECUTIVE SUMMARY (2-3 paragraphs)
─────────────────────────────────────────────────────────────────────────────
   - What type of company is this? (Growth/Value/Dividend/Turnaround)
   - What is the main investment thesis?
   - Overall assessment in plain English for a retail investor

─────────────────────────────────────────────────────────────────────────────
2. BUSINESS QUALITY ASSESSMENT
─────────────────────────────────────────────────────────────────────────────
   - Profitability Analysis (ROE, margins, cash conversion)
   - Competitive Advantages (moat, market position)
   - Management Effectiveness (capital allocation, ROE trend)
   - Quality Rating: ★★★★★ (5-star scale) with justification

─────────────────────────────────────────────────────────────────────────────
3. GROWTH ANALYSIS
─────────────────────────────────────────────────────────────────────────────
   - Historical growth trajectory (earnings, revenue)
   - Growth drivers and sustainability
   - Industry/sector tailwinds or headwinds
   - Comparison to CAN SLIM 25% threshold
   - Growth Rating: HIGH / MODERATE / LOW / DECLINING

─────────────────────────────────────────────────────────────────────────────
4. FINANCIAL HEALTH & RISK ASSESSMENT
─────────────────────────────────────────────────────────────────────────────
   - Balance sheet strength (debt levels, liquidity)
   - Cash flow quality and sustainability
   - Key risk factors specific to this company
   - Risk Rating: LOW / MEDIUM / HIGH / VERY HIGH

─────────────────────────────────────────────────────────────────────────────
5. VALUATION ANALYSIS
─────────────────────────────────────────────────────────────────────────────
   - Current valuation vs historical averages
   - Comparison to sector peers
   - Fair value estimate (if calculable)
   - Margin of safety assessment
   - Valuation Rating: UNDERVALUED / FAIR / OVERVALUED

─────────────────────────────────────────────────────────────────────────────
6. TECHNICAL ANALYSIS & TIMING
─────────────────────────────────────────────────────────────────────────────
   - Current trend (uptrend/downtrend/sideways)
   - Key support levels to watch
   - Key resistance levels to watch
   - Optimal entry zone (price range)
   - Stop-loss recommendation
   - Timing Assessment: BUY NOW / WAIT FOR PULLBACK / AVOID

─────────────────────────────────────────────────────────────────────────────
7. INSTITUTIONAL & INSIDER SIGNALS (if data available)
─────────────────────────────────────────────────────────────────────────────
   - What is "smart money" doing?
   - Institutional buying/selling implications
   - Director/insider activity interpretation
   - Confidence Rating: HIGH / MEDIUM / LOW

─────────────────────────────────────────────────────────────────────────────
8. CATALYSTS & RISKS
─────────────────────────────────────────────────────────────────────────────
   POTENTIAL CATALYSTS (what could drive the stock higher):
   - Near-term (0-6 months)
   - Medium-term (6-12 months)
   
   KEY RISKS (what could cause decline):
   - Company-specific risks
   - Sector/macro risks
   - Valuation risks

─────────────────────────────────────────────────────────────────────────────
9. FINAL RECOMMENDATION
─────────────────────────────────────────────────────────────────────────────
   
   RATING: [STRONG BUY / BUY / HOLD / SELL / STRONG SELL]
   
   ACTION PLAN:
   ┌─────────────────────────────────────────────────────────────────────┐
   │ Entry Strategy:   [Specific guidance on when/how to enter]         │
   │ Position Size:    [% of portfolio recommendation, e.g., 2-5%]      │
   │ Target Price:     RM [X.XX] (12-month target)                      │
   │ Upside Potential: [X]%                                             │
   │ Stop Loss:        RM [X.XX] ([X]% from entry)                      │
   │ Time Horizon:     [Short/Medium/Long-term]                         │
   └─────────────────────────────────────────────────────────────────────┘

─────────────────────────────────────────────────────────────────────────────
10. KEY QUESTIONS FOR FURTHER RESEARCH
─────────────────────────────────────────────────────────────────────────────
   List 5 specific questions the investor should research before making a final decision:
   1. [Question about the business]
   2. [Question about competition]
   3. [Question about management]
   4. [Question about valuation]
   5. [Question about timing/catalysts]

═══════════════════════════════════════════════════════════════════════════════

IMPORTANT NOTES:
- This analysis is based on quantitative data only. The AI should acknowledge limitations.
- Always recommend additional qualitative research (management quality, competitive position, recent news).
- For Malaysian stocks, consider currency risks for foreign investors.
- Past performance does not guarantee future results.
- This is not personalized financial advice.

Please provide your comprehensive analysis now.
"""
    
    return prompt


# ═══════════════════════════════════════════════════════════════════════════════
# CONSOLE OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

def print_analysis(analysis: StockAnalysis) -> None:
    """Print analysis results to console in a formatted way."""
    s = analysis.summary
    f = analysis.fund_score
    t = analysis.tech_score
    
    # Header
    console.print(Panel(
        f"[bold]{analysis.name or analysis.ticker}[/bold]\n"
        f"Ticker: {analysis.ticker} | Sector: {f.klse_sector or f.sector or 'N/A'}",
        title="📊 Stock Analysis",
        border_style="blue"
    ))
    
    # Summary table
    table = Table(title="Summary", show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    
    # Color code recommendation
    rec_color = {
        "STRONG BUY": "bold green",
        "BUY": "green",
        "ACCUMULATE": "yellow",
        "HOLD - Wait for Confirmation": "yellow",
        "HOLD - Monitor": "blue",
        "AVOID": "red",
    }.get(s['recommendation'], "white")
    
    table.add_row("Recommendation", f"[{rec_color}]{s['recommendation']}[/{rec_color}]")
    table.add_row("Classification", s['classification'])
    table.add_row("Fundamental Score", s['fundamental_score'])
    table.add_row("Technical Score", s['technical_score'])
    table.add_row("Risk Level", s['risk_level'])
    table.add_row("Conviction", s['conviction'])
    
    console.print(table)
    console.print()
    
    # Strengths and weaknesses
    if s['strengths']:
        console.print("[bold green]✅ Strengths:[/bold green]")
        for strength in s['strengths']:
            console.print(f"   • {strength}")
        console.print()
    
    if s['weaknesses']:
        console.print("[bold red]⚠️ Concerns:[/bold red]")
        for weakness in s['weaknesses']:
            console.print(f"   • {weakness}")
        console.print()
    
    # Key metrics
    metrics = Table(title="Key Metrics", show_header=True)
    metrics.add_column("Metric")
    metrics.add_column("Value", justify="right")
    metrics.add_column("Assessment")
    
    # Safe price display
    price_str = f"RM {t.price:.3f}" if t.price is not None else "N/A"
    metrics.add_row("Price", price_str, "-")
    metrics.add_row("PE Ratio", f"{f.pe_ttm:.1f}x" if f.pe_ttm else "N/A", _assess_pe(f.pe_ttm))
    metrics.add_row("ROE", f"{f.roe_pct:.1f}%" if f.roe_pct else "N/A", "Good ✓" if f.roe_pct and f.roe_pct >= 15 else "Weak" if f.roe_pct else "N/A")
    metrics.add_row("Gearing", f"{f.net_gearing:.2f}x" if f.net_gearing is not None else "N/A", "Net Cash ✓" if f.net_gearing and f.net_gearing < 0 else "Healthy" if f.net_gearing and f.net_gearing < 0.5 else "High" if f.net_gearing else "N/A")
    metrics.add_row("Div Yield", f"{f.div_yield_pct:.1f}%" if f.div_yield_pct else "N/A", _assess_div_yield(f.div_yield_pct))
    
    console.print(metrics)
    console.print()


def save_analysis(analysis: StockAnalysis, output_dir: str | Path | None = None) -> dict[str, Path]:
    """
    Save analysis outputs to files.
    
    Returns dict with paths: {"report": path, "prompt": path, "json": path}
    """
    if output_dir is None:
        output_dir = Path("results")
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    base_name = f"{analysis.ticker.replace('.', '_')}_{timestamp}"
    
    paths = {}
    
    # Save markdown report
    report_path = output_dir / f"{base_name}_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(analysis.report_markdown)
    paths["report"] = report_path
    
    # Save AI prompt
    prompt_path = output_dir / f"{base_name}_ai_prompt.txt"
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(analysis.ai_prompt)
    paths["prompt"] = prompt_path
    
    # Save JSON data
    json_path = output_dir / f"{base_name}_data.json"
    json_data = {
        "ticker": analysis.ticker,
        "name": analysis.name,
        "analysis_date": analysis.analysis_date,
        "summary": analysis.summary,
        "fundamental_score": {
            "total": analysis.fund_score.total,
            "max": analysis.fund_score.max_score,
            "breakdown": analysis.fund_score.breakdown,
        },
        "technical_score": {
            "total": analysis.tech_score.total,
            "max": 25,
            "status": analysis.tech_score.status,
        },
        "classification": analysis.classification,
        "recommendation": analysis.recommendation,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, default=str)
    paths["json"] = json_path
    
    return paths


# ═══════════════════════════════════════════════════════════════════════════════
# HTML REPORT GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_html_report(analysis: StockAnalysis) -> str:
    """Generate a beautiful, comprehensive HTML report for a single stock."""
    f = analysis.fund_score
    t = analysis.tech_score
    s = analysis.summary
    
    # Helper functions
    def _safe(val, fmt=".2f", suffix="", default="N/A"):
        if val is None:
            return default
        try:
            return f"{val:{fmt}}{suffix}"
        except (ValueError, TypeError):
            return str(val) if val else default
    
    def _get_class_color(classification: str) -> tuple[str, str]:
        colors = {
            "READY TO BUY": ("#22c55e", "#000"),
            "EARLY RE-RATING": ("#eab308", "#000"),
            "WATCHLIST": ("#3b82f6", "#fff"),
            "REJECT": ("#ef4444", "#fff"),
        }
        return colors.get(classification, ("#6b7280", "#fff"))
    
    def _get_rec_color(rec: str) -> str:
        if "STRONG BUY" in rec or "BUY" in rec:
            return "#22c55e"
        elif "ACCUMULATE" in rec:
            return "#84cc16"
        elif "HOLD" in rec:
            return "#eab308"
        else:
            return "#ef4444"
    
    def _score_bar(score: int, max_score: int, label: str, color: str = "#3b82f6") -> str:
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
    
    def _metric_card(label: str, value: str, explain: str = "", status: str = "neutral") -> str:
        status_class = {
            "good": "metric-good",
            "warn": "metric-warn", 
            "bad": "metric-bad",
            "neutral": ""
        }.get(status, "")
        return f'''
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value {status_class}">{value}</div>
                <div class="metric-explain">{explain}</div>
            </div>
        '''
    
    # Classification styling
    cls_bg, cls_text = _get_class_color(analysis.classification)
    rec_color = _get_rec_color(s['recommendation'])
    
    # Score colors based on percentage
    fund_pct = f.total / f.max_score * 100
    tech_pct = t.total / 25 * 100
    fund_color = "#22c55e" if fund_pct >= 70 else "#eab308" if fund_pct >= 50 else "#ef4444"
    tech_color = "#22c55e" if tech_pct >= 70 else "#eab308" if tech_pct >= 50 else "#ef4444"
    
    # Valuation metrics with status
    pe_val = f.klse_pe if f.klse_pe is not None else f.pe_ttm
    pe_status = "good" if pe_val and 0 < pe_val < 12 else "neutral" if pe_val and pe_val < 20 else "warn" if pe_val and pe_val >= 20 else "bad" if pe_val and pe_val < 0 else "neutral"
    
    roe_status = "good" if f.roe_pct and f.roe_pct >= 15 else "neutral" if f.roe_pct and f.roe_pct >= 10 else "warn" if f.roe_pct and f.roe_pct >= 5 else "bad" if f.roe_pct else "neutral"
    
    gearing_status = "good" if f.net_gearing is not None and f.net_gearing < 0 else "good" if f.net_gearing is not None and f.net_gearing < 0.3 else "neutral" if f.net_gearing is not None and f.net_gearing < 0.7 else "bad" if f.net_gearing else "neutral"
    
    # Build HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stock Analysis - {analysis.ticker}</title>
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
        
        .container {{ max-width: 1000px; margin: 0 auto; }}
        
        /* Header */
        header {{
            text-align: center;
            padding: 30px 20px;
            background: linear-gradient(135deg, var(--bg-secondary) 0%, #1a2744 100%);
            border-radius: 20px;
            margin-bottom: 30px;
            border-left: 5px solid {cls_bg};
        }}
        
        h1 {{ font-size: 2rem; margin-bottom: 5px; }}
        .ticker {{ color: var(--blue); font-size: 1.3rem; font-weight: 600; }}
        .subtitle {{ color: var(--text-secondary); font-size: 1rem; margin-top: 10px; }}
        
        .classification-badge {{
            display: inline-block;
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 1rem;
            margin-top: 15px;
            background: {cls_bg};
            color: {cls_text};
        }}
        
        /* Summary Cards */
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        
        .summary-card {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }}
        
        .summary-label {{ font-size: 0.85rem; color: var(--text-muted); margin-bottom: 8px; }}
        .summary-value {{ font-size: 1.5rem; font-weight: 700; }}
        .summary-sub {{ font-size: 0.8rem; color: var(--text-secondary); margin-top: 5px; }}
        
        /* Section */
        .section {{
            background: var(--bg-secondary);
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 25px;
        }}
        
        .section-title {{
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
            padding-bottom: 15px;
            border-bottom: 1px solid var(--border);
        }}
        
        /* Score Gauges */
        .scores-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}
        
        .gauge-container {{
            background: var(--bg-tertiary);
            border-radius: 10px;
            padding: 15px;
        }}
        
        .gauge-label {{ font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 8px; }}
        .gauge-bar {{
            height: 10px;
            background: rgba(255,255,255,0.1);
            border-radius: 5px;
            overflow: hidden;
            margin-bottom: 8px;
        }}
        .gauge-fill {{ height: 100%; border-radius: 5px; transition: width 0.5s ease; }}
        .gauge-value {{ font-size: 1.1rem; font-weight: 600; }}
        
        /* Metrics Grid */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 12px;
        }}
        
        .metric-card {{
            background: var(--bg-tertiary);
            border-radius: 10px;
            padding: 15px;
        }}
        
        .metric-label {{ font-size: 0.8rem; color: var(--text-muted); margin-bottom: 5px; }}
        .metric-value {{ font-size: 1.2rem; font-weight: 600; margin-bottom: 5px; }}
        .metric-explain {{ font-size: 0.75rem; color: var(--text-secondary); }}
        
        .metric-good {{ color: var(--green); }}
        .metric-warn {{ color: var(--yellow); }}
        .metric-bad {{ color: var(--red); }}
        
        /* Strengths/Weaknesses */
        .swot-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        
        @media (max-width: 600px) {{
            .swot-grid {{ grid-template-columns: 1fr; }}
        }}
        
        .swot-box {{
            background: var(--bg-tertiary);
            border-radius: 12px;
            padding: 20px;
        }}
        
        .swot-title {{
            font-weight: 600;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .swot-list {{ list-style: none; }}
        .swot-list li {{
            padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            font-size: 0.9rem;
        }}
        .swot-list li:last-child {{ border-bottom: none; }}
        
        /* Flags */
        .flags {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 15px; }}
        .flag {{
            background: var(--bg-tertiary);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.8rem;
        }}
        .flag.positive {{ background: rgba(34, 197, 94, 0.2); color: #86efac; }}
        .flag.warning {{ background: rgba(239, 68, 68, 0.2); color: #fca5a5; }}
        
        /* AI Prompt Section */
        .prompt-section {{
            margin-top: 30px;
        }}
        
        .prompt-toggle {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            cursor: pointer;
            padding: 15px 20px;
            background: linear-gradient(135deg, #4c1d95 0%, #5b21b6 100%);
            border: none;
            border-radius: 12px;
            color: white;
            font-weight: 600;
            font-size: 1rem;
            width: 100%;
            transition: all 0.2s;
        }}
        
        .prompt-toggle:hover {{
            background: linear-gradient(135deg, #5b21b6 0%, #6d28d9 100%);
            transform: translateY(-2px);
        }}
        
        .prompt-content {{
            display: none;
            margin-top: 15px;
            background: var(--bg-tertiary);
            border-radius: 12px;
            padding: 20px;
        }}
        
        .prompt-content.show {{ display: block; }}
        
        .prompt-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            flex-wrap: wrap;
            gap: 10px;
        }}
        
        .prompt-text {{
            background: var(--bg-primary);
            border-radius: 8px;
            padding: 15px;
            font-family: monospace;
            font-size: 0.85rem;
            white-space: pre-wrap;
            max-height: 400px;
            overflow-y: auto;
            line-height: 1.5;
        }}
        
        .copy-btn {{
            padding: 10px 20px;
            background: var(--purple);
            border: none;
            border-radius: 8px;
            color: white;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .copy-btn:hover {{ background: #7c3aed; }}
        .copy-btn.copied {{ background: var(--green); }}
        
        /* Technical Table */
        .tech-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        
        .tech-table th, .tech-table td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        
        .tech-table th {{
            color: var(--text-muted);
            font-weight: 500;
            font-size: 0.85rem;
        }}
        
        .tech-table td {{ font-size: 0.95rem; }}
        
        .status-above {{ color: var(--green); }}
        .status-below {{ color: var(--red); }}
        
        /* Footer */
        footer {{
            text-align: center;
            padding: 20px;
            color: var(--text-muted);
            font-size: 0.85rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <h1>{analysis.name or analysis.ticker}</h1>
            <div class="ticker">{analysis.ticker}</div>
            <div class="subtitle">{f.klse_sector or f.sector or 'N/A'} | {analysis.analysis_date}</div>
            <div class="classification-badge">{analysis.classification}</div>
        </header>
        
        <!-- Summary Cards -->
        <div class="summary-grid">
            <div class="summary-card">
                <div class="summary-label">Recommendation</div>
                <div class="summary-value" style="color: {rec_color}">{s['recommendation']}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">Risk Level</div>
                <div class="summary-value">{s['risk_level']}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">Conviction</div>
                <div class="summary-value">{s['conviction']}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">Total Score</div>
                <div class="summary-value">{s['total_score']}</div>
                <div class="summary-sub">out of {f.max_score + 25}</div>
            </div>
        </div>
        
        <!-- Scores Section -->
        <div class="section">
            <div class="section-title">📊 Score Breakdown</div>
            <div class="scores-grid">
                {_score_bar(f.total, f.max_score, "Fundamental Score", fund_color)}
                {_score_bar(t.total, 25, "Technical Score", tech_color)}
            </div>
        </div>
        
        <!-- Key Metrics -->
        <div class="section">
            <div class="section-title">💰 Key Metrics</div>
            <div class="metrics-grid">
                {_metric_card("Current Price", f"RM {_safe(t.price, '.3f')}", "", "neutral")}
                {_metric_card("PE Ratio", _safe(pe_val, '.1f', 'x'), "< 12 is cheap, > 20 is expensive", pe_status)}
                {_metric_card("ROE", _safe(f.roe_pct, '.1f', '%'), "> 15% is excellent", roe_status)}
                {_metric_card("Net Gearing", _safe(f.net_gearing, '.2f', 'x'), "< 0 = net cash, < 0.5 is healthy", gearing_status)}
                {_metric_card("Dividend Yield", _safe(f.div_yield_pct, '.2f', '%'), "> 4% is high yield", "good" if f.div_yield_pct and f.div_yield_pct >= 4 else "neutral")}
                {_metric_card("Earnings Growth", _safe(f.earnings_growth_pct, '+.1f', '%'), "> 15% is strong", "good" if f.earnings_growth_pct and f.earnings_growth_pct >= 15 else "warn" if f.earnings_growth_pct and f.earnings_growth_pct >= 0 else "bad" if f.earnings_growth_pct else "neutral")}
            </div>
        </div>
        
        <!-- Technical Analysis -->
        <div class="section">
            <div class="section-title">📈 Technical Analysis</div>
            <table class="tech-table">
                <tr>
                    <th>Indicator</th>
                    <th>Value</th>
                    <th>Status</th>
                    <th>Score</th>
                </tr>
                <tr>
                    <td>Price vs 20-Day MA</td>
                    <td>RM {_safe(t.price, '.3f')} vs {_safe(t.ma20, '.3f')}</td>
                    <td class="{'status-above' if t.price and t.ma20 and t.price > t.ma20 else 'status-below'}">{'Above ✓' if t.price and t.ma20 and t.price > t.ma20 else 'Below ✗'}</td>
                    <td>{t.score_20ma}/3</td>
                </tr>
                <tr>
                    <td>Price vs 50-Day MA</td>
                    <td>RM {_safe(t.price, '.3f')} vs {_safe(t.ma50, '.3f')}</td>
                    <td class="{'status-above' if t.price and t.ma50 and t.price > t.ma50 else 'status-below'}">{'Above ✓' if t.price and t.ma50 and t.price > t.ma50 else 'Below ✗'}</td>
                    <td>{t.score_50ma}/3</td>
                </tr>
                <tr>
                    <td>Price vs 200-Day MA</td>
                    <td>RM {_safe(t.price, '.3f')} vs {_safe(t.ma200, '.3f')}</td>
                    <td class="{'status-above' if t.price and t.ma200 and t.price > t.ma200 else 'status-below'}">{'Above ✓' if t.price and t.ma200 and t.price > t.ma200 else 'Below ✗'}</td>
                    <td>{t.score_200ma}/3</td>
                </tr>
                <tr>
                    <td>RSI (14)</td>
                    <td>{_safe(t.rsi_val, '.1f')}</td>
                    <td>{'Overbought ⚠' if t.rsi_val and t.rsi_val > 70 else 'Bullish ✓' if t.rsi_val and t.rsi_val >= 50 else 'Neutral' if t.rsi_val and t.rsi_val >= 30 else 'Oversold' if t.rsi_val else 'N/A'}</td>
                    <td>{t.score_rsi}/2</td>
                </tr>
                <tr>
                    <td>MACD</td>
                    <td>{_safe(t.macd_val, '.4f')}</td>
                    <td class="{'status-above' if t.macd_val and t.macd_signal and t.macd_val > t.macd_signal else 'status-below'}">{'Bullish ✓' if t.macd_val is not None and t.macd_signal is not None and t.macd_val > t.macd_signal else 'Bearish ✗'}</td>
                    <td>{t.score_macd}/2</td>
                </tr>
                <tr>
                    <td>Volume</td>
                    <td>{_safe(t.volume_ratio, '.2f')}x avg</td>
                    <td>{'Heavy ✓' if t.volume_ratio and t.volume_ratio >= 1.5 else 'Above avg' if t.volume_ratio and t.volume_ratio >= 1.2 else 'Normal' if t.volume_ratio else 'N/A'}</td>
                    <td>{t.score_volume}/3</td>
                </tr>
                <tr>
                    <td>Relative Strength</td>
                    <td>{_safe(t.rs_ratio, '.2f')}x vs KLCI</td>
                    <td class="{'status-above' if t.rs_ratio and t.rs_ratio >= 1.0 else 'status-below'}">{'Outperforming ✓' if t.rs_ratio and t.rs_ratio >= 1.2 else 'At par' if t.rs_ratio and t.rs_ratio >= 1.0 else 'Underperforming ✗' if t.rs_ratio else 'N/A'}</td>
                    <td>{t.score_rs}/3</td>
                </tr>
            </table>
            <div style="margin-top: 15px; padding: 15px; background: var(--bg-tertiary); border-radius: 10px;">
                <strong>Trend Status:</strong> {t.status or 'N/A'} | 
                <strong>1-Week:</strong> {_safe(t.week_return, '+.2f', '%')} | 
                <strong>1-Month:</strong> {_safe(t.month_return, '+.2f', '%')}
            </div>
        </div>
        
        <!-- Strengths & Weaknesses -->
        <div class="section">
            <div class="section-title">⚖️ Strengths & Concerns</div>
            <div class="swot-grid">
                <div class="swot-box">
                    <div class="swot-title" style="color: var(--green);">✅ Strengths</div>
                    <ul class="swot-list">
                        {''.join(f'<li>{s}</li>' for s in s['strengths']) if s['strengths'] else '<li style="color: var(--text-muted);">No major strengths identified</li>'}
                    </ul>
                </div>
                <div class="swot-box">
                    <div class="swot-title" style="color: var(--red);">⚠️ Concerns</div>
                    <ul class="swot-list">
                        {''.join(f'<li>{w}</li>' for w in s['weaknesses']) if s['weaknesses'] else '<li style="color: var(--text-muted);">No major concerns identified</li>'}
                    </ul>
                </div>
            </div>
        </div>
'''
    
    # Add flags if present
    if f.flags:
        positive_flags = [fl for fl in f.flags if any(p in fl for p in ["✓", "Net cash", "Strong", "buying", "📈", "🚀"])]
        warning_flags = [fl for fl in f.flags if any(w in fl for w in ["⚠", "Negative", "High", "Declining", "selling"])]
        
        html += '''
        <div class="section">
            <div class="section-title">🚩 Flags & Signals</div>
            <div class="flags">
'''
        for fl in positive_flags:
            html += f'<span class="flag positive">{fl}</span>\n'
        for fl in warning_flags:
            html += f'<span class="flag warning">{fl}</span>\n'
        for fl in f.flags:
            if fl not in positive_flags and fl not in warning_flags:
                html += f'<span class="flag">{fl}</span>\n'
        
        html += '''
            </div>
        </div>
'''
    
    # AI Prompt Section
    escaped_prompt = analysis.ai_prompt.replace('`', '\\`').replace('${', '\\${')
    html += f'''
        <!-- AI Prompt Section -->
        <div class="prompt-section">
            <button class="prompt-toggle" onclick="togglePrompt()">
                <span>🤖</span> View AI Analysis Prompt
            </button>
            <div class="prompt-content" id="promptContent">
                <div class="prompt-header">
                    <span style="color: var(--purple); font-weight: 600;">📋 Copy this prompt to ChatGPT/Claude for deeper analysis</span>
                    <button class="copy-btn" onclick="copyPrompt()">📋 Copy Prompt</button>
                </div>
                <div class="prompt-text" id="promptText">{analysis.ai_prompt}</div>
            </div>
        </div>
        
        <!-- Footer -->
        <footer>
            <p>Generated by Be Richer Stock Screener</p>
            <p>{analysis.analysis_date}</p>
            <p style="margin-top: 10px; font-size: 0.75rem;">
                Disclaimer: This is not financial advice. Always do your own research before investing.
            </p>
        </footer>
    </div>
    
    <script>
        function togglePrompt() {{
            const content = document.getElementById('promptContent');
            content.classList.toggle('show');
        }}
        
        function copyPrompt() {{
            const text = document.getElementById('promptText').innerText;
            navigator.clipboard.writeText(text).then(() => {{
                const btn = document.querySelector('.copy-btn');
                btn.textContent = '✓ Copied!';
                btn.classList.add('copied');
                setTimeout(() => {{
                    btn.textContent = '📋 Copy Prompt';
                    btn.classList.remove('copied');
                }}, 2000);
            }});
        }}
    </script>
</body>
</html>
'''
    
    return html


def save_analysis(analysis: StockAnalysis, output_dir: str | Path | None = None) -> dict[str, Path]:
    """
    Save analysis outputs to files.
    
    Returns dict with paths: {"report": path, "prompt": path, "json": path}
    """
    if output_dir is None:
        output_dir = Path("results")
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    base_name = f"{analysis.ticker.replace('.', '_')}_{timestamp}"
    
    paths = {}
    
    # Generate and save HTML report
    html_report = _generate_html_report(analysis)
    report_path = output_dir / f"{base_name}_report.html"
    with open(report_path, "w", encoding="utf-8") as file:
        file.write(html_report)
    paths["report"] = report_path
    
    # Save AI prompt
    prompt_path = output_dir / f"{base_name}_ai_prompt.txt"
    with open(prompt_path, "w", encoding="utf-8") as file:
        file.write(analysis.ai_prompt)
    paths["prompt"] = prompt_path
    
    # Save JSON data
    json_path = output_dir / f"{base_name}_data.json"
    json_data = {
        "ticker": analysis.ticker,
        "name": analysis.name,
        "analysis_date": analysis.analysis_date,
        "summary": analysis.summary,
        "fundamental_score": {
            "total": analysis.fund_score.total,
            "max": analysis.fund_score.max_score,
            "breakdown": analysis.fund_score.breakdown,
        },
        "technical_score": {
            "total": analysis.tech_score.total,
            "max": 25,
            "status": analysis.tech_score.status,
        },
        "classification": analysis.classification,
        "recommendation": analysis.recommendation,
    }
    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(json_data, json_file, indent=2, default=str)
    paths["json"] = json_path
    
    return paths
