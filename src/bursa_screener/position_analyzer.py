"""
Position Analyzer — Analyze an existing position with entry price.

For users who already own a stock and want to know:
1. Current P&L (profit/loss) based on entry price
2. Whether to HOLD, TAKE PROFIT, or CUT LOSS
3. Trend analysis (uptrend, downtrend, sideways)
4. Key support/resistance levels relative to their entry
5. AI prompt for detailed position review

Usage:
    python -m bursa_screener --position 1155.KL --entry 9.50
    python -m bursa_screener --position MAYBANK --entry 9.50 --shares 1000

Or programmatically:
    from bursa_screener.position_analyzer import analyze_position
    result = analyze_position("1155.KL", entry_price=9.50, shares=1000)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

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

# News fetcher integration
try:
    from . import news_fetcher
    NEWS_AVAILABLE = True
except ImportError:
    NEWS_AVAILABLE = False

console = Console()


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TrendAnalysis:
    """Detailed trend analysis result."""
    primary_trend: str  # "UPTREND", "DOWNTREND", "SIDEWAYS"
    trend_strength: str  # "STRONG", "MODERATE", "WEAK"
    trend_duration_days: int
    
    # Moving average analysis
    price_vs_ma20: str  # "ABOVE", "BELOW", "AT"
    price_vs_ma50: str
    price_vs_ma200: str
    ma_alignment: str  # "BULLISH" (20>50>200), "BEARISH" (20<50<200), "MIXED"
    
    # Momentum
    rsi_zone: str  # "OVERBOUGHT", "BULLISH", "NEUTRAL", "BEARISH", "OVERSOLD"
    macd_signal: str  # "BULLISH", "BEARISH", "NEUTRAL"
    volume_trend: str  # "INCREASING", "DECREASING", "STABLE"
    
    # Key levels (fields with defaults must come last)
    support_levels: list[float] = field(default_factory=list)
    resistance_levels: list[float] = field(default_factory=list)
    nearest_support: float | None = None
    nearest_resistance: float | None = None
    
    # Recent price action
    week_change_pct: float = 0.0
    month_change_pct: float = 0.0
    quarter_change_pct: float = 0.0


@dataclass
class PositionAnalysis:
    """Complete position analysis result."""
    ticker: str
    name: str | None
    analysis_date: str
    
    # Position details
    entry_price: float
    current_price: float
    shares: int
    
    # P&L calculations
    pnl_per_share: float
    pnl_pct: float
    total_pnl: float
    position_value: float
    cost_basis: float
    
    # Analysis
    trend: TrendAnalysis
    action_recommendation: str  # "HOLD", "TAKE PROFIT", "CUT LOSS", "ADD MORE", "PARTIAL PROFIT"
    action_reasoning: list[str]
    risk_reward_assessment: str
    
    # Scores
    fund_score: FundamentalScore
    tech_score: TechnicalScore
    result: StockResult
    
    # Additional data
    fundamentals: dict[str, Any] = field(default_factory=dict)
    klse_data: dict[str, Any] | None = None
    news_data: dict[str, Any] | None = None
    
    # Generated content
    ai_prompt: str = ""
    summary: dict = field(default_factory=dict)
    
    @property
    def is_profitable(self) -> bool:
        return self.pnl_pct > 0
    
    @property
    def pnl_status(self) -> str:
        if self.pnl_pct >= 20:
            return "SIGNIFICANT PROFIT"
        elif self.pnl_pct >= 10:
            return "GOOD PROFIT"
        elif self.pnl_pct >= 0:
            return "SMALL PROFIT"
        elif self.pnl_pct >= -5:
            return "SMALL LOSS"
        elif self.pnl_pct >= -10:
            return "MODERATE LOSS"
        else:
            return "SIGNIFICANT LOSS"


# ═══════════════════════════════════════════════════════════════════════════════
# TREND ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def _analyze_trend(price_df: pd.DataFrame, tech_score: TechnicalScore) -> TrendAnalysis:
    """Perform detailed trend analysis on price data."""
    if price_df is None or len(price_df) < 20:
        return TrendAnalysis(
            primary_trend="UNKNOWN",
            trend_strength="UNKNOWN",
            trend_duration_days=0,
            price_vs_ma20="UNKNOWN",
            price_vs_ma50="UNKNOWN",
            price_vs_ma200="UNKNOWN",
            ma_alignment="UNKNOWN",
            rsi_zone="UNKNOWN",
            macd_signal="UNKNOWN",
            volume_trend="UNKNOWN",
        )
    
    current_price = tech_score.price
    ma20 = tech_score.ma20
    ma50 = tech_score.ma50
    ma200 = tech_score.ma200
    rsi = tech_score.rsi_val
    macd = tech_score.macd_val
    macd_sig = tech_score.macd_signal
    
    # Price vs MAs
    def price_vs_ma(price, ma):
        if ma is None:
            return "UNKNOWN"
        pct_diff = ((price - ma) / ma) * 100
        if pct_diff > 2:
            return "ABOVE"
        elif pct_diff < -2:
            return "BELOW"
        return "AT"
    
    price_vs_ma20 = price_vs_ma(current_price, ma20)
    price_vs_ma50 = price_vs_ma(current_price, ma50)
    price_vs_ma200 = price_vs_ma(current_price, ma200)
    
    # MA Alignment
    if ma20 and ma50 and ma200:
        if ma20 > ma50 > ma200:
            ma_alignment = "BULLISH"
        elif ma20 < ma50 < ma200:
            ma_alignment = "BEARISH"
        else:
            ma_alignment = "MIXED"
    else:
        ma_alignment = "UNKNOWN"
    
    # Determine primary trend
    bullish_signals = 0
    bearish_signals = 0
    
    if price_vs_ma20 == "ABOVE":
        bullish_signals += 1
    elif price_vs_ma20 == "BELOW":
        bearish_signals += 1
        
    if price_vs_ma50 == "ABOVE":
        bullish_signals += 1
    elif price_vs_ma50 == "BELOW":
        bearish_signals += 1
        
    if price_vs_ma200 == "ABOVE":
        bullish_signals += 2  # More weight for long-term trend
    elif price_vs_ma200 == "BELOW":
        bearish_signals += 2
    
    if ma_alignment == "BULLISH":
        bullish_signals += 2
    elif ma_alignment == "BEARISH":
        bearish_signals += 2
    
    # Primary trend determination
    if bullish_signals >= 5:
        primary_trend = "UPTREND"
        trend_strength = "STRONG" if bullish_signals >= 6 else "MODERATE"
    elif bearish_signals >= 5:
        primary_trend = "DOWNTREND"
        trend_strength = "STRONG" if bearish_signals >= 6 else "MODERATE"
    else:
        primary_trend = "SIDEWAYS"
        trend_strength = "WEAK"
    
    # RSI Zone
    if rsi is None:
        rsi_zone = "UNKNOWN"
    elif rsi >= 70:
        rsi_zone = "OVERBOUGHT"
    elif rsi >= 55:
        rsi_zone = "BULLISH"
    elif rsi >= 45:
        rsi_zone = "NEUTRAL"
    elif rsi >= 30:
        rsi_zone = "BEARISH"
    else:
        rsi_zone = "OVERSOLD"
    
    # MACD Signal
    if macd is None or macd_sig is None:
        macd_signal = "UNKNOWN"
    elif macd > macd_sig and macd > 0:
        macd_signal = "BULLISH"
    elif macd < macd_sig and macd < 0:
        macd_signal = "BEARISH"
    else:
        macd_signal = "NEUTRAL"
    
    # Volume trend
    vol_ratio = tech_score.volume_ratio
    if vol_ratio is None:
        volume_trend = "UNKNOWN"
    elif vol_ratio >= 1.5:
        volume_trend = "INCREASING"
    elif vol_ratio <= 0.7:
        volume_trend = "DECREASING"
    else:
        volume_trend = "STABLE"
    
    # Calculate support/resistance levels
    support_levels = []
    resistance_levels = []
    
    if ma20:
        if current_price > ma20:
            support_levels.append(round(ma20, 4))
        else:
            resistance_levels.append(round(ma20, 4))
    if ma50:
        if current_price > ma50:
            support_levels.append(round(ma50, 4))
        else:
            resistance_levels.append(round(ma50, 4))
    if ma200:
        if current_price > ma200:
            support_levels.append(round(ma200, 4))
        else:
            resistance_levels.append(round(ma200, 4))
    
    # Add 52-week levels (calculate from percentage values)
    # If we have pct_from_52wk_high, we can calculate the actual high
    # high_52wk = current_price / (1 - pct_from_52wk_high/100)
    if tech_score.pct_from_52wk_high and tech_score.pct_from_52wk_high > 0:
        high_52wk = current_price / (1 - tech_score.pct_from_52wk_high / 100)
        resistance_levels.append(round(high_52wk, 4))
    if tech_score.pct_from_52wk_low and tech_score.pct_from_52wk_low > 0:
        low_52wk = current_price / (1 + tech_score.pct_from_52wk_low / 100)
        support_levels.append(round(low_52wk, 4))
    
    # Sort and deduplicate
    support_levels = sorted(set(support_levels), reverse=True)
    resistance_levels = sorted(set(resistance_levels))
    
    # Nearest levels
    nearest_support = support_levels[0] if support_levels else None
    nearest_resistance = resistance_levels[0] if resistance_levels else None
    
    # Trend duration (simplified - count days above/below MA50)
    trend_duration_days = 0
    if len(price_df) >= 50 and ma50:
        closes = price_df['Close'].values[-50:]
        if primary_trend == "UPTREND":
            for i in range(len(closes) - 1, -1, -1):
                if closes[i] > ma50:
                    trend_duration_days += 1
                else:
                    break
        elif primary_trend == "DOWNTREND":
            for i in range(len(closes) - 1, -1, -1):
                if closes[i] < ma50:
                    trend_duration_days += 1
                else:
                    break
    
    # Price changes
    week_change = tech_score.week_return or 0.0
    month_change = tech_score.month_return or 0.0
    quarter_change = 0.0
    if len(price_df) >= 63:
        quarter_ago = price_df['Close'].iloc[-63]
        quarter_change = ((current_price - quarter_ago) / quarter_ago) * 100
    
    return TrendAnalysis(
        primary_trend=primary_trend,
        trend_strength=trend_strength,
        trend_duration_days=trend_duration_days,
        price_vs_ma20=price_vs_ma20,
        price_vs_ma50=price_vs_ma50,
        price_vs_ma200=price_vs_ma200,
        ma_alignment=ma_alignment,
        support_levels=support_levels,
        resistance_levels=resistance_levels,
        nearest_support=nearest_support,
        nearest_resistance=nearest_resistance,
        rsi_zone=rsi_zone,
        macd_signal=macd_signal,
        volume_trend=volume_trend,
        week_change_pct=week_change,
        month_change_pct=month_change,
        quarter_change_pct=quarter_change,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ACTION RECOMMENDATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def _determine_action(
    pnl_pct: float,
    trend: TrendAnalysis,
    fund_score: FundamentalScore,
    tech_score: TechnicalScore,
    entry_price: float,
    current_price: float,
) -> tuple[str, list[str], str]:
    """
    Determine recommended action based on position status and market conditions.
    
    Returns: (action, reasoning_list, risk_reward_assessment)
    """
    reasoning = []
    
    # Score thresholds
    fund_pct = (fund_score.total / fund_score.max_score) * 100
    tech_pct = (tech_score.total / 25) * 100
    
    is_fundamentally_strong = fund_pct >= 65
    is_technically_strong = tech_pct >= 70
    is_in_uptrend = trend.primary_trend == "UPTREND"
    is_in_downtrend = trend.primary_trend == "DOWNTREND"
    
    # Risk/reward calculation
    nearest_support = trend.nearest_support or (current_price * 0.9)
    nearest_resistance = trend.nearest_resistance or (current_price * 1.1)
    
    downside_risk = ((current_price - nearest_support) / current_price) * 100
    upside_potential = ((nearest_resistance - current_price) / current_price) * 100
    
    if upside_potential > 0 and downside_risk > 0:
        rr_ratio = upside_potential / downside_risk
    else:
        rr_ratio = 1.0
    
    if rr_ratio >= 2:
        risk_reward = "FAVORABLE (R:R > 2:1)"
    elif rr_ratio >= 1:
        risk_reward = "NEUTRAL (R:R ~1:1)"
    else:
        risk_reward = "UNFAVORABLE (R:R < 1:1)"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DECISION LOGIC
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Case 1: Significant profit (>20%)
    if pnl_pct >= 20:
        if is_in_downtrend or trend.rsi_zone == "OVERBOUGHT":
            action = "TAKE PROFIT"
            reasoning.append(f"✅ Significant profit of {pnl_pct:.1f}% achieved")
            reasoning.append("⚠️ Trend weakening or overbought conditions")
            reasoning.append("💡 Consider locking in gains")
        elif is_fundamentally_strong and is_in_uptrend:
            action = "PARTIAL PROFIT"
            reasoning.append(f"✅ Excellent profit of {pnl_pct:.1f}%")
            reasoning.append("📈 Fundamentals and trend still strong")
            reasoning.append("💡 Consider taking partial profit (50%) and letting rest run")
        else:
            action = "HOLD"
            reasoning.append(f"✅ Good profit of {pnl_pct:.1f}%")
            reasoning.append("📊 Mixed signals - hold with trailing stop")
    
    # Case 2: Good profit (10-20%)
    elif pnl_pct >= 10:
        if is_in_downtrend:
            action = "TAKE PROFIT"
            reasoning.append(f"✅ Profit of {pnl_pct:.1f}%")
            reasoning.append("📉 Downtrend detected - protect gains")
        elif is_fundamentally_strong and is_in_uptrend:
            action = "HOLD"
            reasoning.append(f"✅ Profit of {pnl_pct:.1f}%")
            reasoning.append("📈 Strong fundamentals + uptrend")
            reasoning.append("💡 Continue holding with stop at breakeven")
        else:
            action = "HOLD"
            reasoning.append(f"✅ Profit of {pnl_pct:.1f}%")
            reasoning.append("💡 Set stop-loss at entry price to protect gains")
    
    # Case 3: Small profit (0-10%)
    elif pnl_pct >= 0:
        if is_in_downtrend and not is_fundamentally_strong:
            action = "TAKE PROFIT"
            reasoning.append("⚠️ Small profit but trend weakening")
            reasoning.append("📉 Fundamentals not strong enough to hold")
        elif is_fundamentally_strong and is_in_uptrend:
            action = "ADD MORE"
            reasoning.append(f"📈 Position slightly profitable ({pnl_pct:.1f}%)")
            reasoning.append("✅ Strong fundamentals + uptrend")
            reasoning.append("💡 Consider adding on pullback to support")
        else:
            action = "HOLD"
            reasoning.append(f"📊 Small profit of {pnl_pct:.1f}%")
            reasoning.append("💡 Wait for clearer direction")
    
    # Case 4: Small loss (0 to -8%)
    elif pnl_pct >= -8:
        if is_fundamentally_strong and (is_in_uptrend or trend.primary_trend == "SIDEWAYS"):
            action = "HOLD"
            reasoning.append(f"📉 Small loss of {pnl_pct:.1f}%")
            reasoning.append("✅ Fundamentals still strong")
            reasoning.append("💡 Hold but set stop-loss at -10% from entry")
        elif is_fundamentally_strong and is_in_downtrend:
            action = "HOLD"
            reasoning.append(f"📉 Small loss of {pnl_pct:.1f}%")
            reasoning.append("⚠️ Short-term downtrend but fundamentals intact")
            reasoning.append("💡 Tight stop recommended (-10%)")
        else:
            action = "CUT LOSS"
            reasoning.append(f"📉 Loss of {pnl_pct:.1f}%")
            reasoning.append("⚠️ Weak fundamentals or deteriorating trend")
            reasoning.append("💡 Cut loss early to preserve capital")
    
    # Case 5: Moderate loss (-8% to -15%)
    elif pnl_pct >= -15:
        if is_fundamentally_strong and is_in_uptrend:
            action = "HOLD"
            reasoning.append(f"⚠️ Moderate loss of {pnl_pct:.1f}%")
            reasoning.append("✅ But fundamentals strong and trend turning up")
            reasoning.append("💡 Last chance - set hard stop at -20%")
        elif is_fundamentally_strong:
            action = "HOLD"
            reasoning.append(f"⚠️ Moderate loss of {pnl_pct:.1f}%")
            reasoning.append("📊 Fundamentals okay - review thesis")
            reasoning.append("💡 Strict stop at -20%")
        else:
            action = "CUT LOSS"
            reasoning.append(f"🔴 Loss of {pnl_pct:.1f}%")
            reasoning.append("❌ Fundamentals weak")
            reasoning.append("💡 Cut loss to protect remaining capital")
    
    # Case 6: Significant loss (>-15%)
    else:
        if is_fundamentally_strong and is_in_uptrend and trend.trend_strength == "STRONG":
            action = "HOLD"
            reasoning.append(f"🔴 Significant loss of {pnl_pct:.1f}%")
            reasoning.append("✅ However, strong recovery signals")
            reasoning.append("⚠️ High risk - evaluate if thesis still valid")
        else:
            action = "CUT LOSS"
            reasoning.append(f"🔴 Significant loss of {pnl_pct:.1f}%")
            reasoning.append("❌ Position has deteriorated significantly")
            reasoning.append("💡 Cut loss - don't let losers run")
    
    # Add trend context
    reasoning.append(f"📊 Trend: {trend.primary_trend} ({trend.trend_strength})")
    reasoning.append(f"📈 Technical Score: {tech_score.total}/25 ({tech_pct:.0f}%)")
    reasoning.append(f"💼 Fundamental Score: {fund_score.total}/{fund_score.max_score} ({fund_pct:.0f}%)")
    
    return action, reasoning, risk_reward


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ANALYSIS FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_position(
    ticker: str,
    entry_price: float,
    shares: int = 1000,
    use_cache: bool = True,
    verbose: bool = True,
) -> PositionAnalysis:
    """
    Analyze an existing position with entry price.
    
    Args:
        ticker: Stock ticker (e.g., "1155.KL")
        entry_price: Price at which position was entered
        shares: Number of shares held (default 1000)
        use_cache: Whether to use cached data
        verbose: Print progress to console
    
    Returns:
        PositionAnalysis object with complete analysis
    """
    # Normalize ticker
    ticker = _normalize_ticker(ticker)
    analysis_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    if verbose:
        console.print(f"\n[bold blue]📊 Analyzing Position: {ticker}[/bold blue]")
        console.print(f"[dim]Entry Price: RM {entry_price:.4f} | Shares: {shares:,}[/dim]\n")
    
    # ── Fetch data ────────────────────────────────────────────────────────────
    if verbose:
        console.print("[dim]Fetching market data...[/dim]")
    
    price_df = fetch_price_history(ticker, period="1y", use_cache=use_cache)
    fundamentals = fetch_fundamentals(ticker, use_cache=use_cache)
    
    # KLSE data
    klse_data = None
    if KLSE_AVAILABLE and ticker.upper().endswith(".KL"):
        klse_data = klse_fetcher.get_klse_enhanced_data(ticker, use_cache=use_cache)
    
    # News
    news_data = None
    if NEWS_AVAILABLE:
        news_data = news_fetcher.fetch_all_news(ticker, use_cache=use_cache)
    
    # ── Calculate scores ──────────────────────────────────────────────────────
    if verbose:
        console.print("[dim]Calculating scores...[/dim]")
    
    fund_score = score_fundamentals(ticker, fundamentals, None, klse_data)
    tech_score = score_technicals(ticker, price_df)
    
    # Current price
    current_price = tech_score.price if tech_score.price else fundamentals.get("price", entry_price)
    
    # ── P&L Calculations ──────────────────────────────────────────────────────
    pnl_per_share = current_price - entry_price
    pnl_pct = ((current_price - entry_price) / entry_price) * 100
    total_pnl = pnl_per_share * shares
    position_value = current_price * shares
    cost_basis = entry_price * shares
    
    # ── Trend Analysis ────────────────────────────────────────────────────────
    if verbose:
        console.print("[dim]Analyzing trend...[/dim]")
    
    trend = _analyze_trend(price_df, tech_score)
    
    # ── Determine Action ──────────────────────────────────────────────────────
    action, reasoning, risk_reward = _determine_action(
        pnl_pct, trend, fund_score, tech_score, entry_price, current_price
    )
    
    # Build StockResult
    result = StockResult(
        ticker=ticker,
        long_name=fundamentals.get("long_name"),
        fund=fund_score,
        tech=tech_score,
    )
    
    # ── Create analysis object ────────────────────────────────────────────────
    analysis = PositionAnalysis(
        ticker=ticker,
        name=fundamentals.get("long_name"),
        analysis_date=analysis_date,
        entry_price=entry_price,
        current_price=current_price,
        shares=shares,
        pnl_per_share=pnl_per_share,
        pnl_pct=pnl_pct,
        total_pnl=total_pnl,
        position_value=position_value,
        cost_basis=cost_basis,
        trend=trend,
        action_recommendation=action,
        action_reasoning=reasoning,
        risk_reward_assessment=risk_reward,
        fund_score=fund_score,
        tech_score=tech_score,
        result=result,
        fundamentals=fundamentals,
        klse_data=klse_data,
        news_data=news_data,
    )
    
    # ── Generate AI prompt ────────────────────────────────────────────────────
    if verbose:
        console.print("[dim]Generating AI analysis prompt...[/dim]")
    
    analysis.ai_prompt = _generate_position_ai_prompt(analysis)
    analysis.summary = _generate_position_summary(analysis)
    
    if verbose:
        console.print(f"[bold green]✓ Position analysis complete[/bold green]\n")
    
    return analysis


def _normalize_ticker(ticker: str) -> str:
    """Normalize ticker format."""
    ticker = ticker.upper().strip()
    
    NAME_MAP = {
        "MAYBANK": "1155.KL",
        "CIMB": "1023.KL",
        "PBBANK": "1295.KL",
        "TENAGA": "5347.KL",
        "IHH": "5225.KL",
        "PCHEM": "5183.KL",
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
    
    if not ticker.endswith(".KL"):
        ticker = f"{ticker}.KL"
    
    return ticker


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_position_summary(analysis: PositionAnalysis) -> dict:
    """Generate summary dict for position analysis."""
    return {
        "ticker": analysis.ticker,
        "name": analysis.name,
        "entry_price": analysis.entry_price,
        "current_price": analysis.current_price,
        "pnl_pct": round(analysis.pnl_pct, 2),
        "pnl_status": analysis.pnl_status,
        "total_pnl": round(analysis.total_pnl, 2),
        "action": analysis.action_recommendation,
        "trend": analysis.trend.primary_trend,
        "trend_strength": analysis.trend.trend_strength,
        "risk_reward": analysis.risk_reward_assessment,
        "fundamental_score": f"{analysis.fund_score.total}/{analysis.fund_score.max_score}",
        "technical_score": f"{analysis.tech_score.total}/25",
        "classification": analysis.result.classification,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# AI PROMPT GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_position_ai_prompt(analysis: PositionAnalysis) -> str:
    """Generate comprehensive AI prompt for position analysis."""
    
    # Safe formatting helpers
    def _safe(val, fmt=".2f", suffix=""):
        if val is None:
            return "N/A"
        try:
            return f"{val:{fmt}}{suffix}"
        except (ValueError, TypeError):
            return str(val)
    
    def _safe_int(val):
        if val is None:
            return "N/A"
        try:
            return f"{int(val):,}"
        except (ValueError, TypeError):
            return str(val)
    
    a = analysis
    t = a.trend
    fs = a.fund_score
    ts = a.tech_score
    
    # Format news section
    news_section = ""
    if NEWS_AVAILABLE and a.news_data and a.news_data.get("news"):
        news_section = news_fetcher.format_news_for_prompt(a.news_data, max_items=8)
    
    # Build quarterly section if KLSE data available
    quarterly_section = ""
    if a.klse_data and a.klse_data.get("has_klse_data"):
        quarterly_section = f"""
