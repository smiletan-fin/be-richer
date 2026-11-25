"""
Data fetcher — pulls price history and fundamental snapshots from yfinance.

All public functions return clean DataFrames / dicts; callers never touch
yfinance directly.  This makes swapping the data source easy later.

Limitations (be honest):
- 15-min delayed prices on the free yfinance feed
- Fundamentals come from Yahoo's own scrape; may lag filings by days
- Forward PE / analyst estimates are sparse for small-cap Bursa names
- Yahoo Finance rate limits aggressively; we use caching and throttling
"""

from __future__ import annotations

import hashlib
import json
import random
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

# suppress noisy yfinance deprecation chatter
warnings.filterwarnings("ignore", category=FutureWarning)


# ── constants ─────────────────────────────────────────────────────────────────
DEFAULT_PERIOD = "6mo"
DEFAULT_INTERVAL = "1d"
MIN_PRICE_ROWS = 20
MAX_RETRIES = 3
BASE_RETRY_DELAY = 2.0  # exponential backoff base (more conservative)
MAX_RETRY_DELAY = 30.0  # cap on retry delay
RATE_LIMIT_DELAY = 5.0  # extra delay after rate limit error

# Cache configuration
CACHE_DIR = Path(__file__).parent / "cache"
PRICE_CACHE_HOURS = 4  # cache price data for 4 hours
FUNDAMENTALS_CACHE_HOURS = 24  # cache fundamentals for 24 hours


# ── caching helpers ───────────────────────────────────────────────────────────

def _get_cache_path(ticker: str, data_type: str) -> Path:
    """Get cache file path for a ticker."""
    # Sanitize ticker for filesystem
    safe_ticker = ticker.replace("/", "_").replace("\\", "_")
    return CACHE_DIR / data_type / f"{safe_ticker}.json"


def _is_cache_valid(cache_path: Path, max_age_hours: float) -> bool:
    """Check if cache file exists and is not stale."""
    if not cache_path.exists():
        return False
    try:
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < timedelta(hours=max_age_hours)
    except (OSError, ValueError):
        return False


def _load_price_cache(ticker: str, period: str) -> pd.DataFrame | None:
    """Load cached price data if valid."""
    cache_path = _get_cache_path(f"{ticker}_{period}", "prices")
    if not _is_cache_valid(cache_path, PRICE_CACHE_HOURS):
        return None
    try:
        with open(cache_path) as f:
            data = json.load(f)
        df = pd.DataFrame(data["data"])
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
        return df
    except (json.JSONDecodeError, KeyError, IOError):
        return None


def _save_price_cache(ticker: str, period: str, df: pd.DataFrame) -> None:
    """Save price data to cache."""
    cache_path = _get_cache_path(f"{ticker}_{period}", "prices")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = {
            "ticker": ticker,
            "period": period,
            "cached_at": datetime.now().isoformat(),
            "data": df.reset_index().to_dict(orient="records"),
        }
        # Convert Timestamp objects to strings for JSON serialization
        for record in data["data"]:
            if "Date" in record and hasattr(record["Date"], "isoformat"):
                record["Date"] = record["Date"].isoformat()
        with open(cache_path, "w") as f:
            json.dump(data, f, default=str)
    except (IOError, TypeError):
        pass  # Cache write failures are non-fatal


def _load_fundamentals_cache(ticker: str) -> dict[str, Any] | None:
    """Load cached fundamentals if valid."""
    cache_path = _get_cache_path(ticker, "fundamentals")
    if not _is_cache_valid(cache_path, FUNDAMENTALS_CACHE_HOURS):
        return None
    try:
        with open(cache_path) as f:
            data = json.load(f)
        return data.get("fundamentals")
    except (json.JSONDecodeError, KeyError, IOError):
        return None


def _save_fundamentals_cache(ticker: str, fundamentals: dict[str, Any]) -> None:
    """Save fundamentals to cache."""
    cache_path = _get_cache_path(ticker, "fundamentals")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = {
            "ticker": ticker,
            "cached_at": datetime.now().isoformat(),
            "fundamentals": fundamentals,
        }
        with open(cache_path, "w") as f:
            json.dump(data, f, default=str)
    except (IOError, TypeError):
        pass


def _is_rate_limit_error(e: Exception) -> bool:
    """Check if exception is a rate limit error."""
    error_str = str(e).lower()
    return any(phrase in error_str for phrase in [
        "429", "rate limit", "too many requests", "throttl"
    ])


# ── price history ─────────────────────────────────────────────────────────────

