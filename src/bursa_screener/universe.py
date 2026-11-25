"""
Bursa Malaysia stock universe.

Fetches KLCI 30 constituents dynamically from yfinance when possible,
with a cached fallback for reliability.

Yahoo Finance uses the .KL suffix for Bursa Malaysia stocks.
"""

from __future__ import annotations

import json
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import yfinance as yf

warnings.filterwarnings("ignore", category=FutureWarning)


# ── config paths ──────────────────────────────────────────────────────────────
CONFIG_DIR = Path(__file__).parent / "config"
KLCI_CACHE_FILE = CONFIG_DIR / "klci_constituents.json"
CACHE_MAX_AGE_DAYS = 7  # refresh cache weekly


# ── fallback list (used if fetch fails and no cache exists) ───────────────────
# Last verified: 2026-11
# Note: Tickers verified against yfinance — some may differ from Bursa codes
KLCI_FALLBACK = [
    "1155.KL",   # Malayan Banking (Maybank)
    "5347.KL",   # Tenaga Nasional
    "1023.KL",   # CIMB Group
    "5285.KL",   # SD Guthrie (formerly Sime Darby Plantation)
    "6888.KL",   # Axiata Group
    "4715.KL",   # Petronas Chemicals
    "6947.KL",   # Petronas Gas
    "5681.KL",   # Petronas Dagangan
    "1082.KL",   # Hong Leong Financial Group
    "4065.KL",   # PPB Group
    "5183.KL",   # Public Bank
    "3816.KL",   # MISC Berhad
    "6033.KL",   # RHB Bank
    "8869.KL",   # Press Metal
    "1961.KL",   # IOI Corporation
    "2445.KL",   # Kuala Lumpur Kepong (KLK)
    "4197.KL",   # Sime Darby Berhad
    "5288.KL",   # Sime Darby Property
    "6012.KL",   # Maxis
    "0166.KL",   # Telekom Malaysia
    "5008.KL",   # Westports
    "3689.KL",   # Genting Berhad
    "5819.KL",   # Hong Leong Bank
    "6742.KL",   # YTL Power International
    "4677.KL",   # YTL Corporation
    "7084.KL",   # QL Resources
    "3182.KL",   # Genting Malaysia
    "5296.KL",   # MR DIY Group
    "5225.KL",   # IHH Healthcare
    "1818.KL",   # Bursa Malaysia Berhad
]


def fetch_klci_constituents() -> list[str] | None:
    """
    Fetch FTSE Bursa Malaysia KLCI constituents from yfinance.
    
    Returns list of tickers or None if fetch fails.
    """
    try:
        # ^KLSE is the FTSE Bursa Malaysia KLCI index
        index = yf.Ticker("^KLSE")
        
        # Try to get components (yfinance may not always have this)
        # Method 1: Check if index has components attribute
        if hasattr(index, 'components') and index.components is not None:
            components = list(index.components)
            if components:
                return [f"{c}.KL" if not c.endswith(".KL") else c for c in components]
        
        # Method 2: Try info dict
        info = index.info or {}
        if 'components' in info:
            components = info['components']
            if components:
                return [f"{c}.KL" if not c.endswith(".KL") else c for c in components]
        
        return None
    except Exception:
        return None


def validate_ticker(ticker: str, timeout: float = 5.0) -> dict:
    """
    Validate a single ticker against yfinance.
    
    Returns:
        {
            "ticker": str,
            "valid": bool,
            "name": str | None,
            "price": float | None,
            "error": str | None,
        }
    """
    result = {
        "ticker": ticker,
        "valid": False,
        "name": None,
        "price": None,
        "market_cap": None,
        "error": None,
    }
    
    try:
        info = yf.Ticker(ticker).info
        name = info.get("longName") or info.get("shortName")
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        market_cap = info.get("marketCap")
        
        # A ticker is valid if it has a name and price
        if name and price:
            result["valid"] = True
            result["name"] = name
            result["price"] = price
            result["market_cap"] = market_cap
        else:
            result["error"] = "No price data (possibly delisted)"
    except Exception as e:
        result["error"] = str(e)[:50]
    
    return result