## KLSE QUARTERLY DATA

| Metric | Value |
|--------|-------|
| Latest QoQ Growth | {_safe(fs.latest_qoq, '+.1f', '%')} |
| Latest YoY Growth | {_safe(fs.latest_yoy, '+.1f', '%')} |
| PE (KLSE) | {_safe(fs.klse_pe, '.2f')}x |
| ROE (KLSE) | {_safe(fs.klse_roe, '.1f', '%')} |
| Dividend Yield | {_safe(fs.klse_div_yield, '.2f', '%')} |

### Enhanced Scores from KLSE Data:
- Earnings Momentum: {fs.score_earnings_momentum}/5
- Earnings Consistency: {fs.score_earnings_consistency}/3
- Institutional Flow: {fs.score_institutional_flow}/3
- Insider Trading: {fs.score_insider_trading}/3
"""
    
    prompt = f"""You are a professional equity research analyst and trading coach. I need your help analyzing my existing stock position and deciding whether to HOLD, TAKE PROFIT, or CUT LOSS.

═══════════════════════════════════════════════════════════════════════════════
                        POSITION ANALYSIS REQUEST
═══════════════════════════════════════════════════════════════════════════════

## MY POSITION DETAILS

| Metric | Value |
|--------|-------|
| **Stock** | {a.ticker} - {a.name or 'Unknown'} |
| **Entry Price** | RM {a.entry_price:.4f} |
| **Current Price** | RM {a.current_price:.4f} |
| **Shares Held** | {a.shares:,} |
| **Cost Basis** | RM {a.cost_basis:,.2f} |
| **Current Value** | RM {a.position_value:,.2f} |

