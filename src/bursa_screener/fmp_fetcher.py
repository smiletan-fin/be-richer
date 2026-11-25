"""
Financial Modeling Prep (FMP) API client.

Provides enhanced fundamental data beyond yfinance:
- Earnings estimates and surprises
- Analyst recommendations
- More reliable financial ratios
- Quarterly/annual financial statements

API docs: https://financialmodelingprep.com/developer/docs

Free tier: 250 API calls/day
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests

# ── Configuration ─────────────────────────────────────────────────────────────
# FMP changed their API in August 2025 - use /stable/ endpoints for free tier
FMP_BASE_URL = "https://financialmodelingprep.com/stable"
FMP_V3_URL = "https://financialmodelingprep.com/api/v3"  # For some legacy endpoints
CACHE_DIR = Path(__file__).parent / "cache" / "fmp"
CACHE_HOURS = 24  # Cache FMP data for 24 hours

# Rate limiting
REQUEST_DELAY = 0.3  # seconds between requests
_last_request_time = 0.0


def get_api_key() -> str | None:
    """
    Get FMP API key from environment variable or .env file.
    
    Priority:
    1. FMP_API_KEY environment variable
    2. .env file in project root
    
    Returns None if not configured.
    """
    # Check environment variable first
    key = os.environ.get("FMP_API_KEY")
    if key:
        return key
    
    # Try loading from .env file
    env_paths = [
        Path(__file__).parent.parent.parent.parent / ".env",  # Project root
        Path.cwd() / ".env",
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            try:
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("FMP_API_KEY="):
                            return line.split("=", 1)[1].strip().strip('"\'')
            except IOError:
                pass
    
    return None


def is_configured() -> bool:
    """Check if FMP API key is configured."""
    return get_api_key() is not None


# ── Caching ───────────────────────────────────────────────────────────────────

def _get_cache_path(endpoint: str, ticker: str) -> Path:
    """Get cache file path for an endpoint."""
    safe_ticker = ticker.replace("/", "_").replace("\\", "_").replace(".", "_")
    safe_endpoint = endpoint.replace("/", "_")
    return CACHE_DIR / f"{safe_endpoint}_{safe_ticker}.json"


def _is_cache_valid(cache_path: Path) -> bool:
    """Check if cache file exists and is fresh."""
    if not cache_path.exists():
        return False
    try:
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < timedelta(hours=CACHE_HOURS)
    except (OSError, ValueError):
        return False


def _load_cache(endpoint: str, ticker: str) -> dict | None:
    """Load cached data if valid."""
    cache_path = _get_cache_path(endpoint, ticker)
    if not _is_cache_valid(cache_path):
        return None
    try:
        with open(cache_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _save_cache(endpoint: str, ticker: str, data: dict) -> None:
    """Save data to cache."""
    cache_path = _get_cache_path(endpoint, ticker)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(cache_path, "w") as f:
            json.dump(data, f, default=str)
    except IOError:
        pass


# ── API Requests ──────────────────────────────────────────────────────────────

def _rate_limit():
    """Apply rate limiting between requests."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)
    _last_request_time = time.time()


def _make_request(endpoint: str, params: dict | None = None, use_stable: bool = True) -> dict | list | None:
    """
    Make a request to FMP API.
    
    Returns parsed JSON or None on error.
    """
    api_key = get_api_key()
    if not api_key:
        return None
    
    _rate_limit()
    
    base_url = FMP_BASE_URL if use_stable else FMP_V3_URL
    url = f"{base_url}/{endpoint}"
    params = params or {}
    params["apikey"] = api_key
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        # Log error but don't crash
        return None
    except json.JSONDecodeError:
        return None


def _convert_ticker(ticker: str) -> str:
    """
    Convert yfinance ticker format to FMP format.
    
    yfinance: 1155.KL
    FMP: 1155.KL (same for Malaysian stocks)
    """
    # FMP uses the same format for Malaysian stocks
    return ticker


# ── Public API Functions ──────────────────────────────────────────────────────

def fetch_company_profile(ticker: str, use_cache: bool = True) -> dict | None:
    """
    Fetch company profile from FMP.
    
    Returns:
        {
            "symbol": "1155.KL",
            "companyName": "Malayan Banking Berhad",
            "sector": "Financial Services",
            "industry": "Banks—Regional",
            "mktCap": 123456789000,
            "price": 10.12,
            ...
        }
    """
    fmp_ticker = _convert_ticker(ticker)
    
    if use_cache:
        cached = _load_cache("profile", ticker)
        if cached:
            return cached
    
    # Use stable API: /stable/profile?symbol=TICKER
    data = _make_request("profile", {"symbol": fmp_ticker}, use_stable=True)
    
    if data and isinstance(data, list) and len(data) > 0:
        result = data[0]
        if use_cache:
            _save_cache("profile", ticker, result)
        return result
    
    return None


