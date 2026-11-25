"""
Fundamental scoring engine — Enhanced 65-point framework.

Aligned with industry standards (Piotroski F-Score, Quality Factor Investing):

Scoring map:
    A. Earnings Quality      10 pts  (reduced from 15)
    B. Earnings Growth       10 pts  (NEW - critical for quality)
    C. ROE / ROIC            10 pts
    D. Financial Health      10 pts
    E. Valuation Margin      12 pts  (reduced from 15)
    F. Operating Cash Flow    5 pts
    G. Dividends              3 pts  (reduced from 5 - growth stocks don't pay)
    H. Improving Fundamentals 5 pts  (NEW - Piotroski-style YoY checks)
    ──────────────────────────────
    Total                    65 pts

Industry alignment:
- Earnings Growth: CAN SLIM requires >25% EPS growth
- ROIC consideration: Research shows ROIC beats ROE 17:1
- Improving Fundamentals: Piotroski F-Score elements
- Reduced dividend weight: High-growth companies often don't pay dividends

Limitations:
- Core EPS (normalized) cannot be computed from yfinance alone.
- YoY growth data may be incomplete for some stocks.
- Forward PE from Yahoo analyst consensus — sparse for small caps.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any


# ── constants ────────────────────────────────────────────────────────────────
CONFIG_DIR = Path(__file__).parent / "config"
SECTOR_PE_CONFIG_FILE = CONFIG_DIR / "sector_pe_benchmarks.json"

# Default sector-level PE benchmarks (rough Bursa averages)
# These are reference midpoints — can be overridden via config file
DEFAULT_SECTOR_PE_BENCHMARKS: dict[str, float] = {
    "Financial Services":     12.0,
    "Consumer Defensive":     18.0,
    "Consumer Cyclical":      16.0,
    "Healthcare":             22.0,
    "Technology":             25.0,
    "Energy":                 10.0,
    "Basic Materials":        14.0,
    "Industrials":            14.0,
    "Real Estate":            12.0,
    "Utilities":              16.0,
    "Communication Services": 15.0,
    "default":                15.0,
}

# Sectors where cyclical earnings warning applies
CYCLICAL_SECTORS = {
    "Energy", "Basic Materials", "Industrials",
    "Consumer Cyclical", "Real Estate",
}

# ── ROE scoring thresholds ───────────────────────────────────────────────────
ROE_EXCELLENT = 18.0    # max score
ROE_GOOD = 14.0
ROE_FAIR = 10.0
ROE_WEAK = 6.0

# ── Financial health (gearing) thresholds ────────────────────────────────────
GEARING_NET_CASH = -0.1      # net cash position
GEARING_LOW = 0.2
GEARING_MODERATE = 0.5
GEARING_ELEVATED = 1.0

# ── Valuation thresholds ─────────────────────────────────────────────────────
PE_DISCOUNT_DEEP = 0.30      # 30% below sector benchmark
PE_DISCOUNT_MODERATE = 0.15
PE_PREMIUM_MODERATE = 0.20

PB_DEEP_VALUE = 0.7
PB_FAIR = 1.0
PB_MODERATE = 1.5
PB_GROWTH = 2.5
PB_EXPENSIVE = 4.0

# ── Cash flow thresholds ─────────────────────────────────────────────────────
FCF_YIELD_EXCELLENT = 0.08
FCF_YIELD_GOOD = 0.05
FCF_YIELD_FAIR = 0.03
FCF_YIELD_WEAK = 0.01

# ── Dividend yield thresholds ────────────────────────────────────────────────
DIV_YIELD_HIGH = 5.0
DIV_YIELD_GOOD = 3.5
DIV_YIELD_MODERATE = 2.0
DIV_YIELD_LOW = 0.5

# ── Earnings Growth thresholds (NEW - CAN SLIM aligned) ──────────────────────
EARNINGS_GROWTH_EXCELLENT = 25.0   # CAN SLIM threshold
EARNINGS_GROWTH_GOOD = 15.0        # Quality factor threshold  
EARNINGS_GROWTH_FAIR = 8.0
EARNINGS_GROWTH_WEAK = 0.0

# ── Revenue Growth thresholds (NEW) ──────────────────────────────────────────
REVENUE_GROWTH_EXCELLENT = 20.0
REVENUE_GROWTH_GOOD = 10.0
REVENUE_GROWTH_FAIR = 5.0


def load_sector_benchmarks() -> dict[str, float]:
    """
    Load sector PE benchmarks from config file if available,
    otherwise use defaults.
    """
    if SECTOR_PE_CONFIG_FILE.exists():
        try:
            with open(SECTOR_PE_CONFIG_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_SECTOR_PE_BENCHMARKS.copy()


def save_sector_benchmarks(benchmarks: dict[str, float]) -> None:
    """Save sector PE benchmarks to config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(SECTOR_PE_CONFIG_FILE, "w") as f:
        json.dump(benchmarks, f, indent=2)