## PROFIT/LOSS STATUS

| Metric | Value |
|--------|-------|
| **P&L per Share** | RM {a.pnl_per_share:+.4f} |
| **P&L Percentage** | {a.pnl_pct:+.2f}% |
| **Total P&L** | RM {a.total_pnl:+,.2f} |
| **Status** | {a.pnl_status} |

---

## TREND ANALYSIS

| Indicator | Status | Interpretation |
|-----------|--------|----------------|
| **Primary Trend** | {t.primary_trend} | {t.trend_strength} strength |
| **Trend Duration** | {t.trend_duration_days} days | - |
| **Price vs 20-MA** | {t.price_vs_ma20} | Short-term {"bullish" if t.price_vs_ma20 == "ABOVE" else "bearish" if t.price_vs_ma20 == "BELOW" else "neutral"} |
| **Price vs 50-MA** | {t.price_vs_ma50} | Medium-term {"bullish" if t.price_vs_ma50 == "ABOVE" else "bearish" if t.price_vs_ma50 == "BELOW" else "neutral"} |
| **Price vs 200-MA** | {t.price_vs_ma200} | Long-term {"bullish" if t.price_vs_ma200 == "ABOVE" else "bearish" if t.price_vs_ma200 == "BELOW" else "neutral"} |
| **MA Alignment** | {t.ma_alignment} | {"20>50>200 = Bullish stacking" if t.ma_alignment == "BULLISH" else "20<50<200 = Bearish stacking" if t.ma_alignment == "BEARISH" else "Mixed signals"} |