def fetch_key_metrics(ticker: str, use_cache: bool = True) -> dict | None:
    """
    Fetch key financial metrics (TTM) from FMP.
    
    Includes: PE, PB, ROE, ROA, debt ratios, etc.
    """
    fmp_ticker = _convert_ticker(ticker)
    
    if use_cache:
        cached = _load_cache("metrics_ttm", ticker)
        if cached:
            return cached
    
    # Use stable API: /stable/key-metrics-ttm?symbol=TICKER
    data = _make_request("key-metrics-ttm", {"symbol": fmp_ticker}, use_stable=True)
    
    if data and isinstance(data, list) and len(data) > 0:
        result = data[0]
        if use_cache:
            _save_cache("metrics_ttm", ticker, result)
        return result
    
    return None


def fetch_ratios(ticker: str, use_cache: bool = True) -> dict | None:
    """
    Fetch financial ratios (TTM) from FMP.
    
    Includes: ROE, ROA, profit margins, liquidity ratios, etc.
    """
    fmp_ticker = _convert_ticker(ticker)
    
    if use_cache:
        cached = _load_cache("ratios_ttm", ticker)
        if cached:
            return cached
    
    # Use stable API: /stable/ratios-ttm?symbol=TICKER
    data = _make_request("ratios-ttm", {"symbol": fmp_ticker}, use_stable=True)
    
    if data and isinstance(data, list) and len(data) > 0:
        result = data[0]
        if use_cache:
            _save_cache("ratios_ttm", ticker, result)
        return result
    
    return None


def fetch_earnings_surprises(ticker: str, use_cache: bool = True) -> list[dict] | None:
    """
    Fetch earnings data with actual vs estimated EPS.
    
    Uses /stable/earnings endpoint (the deprecated earnings-surprises endpoint 
    was removed - we now calculate surprises from actual vs estimated EPS).
    
    Note: Free tier only allows limit=5 max.
    
    Returns list of recent quarters:
        [
            {
                "date": "2024-08-28",
                "epsActual": 0.25,
                "epsEstimated": 0.22,
                "surprise": 0.03,
                "surprisePercentage": 13.6
            },
            ...
        ]
    """
    fmp_ticker = _convert_ticker(ticker)
    
    if use_cache:
        cached = _load_cache("earnings", ticker)
        if cached:
            return cached
    
    # Use stable API: /stable/earnings?symbol=TICKER
    # Note: Free tier limit is 5 max
    data = _make_request("earnings", {"symbol": fmp_ticker, "limit": 5}, use_stable=True)
    
    if data and isinstance(data, list):
        # Process and calculate surprise percentages
        result = []
        for item in data:
            eps_actual = item.get("epsActual")
            eps_estimated = item.get("epsEstimated")
            
            # Only include if we have both values (historical, not future earnings)
            if eps_actual is not None and eps_estimated is not None and eps_estimated != 0:
                surprise = eps_actual - eps_estimated
                surprise_pct = (surprise / abs(eps_estimated)) * 100
                result.append({
                    "date": item.get("date"),
                    "actualEarningResult": eps_actual,
                    "estimatedEarning": eps_estimated,
                    "surprise": surprise,
                    "surprisePercentage": surprise_pct,
                })
        
        if use_cache and result:
            _save_cache("earnings", ticker, result)
        return result if result else None
    
    return None


def fetch_analyst_estimates(ticker: str, use_cache: bool = True) -> list[dict] | None:
    """
    Fetch analyst EPS/revenue estimates.
    
    Returns estimates for upcoming periods.
    """
    fmp_ticker = _convert_ticker(ticker)
    
    if use_cache:
        cached = _load_cache("analyst_estimates", ticker)
        if cached:
            return cached
    
    # Use stable API: /stable/analyst-estimates?symbol=TICKER
    data = _make_request("analyst-estimates", {"symbol": fmp_ticker, "limit": 4}, use_stable=True)
    
    if data and isinstance(data, list):
        if use_cache and data:
            _save_cache("analyst_estimates", ticker, data)
        return data
    
    return None


def fetch_growth_metrics(ticker: str, use_cache: bool = True) -> dict | None:
    """
    Fetch financial growth metrics from FMP.
    
    Includes: Revenue growth, EPS growth, etc.
    """
    fmp_ticker = _convert_ticker(ticker)
    
    if use_cache:
        cached = _load_cache("growth", ticker)
        if cached:
            return cached
    
    # Use stable API: /stable/financial-growth?symbol=TICKER
    data = _make_request("financial-growth", {"symbol": fmp_ticker, "limit": 1}, use_stable=True)
    
    if data and isinstance(data, list) and len(data) > 0:
        result = data[0]
        if use_cache:
            _save_cache("growth", ticker, result)
        return result
    
    return None