def validate_universe(
    tickers: list[str],
    remove_invalid: bool = True,
    verbose: bool = False,
) -> tuple[list[str], list[dict]]:
    """
    Validate a list of tickers and optionally remove invalid ones.
    
    Args:
        tickers: List of ticker symbols to validate
        remove_invalid: If True, return only valid tickers
        verbose: If True, print validation progress
    
    Returns:
        (valid_tickers, validation_results)
    """
    results = []
    valid_tickers = []
    
    for i, ticker in enumerate(tickers):
        if verbose:
            print(f"  Validating {ticker} ({i+1}/{len(tickers)})...", end="", flush=True)
        
        result = validate_ticker(ticker)
        results.append(result)
        
        if result["valid"]:
            valid_tickers.append(ticker)
            if verbose:
                print(f" ✓ {result['name'][:30]}")
        else:
            if verbose:
                print(f" ✗ {result['error']}")
        
        time.sleep(0.1)  # Rate limiting
    
    if remove_invalid:
        return valid_tickers, results
    return tickers, results


def get_validated_fallback() -> list[str]:
    """
    Return the fallback list after removing any invalid tickers.
    Caches the validation result.
    """
    cache_file = CONFIG_DIR / "validated_fallback.json"
    
    # Check if we have a recent validation
    if cache_file.exists():
        try:
            with open(cache_file) as f:
                data = json.load(f)
            validated_date = datetime.fromisoformat(data.get("validated", ""))
            if datetime.now() - validated_date < timedelta(days=30):
                return data.get("tickers", KLCI_FALLBACK)
        except (json.JSONDecodeError, ValueError, IOError):
            pass
    
    # Validate the fallback list
    valid_tickers, _ = validate_universe(KLCI_FALLBACK, remove_invalid=True, verbose=False)
    
    # Cache the result
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(cache_file, "w") as f:
            json.dump({
                "tickers": valid_tickers,
                "validated": datetime.now().isoformat(),
            }, f, indent=2)
    except IOError:
        pass
    
    return valid_tickers if valid_tickers else KLCI_FALLBACK


def fetch_bursa_tickers_by_market_cap(
    min_market_cap: float = 1e9,  # 1 billion MYR
    max_tickers: int = 50,
) -> list[str] | None:
    """
    Alternative: fetch top Bursa tickers by market cap.
    
    This is a fallback approach using a broader search.
    Returns None if fetch fails.
    """
    # Known large-cap Bursa tickers to seed the search
    seed_tickers = KLCI_FALLBACK[:10]
    
    try:
        results = []
        for ticker in seed_tickers:
            try:
                info = yf.Ticker(ticker).info
                market_cap = info.get("marketCap")
                if market_cap and market_cap >= min_market_cap:
                    results.append((ticker, market_cap))
            except Exception:
                continue
            time.sleep(0.1)
        
        # Sort by market cap descending
        results.sort(key=lambda x: x[1], reverse=True)
        return [t[0] for t in results[:max_tickers]] if results else None
    except Exception:
        return None


def load_cached_klci() -> tuple[list[str] | None, datetime | None]:
    """Load KLCI constituents from cache file."""
    if not KLCI_CACHE_FILE.exists():
        return None, None
    
    try:
        with open(KLCI_CACHE_FILE) as f:
            data = json.load(f)
        
        tickers = data.get("tickers", [])
        updated = data.get("updated")
        updated_dt = datetime.fromisoformat(updated) if updated else None
        
        return tickers if tickers else None, updated_dt
    except (json.JSONDecodeError, IOError, ValueError):
        return None, None