### Momentum Indicators

| Indicator | Value | Signal |
|-----------|-------|--------|
| RSI Zone | {t.rsi_zone} | {_safe(ts.rsi_val, '.1f')} |
| MACD Signal | {t.macd_signal} | MACD: {_safe(ts.macd_val, '.4f')}, Signal: {_safe(ts.macd_signal, '.4f')} |
| Volume Trend | {t.volume_trend} | Volume Ratio: {_safe(ts.volume_ratio, '.2f')}x |

### Price Performance

| Period | Change |
|--------|--------|
| 1 Week | {t.week_change_pct:+.1f}% |
| 1 Month | {t.month_change_pct:+.1f}% |
| 3 Months | {t.quarter_change_pct:+.1f}% |

### Key Price Levels

**Support Levels (prices below current):**
{chr(10).join([f"- RM {level:.4f}" for level in t.support_levels[:3]]) if t.support_levels else "- No clear support levels identified"}

**Resistance Levels (prices above current):**
{chr(10).join([f"- RM {level:.4f}" for level in t.resistance_levels[:3]]) if t.resistance_levels else "- No clear resistance levels identified"}

**Nearest Support:** RM {f"{t.nearest_support:.4f}" if t.nearest_support else "N/A"}
**Nearest Resistance:** RM {f"{t.nearest_resistance:.4f}" if t.nearest_resistance else "N/A"}

**Entry Price Position:**
- Entry (RM {a.entry_price:.4f}) is {"ABOVE" if a.entry_price > a.current_price else "BELOW" if a.entry_price < a.current_price else "AT"} current price
- Distance to nearest support: {((a.current_price - t.nearest_support) / a.current_price * 100):.1f}% below current if t.nearest_support else "N/A"
- Distance to nearest resistance: {((t.nearest_resistance - a.current_price) / a.current_price * 100):.1f}% above current if t.nearest_resistance else "N/A"

---

## FUNDAMENTAL SCORES

