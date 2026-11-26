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
    
    # Price information
    report += f"""---

## 💰 Price & Valuation

| Metric | Value | Assessment |
|--------|-------|------------|
| **Current Price** | RM {t.price:.3f} | - |
| **PE Ratio** | {f.klse_pe or f.pe_ttm:.1f}x | {_assess_pe(f.pe_ttm)} |
| **P/B Ratio** | {f.klse_pb or f.pb:.2f}x | {_assess_pb(f.pb)} |
| **Dividend Yield** | {f.klse_div_yield or f.div_yield_pct:.2f}% | {_assess_div_yield(f.div_yield_pct)} |
| **52-Week Range** | {t.pct_from_52wk_low:+.1f}% from low / -{t.pct_from_52wk_high:.1f}% from high | - |

"""
    
    # Analyst targets
    if f.has_analyst_data and f.analyst_target_mean:
        report += f"""### 🎯 Analyst Targets

| Metric | Value |
|--------|-------|
| Mean Target | RM {f.analyst_target_mean:.2f} |
| Upside/Downside | {f.analyst_target_upside:+.1f}% |
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
| ROE | {f.roe_pct:.1f}% | >15% is excellent |
| Net Gearing | {f.net_gearing:.2f}x | <0.5 is healthy |
| Earnings Growth | {f.earnings_growth_pct:+.1f}% | >15% is good |
| Revenue Growth | {f.revenue_growth_pct:+.1f}% | >10% is good |

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
    report += f"""---

## 📉 Technical Analysis ({t.total}/25 points)

**Status:** {t.status}

### Score Breakdown

| Factor | Score | Max | Assessment |
|--------|-------|-----|------------|
| 20-Day MA | {t.score_20ma} | 3 | {"Above" if t.price > t.ma20 else "Below"} MA ({t.ma20:.3f}) |
| 50-Day MA | {t.score_50ma} | 3 | {"Above" if t.price > t.ma50 else "Below"} MA ({t.ma50:.3f}) |
| 200-Day MA | {t.score_200ma} | 3 | {"Above" if t.price > t.ma200 else "Below"} MA ({t.ma200:.3f}) |
| RSI ({t.rsi_val:.0f}) | {t.score_rsi} | 2 | {_assess_rsi(t.rsi_val)} |
| MACD | {t.score_macd} | 2 | {"Bullish" if t.macd_val > t.macd_signal else "Bearish"} |
| Volume | {t.score_volume} | 3 | {t.volume_ratio:.1f}x avg volume |
| Breakout Pattern | {t.score_breakout} | 2 | {_score_assessment(t.score_breakout, 2)} |
| Support Holding | {t.score_support} | 2 | {_score_assessment(t.score_support, 2)} |
| Relative Strength | {t.score_rs} | 3 | {t.rs_ratio:.2f}x vs KLCI |
| 52-Week Position | {t.score_52wk} | 2 | {_score_assessment(t.score_52wk, 2)} |

### Price Performance

| Period | Return |
|--------|--------|
| 1 Week | {t.week_return:+.2f}% |
| 1 Month | {t.month_return:+.2f}% |

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
    
    # Basic info
    ticker = analysis.ticker
    name = analysis.name or "Unknown"
    sector = f.klse_sector or f.sector or "Unknown"
    price = t.price
    
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
Current Price: RM {price:.3f}
Market Cap: RM {fundamentals.get('market_cap', 0)/1e9:.2f} billion
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
   - PE Ratio (TTM): {f.pe_ttm:.2f}x (Sector benchmark: ~15x)
   - Forward PE: {f.forward_pe:.2f}x
   - Interpretation: {"Undervalued" if f.pe_ttm and f.pe_ttm < 12 else "Fair value" if f.pe_ttm and f.pe_ttm < 18 else "Premium" if f.pe_ttm else "N/A"}

B. EARNINGS GROWTH ({f.score_earnings_growth}/10)
   - YoY Earnings Growth: {f.earnings_growth_pct:+.1f}%
   - YoY Revenue Growth: {f.revenue_growth_pct:+.1f}%
   - CAN SLIM Threshold: 25%+ ({"PASS ✓" if f.earnings_growth_pct and f.earnings_growth_pct >= 25 else "BELOW"})

C. RETURN ON EQUITY ({f.score_roe}/10)
   - ROE: {f.roe_pct:.1f}%
   - Buffett's Threshold: 15%+ ({"PASS ✓" if f.roe_pct and f.roe_pct >= 15 else "BELOW"})

D. FINANCIAL HEALTH ({f.score_financial_health}/10)
   - Net Gearing: {f.net_gearing:.2f}x
   - Total Debt: RM {fundamentals.get('total_debt', 0)/1e6:.1f}M
   - Total Cash: RM {fundamentals.get('total_cash', 0)/1e6:.1f}M
   - Assessment: {"NET CASH ✓" if f.net_gearing and f.net_gearing < 0 else "LOW DEBT ✓" if f.net_gearing and f.net_gearing < 0.3 else "MODERATE DEBT" if f.net_gearing and f.net_gearing < 0.7 else "HIGH DEBT ⚠" if f.net_gearing else "N/A"}

