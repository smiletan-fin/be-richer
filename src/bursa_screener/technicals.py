"""
Technical scoring engine — Enhanced 25-point framework.

Aligned with industry standards (Minervini SEPA, O'Neil CAN SLIM):

Scoring map:
    20MA                3 pts
    50MA                3 pts
    200MA               3 pts
    RSI                 2 pts
    MACD                2 pts
    Volume              3 pts
    Breakout / Base     2 pts
    Support/Resistance  2 pts
    Relative Strength   3 pts  (NEW - vs index performance)
    52-Week Position    2 pts  (NEW - Minervini template)
    ─────────────────────────
    Total              25 pts

Industry alignment:
- Relative Strength: Compare stock vs KLCI index (momentum factor)
- 52-Week Position: Minervini requires price >25% above 52-wk low, within 25% of high
- Trend Template completion with MA stacking checks

Returns a TechnicalScore dataclass with per-factor breakdown,
total score, and a status label:
    "Confirmed Uptrend"   ≥ 18 / 25
    "Early Re-Rating"     12 – 17 / 25
    "Downtrend/Value Trap" < 12 / 25
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


# ── constants ─────────────────────────────────────────────────────────────────
# Minimum data requirements
MIN_DAYS_REQUIRED = 30
MIN_DAYS_FOR_200MA = 200

# Moving average periods
MA_SHORT = 20
MA_MID = 50
MA_LONG = 200

# RSI parameters
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_BULLISH_UPPER = 70
RSI_BULLISH_LOWER = 50
RSI_NEUTRAL_LOWER = 40
RSI_OVERSOLD = 30

# MACD parameters
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# Volume analysis
ADV_PERIOD = 30
VOLUME_SURGE_THRESHOLD = 1.5
VOLUME_ELEVATED_THRESHOLD = 1.2

# Breakout detection
BREAKOUT_PROXIMITY_PCT = 0.97    # within 3% of high
CONSOLIDATION_PROXIMITY_PCT = 0.90
CONSOLIDATION_ATR_PCT = 0.02    # low volatility threshold

# Support detection
SUPPORT_TOLERANCE_PCT = 0.99    # within 1% counts as holding
MA_TOLERANCE_NEAR = 0.98        # within 2% of MA
MA_TOLERANCE_200 = 0.95         # within 5% of 200MA

# Trend confirmation periods
MA20_TREND_LOOKBACK = 5
MA50_TREND_LOOKBACK = 10

# Return calculation periods
WEEK_DAYS = 6    # 5 trading days + 1 for diff
MONTH_DAYS = 21  # ~20 trading days
QUARTER_DAYS = 63  # ~3 months
HALF_YEAR_DAYS = 126  # ~6 months

# 52-Week position thresholds (Minervini template)
MINERVINI_ABOVE_52WK_LOW = 0.25    # Must be >25% above 52-week low
MINERVINI_BELOW_52WK_HIGH = 0.25  # Must be within 25% of 52-week high

# Relative Strength thresholds
RS_STRONG = 1.5      # Stock outperforming index by 50%+
RS_GOOD = 1.2        # Stock outperforming index by 20%+
RS_NEUTRAL = 1.0     # At par with index
RS_WEAK = 0.8        # Underperforming by 20%+


# ── helpers ───────────────────────────────────────────────────────────────────

def _safe_series(df: pd.DataFrame, col: str) -> pd.Series:
    """
    Extract a clean Series from a potentially MultiIndex DataFrame.
    Handles edge cases from yfinance batch downloads.
    """
    s = df[col]
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    return s.dropna() if hasattr(s, 'dropna') else s


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def _rsi(series: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """
    Compute RSI with proper handling of edge cases.
    Returns values between 0-100, with NaN for insufficient data.
    """
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    
    # Handle division by zero — when loss is 0, RSI = 100
    rs = np.where(loss == 0, np.inf, gain / loss)
    rsi = 100 - (100 / (1 + rs))
    
    # Cap at 100 for inf cases, convert back to Series
    rsi = np.clip(rsi, 0, 100)
    return pd.Series(rsi, index=series.index)


def _macd(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Returns (macd_line, signal_line)."""
    fast = _ema(series, MACD_FAST)
    slow = _ema(series, MACD_SLOW)
    macd = fast - slow
    signal = _ema(macd, MACD_SIGNAL)
    return macd, signal


def _adv(volume: pd.Series, window: int = ADV_PERIOD) -> float:
    """Average daily volume over last `window` trading days."""
    return float(volume.tail(window).mean())


# ── Index data for Relative Strength ──────────────────────────────────────────
# Cache index returns to avoid repeated fetches
_INDEX_RETURNS_CACHE: dict[str, float] = {}