| Factor | Score | Max | Assessment |
|--------|-------|-----|------------|
| Earnings Quality | {fs.score_earnings_quality} | 10 | {"Good" if fs.score_earnings_quality >= 6 else "Weak"} |
| Earnings Growth | {fs.score_earnings_growth} | 10 | {"Strong" if fs.score_earnings_growth >= 6 else "Moderate" if fs.score_earnings_growth >= 3 else "Weak"} |
| ROE | {fs.score_roe} | 10 | {"Excellent" if fs.score_roe >= 8 else "Good" if fs.score_roe >= 6 else "Average"} |
| Financial Health | {fs.score_financial_health} | 10 | {"Strong" if fs.score_financial_health >= 8 else "OK" if fs.score_financial_health >= 5 else "Risky"} |
| Valuation | {fs.score_valuation} | 12 | {"Cheap" if fs.score_valuation >= 8 else "Fair" if fs.score_valuation >= 5 else "Expensive"} |
| Cash Flow | {fs.score_cashflow} | 5 | {"Strong" if fs.score_cashflow >= 4 else "OK"} |
| **TOTAL** | **{fs.total}** | **{fs.max_score}** | **{fs.total/fs.max_score*100:.0f}%** |

## TECHNICAL SCORES

| Factor | Score | Max | Signal |
|--------|-------|-----|--------|
| 20-Day MA | {ts.score_20ma} | 3 | {"Bullish" if ts.score_20ma >= 2 else "Neutral" if ts.score_20ma == 1 else "Bearish"} |
| 50-Day MA | {ts.score_50ma} | 3 | {"Bullish" if ts.score_50ma >= 2 else "Neutral" if ts.score_50ma == 1 else "Bearish"} |
| 200-Day MA | {ts.score_200ma} | 3 | {"Bullish" if ts.score_200ma >= 2 else "Neutral" if ts.score_200ma == 1 else "Bearish"} |
| RSI | {ts.score_rsi} | 2 | {"Bullish" if ts.score_rsi >= 1 else "Weak"} |
| MACD | {ts.score_macd} | 2 | {"Bullish" if ts.score_macd >= 1 else "Bearish"} |
| Volume | {ts.score_volume} | 3 | {"Strong" if ts.score_volume >= 2 else "Normal"} |
| Breakout | {ts.score_breakout} | 2 | {"Near highs" if ts.score_breakout >= 1 else "No"} |
| Support | {ts.score_support} | 2 | {"Holding" if ts.score_support >= 1 else "Breaking"} |
| Relative Strength | {ts.score_rs} | 3 | {"Outperforming" if ts.score_rs >= 2 else "In-line" if ts.score_rs == 1 else "Lagging"} |
| 52-Week Position | {ts.score_52wk} | 2 | {"Sweet spot" if ts.score_52wk >= 1 else "Poor"} |
| **TOTAL** | **{ts.total}** | **25** | **{ts.total/25*100:.0f}%** |

**Classification:** {a.result.classification}
**Technical Status:** {ts.status}

---

## KEY FUNDAMENTAL METRICS

| Metric | Value | Assessment |
|--------|-------|------------|
| PE Ratio | {_safe(fs.pe_ttm, '.1f')}x | {"Cheap" if fs.pe_ttm and fs.pe_ttm < 12 else "Fair" if fs.pe_ttm and fs.pe_ttm < 18 else "Expensive" if fs.pe_ttm else "N/A"} |
| P/B Ratio | {_safe(fs.pb, '.2f')}x | {"Undervalued" if fs.pb and fs.pb < 1 else "Fair" if fs.pb and fs.pb < 2 else "Premium" if fs.pb else "N/A"} |
| ROE | {_safe(fs.roe_pct, '.1f')}% | {"Excellent" if fs.roe_pct and fs.roe_pct >= 15 else "Good" if fs.roe_pct and fs.roe_pct >= 10 else "Weak" if fs.roe_pct else "N/A"} |
| Net Gearing | {_safe(fs.net_gearing, '.2f')} | {"Net Cash" if fs.net_gearing and fs.net_gearing < 0 else "Low debt" if fs.net_gearing and fs.net_gearing < 0.3 else "High debt" if fs.net_gearing else "N/A"} |
| Div Yield | {_safe(fs.div_yield_pct, '.2f')}% | - |
| EPS Growth | {_safe(fs.earnings_growth_pct, '+.1f')}% | {"Strong" if fs.earnings_growth_pct and fs.earnings_growth_pct > 15 else "Moderate" if fs.earnings_growth_pct and fs.earnings_growth_pct > 0 else "Negative" if fs.earnings_growth_pct else "N/A"} |
{quarterly_section}
---

## SYSTEM RECOMMENDATION

**Recommended Action:** {a.action_recommendation}

**Risk/Reward Assessment:** {a.risk_reward_assessment}

**Reasoning:**
{chr(10).join([f"- {r}" for r in a.action_reasoning])}

---
{news_section}
---

## ANALYSIS REQUEST

Based on all the data above, please provide:

### 1. POSITION ASSESSMENT
- Is my entry price good relative to current support/resistance levels?
- Am I in a favorable position or should I be concerned?

### 2. TREND CONFIRMATION
- Is the current trend likely to continue or reverse?
- What are the key levels to watch that would confirm or invalidate the trend?

### 3. ACTION RECOMMENDATION
Provide your recommendation:
- **HOLD**: Continue holding the position
- **TAKE PROFIT**: Sell all shares to lock in gains
- **PARTIAL PROFIT**: Sell some shares (suggest %), keep rest
- **ADD MORE**: Consider buying more shares (suggest entry zone)
- **CUT LOSS**: Sell to prevent further losses

### 4. RISK MANAGEMENT
- Where should I set my stop-loss?
- What is a reasonable profit target?
- Position sizing advice (should I reduce/increase exposure?)

### 5. KEY CATALYSTS & RISKS
- What upcoming events could affect this stock?
- What are the main risks to my position?
- What would make you change your recommendation?

### 6. TIMELINE
- Short-term outlook (1-4 weeks)
- Medium-term outlook (1-3 months)
- Key dates or events to monitor

---