def save_cached_klci(tickers: list[str]) -> None:
    """Save KLCI constituents to cache file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    data = {
        "tickers": tickers,
        "updated": datetime.now().isoformat(),
        "source": "yfinance",
    }
    
    try:
        with open(KLCI_CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except IOError:
        pass  # Fail silently — cache is optional


def get_klci_constituents(force_refresh: bool = False) -> list[str]:
    """
    Get KLCI 30 constituents with smart caching.
    
    Priority:
    1. Fresh fetch from yfinance (if cache is stale or force_refresh)
    2. Cached constituents (if recent)
    3. Hardcoded fallback (if all else fails)
    
    Args:
        force_refresh: bypass cache and fetch fresh data
    
    Returns:
        List of KLCI ticker symbols
    """
    cached, cached_date = load_cached_klci()
    cache_is_fresh = (
        cached_date is not None 
        and datetime.now() - cached_date < timedelta(days=CACHE_MAX_AGE_DAYS)
    )
    
    # Use cache if fresh and not forcing refresh
    if cached and cache_is_fresh and not force_refresh:
        return cached
    
    # Try to fetch fresh data
    fresh = fetch_klci_constituents()
    
    if fresh and len(fresh) >= 20:  # Sanity check — KLCI should have ~30
        save_cached_klci(fresh)
        return fresh
    
    # Fetch failed — use cache if available (even if stale)
    if cached:
        return cached
    
    # Last resort: hardcoded fallback
    return KLCI_FALLBACK.copy()


# ── Mid-cap / thematic watchlist ─────────────────────────────────────────────
# Last verified: 2026-11
MID_CAP = [
    "5200.KL",   # UOA Development (UOADEV)
    "7113.KL",   # Hartalega
    "7277.KL",   # Dialog Group
    "5218.KL",   # MyNews
    "0072.KL",   # Pavilion REIT
    "5212.KL",   # Pavilion Real Estate Investment Trust
    "3336.KL",   # Scientex
    "0082.KL",   # Sunway REIT
    "5109.KL",   # Eco World Development
    "1996.KL",   # SKP Resources
    "0078.KL",   # IGB REIT
    "0138.KL",   # Axis REIT
    "5168.KL",   # Hartalega Holdings
]

# ── Southeast Asia cross-listings / regional ─────────────────────────────────
# These use Yahoo Finance tickers for SG, TH, ID boards.
SEA_REGIONAL: list[str] = []


# ── Convenience groupings ─────────────────────────────────────────────────────
def get_universe(tier: str = "klci", force_refresh: bool = False, sector: str | None = None) -> list[str]:
    """
    Return deduplicated ticker list.

    tier options
    ------------
    "klci"   – KLCI 30 only  (fast, ~30 tickers)
    "broad"  – KLCI + mid-cap  (~45 tickers)
    "full"   – all tiers
    
    sector options
    --------------
    If provided, filters tickers by sector using KLSE Screener data.
    Supported sectors: banking, technology, plantation, property, construction,
                      consumer, industrial, healthcare, telco, utilities, energy, reit
    
    force_refresh: bypass cache and fetch fresh KLCI constituents
    """
    klci = get_klci_constituents(force_refresh=force_refresh)
    
    if tier == "klci":
        tickers = klci
    elif tier == "broad":
        tickers = klci + MID_CAP
    else:
        tickers = klci + MID_CAP + SEA_REGIONAL

    # deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            result.append(t)
    
    # Apply sector filter if provided
    if sector:
        result = filter_by_sector(result, sector)
    
    return result


def filter_by_sector(tickers: list[str], sector: str) -> list[str]:
    """
    Filter tickers by sector using KLSE Screener data.
    
    Args:
        tickers: List of ticker symbols to filter
        sector: Sector name (case-insensitive)
    
    Returns:
        Filtered list of tickers in the specified sector
    """
    # Try to import klse_fetcher
    try:
        from . import klse_fetcher
        if not klse_fetcher.is_available():
            print(f"Warning: KLSE Screener not available, cannot filter by sector")
            return tickers
    except ImportError:
        print(f"Warning: KLSE Screener not available, cannot filter by sector")
        return tickers
    
    # Get all tickers in the sector
    sector_tickers = set(klse_fetcher.get_sector_tickers(sector))
    
    if not sector_tickers:
        # Sector not found or empty - try filtering by fundamentals
        print(f"Warning: Sector '{sector}' not found in KLSE data, filtering by fundamentals...")
        filtered = []
        for ticker in tickers:
            fund = klse_fetcher.fetch_fundamentals(ticker)
            if fund and fund.get("sector", "").lower() == sector.lower():
                filtered.append(ticker)
        return filtered if filtered else tickers
    
    # Filter to only tickers in both the input list and the sector
    return [t for t in tickers if t in sector_tickers]


def get_sector_universe(sector: str) -> list[str]:
    """
    Get all tickers in a sector directly from KLSE Screener.
    
    This bypasses the predefined universes and returns all stocks
    in the specified sector.
    
    Args:
        sector: Sector name (e.g., "banking", "technology", "plantation")
    
    Returns:
        List of all tickers in the sector
    """
    try:
        from . import klse_fetcher
        if klse_fetcher.is_available():
            return klse_fetcher.get_sector_tickers(sector)
    except ImportError:
        pass
    return []


def list_available_sectors() -> list[dict]:
    """
    List all available sectors that can be used for filtering.
    
    Returns:
        List of sector info dicts with 'code', 'name', and 'aliases'
    """
    try:
        from . import klse_fetcher
        if klse_fetcher.is_available():
            return klse_fetcher.get_available_sectors()
    except ImportError:
        pass
    return []


# For backward compatibility — lazy loaded on import
# This uses cache or fallback, no network call on import
def _get_klci_30() -> list[str]:
    """Lazy loader for KLCI_30 backward compatibility."""
    cached, _ = load_cached_klci()
    return cached if cached else KLCI_FALLBACK.copy()


KLCI_30 = _get_klci_30()