def compute_sector_benchmarks_from_data(
    raw_data: dict[str, dict],
    min_samples: int = 3,
) -> dict[str, float]:
    """
    Dynamically compute sector PE benchmarks from the screened universe.

    Args:
        raw_data: dict from batch_fetch { ticker: { "fundamentals": {...} } }
        min_samples: minimum stocks per sector to compute a benchmark

    Returns:
        dict of { sector: median_pe }
        Falls back to default if insufficient data.
    """
    from collections import defaultdict

    sector_pes: dict[str, list[float]] = defaultdict(list)

    for ticker, data in raw_data.items():
        fund = data.get("fundamentals") or {}
        sector = fund.get("sector")
        pe = fund.get("pe_ttm")

        if sector and pe is not None and 0 < pe < 100:  # filter outliers
            sector_pes[sector].append(pe)

    defaults = load_sector_benchmarks()
    result = defaults.copy()

    for sector, pes in sector_pes.items():
        if len(pes) >= min_samples:
            result[sector] = round(median(pes), 1)

    return result


# Load benchmarks at module level (can be reloaded dynamically)
SECTOR_PE_BENCHMARKS = load_sector_benchmarks()


# ── result dataclass ──────────────────────────────────────────────────────────

@dataclass
class FundamentalScore:
    ticker: str

    # factor scores (updated weights)
    score_earnings_quality: int = 0   # max 10 (reduced from 15)
    score_earnings_growth:  int = 0   # max 10 (NEW)
    score_roe:              int = 0   # max 10
    score_financial_health: int = 0   # max 10
    score_valuation:        int = 0   # max 12 (reduced from 15)
    score_cashflow:         int = 0   # max  5
    score_dividends:        int = 0   # max  3 (reduced from 5)
    score_improving:        int = 0   # max  5 (NEW - Piotroski-style)

    # display values
    pe_ttm:       float | None = None
    forward_pe:   float | None = None
    pb:           float | None = None
    roe_pct:      float | None = None   # as %
    net_gearing:  float | None = None
    div_yield_pct: float | None = None  # as %
    sector:       str | None   = None
    is_cyclical:  bool         = False
    
    # NEW: Growth metrics
    earnings_growth_pct: float | None = None  # YoY EPS growth %
    revenue_growth_pct:  float | None = None  # YoY revenue growth %

    # flags
    flags: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def total(self) -> int:
        return (
            self.score_earnings_quality + self.score_earnings_growth
            + self.score_roe + self.score_financial_health 
            + self.score_valuation + self.score_cashflow 
            + self.score_dividends + self.score_improving
        )

    @property
    def breakdown(self) -> str:
        return (
            f"EQ={self.score_earnings_quality}/10  "
            f"EG={self.score_earnings_growth}/10  "
            f"ROE={self.score_roe}/10  "
            f"FH={self.score_financial_health}/10  "
            f"Val={self.score_valuation}/12  "
            f"CF={self.score_cashflow}/5  "
            f"Div={self.score_dividends}/3  "
            f"Imp={self.score_improving}/5"
        )