Please be specific with price levels (in RM) and percentages. Consider my entry price of RM {a.entry_price:.4f} when providing stop-loss and target recommendations.
"""
    
    return prompt


# ═══════════════════════════════════════════════════════════════════════════════
# CONSOLE OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

def print_position_analysis(analysis: PositionAnalysis) -> None:
    """Print position analysis to console."""
    a = analysis
    
    # Header
    console.print()
    console.print(Panel(
        f"[bold]{a.ticker}[/bold] - {a.name or 'Unknown'}",
        title="📊 Position Analysis",
        border_style="blue",
    ))
    
    # P&L Table
    pnl_color = "green" if a.pnl_pct >= 0 else "red"
    
    table = Table(title="💰 Position P&L", show_header=True, header_style="bold")
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")
    
    table.add_row("Entry Price", f"RM {a.entry_price:.4f}")
    table.add_row("Current Price", f"RM {a.current_price:.4f}")
    table.add_row("Shares", f"{a.shares:,}")
    table.add_row("Cost Basis", f"RM {a.cost_basis:,.2f}")
    table.add_row("Current Value", f"RM {a.position_value:,.2f}")
    table.add_row("─" * 15, "─" * 15)
    table.add_row("P&L per Share", f"[{pnl_color}]RM {a.pnl_per_share:+.4f}[/{pnl_color}]")
    table.add_row("P&L %", f"[{pnl_color}]{a.pnl_pct:+.2f}%[/{pnl_color}]")
    table.add_row("Total P&L", f"[{pnl_color}]RM {a.total_pnl:+,.2f}[/{pnl_color}]")
    table.add_row("Status", f"[{pnl_color}]{a.pnl_status}[/{pnl_color}]")
    
    console.print(table)
    
    # Trend Table
    trend_color = "green" if a.trend.primary_trend == "UPTREND" else "red" if a.trend.primary_trend == "DOWNTREND" else "yellow"
    
    trend_table = Table(title="📈 Trend Analysis", show_header=True, header_style="bold")
    trend_table.add_column("Indicator", style="dim")
    trend_table.add_column("Status", justify="center")
    
    trend_table.add_row("Primary Trend", f"[{trend_color}]{a.trend.primary_trend}[/{trend_color}]")
    trend_table.add_row("Strength", a.trend.trend_strength)
    trend_table.add_row("Duration", f"{a.trend.trend_duration_days} days")
    trend_table.add_row("MA Alignment", a.trend.ma_alignment)
    trend_table.add_row("RSI Zone", a.trend.rsi_zone)
    trend_table.add_row("MACD Signal", a.trend.macd_signal)
    trend_table.add_row("Volume Trend", a.trend.volume_trend)
    
    console.print(trend_table)
    
    # Scores
    score_table = Table(title="📊 Scores", show_header=True, header_style="bold")
    score_table.add_column("Score Type", style="dim")
    score_table.add_column("Value", justify="center")
    score_table.add_column("Rating", justify="center")
    
    fund_pct = (a.fund_score.total / a.fund_score.max_score) * 100
    tech_pct = (a.tech_score.total / 25) * 100
    
    fund_color = "green" if fund_pct >= 65 else "yellow" if fund_pct >= 50 else "red"
    tech_color = "green" if tech_pct >= 70 else "yellow" if tech_pct >= 50 else "red"
    
    score_table.add_row(
        "Fundamental",
        f"[{fund_color}]{a.fund_score.total}/{a.fund_score.max_score}[/{fund_color}]",
        f"[{fund_color}]{fund_pct:.0f}%[/{fund_color}]"
    )
    score_table.add_row(
        "Technical",
        f"[{tech_color}]{a.tech_score.total}/25[/{tech_color}]",
        f"[{tech_color}]{tech_pct:.0f}%[/{tech_color}]"
    )
    score_table.add_row("Classification", a.result.classification, "")
    
    console.print(score_table)
    
    # Recommendation Panel
    action_color = {
        "HOLD": "blue",
        "TAKE PROFIT": "green",
        "PARTIAL PROFIT": "green",
        "ADD MORE": "cyan",
        "CUT LOSS": "red",
    }.get(a.action_recommendation, "white")
    
    reasoning_text = "\n".join(a.action_reasoning)
    
    console.print(Panel(
        f"[bold {action_color}]{a.action_recommendation}[/bold {action_color}]\n\n{reasoning_text}\n\n[dim]Risk/Reward: {a.risk_reward_assessment}[/dim]",
        title="🎯 Recommendation",
        border_style=action_color,
    ))


# ═══════════════════════════════════════════════════════════════════════════════
# FILE SAVING
# ═══════════════════════════════════════════════════════════════════════════════

def save_position_analysis(analysis: PositionAnalysis, output_dir: str = "results") -> dict[str, str]:
    """Save position analysis to files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    safe_ticker = analysis.ticker.replace(".", "_")
    base_name = f"{safe_ticker}_{timestamp}_position"
    
    paths = {}
    
    # Save AI prompt
    prompt_path = output_path / f"{base_name}_prompt.txt"
    with open(prompt_path, "w") as f:
        f.write(analysis.ai_prompt)
    paths["prompt"] = str(prompt_path)
    
    # Save JSON data
    json_path = output_path / f"{base_name}_data.json"
    json_data = {
        "ticker": analysis.ticker,
        "name": analysis.name,
        "analysis_date": analysis.analysis_date,
        "entry_price": analysis.entry_price,
        "current_price": analysis.current_price,
        "shares": analysis.shares,
        "pnl": {
            "per_share": analysis.pnl_per_share,
            "percentage": analysis.pnl_pct,
            "total": analysis.total_pnl,
            "status": analysis.pnl_status,
        },
        "position_value": analysis.position_value,
        "cost_basis": analysis.cost_basis,
        "trend": {
            "primary": analysis.trend.primary_trend,
            "strength": analysis.trend.trend_strength,
            "duration_days": analysis.trend.trend_duration_days,
            "ma_alignment": analysis.trend.ma_alignment,
            "rsi_zone": analysis.trend.rsi_zone,
            "macd_signal": analysis.trend.macd_signal,
            "support_levels": analysis.trend.support_levels,
            "resistance_levels": analysis.trend.resistance_levels,
        },
        "recommendation": {
            "action": analysis.action_recommendation,
            "reasoning": analysis.action_reasoning,
            "risk_reward": analysis.risk_reward_assessment,
        },
        "scores": {
            "fundamental": {
                "total": analysis.fund_score.total,
                "max": analysis.fund_score.max_score,
            },
            "technical": {
                "total": analysis.tech_score.total,
                "max": 25,
            },
        },
        "classification": analysis.result.classification,
        "summary": analysis.summary,
    }
    
    with open(json_path, "w") as f:
        json.dump(json_data, f, indent=2, default=str)
    paths["json"] = str(json_path)
    
    # Save HTML report
    html_path = output_path / f"{base_name}_report.html"
    html_content = _generate_position_html_report(analysis)
    with open(html_path, "w") as f:
        f.write(html_content)
    paths["report"] = str(html_path)
    
    return paths