def fetch_price_history(
    ticker: str,
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
    retries: int = MAX_RETRIES,
    use_cache: bool = True,
) -> pd.DataFrame | None:
    """
    Return OHLCV DataFrame with a DatetimeIndex.
    Returns None if the ticker is unavailable or has fewer than MIN_PRICE_ROWS rows.
    Uses exponential backoff for retries with jitter.
    """
    # Try cache first
    if use_cache:
        cached = _load_price_cache(ticker, period)
        if cached is not None and len(cached) >= MIN_PRICE_ROWS:
            return cached

    for attempt in range(retries + 1):
        try:
            df = yf.download(
                ticker,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
            )
            if df is None or df.empty or len(df) < MIN_PRICE_ROWS:
                return None
            # flatten MultiIndex columns that yfinance sometimes returns
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # Cache successful fetch
            if use_cache:
                _save_price_cache(ticker, period, df)
            return df
        except Exception as e:
            if attempt < retries:
                # Longer delay for rate limit errors
                if _is_rate_limit_error(e):
                    delay = RATE_LIMIT_DELAY + random.uniform(1, 3)
                else:
                    # Exponential backoff with jitter
                    delay = min(BASE_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
                    delay += random.uniform(0, 1)  # Add jitter
                time.sleep(delay)
    return None


def batch_fetch_prices(
    tickers: list[str],
    period: str = DEFAULT_PERIOD,
    use_cache: bool = True,
) -> dict[str, pd.DataFrame | None]:
    """
    Fetch price history for multiple tickers in a single yfinance call.
    Significantly faster than sequential fetching.

    Returns dict: { ticker: DataFrame | None }
    """
    if not tickers:
        return {}

    results: dict[str, pd.DataFrame | None] = {}
    uncached_tickers: list[str] = []

    # Check cache first
    if use_cache:
        for ticker in tickers:
            cached = _load_price_cache(ticker, period)
            if cached is not None and len(cached) >= MIN_PRICE_ROWS:
                results[ticker] = cached
            else:
                uncached_tickers.append(ticker)
    else:
        uncached_tickers = list(tickers)

    if not uncached_tickers:
        return results

    # Batch fetch uncached tickers with retry logic
    for attempt in range(MAX_RETRIES + 1):
        try:
            # yfinance batch download — much faster than sequential
            df = yf.download(
                uncached_tickers,
                period=period,
                group_by="ticker",
                progress=False,
                auto_adjust=True,
                threads=True,
            )
            break
        except Exception as e:
            if attempt < MAX_RETRIES:
                if _is_rate_limit_error(e):
                    delay = RATE_LIMIT_DELAY * (attempt + 1) + random.uniform(1, 3)
                else:
                    delay = BASE_RETRY_DELAY * (2 ** attempt) + random.uniform(0, 1)
                time.sleep(delay)
            else:
                # Fallback to sequential if batch fails
                for t in uncached_tickers:
                    results[t] = fetch_price_history(t, period, use_cache=use_cache)
                return results

    if len(uncached_tickers) == 1:
        # Single ticker — df is not grouped
        ticker = uncached_tickers[0]
        if df is not None and not df.empty and len(df) >= MIN_PRICE_ROWS:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            results[ticker] = df
            if use_cache:
                _save_price_cache(ticker, period, df)
        else:
            results[ticker] = None
    else:
        # Multiple tickers — df is grouped by ticker
        for ticker in uncached_tickers:
            try:
                ticker_df = df[ticker].copy() if ticker in df.columns.get_level_values(0) else None
                if ticker_df is not None and not ticker_df.empty and len(ticker_df) >= MIN_PRICE_ROWS:
                    # Drop rows where all OHLCV are NaN
                    ticker_df = ticker_df.dropna(how="all")
                    if len(ticker_df) >= MIN_PRICE_ROWS:
                        results[ticker] = ticker_df
                        if use_cache:
                            _save_price_cache(ticker, period, ticker_df)
                    else:
                        results[ticker] = None
                else:
                    results[ticker] = None
            except Exception:
                results[ticker] = None

    return results


# ── fundamentals snapshot ─────────────────────────────────────────────────────

def fetch_fundamentals(ticker: str, use_cache: bool = True) -> dict[str, Any]:
    """
    Return a dict of key fundamental metrics from yfinance .info.

    Keys returned (all may be None if unavailable):
        price, market_cap, pe_ttm, forward_pe, pb, roe,
        eps_ttm, dividend_yield, debt_to_equity, operating_cash_flow,
        revenue_ttm, net_income_ttm, total_debt, total_cash,
        shares_outstanding, sector, industry, long_name
    """
    # Try cache first
    if use_cache:
        cached = _load_fundamentals_cache(ticker)
        if cached is not None:
            return cached

    for attempt in range(MAX_RETRIES + 1):
        try:
            info = yf.Ticker(ticker).info
            break
        except Exception as e:
            if attempt < MAX_RETRIES:
                if _is_rate_limit_error(e):
                    delay = RATE_LIMIT_DELAY * (attempt + 1) + random.uniform(1, 3)
                else:
                    delay = BASE_RETRY_DELAY * (2 ** attempt) + random.uniform(0, 1)
                time.sleep(delay)
            else:
                return _empty_fundamentals(ticker)

    def _get(*keys: str) -> Any:
        """Return the first non-None value across a list of key aliases."""
        for k in keys:
            v = info.get(k)
            if v is not None and v != "N/A" and v != 0:
                return v
        return None

    # net gearing proxy: (total_debt - cash) / equity
    total_debt  = _get("totalDebt")
    total_cash  = _get("totalCash")
    book_value  = _get("bookValue")          # per share
    shares_out  = _get("sharesOutstanding")

    net_gearing: float | None = None
    if total_debt is not None and total_cash is not None and book_value and shares_out:
        equity = book_value * shares_out
        if equity > 0:
            net_gearing = round((total_debt - total_cash) / equity, 3)

    fundamentals = {
        "ticker":               ticker,
        "long_name":            info.get("longName") or info.get("shortName"),
        "sector":               info.get("sector"),
        "industry":             info.get("industry"),
        "price":                _get("currentPrice", "regularMarketPrice"),
        "market_cap":           _get("marketCap"),
        "pe_ttm":               _get("trailingPE"),
        "forward_pe":           _get("forwardPE"),
        "pb":                   _get("priceToBook"),
        "roe":                  _get("returnOnEquity"),           # decimal, e.g. 0.12
        "eps_ttm":              _get("trailingEps"),
        "dividend_yield":       _get("dividendYield"),            # decimal
        "debt_to_equity":       _get("debtToEquity"),
        "net_gearing":          net_gearing,
        "operating_cash_flow":  _get("operatingCashflow"),
        "revenue_ttm":          _get("totalRevenue"),
        "net_income_ttm":       _get("netIncomeToCommon"),
        "total_debt":           total_debt,
        "total_cash":           total_cash,
        "shares_outstanding":   shares_out,
        "book_value_per_share": book_value,
        # NEW: Growth metrics for enhanced scoring
        "earningsGrowth":       _get("earningsGrowth"),           # YoY earnings growth (decimal)
        "revenueGrowth":        _get("revenueGrowth"),            # YoY revenue growth (decimal)
        "earningsQuarterlyGrowth": _get("earningsQuarterlyGrowth"),  # QoQ earnings growth
        # NEW: Additional quality metrics
        "grossMargins":         _get("grossMargins"),
        "operatingMargins":     _get("operatingMargins"),
        "profitMargins":        _get("profitMargins"),
        "returnOnAssets":       _get("returnOnAssets"),           # ROA for Piotroski
        "currentRatio":         _get("currentRatio"),             # Liquidity
        "quickRatio":           _get("quickRatio"),
        # 52-week data for relative strength
        "fiftyTwoWeekHigh":     _get("fiftyTwoWeekHigh"),
        "fiftyTwoWeekLow":      _get("fiftyTwoWeekLow"),
    }

    # Cache successful fetch (only if we got actual data)
    if use_cache and fundamentals.get("price") is not None:
        _save_fundamentals_cache(ticker, fundamentals)

    return fundamentals


def _empty_fundamentals(ticker: str) -> dict[str, Any]:
    keys = [
        "ticker", "long_name", "sector", "industry", "price", "market_cap",
        "pe_ttm", "forward_pe", "pb", "roe", "eps_ttm", "dividend_yield",
        "debt_to_equity", "net_gearing", "operating_cash_flow", "revenue_ttm",
        "net_income_ttm", "total_debt", "total_cash", "shares_outstanding",
        "book_value_per_share",
    ]
    return {k: (ticker if k == "ticker" else None) for k in keys}


# ── batch fetch ───────────────────────────────────────────────────────────────

def batch_fetch(
    tickers: list[str],
    period: str = DEFAULT_PERIOD,
    throttle: float = 0.5,
    max_workers: int = 3,
    use_cache: bool = True,
) -> dict[str, dict]:
    """
    Fetch price history + fundamentals for a list of tickers.

    Uses batch download for prices (single API call) and parallel
    ThreadPoolExecutor for fundamentals (can't be batched in yfinance).

    Returns a dict keyed by ticker:
        {
          "price_df":   pd.DataFrame | None,
          "fundamentals": dict,
        }

    throttle: seconds between fundamental fetches to avoid rate-limiting.
    max_workers: parallel threads for fundamental fetching.
    use_cache: whether to use/update local cache.
    """
    # Step 1: Batch fetch all prices in one call (fast)
    price_data = batch_fetch_prices(tickers, period=period, use_cache=use_cache)

    # Step 2: Fetch fundamentals sequentially with throttling
    # (parallel fetching increases rate limit risk)
    fundamentals_data: dict[str, dict] = {}

    for i, ticker in enumerate(tickers):
        # Check cache first (avoid unnecessary API calls)
        if use_cache:
            cached = _load_fundamentals_cache(ticker)
            if cached is not None:
                fundamentals_data[ticker] = cached
                continue

        # Throttle between requests (with jitter)
        if i > 0:
            time.sleep(throttle + random.uniform(0.1, 0.3))
        
        fundamentals_data[ticker] = fetch_fundamentals(ticker, use_cache=use_cache)

    # Step 3: Combine results
    results: dict[str, dict] = {}
    for ticker in tickers:
        results[ticker] = {
            "price_df": price_data.get(ticker),
            "fundamentals": fundamentals_data.get(ticker, _empty_fundamentals(ticker)),
        }

    return results


def clear_cache(older_than_hours: float | None = None) -> int:
    """
    Clear cached data files.
    
    Args:
        older_than_hours: If specified, only clear files older than this.
                         If None, clear all cache files.
    
    Returns:
        Number of files deleted.
    """
    if not CACHE_DIR.exists():
        return 0
    
    deleted = 0
    cutoff = datetime.now() - timedelta(hours=older_than_hours) if older_than_hours else None
    
    for cache_type in ["prices", "fundamentals"]:
        type_dir = CACHE_DIR / cache_type
        if not type_dir.exists():
            continue
        for cache_file in type_dir.glob("*.json"):
            try:
                if cutoff is None:
                    cache_file.unlink()
                    deleted += 1
                else:
                    mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                    if mtime < cutoff:
                        cache_file.unlink()
                        deleted += 1
            except (OSError, ValueError):
                pass
    
    return deleted


def check_yahoo_connectivity(test_ticker: str = "1155.KL") -> dict:
    """
    Check if Yahoo Finance API is accessible (not rate-limited).
    
    Returns:
        {
            "ok": bool,
            "message": str,
            "rate_limited": bool,
            "test_ticker": str,
        }
    """
    result = {
        "ok": False,
        "message": "",
        "rate_limited": False,
        "test_ticker": test_ticker,
    }
    
    try:
        info = yf.Ticker(test_ticker).info
        name = info.get("longName") or info.get("shortName")
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        
        if name and price:
            result["ok"] = True
            result["message"] = f"Connected! {name} @ {price}"
        else:
            result["message"] = "Connected but no data returned (ticker may be invalid)"
    except Exception as e:
        error_str = str(e).lower()
        if _is_rate_limit_error(e):
            result["rate_limited"] = True
            result["message"] = (
                "Rate limited by Yahoo Finance (HTTP 429). "
                "Options: 1) Wait 15-30 minutes, 2) Use cached data, "
                "3) Try from a different IP/network."
            )
        else:
            result["message"] = f"Connection error: {str(e)[:100]}"
    
    return result


def get_cache_stats() -> dict:
    """
    Get statistics about cached data.
    
    Returns:
        {
            "prices_count": int,
            "fundamentals_count": int,
            "total_size_mb": float,
            "oldest_file": str | None,
            "newest_file": str | None,
        }
    """
    stats = {
        "prices_count": 0,
        "fundamentals_count": 0,
        "total_size_bytes": 0,
        "total_size_mb": 0.0,
        "oldest_file": None,
        "newest_file": None,
    }
    
    if not CACHE_DIR.exists():
        return stats
    
    oldest_time = None
    newest_time = None
    
    for cache_type in ["prices", "fundamentals"]:
        type_dir = CACHE_DIR / cache_type
        if not type_dir.exists():
            continue
        
        for cache_file in type_dir.glob("*.json"):
            try:
                mtime = cache_file.stat().st_mtime
                size = cache_file.stat().st_size
                stats["total_size_bytes"] += size
                
                if cache_type == "prices":
                    stats["prices_count"] += 1
                else:
                    stats["fundamentals_count"] += 1
                
                if oldest_time is None or mtime < oldest_time:
                    oldest_time = mtime
                    stats["oldest_file"] = datetime.fromtimestamp(mtime).isoformat()
                if newest_time is None or mtime > newest_time:
                    newest_time = mtime
                    stats["newest_file"] = datetime.fromtimestamp(mtime).isoformat()
            except (OSError, ValueError):
                pass
    
    stats["total_size_mb"] = round(stats["total_size_bytes"] / (1024 * 1024), 2)
    return stats