def fetch_all_fundamentals(ticker: str, use_cache: bool = True) -> dict[str, Any]:
    """
    Fetch all available fundamental data for a ticker.
    
    Combines profile, metrics, ratios, earnings surprises, and growth.
    
    Returns:
        {
            "profile": {...},
            "metrics": {...},
            "ratios": {...},
            "earnings_surprises": [...],
            "growth": {...},
            "has_data": bool,
        }
    """
    result = {
        "ticker": ticker,
        "profile": None,
        "metrics": None,
        "ratios": None,
        "earnings_surprises": None,
        "growth": None,
        "has_data": False,
    }
    
    if not is_configured():
        return result
    
    # Fetch all data points
    result["profile"] = fetch_company_profile(ticker, use_cache)
    result["metrics"] = fetch_key_metrics(ticker, use_cache)
    result["ratios"] = fetch_ratios(ticker, use_cache)
    result["earnings_surprises"] = fetch_earnings_surprises(ticker, use_cache)
    result["growth"] = fetch_growth_metrics(ticker, use_cache)
    
    # Mark if we got any useful data
    result["has_data"] = any([
        result["profile"],
        result["metrics"],
        result["ratios"],
    ])
    
    return result


def calculate_earnings_surprise_score(surprises: list[dict] | None) -> tuple[int, str | None]:
    """
    Calculate a score based on earnings surprises.
    
    Returns:
        (score: 0-5, flag: str or None)
    
    Scoring:
        - 5 pts: 4+ consecutive beats
        - 4 pts: 3 consecutive beats
        - 3 pts: 2 consecutive beats or mostly beats
        - 2 pts: Mixed results
        - 1 pt: Mostly misses
        - 0 pts: Consecutive misses or no data
    """
    if not surprises or len(surprises) == 0:
        return 0, None
    
    # Count beats/misses in recent quarters
    beats = 0
    misses = 0
    consecutive_beats = 0
    max_consecutive_beats = 0
    
    for surprise in surprises[:4]:  # Last 4 quarters
        pct = surprise.get("surprisePercentage", 0)
        if pct is None:
            continue
        
        if pct > 0:
            beats += 1
            consecutive_beats += 1
            max_consecutive_beats = max(max_consecutive_beats, consecutive_beats)
        else:
            misses += 1
            consecutive_beats = 0
    
    # Calculate score
    if max_consecutive_beats >= 4:
        return 5, f"🎯 4+ consecutive earnings beats"
    elif max_consecutive_beats >= 3:
        return 4, f"🎯 3 consecutive earnings beats"
    elif max_consecutive_beats >= 2 or beats >= 3:
        return 3, f"Mostly beating estimates ({beats}/4 quarters)"
    elif beats >= 2:
        return 2, None
    elif beats >= 1:
        return 1, None
    else:
        return 0, "⚠ Missing earnings estimates recently"


def get_fmp_enhanced_data(ticker: str, use_cache: bool = True) -> dict[str, Any]:
    """
    Get FMP data formatted for integration with existing scoring.
    
    For efficiency, this only fetches earnings data (which is what we need
    for the earnings surprise score). Other FMP data like ratios can be
    fetched separately if needed.
    
    Returns a dict with keys matching what fundamentals.py expects,
    plus additional FMP-specific metrics.
    """
    result = {
        "has_fmp_data": False,
        # Earnings surprise score (0-5 points)
        "earnings_surprise_score": 0,
        "earnings_surprise_flag": None,
        # Growth metrics from FMP (not fetched for efficiency)
        "fmp_revenue_growth": None,
        "fmp_eps_growth": None,
        "fmp_net_income_growth": None,
        # Ratios from FMP (not fetched for efficiency)
        "fmp_roe": None,
        "fmp_roa": None,
        "fmp_debt_to_equity": None,
        "fmp_current_ratio": None,
        "fmp_pe": None,
        "fmp_pb": None,
        # Analyst estimates
        "has_analyst_coverage": False,
    }
    
    if not is_configured():
        return result
    
    # Only fetch earnings data for the surprise score
    earnings = fetch_earnings_surprises(ticker, use_cache)
    
    if earnings and len(earnings) > 0:
        result["has_fmp_data"] = True
        result["has_analyst_coverage"] = True
        
        # Calculate earnings surprise score
        surprise_score, surprise_flag = calculate_earnings_surprise_score(earnings)
        result["earnings_surprise_score"] = surprise_score
        result["earnings_surprise_flag"] = surprise_flag
    
    return result


def clear_cache() -> int:
    """Clear all FMP cache files. Returns count of files deleted."""
    if not CACHE_DIR.exists():
        return 0
    
    deleted = 0
    for cache_file in CACHE_DIR.glob("*.json"):
        try:
            cache_file.unlink()
            deleted += 1
        except OSError:
            pass
    
    return deleted


def check_api_status() -> dict:
    """
    Check FMP API connectivity and quota.
    
    Returns:
        {
            "configured": bool,
            "connected": bool,
            "message": str,
        }
    """
    result = {
        "configured": False,
        "connected": False,
        "message": "",
    }
    
    api_key = get_api_key()
    if not api_key:
        result["message"] = "FMP API key not configured (set FMP_API_KEY in .env or environment)"
        return result
    
    result["configured"] = True
    
    # Test with AAPL (more reliable than Malaysian stocks on FMP)
    test_data = fetch_company_profile("AAPL", use_cache=False)
    
    if test_data and test_data.get("companyName"):
        result["connected"] = True
        result["message"] = f"Connected! FMP API ready"
    else:
        result["message"] = "API key configured but request failed (check key validity or quota)"
    
    return result