E. VALUATION ({f.score_valuation}/12)
   - PE Ratio: {f.pe_ttm:.2f}x
   - P/B Ratio: {f.pb:.2f}x
   - Dividend Yield: {f.div_yield_pct:.2f}%

F. CASH FLOW ({f.score_cashflow}/5)
   - Operating Cash Flow: RM {fundamentals.get('operating_cash_flow', 0)/1e6:.1f}M
   - FCF Yield: {"Positive" if fundamentals.get('operating_cash_flow', 0) > 0 else "Negative ⚠"}

G. DIVIDENDS ({f.score_dividends}/3)
   - Dividend Yield: {f.div_yield_pct:.2f}%
   - {"High yield (>5%)" if f.div_yield_pct and f.div_yield_pct >= 5 else "Good yield (3-5%)" if f.div_yield_pct and f.div_yield_pct >= 3 else "Modest/No dividend"}

H. IMPROVING FUNDAMENTALS ({f.score_improving}/5)
   - Piotroski-style momentum checks
"""

    # Add analyst data if available
    if f.has_analyst_data and f.analyst_target_mean:
        prompt += f"""
I. ANALYST CONSENSUS ({f.score_analyst_target}/5)
   - Mean Target Price: RM {f.analyst_target_mean:.2f}
   - Current Price: RM {price:.2f}
   - Implied Upside: {f.analyst_target_upside:+.1f}%
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
   - PE Ratio (KLSE): {f.klse_pe:.2f}x
   - ROE (KLSE): {f.klse_roe:.2f}%
   - P/B (KLSE): {f.klse_pb:.2f}x
   - Dividend Yield (KLSE): {f.klse_div_yield:.2f}%
   - Sector: {f.klse_sector}

QUARTERLY PERFORMANCE:
   - Latest QoQ Growth: {f.latest_qoq:+.1f}%
   - Latest YoY Growth: {f.latest_yoy:+.1f}%

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
                prompt += f"   - {txn.get('date', 'N/A')}: {txn.get('name', 'Unknown')[:30]} {action} {txn.get('shares', 'N/A'):,} shares\n"

    # Technical data
    prompt += f"""
═══════════════════════════════════════════════════════════════════════════════
                     TECHNICAL DATA (Timing & Momentum)
═══════════════════════════════════════════════════════════════════════════════

TECHNICAL SCORE BREAKDOWN ({t.total}/25 points):

TREND ANALYSIS:
   - Price: RM {price:.4f}
   - 20-Day MA: RM {t.ma20:.4f} (Price is {"ABOVE ✓" if price > t.ma20 else "BELOW ✗"}) - Score: {t.score_20ma}/3
   - 50-Day MA: RM {t.ma50:.4f} (Price is {"ABOVE ✓" if price > t.ma50 else "BELOW ✗"}) - Score: {t.score_50ma}/3
   - 200-Day MA: RM {t.ma200:.4f} (Price is {"ABOVE ✓" if price > t.ma200 else "BELOW ✗"}) - Score: {t.score_200ma}/3
   - Trend Status: {t.status}

MOMENTUM INDICATORS:
   - RSI (14-period): {t.rsi_val:.1f} ({"Overbought >70" if t.rsi_val > 70 else "Bullish 50-70 ✓" if t.rsi_val >= 50 else "Neutral 30-50" if t.rsi_val >= 30 else "Oversold <30"}) - Score: {t.score_rsi}/2
   - MACD: {t.macd_val:.4f}
   - MACD Signal: {t.macd_signal:.4f}
   - MACD Status: {"BULLISH (MACD > Signal) ✓" if t.macd_val > t.macd_signal else "BEARISH (MACD < Signal) ✗"} - Score: {t.score_macd}/2

VOLUME ANALYSIS:
   - 30-Day ADV: {t.adv_30d:,.0f} shares
   - Recent Volume Ratio: {t.volume_ratio:.2f}x average
   - Volume Assessment: {"Heavy accumulation ✓" if t.volume_ratio >= 1.5 else "Above average" if t.volume_ratio >= 1.2 else "Normal" if t.volume_ratio >= 0.8 else "Below average"} - Score: {t.score_volume}/3

PRICE PERFORMANCE:
   - 1-Week Return: {t.week_return:+.2f}%
   - 1-Month Return: {t.month_return:+.2f}%

RELATIVE STRENGTH (vs KLCI):
   - RS Ratio: {t.rs_ratio:.2f}x ({"OUTPERFORMING ✓" if t.rs_ratio >= 1.2 else "AT PAR" if t.rs_ratio >= 1.0 else "UNDERPERFORMING ✗"}) - Score: {t.score_rs}/3

52-WEEK POSITION (Minervini Template):
   - Above 52-Week Low: {t.pct_from_52wk_low:+.1f}% (Need >25%: {"✓" if t.pct_from_52wk_low >= 25 else "✗"})
   - Below 52-Week High: {t.pct_from_52wk_high:.1f}% (Need <25%: {"✓" if t.pct_from_52wk_high <= 25 else "✗"})
   - In "Sweet Spot": {"YES ✓" if t.pct_from_52wk_low >= 25 and t.pct_from_52wk_high <= 25 else "NO"} - Score: {t.score_52wk}/2

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
    
    metrics.add_row("Price", f"RM {t.price:.3f}", "-")
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
