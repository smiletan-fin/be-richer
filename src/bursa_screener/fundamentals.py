"""
Fundamental scoring engine — maps to your 60-point framework.

Scoring map (matches your spec):
    A. Earnings Quality      15 pts
    B. ROE / ROIC            10 pts
    C. Financial Health      10 pts
    D. Valuation Margin      15 pts
    E. Operating Cash Flow    5 pts
    F. Dividends              5 pts
    ──────────────────────────────
    Total                    60 pts

Honest limitations:
- Core EPS (normalized) cannot be computed from yfinance alone.
  We use TTM EPS as a proxy and flag it clearly.
- Cyclical earnings adjustment is flagged by sector, not computed.
- Forward PE comes from Yahoo analyst consensus — sparse for small caps.
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

    # factor scores
    score_earnings_quality: int = 0   # max 15
    score_roe:              int = 0   # max 10
    score_financial_health: int = 0   # max 10
    score_valuation:        int = 0   # max 15
    score_cashflow:         int = 0   # max  5
    score_dividends:        int = 0   # max  5

    # display values
    pe_ttm:       float | None = None
    forward_pe:   float | None = None
    pb:           float | None = None
    roe_pct:      float | None = None   # as %
    net_gearing:  float | None = None
    div_yield_pct: float | None = None  # as %
    sector:       str | None   = None
    is_cyclical:  bool         = False

    # flags
    flags: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def total(self) -> int:
        return (
            self.score_earnings_quality + self.score_roe
            + self.score_financial_health + self.score_valuation
            + self.score_cashflow + self.score_dividends
        )

    @property
    def breakdown(self) -> str:
        return (
            f"EQ={self.score_earnings_quality}/15  "
            f"ROE={self.score_roe}/10  "
            f"FH={self.score_financial_health}/10  "
            f"Val={self.score_valuation}/15  "
            f"CF={self.score_cashflow}/5  "
            f"Div={self.score_dividends}/5"
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

    result.pe_ttm       = pe_ttm
    result.forward_pe   = forward_pe
    result.pb           = pb
    result.roe_pct      = round(roe * 100, 1) if roe is not None else None
    result.net_gearing  = net_gearing
    result.div_yield_pct = round(div_yield * 100, 1) if div_yield is not None else None
    result.sector       = sector
    result.is_cyclical  = sector in CYCLICAL_SECTORS

    benchmark_pe = SECTOR_PE_BENCHMARKS.get(sector, SECTOR_PE_BENCHMARKS["default"])

    # ── A. Earnings Quality (max 15) ──────────────────────────────────────────
    # Without quarterly report parsing, we can't do full normalization.
    # Score based on PE reasonableness + OCF vs net income consistency.
    eq = 0
    if pe_ttm is not None:
        if pe_ttm < 0:
            eq = 0
            result.flags.append("Negative PE — loss-making or negative earnings")
        elif pe_ttm < benchmark_pe * 0.7:
            eq = 12   # well below sector average — potentially undervalued or cyclical peak
        elif pe_ttm < benchmark_pe:
            eq = 10
        elif pe_ttm < benchmark_pe * 1.3:
            eq = 7
        else:
            eq = 4    # expensive relative to sector

        # OCF quality check: good earnings backed by cash
        # Skip for Financial Services — OCF from yfinance is unreliable for banks
        is_financial_sector = sector in ("Financial Services",)
        if not is_financial_sector and ocf is not None and net_income is not None and net_income > 0:
            ocf_ratio = ocf / net_income
            if ocf_ratio >= 0.8:
                eq = min(eq + 3, 15)   # strong cash conversion
            elif ocf_ratio >= 0.5:
                eq = min(eq + 1, 15)
            else:
                result.flags.append("Low OCF/Net Income ratio — earnings quality concern")
    else:
        eq = 5   # no PE data — partial credit, flag it
        result.flags.append("TTM PE unavailable — earnings quality score reduced")

    if result.is_cyclical:
        result.flags.append(
            f"⚠ Cyclical sector ({sector}) — PE may reflect cycle position, not intrinsic value"
        )

    result.score_earnings_quality = eq

    # ── B. ROE / ROIC (max 10) ────────────────────────────────────────────────
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

    # ── C. Financial Health (max 10) ──────────────────────────────────────────
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
        # fallback: simple net debt signal
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

    # ── D. Valuation Margin of Safety (max 15) ────────────────────────────────
    val = 0
    pe_score = 0
    pb_score = 0

    # PE component (max 9)
    if pe_ttm is not None and pe_ttm > 0:
        pe_discount = (benchmark_pe - pe_ttm) / benchmark_pe
        if pe_discount >= PE_DISCOUNT_DEEP:
            pe_score = 9
        elif pe_discount >= PE_DISCOUNT_MODERATE:
            pe_score = 7
        elif pe_discount >= 0.0:
            pe_score = 5
        elif pe_discount >= -PE_PREMIUM_MODERATE:
            pe_score = 3
        else:
            pe_score = 1   # expensive vs sector
    elif forward_pe is not None and forward_pe > 0:
        # fallback to forward PE
        fwd_discount = (benchmark_pe - forward_pe) / benchmark_pe
        pe_score = max(0, min(7, int((fwd_discount + 0.3) / 0.1 * 2)))
        result.flags.append("Using forward PE (TTM unavailable)")
    else:
        pe_score = 3
        result.flags.append("PE unavailable — valuation score reduced")

    # PB component (max 6)
    if pb is not None:
        if pb < PB_DEEP_VALUE:
            pb_score = 6   # deep value / potential asset play
        elif pb < PB_FAIR:
            pb_score = 5
        elif pb < PB_MODERATE:
            pb_score = 4
        elif pb < PB_GROWTH:
            pb_score = 3
        elif pb < PB_EXPENSIVE:
            pb_score = 2
        else:
            pb_score = 1
    else:
        pb_score = 2
        result.flags.append("PB unavailable")

    result.score_valuation = min(pe_score + pb_score, 15)

    # ── E. Operating Cash Flow (max 5) ────────────────────────────────────────
    # Note: For banks/financial services, yfinance OCF from .info is unreliable
    # (it can reflect loan book changes, not operating performance).
    # We score conservatively for Financial Services sector.
    is_financial = sector in ("Financial Services",)

    if is_financial:
        # Use net income as a proxy; award partial score if profitable
        if net_income is not None and net_income > 0:
            result.score_cashflow = 3
            result.flags.append("Financial sector: OCF scored on net income proxy (yfinance limitation)")
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
        result.score_cashflow = 2   # positive but can't compute yield
    else:
        result.score_cashflow = 1
        result.flags.append("OCF data unavailable")

    # ── F. Dividends / Capital Returns (max 5) ────────────────────────────────
    if div_yield is not None:
        dy_pct = div_yield * 100
        if dy_pct >= DIV_YIELD_HIGH:
            result.score_dividends = 5
        elif dy_pct >= DIV_YIELD_GOOD:
            result.score_dividends = 4
        elif dy_pct >= DIV_YIELD_MODERATE:
            result.score_dividends = 3
        elif dy_pct >= DIV_YIELD_LOW:
            result.score_dividends = 2
        else:
            result.score_dividends = 1
    else:
        result.score_dividends = 1
        result.flags.append("No dividend data")

    return result