def get_index_return(period_days: int = HALF_YEAR_DAYS) -> float:
    """
    Get KLCI index return for relative strength calculation.
    Returns the percentage return over the specified period.
    Caches result to avoid repeated API calls.
    """
    cache_key = f"klci_{period_days}"
    if cache_key in _INDEX_RETURNS_CACHE:
        return _INDEX_RETURNS_CACHE[cache_key]
    
    try:
        import yfinance as yf
        # ^KLSE is the FTSE Bursa Malaysia KLCI
        df = yf.download("^KLSE", period="1y", progress=False, auto_adjust=True)
        if df is not None and len(df) >= period_days:
            close = df["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            index_return = float((close.iloc[-1] / close.iloc[-period_days] - 1) * 100)
            _INDEX_RETURNS_CACHE[cache_key] = index_return
            return index_return
    except Exception:
        pass
    
    # Default to 0 if can't fetch index data
    _INDEX_RETURNS_CACHE[cache_key] = 0.0
    return 0.0


# ── result dataclass ──────────────────────────────────────────────────────────

@dataclass
class TechnicalScore:
    ticker: str

    # individual factor scores (updated for 25-point system)
    score_20ma:     int = 0   # max 3
    score_50ma:     int = 0   # max 3
    score_200ma:    int = 0   # max 3
    score_rsi:      int = 0   # max 2
    score_macd:     int = 0   # max 2
    score_volume:   int = 0   # max 3
    score_breakout: int = 0   # max 2
    score_support:  int = 0   # max 2
    score_rs:       int = 0   # max 3 (NEW - Relative Strength)
    score_52wk:     int = 0   # max 2 (NEW - 52-Week Position)

    # computed values for display
    price:        float = 0.0
    ma20:         float = 0.0
    ma50:         float = 0.0
    ma200:        float = 0.0
    rsi_val:      float = 0.0
    adv_30d:      float = 0.0
    volume_ratio: float = 0.0  # last 5d avg vol / 30d ADV
    macd_val:     float = 0.0
    macd_signal:  float = 0.0
    week_return:  float = 0.0  # 5-day return %
    month_return: float = 0.0  # 20-day return %
    
    # NEW: Relative strength and position metrics
    rs_ratio:      float = 0.0  # Stock return / Index return
    pct_from_52wk_high: float = 0.0  # How far below 52-week high (%)
    pct_from_52wk_low:  float = 0.0  # How far above 52-week low (%)

    error: str | None = None
    detail: dict = field(default_factory=dict)

    @property
    def total(self) -> int:
        return (
            self.score_20ma + self.score_50ma + self.score_200ma
            + self.score_rsi + self.score_macd
            + self.score_volume + self.score_breakout + self.score_support
            + self.score_rs + self.score_52wk
        )

    @property
    def status(self) -> str:
        t = self.total
        if t >= 18:  # Updated threshold for 25-point system
            return "Confirmed Uptrend"
        elif t >= 12:  # Updated threshold
            return "Early Re-Rating"
        else:
            return "Downtrend/Value Trap"


# ── scorer ────────────────────────────────────────────────────────────────────

def score_technicals(ticker: str, df: pd.DataFrame | None) -> TechnicalScore:
    """
    Compute a TechnicalScore from a daily OHLCV DataFrame.
    Returns a zeroed score with error set if data is insufficient.
    """
    result = TechnicalScore(ticker=ticker)

    if df is None or len(df) < MIN_DAYS_REQUIRED:
        result.error = f"Insufficient price data (need ≥ {MIN_DAYS_REQUIRED} days)"
        return result

    # Use safe series extraction to handle MultiIndex edge cases
    close  = _safe_series(df, "Close")
    volume = _safe_series(df, "Volume")
    high   = _safe_series(df, "High")
    low    = _safe_series(df, "Low")
    open_  = _safe_series(df, "Open")

    # ── compute indicators ────────────────────────────────────────────────────
    ma20  = _sma(close, MA_SHORT)
    ma50  = _sma(close, MA_MID)
    ma200 = _sma(close, MA_LONG) if len(df) >= MIN_DAYS_FOR_200MA else None

    rsi        = _rsi(close, RSI_PERIOD)
    macd, signal = _macd(close)

    last_close  = float(close.iloc[-1])
    last_ma20   = float(ma20.iloc[-1]) if not np.isnan(ma20.iloc[-1]) else None
    last_ma50   = float(ma50.iloc[-1]) if not np.isnan(ma50.iloc[-1]) else None
    last_ma200  = float(ma200.iloc[-1]) if ma200 is not None and not np.isnan(ma200.iloc[-1]) else None
    last_rsi    = float(rsi.iloc[-1])   if not np.isnan(rsi.iloc[-1]) else None
    last_macd   = float(macd.iloc[-1])
    last_signal = float(signal.iloc[-1])

    adv        = _adv(volume, ADV_PERIOD)
    recent_vol = float(volume.tail(5).mean()) if len(volume) >= 5 else float(volume.mean())
    vol_ratio  = (recent_vol / adv) if adv > 0 else 0.0

    # returns
    week_ret  = float((close.iloc[-1] / close.iloc[-WEEK_DAYS]  - 1) * 100) if len(close) >= WEEK_DAYS  else 0.0
    month_ret = float((close.iloc[-1] / close.iloc[-MONTH_DAYS] - 1) * 100) if len(close) >= MONTH_DAYS else 0.0

    # ── populate display values ───────────────────────────────────────────────
    result.price        = last_close
    result.ma20         = last_ma20   or 0.0
    result.ma50         = last_ma50   or 0.0
    result.ma200        = last_ma200  or 0.0
    result.rsi_val      = last_rsi    or 0.0
    result.adv_30d      = adv
    result.volume_ratio = round(vol_ratio, 2)
    result.macd_val     = round(last_macd, 4)
    result.macd_signal  = round(last_signal, 4)
    result.week_return  = round(week_ret, 2)
    result.month_return = round(month_ret, 2)

    # ── 20MA score (max 3) ────────────────────────────────────────────────────
    if last_ma20 is not None:
        price_above_20 = last_close > last_ma20
        # check if 20MA has been rising for last few sessions
        ma20_rising = float(ma20.iloc[-1]) > float(ma20.iloc[-MA20_TREND_LOOKBACK]) if len(ma20.dropna()) >= MA20_TREND_LOOKBACK else False

        if price_above_20 and ma20_rising:
            result.score_20ma = 3
        elif price_above_20:
            result.score_20ma = 2
        elif last_close > last_ma20 * MA_TOLERANCE_NEAR:   # within 2% below — close to breakout
            result.score_20ma = 1
        else:
            result.score_20ma = 0

    # ── 50MA score (max 3) ────────────────────────────────────────────────────
    if last_ma50 is not None:
        price_above_50 = last_close > last_ma50
        ma20_above_50  = (last_ma20 is not None and last_ma20 > last_ma50)
        ma50_rising    = float(ma50.iloc[-1]) > float(ma50.iloc[-MA50_TREND_LOOKBACK]) if len(ma50.dropna()) >= MA50_TREND_LOOKBACK else False

        if price_above_50 and ma20_above_50 and ma50_rising:
            result.score_50ma = 3
        elif price_above_50 and ma20_above_50:
            result.score_50ma = 2
        elif price_above_50:
            result.score_50ma = 1
        else:
            result.score_50ma = 0

    # ── 200MA score (max 3) ───────────────────────────────────────────────────
    if last_ma200 is not None:
        price_above_200 = last_close > last_ma200
        ma50_above_200  = (last_ma50 is not None and last_ma50 > last_ma200)

        if price_above_200 and ma50_above_200:
            result.score_200ma = 3
        elif price_above_200:
            result.score_200ma = 2
        elif last_close > last_ma200 * MA_TOLERANCE_200:  # within 5% — potential base building
            result.score_200ma = 1
        else:
            result.score_200ma = 0
    else:
        # not enough history — give partial credit if price is in uptrend on shorter window
        result.score_200ma = 1 if week_ret > 0 and month_ret > 0 else 0

    # ── RSI score (max 2) ─────────────────────────────────────────────────────
    if last_rsi is not None:
        if RSI_BULLISH_LOWER <= last_rsi <= RSI_BULLISH_UPPER:   # bullish momentum, not overbought
            result.score_rsi = 2
        elif RSI_NEUTRAL_LOWER <= last_rsi < RSI_BULLISH_LOWER:  # recovering from oversold, potential base
            result.score_rsi = 1
        elif last_rsi > RSI_OVERBOUGHT:                          # overbought — caution
            result.score_rsi = 1
        else:                                                    # < 40 — weak / oversold
            result.score_rsi = 0

    # ── MACD score (max 2) ────────────────────────────────────────────────────
    macd_bullish   = last_macd > last_signal
    macd_above_zero = last_macd > 0

    if macd_bullish and macd_above_zero:
        result.score_macd = 2
    elif macd_bullish:                 # bullish crossover but still below zero
        result.score_macd = 1
    else:
        result.score_macd = 0

    # ── Volume score (max 3) ──────────────────────────────────────────────────
    # Rising price + rising volume = healthy accumulation
    if vol_ratio >= VOLUME_SURGE_THRESHOLD and week_ret > 0:
        result.score_volume = 3        # strong volume on up move
    elif vol_ratio >= VOLUME_ELEVATED_THRESHOLD and week_ret > 0:
        result.score_volume = 2
    elif vol_ratio >= 1.0:
        result.score_volume = 1        # average volume
    else:
        result.score_volume = 0        # shrinking / low volume

    # ── Breakout / Base formation score (max 2) ───────────────────────────────
    # Proxy: is the price near a 3-month high (potential breakout)?
    # or has been consolidating (low ATR) near recent high?
    high_3m  = float(high.tail(QUARTER_DAYS).max())  if len(high)  >= QUARTER_DAYS else float(high.max())
    close_pct_of_3m_high = last_close / high_3m if high_3m > 0 else 0

    # ATR proxy for consolidation detection
    atr = float((high - low).tail(MA_SHORT).mean())
    atr_pct = (atr / last_close) if last_close > 0 else 0

    if close_pct_of_3m_high >= BREAKOUT_PROXIMITY_PCT:          # within 3% of 3-month high
        result.score_breakout = 2
    elif close_pct_of_3m_high >= CONSOLIDATION_PROXIMITY_PCT and atr_pct < CONSOLIDATION_ATR_PCT:  # consolidating below resistance
        result.score_breakout = 1
    else:
        result.score_breakout = 0

    # ── Support / Resistance score (max 2) ───────────────────────────────────
    # Proxy: price holding above recent swing lows (last 20 sessions)
    low_20d   = float(low.tail(MA_SHORT).min())
    low_5d    = float(low.tail(5).min())
    held_support = low_5d > low_20d * SUPPORT_TOLERANCE_PCT   # not breaking down to new lows

    close_above_open = float(close.iloc[-1]) >= float(open_.iloc[-1])

    if held_support and close_above_open and month_ret > 0:
        result.score_support = 2
    elif held_support:
        result.score_support = 1
    else:
        result.score_support = 0

    # ── Relative Strength score (max 3, NEW) ─────────────────────────────────
    # Compare stock's 6-month return to KLCI index return
    half_year_ret = float((close.iloc[-1] / close.iloc[-HALF_YEAR_DAYS] - 1) * 100) if len(close) >= HALF_YEAR_DAYS else month_ret * 3
    index_return = get_index_return(HALF_YEAR_DAYS)
    
    # Calculate relative strength ratio
    if index_return != 0:
        rs_ratio = (1 + half_year_ret / 100) / (1 + index_return / 100)
    else:
        rs_ratio = 1 + half_year_ret / 100  # Compare to flat if no index data
    
    result.rs_ratio = round(rs_ratio, 2)
    
    if rs_ratio >= RS_STRONG:
        result.score_rs = 3
    elif rs_ratio >= RS_GOOD:
        result.score_rs = 2
    elif rs_ratio >= RS_NEUTRAL:
        result.score_rs = 1
    else:
        result.score_rs = 0

    # ── 52-Week Position score (max 2, NEW - Minervini template) ─────────────
    # Check: >25% above 52-week low AND within 25% of 52-week high
    high_52wk = float(high.tail(252).max()) if len(high) >= 252 else float(high.max())
    low_52wk = float(low.tail(252).min()) if len(low) >= 252 else float(low.min())
    
    if low_52wk > 0 and high_52wk > 0:
        pct_above_low = (last_close - low_52wk) / low_52wk
        pct_below_high = (high_52wk - last_close) / high_52wk
        
        result.pct_from_52wk_high = round(pct_below_high * 100, 1)
        result.pct_from_52wk_low = round(pct_above_low * 100, 1)
        
        # Minervini criteria: >25% above low AND within 25% of high
        above_low_ok = pct_above_low >= MINERVINI_ABOVE_52WK_LOW
        near_high_ok = pct_below_high <= MINERVINI_BELOW_52WK_HIGH
        
        if above_low_ok and near_high_ok:
            result.score_52wk = 2  # In the "sweet spot"
        elif above_low_ok or near_high_ok:
            result.score_52wk = 1  # Partial criteria met
        else:
            result.score_52wk = 0  # Neither criteria met
    else:
        result.score_52wk = 1  # Partial credit if data unavailable

    # ── detail dict for transparency ─────────────────────────────────────────
    result.detail = {
        "price_above_20ma":  last_ma20  is not None and last_close > last_ma20,
        "price_above_50ma":  last_ma50  is not None and last_close > last_ma50,
        "price_above_200ma": last_ma200 is not None and last_close > last_ma200,
        "rsi":               round(last_rsi, 1) if last_rsi else None,
        "macd_bullish":      macd_bullish,
        "vol_ratio_5d_vs_30d": round(vol_ratio, 2),
        "close_pct_of_3m_high": round(close_pct_of_3m_high * 100, 1),
        "held_support":      held_support,
        # NEW metrics
        "relative_strength": round(rs_ratio, 2),
        "index_return_6m":   round(index_return, 1),
        "stock_return_6m":   round(half_year_ret, 1),
        "pct_from_52wk_high": result.pct_from_52wk_high,
        "pct_from_52wk_low":  result.pct_from_52wk_low,
    }

    return result