# ═══════════════════════════════════════════════════════════════════════════════
# HTML REPORT GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_position_html_report(analysis: PositionAnalysis) -> str:
    """Generate HTML report for position analysis."""
    a = analysis
    t = a.trend
    
    pnl_color = "#22c55e" if a.pnl_pct >= 0 else "#ef4444"
    trend_color = "#22c55e" if t.primary_trend == "UPTREND" else "#ef4444" if t.primary_trend == "DOWNTREND" else "#eab308"
    action_color = {
        "HOLD": "#3b82f6",
        "TAKE PROFIT": "#22c55e",
        "PARTIAL PROFIT": "#22c55e",
        "ADD MORE": "#06b6d4",
        "CUT LOSS": "#ef4444",
    }.get(a.action_recommendation, "#6b7280")
    
    action_emoji = {
        "HOLD": "⏸️",
        "TAKE PROFIT": "💰",
        "PARTIAL PROFIT": "💵",
        "ADD MORE": "➕",
        "CUT LOSS": "✂️",
    }.get(a.action_recommendation, "❓")
    
    # Format support/resistance levels
    support_html = "".join([f"<span class='level support'>RM {l:.4f}</span>" for l in t.support_levels[:3]]) or "<span class='na'>None identified</span>"
    resistance_html = "".join([f"<span class='level resistance'>RM {l:.4f}</span>" for l in t.resistance_levels[:3]]) or "<span class='na'>None identified</span>"
    
    # Reasoning list
    reasoning_html = "".join([f"<li>{r}</li>" for r in a.action_reasoning])
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Position Analysis - {a.ticker}</title>
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
            --cyan: #06b6d4;
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
        
        .container {{ max-width: 900px; margin: 0 auto; }}
        
        header {{
            text-align: center;
            padding: 30px 20px;
            background: linear-gradient(135deg, var(--bg-secondary) 0%, #1a2744 100%);
            border-radius: 20px;
            margin-bottom: 30px;
        }}
        
        h1 {{ font-size: 2rem; margin-bottom: 10px; }}
        .subtitle {{ color: var(--text-secondary); }}
        
        .pnl-hero {{
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-top: 20px;
            flex-wrap: wrap;
        }}
        
        .pnl-stat {{
            text-align: center;
        }}
        
        .pnl-label {{
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 5px;
        }}
        
        .pnl-value {{
            font-size: 2rem;
            font-weight: 700;
        }}
        
        .pnl-value.positive {{ color: var(--green); }}
        .pnl-value.negative {{ color: var(--red); }}
        
        .section {{
            background: var(--bg-secondary);
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 20px;
        }}
        
        .section-title {{
            font-size: 1.3rem;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .recommendation-box {{
            background: linear-gradient(135deg, {action_color}20, {action_color}10);
            border: 2px solid {action_color};
            border-radius: 16px;
            padding: 30px;
            text-align: center;
            margin-bottom: 20px;
        }}
        
        .recommendation-action {{
            font-size: 2.5rem;
            font-weight: 700;
            color: {action_color};
            margin-bottom: 10px;
        }}
        
        .recommendation-emoji {{
            font-size: 3rem;
            margin-bottom: 10px;
        }}
        
        .reasoning-list {{
            text-align: left;
            margin-top: 20px;
            padding-left: 20px;
        }}
        
        .reasoning-list li {{
            margin-bottom: 8px;
            color: var(--text-secondary);
        }}
        
        .risk-reward {{
            margin-top: 15px;
            padding: 10px;
            background: var(--bg-tertiary);
            border-radius: 8px;
            display: inline-block;
        }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}
        
        .metric-card {{
            background: var(--bg-tertiary);
            border-radius: 12px;
            padding: 20px;
        }}
        
        .metric-label {{
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 5px;
        }}
        
        .metric-value {{
            font-size: 1.5rem;
            font-weight: 600;
        }}
        
        .metric-subtext {{
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-top: 5px;
        }}
        
        .trend-indicator {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 1.1rem;
        }}
        
        .trend-uptrend {{ background: rgba(34, 197, 94, 0.2); color: var(--green); }}
        .trend-downtrend {{ background: rgba(239, 68, 68, 0.2); color: var(--red); }}
        .trend-sideways {{ background: rgba(234, 179, 8, 0.2); color: var(--yellow); }}
        
        .levels-container {{
            display: flex;
            gap: 30px;
            flex-wrap: wrap;
        }}
        
        .levels-group {{
            flex: 1;
            min-width: 200px;
        }}
        
        .levels-title {{
            font-size: 0.9rem;
            color: var(--text-muted);
            margin-bottom: 10px;
        }}
        
        .level {{
            display: inline-block;
            padding: 6px 12px;
            margin: 4px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 0.9rem;
        }}
        
        .level.support {{ background: rgba(34, 197, 94, 0.2); color: var(--green); }}
        .level.resistance {{ background: rgba(239, 68, 68, 0.2); color: var(--red); }}
        
        .score-bar {{
            height: 10px;
            background: var(--bg-primary);
            border-radius: 5px;
            overflow: hidden;
            margin-top: 10px;
        }}
        
        .score-fill {{
            height: 100%;
            border-radius: 5px;
            transition: width 0.5s;
        }}
        
        .na {{ color: var(--text-muted); font-style: italic; }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        
        th {{
            color: var(--text-muted);
            font-weight: 600;
            font-size: 0.85rem;
        }}
        
        .prompt-section {{
            margin-top: 20px;
        }}
        
        .prompt-toggle {{
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, var(--purple), #6d28d9);
            border: none;
            border-radius: 12px;
            color: white;
            font-weight: 600;
            font-size: 1rem;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }}
        
        .prompt-toggle:hover {{
            filter: brightness(1.1);
        }}
        
        .prompt-content {{
            display: none;
            margin-top: 15px;
            background: var(--bg-tertiary);
            border-radius: 12px;
            padding: 20px;
        }}
        
        .prompt-content.show {{ display: block; }}
        
        .prompt-text {{
            background: var(--bg-primary);
            padding: 15px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 0.8rem;
            white-space: pre-wrap;
            max-height: 400px;
            overflow-y: auto;
            color: var(--text-secondary);
        }}
        
        .copy-btn {{
            padding: 10px 20px;
            background: var(--purple);
            border: none;
            border-radius: 8px;
            color: white;
            font-weight: 600;
            cursor: pointer;
            margin-bottom: 15px;
        }}
        
        .copy-btn:hover {{ background: #7c3aed; }}
        .copy-btn.copied {{ background: var(--green); }}
        
        footer {{
            text-align: center;
            padding: 30px;
            margin-top: 30px;
            color: var(--text-muted);
            font-size: 0.85rem;
        }}
        
        @media (max-width: 600px) {{
            .pnl-hero {{ gap: 20px; }}
            .pnl-value {{ font-size: 1.5rem; }}
            .recommendation-action {{ font-size: 1.8rem; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 {a.ticker}</h1>
            <p class="subtitle">{a.name or 'Unknown'}</p>
            <p class="subtitle" style="margin-top: 10px; font-size: 0.85rem;">
                Analysis Date: {a.analysis_date}
            </p>
            
            <div class="pnl-hero">
                <div class="pnl-stat">
                    <div class="pnl-label">Entry Price</div>
                    <div class="pnl-value">RM {a.entry_price:.4f}</div>
                </div>
                <div class="pnl-stat">
                    <div class="pnl-label">Current Price</div>
                    <div class="pnl-value">RM {a.current_price:.4f}</div>
                </div>
                <div class="pnl-stat">
                    <div class="pnl-label">P&L</div>
                    <div class="pnl-value {'positive' if a.pnl_pct >= 0 else 'negative'}">{a.pnl_pct:+.2f}%</div>
                </div>
                <div class="pnl-stat">
                    <div class="pnl-label">Total P&L ({a.shares:,} shares)</div>
                    <div class="pnl-value {'positive' if a.total_pnl >= 0 else 'negative'}">RM {a.total_pnl:+,.2f}</div>
                </div>
            </div>
        </header>
        
        <!-- Recommendation -->
        <div class="recommendation-box">
            <div class="recommendation-emoji">{action_emoji}</div>
            <div class="recommendation-action">{a.action_recommendation}</div>
            <div style="color: var(--text-secondary);">{a.pnl_status}</div>
            
            <ul class="reasoning-list">
                {reasoning_html}
            </ul>
            
            <div class="risk-reward">
                <strong>Risk/Reward:</strong> {a.risk_reward_assessment}
            </div>
        </div>
        
        <!-- Position Details -->
        <div class="section">
            <div class="section-title">💼 Position Details</div>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Shares Held</div>
                    <div class="metric-value">{a.shares:,}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Cost Basis</div>
                    <div class="metric-value">RM {a.cost_basis:,.2f}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Current Value</div>
                    <div class="metric-value">RM {a.position_value:,.2f}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">P&L per Share</div>
                    <div class="metric-value" style="color: {pnl_color}">RM {a.pnl_per_share:+.4f}</div>
                </div>
            </div>
        </div>
        
        <!-- Trend Analysis -->
        <div class="section">
            <div class="section-title">📈 Trend Analysis</div>
            
            <div style="margin-bottom: 20px;">
                <span class="trend-indicator trend-{t.primary_trend.lower()}">
                    {'📈' if t.primary_trend == 'UPTREND' else '📉' if t.primary_trend == 'DOWNTREND' else '➡️'} 
                    {t.primary_trend} ({t.trend_strength})
                </span>
                <span style="margin-left: 15px; color: var(--text-muted);">
                    Duration: {t.trend_duration_days} days
                </span>
            </div>
            
            <table>
                <tr>
                    <th>Indicator</th>
                    <th>Status</th>
                    <th>Signal</th>
                </tr>
                <tr>
                    <td>Price vs 20-MA</td>
                    <td>{t.price_vs_ma20}</td>
                    <td>{'🟢 Bullish' if t.price_vs_ma20 == 'ABOVE' else '🔴 Bearish' if t.price_vs_ma20 == 'BELOW' else '⚪ Neutral'}</td>
                </tr>
                <tr>
                    <td>Price vs 50-MA</td>
                    <td>{t.price_vs_ma50}</td>
                    <td>{'🟢 Bullish' if t.price_vs_ma50 == 'ABOVE' else '🔴 Bearish' if t.price_vs_ma50 == 'BELOW' else '⚪ Neutral'}</td>
                </tr>
                <tr>
                    <td>Price vs 200-MA</td>
                    <td>{t.price_vs_ma200}</td>
                    <td>{'🟢 Bullish' if t.price_vs_ma200 == 'ABOVE' else '🔴 Bearish' if t.price_vs_ma200 == 'BELOW' else '⚪ Neutral'}</td>
                </tr>
                <tr>
                    <td>MA Alignment</td>
                    <td>{t.ma_alignment}</td>
                    <td>{'🟢 20>50>200' if t.ma_alignment == 'BULLISH' else '🔴 20<50<200' if t.ma_alignment == 'BEARISH' else '⚪ Mixed'}</td>
                </tr>
                <tr>
                    <td>RSI Zone</td>
                    <td>{t.rsi_zone}</td>
                    <td>{'🟢' if t.rsi_zone == 'BULLISH' else '🔴' if t.rsi_zone in ['OVERBOUGHT', 'BEARISH'] else '⚪'} {f"{a.tech_score.rsi_val:.1f}" if a.tech_score.rsi_val else 'N/A'}</td>
                </tr>
                <tr>
                    <td>MACD Signal</td>
                    <td>{t.macd_signal}</td>
                    <td>{'🟢 Bullish' if t.macd_signal == 'BULLISH' else '🔴 Bearish' if t.macd_signal == 'BEARISH' else '⚪ Neutral'}</td>
                </tr>
                <tr>
                    <td>Volume Trend</td>
                    <td>{t.volume_trend}</td>
                    <td>{f"{a.tech_score.volume_ratio:.2f}x avg" if a.tech_score.volume_ratio else 'N/A'}</td>
                </tr>
            </table>
            
            <div style="margin-top: 20px;">
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-label">1 Week</div>
                        <div class="metric-value" style="color: {'var(--green)' if t.week_change_pct >= 0 else 'var(--red)'}">{t.week_change_pct:+.1f}%</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">1 Month</div>
                        <div class="metric-value" style="color: {'var(--green)' if t.month_change_pct >= 0 else 'var(--red)'}">{t.month_change_pct:+.1f}%</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">3 Months</div>
                        <div class="metric-value" style="color: {'var(--green)' if t.quarter_change_pct >= 0 else 'var(--red)'}">{t.quarter_change_pct:+.1f}%</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Key Levels -->
        <div class="section">
            <div class="section-title">📍 Key Price Levels</div>
            <div class="levels-container">
                <div class="levels-group">
                    <div class="levels-title">🟢 Support Levels (buy zones)</div>
                    {support_html}
                </div>
                <div class="levels-group">
                    <div class="levels-title">🔴 Resistance Levels (sell zones)</div>
                    {resistance_html}
                </div>
            </div>
            <div style="margin-top: 20px; padding: 15px; background: var(--bg-tertiary); border-radius: 10px;">
                <strong>Your Entry:</strong> RM {a.entry_price:.4f} | 
                <strong>Nearest Support:</strong> RM {f"{t.nearest_support:.4f}" if t.nearest_support else "N/A"} | 
                <strong>Nearest Resistance:</strong> RM {f"{t.nearest_resistance:.4f}" if t.nearest_resistance else "N/A"}
            </div>
        </div>
        
        <!-- Scores -->
        <div class="section">
            <div class="section-title">📊 Quality Scores</div>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Fundamental Score</div>
                    <div class="metric-value">{a.fund_score.total}/{a.fund_score.max_score}</div>
                    <div class="score-bar">
                        <div class="score-fill" style="width: {(a.fund_score.total/a.fund_score.max_score)*100}%; background: {'var(--green)' if a.fund_score.total/a.fund_score.max_score >= 0.65 else 'var(--yellow)' if a.fund_score.total/a.fund_score.max_score >= 0.5 else 'var(--red)'}"></div>
                    </div>
                    <div class="metric-subtext">{(a.fund_score.total/a.fund_score.max_score)*100:.0f}% - {'Strong' if a.fund_score.total/a.fund_score.max_score >= 0.65 else 'Average' if a.fund_score.total/a.fund_score.max_score >= 0.5 else 'Weak'}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Technical Score</div>
                    <div class="metric-value">{a.tech_score.total}/25</div>
                    <div class="score-bar">
                        <div class="score-fill" style="width: {(a.tech_score.total/25)*100}%; background: {'var(--green)' if a.tech_score.total/25 >= 0.7 else 'var(--yellow)' if a.tech_score.total/25 >= 0.5 else 'var(--red)'}"></div>
                    </div>
                    <div class="metric-subtext">{(a.tech_score.total/25)*100:.0f}% - {'Strong' if a.tech_score.total/25 >= 0.7 else 'Average' if a.tech_score.total/25 >= 0.5 else 'Weak'}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Classification</div>
                    <div class="metric-value" style="font-size: 1rem;">{a.result.classification}</div>
                </div>
            </div>
        </div>
        
        <!-- AI Prompt Section -->
        <div class="section prompt-section">
            <div class="section-title">🤖 AI Deep Analysis Prompt</div>
            <p style="color: var(--text-secondary); margin-bottom: 15px;">
                Copy this prompt to ChatGPT, Claude, or any AI assistant for a detailed position analysis with specific recommendations.
            </p>
            <button class="prompt-toggle" onclick="togglePrompt()">
                <span>📋 Show AI Prompt</span>
                <span id="toggle-icon">▼</span>
            </button>
            <div id="prompt-content" class="prompt-content">
                <button class="copy-btn" onclick="copyPrompt()">📋 Copy Prompt</button>
                <div class="prompt-text" id="prompt-text">{_escape_html_for_report(a.ai_prompt)}</div>
            </div>
        </div>
        
        <footer>
            <p><strong>Be Richer</strong> — Position Analyzer</p>
            <p style="margin-top: 10px; font-size: 0.8rem;">
                ⚠️ This is an automated analysis tool for educational purposes only.
                Always do your own research before making investment decisions.
            </p>
        </footer>
    </div>
    
    <script>
        function togglePrompt() {{
            const content = document.getElementById('prompt-content');
            const icon = document.getElementById('toggle-icon');
            if (content.classList.contains('show')) {{
                content.classList.remove('show');
                icon.textContent = '▼';
            }} else {{
                content.classList.add('show');
                icon.textContent = '▲';
            }}
        }}
        
        function copyPrompt() {{
            const text = document.getElementById('prompt-text').textContent;
            navigator.clipboard.writeText(text).then(() => {{
                const btn = event.target;
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
</html>'''
    
    return html


def _escape_html_for_report(text: str) -> str:
    """Escape HTML special characters."""
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