# ── scorer ────────────────────────────────────────────────────────────────────

def score_fundamentals(ticker: str, info: dict[str, Any]) -> FundamentalScore:
    result = FundamentalScore(ticker=ticker)

    if not info or all(v is None for k, v in info.items() if k not in ("ticker",)):
        result.error = "No fundamental data available"
        return result

    # ── convenience getters ───────────────────────────────────────────────────
    def _f(key: str) -> float | None:
        v = info.get(key)
        return float(v) if v is not None else None

    pe_ttm      = _f("pe_ttm")
    forward_pe  = _f("forward_pe")
    pb          = _f("pb")
    roe         = _f("roe")              # decimal (0.12 = 12 %)
    net_gearing = _f("net_gearing")
    ocf         = _f("operating_cash_flow")
    net_income  = _f("net_income_ttm")
    div_yield   = _f("dividend_yield")   # decimal
    sector      = info.get("sector") or "default"
    market_cap  = _f("market_cap")
    total_debt  = _f("total_debt")
    total_cash  = _f("total_cash")
    
    # NEW: Growth metrics from yfinance
    earnings_growth = _f("earningsGrowth")      # YoY earnings growth (decimal)
    revenue_growth  = _f("revenueGrowth")       # YoY revenue growth (decimal)
    earnings_quarterly_growth = _f("earningsQuarterlyGrowth")  # QoQ growth

    result.pe_ttm       = pe_ttm
    result.forward_pe   = forward_pe
    result.pb           = pb
    result.roe_pct      = round(roe * 100, 1) if roe is not None else None
    result.net_gearing  = net_gearing
    # Note: yfinance sometimes returns dividend_yield as percentage (6.11 for 6.11%)
    # and sometimes as decimal (0.0611). Handle both cases.
    if div_yield is not None:
        if div_yield > 1:  # Already in percentage form
            result.div_yield_pct = round(div_yield, 1)
        else:  # Decimal form
            result.div_yield_pct = round(div_yield * 100, 1)
    else:
        result.div_yield_pct = None
    result.sector       = sector
    result.is_cyclical  = sector in CYCLICAL_SECTORS
    
    # Store growth metrics
    if earnings_growth is not None:
        result.earnings_growth_pct = round(earnings_growth * 100, 1)
    if revenue_growth is not None:
        result.revenue_growth_pct = round(revenue_growth * 100, 1)

    benchmark_pe = SECTOR_PE_BENCHMARKS.get(sector, SECTOR_PE_BENCHMARKS["default"])

    # ── A. Earnings Quality (max 10, reduced from 15) ─────────────────────────
    # Score based on PE reasonableness + OCF vs net income consistency.
    eq = 0
    if pe_ttm is not None:
        if pe_ttm < 0:
            eq = 0
            result.flags.append("Negative PE — loss-making or negative earnings")
        elif pe_ttm < benchmark_pe * 0.7:
            eq = 8   # well below sector average
        elif pe_ttm < benchmark_pe:
            eq = 6
        elif pe_ttm < benchmark_pe * 1.3:
            eq = 4
        else:
            eq = 2   # expensive relative to sector

        # OCF quality check (skip for Financial Services)
        is_financial_sector = sector in ("Financial Services",)
        if not is_financial_sector and ocf is not None and net_income is not None and net_income > 0:
            ocf_ratio = ocf / net_income
            if ocf_ratio >= 0.8:
                eq = min(eq + 2, 10)   # strong cash conversion
            elif ocf_ratio < 0.5:
                result.flags.append("Low OCF/Net Income ratio — earnings quality concern")
    else:
        eq = 3
        result.flags.append("TTM PE unavailable — earnings quality score reduced")

    if result.is_cyclical:
        result.flags.append(
            f"⚠ Cyclical sector ({sector}) — PE may reflect cycle position, not intrinsic value"
        )

    result.score_earnings_quality = eq

    # ── B. Earnings Growth (max 10, NEW - CAN SLIM aligned) ───────────────────
    eg = 0
    growth_used = None
    
    # Prefer YoY earnings growth, fallback to quarterly
    if earnings_growth is not None:
        growth_pct = earnings_growth * 100
        growth_used = "annual"
    elif earnings_quarterly_growth is not None:
        growth_pct = earnings_quarterly_growth * 100
        growth_used = "quarterly"
    else:
        growth_pct = None
    
    if growth_pct is not None:
        if growth_pct >= EARNINGS_GROWTH_EXCELLENT:  # 25%+
            eg = 10
            result.flags.append(f"🚀 Strong earnings growth: {growth_pct:.1f}% ({growth_used})")
        elif growth_pct >= EARNINGS_GROWTH_GOOD:     # 15%+
            eg = 8
        elif growth_pct >= EARNINGS_GROWTH_FAIR:     # 8%+
            eg = 5
        elif growth_pct >= EARNINGS_GROWTH_WEAK:     # 0%+
            eg = 3
        else:  # negative growth
            eg = 0
            result.flags.append(f"⚠ Negative earnings growth: {growth_pct:.1f}%")
    else:
        eg = 3  # partial credit if data unavailable
        result.flags.append("Earnings growth data unavailable")
    
    # Bonus for revenue growth confirmation
    if revenue_growth is not None:
        rev_pct = revenue_growth * 100
        if rev_pct >= REVENUE_GROWTH_EXCELLENT and eg >= 5:
            eg = min(eg + 1, 10)
        elif rev_pct < 0:
            result.flags.append(f"⚠ Declining revenue: {rev_pct:.1f}%")
    
    result.score_earnings_growth = eg

    # ── C. ROE / ROIC (max 10) ────────────────────────────────────────────────
    if roe is not None:
        roe_pct = roe * 100
        if roe_pct >= ROE_EXCELLENT:
            result.score_roe = 10
        elif roe_pct >= ROE_GOOD:
            result.score_roe = 8
        elif roe_pct >= ROE_FAIR:
            result.score_roe = 6
        elif roe_pct >= ROE_WEAK:
            result.score_roe = 4
        elif roe_pct > 0:
            result.score_roe = 2
        else:
            result.score_roe = 0
            result.flags.append("Negative ROE")
    else:
        result.score_roe = 3
        result.flags.append("ROE unavailable")

    # ── D. Financial Health (max 10) ──────────────────────────────────────────
    fh = 0
    if net_gearing is not None:
        if net_gearing <= GEARING_NET_CASH:         # net cash
            fh = 10
            result.flags.append("Net cash position ✓")
        elif net_gearing <= GEARING_LOW:            # low gearing
            fh = 8
        elif net_gearing <= GEARING_MODERATE:       # moderate
            fh = 6
        elif net_gearing <= GEARING_ELEVATED:       # elevated
            fh = 4
        else:                                       # high gearing
            fh = 1
            result.flags.append(f"High net gearing: {net_gearing:.2f}x — financial health risk")
    elif total_debt is not None and total_cash is not None:
        if total_cash > total_debt:
            fh = 8
        elif total_debt < total_cash * 2:
            fh = 5
        else:
            fh = 3
    else:
        fh = 4
        result.flags.append("Gearing data unavailable — partial score")

    result.score_financial_health = fh

    # ── E. Valuation Margin of Safety (max 12, reduced from 15) ───────────────
    pe_score = 0
    pb_score = 0

    # PE component (max 7)
    if pe_ttm is not None and pe_ttm > 0:
        pe_discount = (benchmark_pe - pe_ttm) / benchmark_pe
        if pe_discount >= PE_DISCOUNT_DEEP:
            pe_score = 7
        elif pe_discount >= PE_DISCOUNT_MODERATE:
            pe_score = 5
        elif pe_discount >= 0.0:
            pe_score = 4
        elif pe_discount >= -PE_PREMIUM_MODERATE:
            pe_score = 2
        else:
            pe_score = 1
    elif forward_pe is not None and forward_pe > 0:
        fwd_discount = (benchmark_pe - forward_pe) / benchmark_pe
        pe_score = max(0, min(5, int((fwd_discount + 0.3) / 0.1 * 2)))
        result.flags.append("Using forward PE (TTM unavailable)")
    else:
        pe_score = 2
        result.flags.append("PE unavailable — valuation score reduced")

    # PB component (max 5)
    if pb is not None:
        if pb < PB_DEEP_VALUE:
            pb_score = 5
        elif pb < PB_FAIR:
            pb_score = 4
        elif pb < PB_MODERATE:
            pb_score = 3
        elif pb < PB_GROWTH:
            pb_score = 2
        elif pb < PB_EXPENSIVE:
            pb_score = 1
        else:
            pb_score = 0
    else:
        pb_score = 1
        result.flags.append("PB unavailable")

    result.score_valuation = min(pe_score + pb_score, 12)

    # ── F. Operating Cash Flow (max 5) ────────────────────────────────────────
    is_financial = sector in ("Financial Services",)

    if is_financial:
        if net_income is not None and net_income > 0:
            result.score_cashflow = 3
            result.flags.append("Financial sector: OCF scored on net income proxy")
        else:
            result.score_cashflow = 1
    elif ocf is not None and market_cap is not None and market_cap > 0:
        if ocf < 0:
            result.score_cashflow = 0
            result.flags.append("Negative operating cash flow")
        else:
            fcf_yield = ocf / market_cap
            if fcf_yield >= FCF_YIELD_EXCELLENT:
                result.score_cashflow = 5
            elif fcf_yield >= FCF_YIELD_GOOD:
                result.score_cashflow = 4
            elif fcf_yield >= FCF_YIELD_FAIR:
                result.score_cashflow = 3
            elif fcf_yield >= FCF_YIELD_WEAK:
                result.score_cashflow = 2
            else:
                result.score_cashflow = 1
    elif ocf is not None and ocf > 0:
        result.score_cashflow = 2
    else:
        result.score_cashflow = 1
        result.flags.append("OCF data unavailable")

    # ── G. Dividends / Capital Returns (max 3, reduced from 5) ────────────────
    # Note: yfinance sometimes returns dividend_yield as percentage or decimal
    if div_yield is not None:
        # Normalize to percentage
        dy_pct = div_yield if div_yield > 1 else div_yield * 100
        if dy_pct >= DIV_YIELD_HIGH:
            result.score_dividends = 3
        elif dy_pct >= DIV_YIELD_GOOD:
            result.score_dividends = 2
        elif dy_pct >= DIV_YIELD_MODERATE:
            result.score_dividends = 2
        elif dy_pct >= DIV_YIELD_LOW:
            result.score_dividends = 1
        else:
            result.score_dividends = 0
    else:
        result.score_dividends = 0
        # Don't flag - growth stocks often don't pay dividends

    # ── H. Improving Fundamentals (max 5, NEW - Piotroski-style) ──────────────
    # Check for positive momentum in key metrics
    imp = 0
    
    # Positive ROE indicates profitability
    if roe is not None and roe > 0:
        imp += 1
    
    # Positive OCF indicates cash generation
    if ocf is not None and ocf > 0:
        imp += 1
    
    # OCF > Net Income indicates quality earnings
    if ocf is not None and net_income is not None and net_income > 0:
        if ocf > net_income:
            imp += 1
    
    # Low/decreasing debt (net cash or low gearing)
    if net_gearing is not None and net_gearing < GEARING_MODERATE:
        imp += 1
    
    # Positive earnings growth
    if earnings_growth is not None and earnings_growth > 0:
        imp += 1
    
    result.score_improving = min(imp, 5)
    
    if imp >= 4:
        result.flags.append("Strong fundamentals momentum ✓")

    return result
