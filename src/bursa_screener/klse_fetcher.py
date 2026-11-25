"""
KLSE Screener API client.

Provides enhanced Malaysian stock data beyond yfinance:
- More accurate fundamentals (PE, ROE, PB, EPS)
- Quarterly financial results with YoY/QoQ growth
- Shareholding changes (institutional buying signals)
- Insider/director trading activity
- Analyst consensus (target prices, recommendations)
- Trade summary (bid/ask depth)

Data source: klsescreener.com via klse-screener-py package

This is the PRIMARY data source for Malaysian stocks (.KL).
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# ── Configuration ─────────────────────────────────────────────────────────────
CACHE_DIR = Path(__file__).parent / "cache" / "klse"
CACHE_HOURS = 4  # Cache KLSE data for 4 hours (more frequent than yfinance)

# Rate limiting
REQUEST_DELAY = 0.3  # seconds between requests
_last_request_time = 0.0

# Try importing klse_screener
try:
    import klse_screener as klse
    KLSE_AVAILABLE = True
except ImportError:
    KLSE_AVAILABLE = False

# ── Sector Mapping ────────────────────────────────────────────────────────────
# Map readable sector names to KLSE sector codes
SECTOR_CODE_MAP = {
    "consumer": "0001I",
    "consumer products": "0001I",
    "industrial": "0002I",
    "industrials": "0002I",
    "construction": "0003I",
    "technology": "0005I",
    "tech": "0005I",
    "financial": "0010I",
    "finance": "0010I",
    "banking": "0010I",
    "property": "0020I",
    "properties": "0020I",
    "plantation": "0025I",
    "plantations": "0025I",
    "reit": "0050I",
    "reits": "0050I",
    "energy": "0061I",
    "healthcare": "0062I",
    "telco": "0063I",
    "telecommunications": "0063I",
    "utilities": "0064I",
    "transportation": "0065I",
    "transport": "0065I",
}

# Reverse map for display
SECTOR_DISPLAY_NAMES = {
    "0001I": "Consumer Products",
    "0002I": "Industrials",
    "0003I": "Construction",
    "0005I": "Technology",
    "0010I": "Financial Services",
    "0020I": "Property",
    "0025I": "Plantation",
    "0050I": "REITs",
    "0061I": "Energy",
    "0062I": "Healthcare",
    "0063I": "Telecommunications",
    "0064I": "Utilities",
    "0065I": "Transportation",
}


def is_available() -> bool:
    """Check if klse-screener-py is installed."""
    return KLSE_AVAILABLE


# ── Caching ───────────────────────────────────────────────────────────────────

def _get_cache_path(data_type: str, ticker: str) -> Path:
    """Get cache file path for a data type."""
    # Convert ticker format: 1155.KL -> 1155
    code = ticker.replace(".KL", "").replace(".kl", "")
    return CACHE_DIR / f"{data_type}_{code}.json"


def _is_cache_valid(cache_path: Path) -> bool:
    """Check if cache file exists and is fresh."""
    if not cache_path.exists():
        return False
    try:
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < timedelta(hours=CACHE_HOURS)
    except (OSError, ValueError):
        return False


def _load_cache(data_type: str, ticker: str) -> dict | None:
    """Load cached data if valid."""
    cache_path = _get_cache_path(data_type, ticker)
    if not _is_cache_valid(cache_path):
        return None
    try:
        with open(cache_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _save_cache(data_type: str, ticker: str, data: dict | list) -> None:
    """Save data to cache."""
    cache_path = _get_cache_path(data_type, ticker)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(cache_path, "w") as f:
            json.dump(data, f, default=str)
    except IOError:
        pass


def _rate_limit():
    """Apply rate limiting between requests."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)
    _last_request_time = time.time()


def _convert_ticker(ticker: str) -> str:
    """Convert yfinance ticker format to KLSE code.
    
    yfinance: 1155.KL
    KLSE Screener: 1155
    """
    return ticker.replace(".KL", "").replace(".kl", "")


# ── Public API Functions ──────────────────────────────────────────────────────

def fetch_fundamentals(ticker: str, use_cache: bool = True) -> dict | None:
    """
    Fetch fundamentals from KLSE Screener.
    
    Returns:
        {
            "name": "MAYBANK",
            "sector": "Banking",
            "pe_ratio": "11.65",
            "eps": "87.24",
            "dividend_yield": "6.20%",
            "nta": "7.2903",
            "pb_ratio": "1.39",
            "roe": "11.97",
            "market_cap": "123.4B",
            "dps": "63.00",
            ...
        }
    """
    if not KLSE_AVAILABLE:
        return None
    
    code = _convert_ticker(ticker)
    
    if use_cache:
        cached = _load_cache("fundamentals", ticker)
        if cached:
            return cached
    
    _rate_limit()
    
    try:
        data = klse.get_klse_fundamentals(code)
        if data and use_cache:
            _save_cache("fundamentals", ticker, data)
        return data
    except Exception:
        return None


def fetch_quarterly_financials(ticker: str, use_cache: bool = True) -> list[dict] | None:
    """
    Fetch quarterly financial results from KLSE Screener.
    
    Returns list of quarterly results:
        [
            {
                "eps": 22.69,
                "dps": 0.0,
                "nta": 7.2903,
                "revenue": 14600000000.0,
                "net_profit": 2700000000.0,
                "quarter": "3",
                "q_date": "2026-09-30",
                "roe": 3.1,
                "qoq": 2.0,  # QoQ growth %
                "yoy": 4.7   # YoY growth %
            },
            ...
        ]
    """
    if not KLSE_AVAILABLE:
        return None
    
    code = _convert_ticker(ticker)
    
    if use_cache:
        cached = _load_cache("quarterly", ticker)
        if cached:
            return cached
    
    _rate_limit()
    
    try:
        data = klse.get_klse_quarterly_financials_dict(code)
        if data and "quarterly_data" in data:
            result = data["quarterly_data"]
            if result and use_cache:
                _save_cache("quarterly", ticker, result)
            return result
        return None
    except Exception:
        return None


def fetch_shareholding_changes(ticker: str, use_cache: bool = True) -> list[dict] | None:
    """
    Fetch shareholding changes from KLSE Screener.
    
    Returns list of recent transactions:
        [
            {
                "date": "24 Nov 2026",
                "transaction_type": "Acquired",
                "shares": "216,600",
                "holder": "KUMPULAN WANG PERSARAAN (DIPERBADANKAN)"
            },
            ...
        ]
    """
    if not KLSE_AVAILABLE:
        return None
    
    code = _convert_ticker(ticker)
    
    if use_cache:
        cached = _load_cache("shareholding", ticker)
        if cached:
            return cached
    
    _rate_limit()
    
    try:
        data = klse.get_klse_shareholding_changes_raw(code)
        if data and use_cache:
            _save_cache("shareholding", ticker, data)
        return data
    except Exception:
        return None


def fetch_trade_summary(ticker: str, use_cache: bool = True) -> dict | None:
    """
    Fetch trade summary from KLSE Screener.
    
    Returns:
        {
            "current_price": 10.16,
            "price_change": 0.02,
            "price_change_percent": 0.2,
            "total_bid_volume": 11213000,
            "total_ask_volume": 2432900,
            "bid_ask_spread": -0.16,
            ...
        }
    """
    if not KLSE_AVAILABLE:
        return None
    
    code = _convert_ticker(ticker)
    
    if use_cache:
        cached = _load_cache("trade", ticker)
        if cached:
            return cached
    
    _rate_limit()
    
    try:
        data = klse.get_klse_trade_summary(code)
        if data and use_cache:
            _save_cache("trade", ticker, data)
        return data
    except Exception:
        return None


def fetch_insider_dealings(ticker: str, use_cache: bool = True) -> list[dict] | None:
    """
    Fetch insider/director dealings from shareholding changes.
    
    Filters shareholding changes for director/insider transactions
    (not institutional like EPF/KWAP).
    
    Returns list of transactions:
        [
            {
                "date": "24 Nov 2026",
                "transaction_type": "Acquired",
                "shares": "100,000",
                "holder": "TAN SRI DATO' MEGAT ...",
                "is_director": True,
            },
            ...
        ]
    """
    if not KLSE_AVAILABLE:
        return None
    
    code = _convert_ticker(ticker)
    
    if use_cache:
        cached = _load_cache("insider", ticker)
        if cached:
            return cached
    
    _rate_limit()
    
    try:
        # Get all shareholding changes
        all_changes = klse.get_klse_shareholding_changes_raw(code)
        if not all_changes:
            return None
        
        # Filter for insider/director transactions (exclude institutions)
        INSTITUTIONS = [
            "EPF", "KWAP", "PNB", "AMANAH", "PERSARAAN", "TABUNG", 
            "LEMBAGA", "TRUSTEES", "NOMINEES", "CUSTODIAN", "SECURITIES",
            "INVESTMENT", "FUND", "CAPITAL", "ASSET"
        ]
        
        insider_deals = []
        for txn in all_changes:
            holder = txn.get("holder", "").upper()
            
            # Skip if it looks like an institution
            is_institution = any(inst in holder for inst in INSTITUTIONS)
            if is_institution:
                continue
            
            # Likely a director/insider if it contains a person's name
            # (titles like TAN SRI, DATO', DATUK, etc.)
            is_likely_person = any(title in holder for title in [
                "TAN SRI", "DATO", "DATUK", "TUNKU", "TENGKU", "DR.", "DR ",
                "HAJI", "HAJAH", "ENCIK", "PUAN", "MR.", "MRS.", "MS."
            ]) or (len(holder.split()) >= 2 and not any(inst in holder for inst in ["SDN", "BHD", "LTD", "INC", "CORP"]))
            
            if is_likely_person:
                insider_deals.append({
                    **txn,
                    "is_director": True,
                })
        
        if insider_deals and use_cache:
            _save_cache("insider", ticker, insider_deals)
        
        return insider_deals if insider_deals else None
    except Exception:
        return None


def fetch_enhanced_fundamentals(ticker: str, use_cache: bool = True) -> dict | None:
    """
    Fetch enhanced fundamentals from KLSE Screener.
    
    This provides more accurate PE, ROE, EPS than yfinance for Malaysian stocks.
    
    Returns:
        {
            "name": "MAYBANK",
            "sector": "Banking",
            "pe_ratio": 11.65,     # Numeric, not string
            "eps": 87.24,          # Sen
            "roe": 11.97,          # Percentage
            "pb_ratio": 1.39,
            "dividend_yield": 6.20,  # Percentage
            "market_cap": "123.4B",
            "nta": 7.2903,
            "dps": 63.00,          # Sen
            "psr": 2.01,           # Price-to-Sales
            "52_week_low": 9.78,
            "52_week_high": 12.42,
        }
    """
    if not KLSE_AVAILABLE:
        return None
    
    code = _convert_ticker(ticker)
    
    if use_cache:
        cached = _load_cache("enhanced_fund", ticker)
        if cached:
            return cached
    
    _rate_limit()
    
    try:
        data = klse.get_klse_enhanced_fundamentals(code)
        if not data:
            return None
        
        # Parse and clean the data
        result = {
            "name": data.get("name"),
            "sector": data.get("sector"),
            "pe_ratio": _parse_number(data.get("pe_ratio")),
            "eps": _parse_number(data.get("eps")),
            "roe": _parse_number(data.get("roe")),
            "pb_ratio": _parse_number(data.get("pb_ratio")),
            "dividend_yield": _parse_percentage(data.get("dividend_yield")),
            "market_cap": data.get("market_cap"),
            "nta": _parse_number(data.get("nta")),
            "dps": _parse_number(data.get("dps")),
            "psr": _parse_number(data.get("psr")),
        }
        
        # Parse 52-week range
        range_str = data.get("fifty_two_week_range", "")
        if range_str and " - " in range_str:
            parts = range_str.split(" - ")
            result["52_week_low"] = _parse_number(parts[0])
            result["52_week_high"] = _parse_number(parts[1])
        
        if result and use_cache:
            _save_cache("enhanced_fund", ticker, result)
        
        return result
    except Exception:
        return None


def _parse_number(val: str | float | None) -> float | None:
    """Parse a number from string or return float."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        # Remove commas and parse
        cleaned = str(val).replace(",", "").strip()
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _parse_percentage(val: str | float | None) -> float | None:
    """Parse a percentage value (removes % sign)."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        cleaned = str(val).replace("%", "").replace(",", "").strip()
        return float(cleaned)
    except (ValueError, TypeError):
        return None


# ── Sector Functions ──────────────────────────────────────────────────────────

def get_sector_tickers(sector: str, use_cache: bool = True) -> list[str]:
    """
    Get all tickers for a given sector.
    
    Args:
        sector: Sector name (e.g., "banking", "technology", "plantation")
                Case-insensitive, supports aliases.
    
    Returns:
        List of tickers in yfinance format (e.g., ["1155.KL", "1023.KL"])
    """
    if not KLSE_AVAILABLE:
        return []
    
    sector_lower = sector.lower().strip()
    sector_code = SECTOR_CODE_MAP.get(sector_lower)
    
    if not sector_code:
        # Try partial match
        for key, code in SECTOR_CODE_MAP.items():
            if sector_lower in key or key in sector_lower:
                sector_code = code
                break
    
    if not sector_code:
        return []
    
    # Check cache
    cache_key = f"sector_{sector_code}"
    if use_cache:
        cached = _load_cache(cache_key, "all")
        if cached:
            return cached
    
    _rate_limit()
    
    try:
        all_sectors = klse.get_klse_all_sector_stocks()
        if not all_sectors or sector_code not in all_sectors:
            return []
        
        stocks = all_sectors[sector_code]
        tickers = [s.get("symbol") for s in stocks if s.get("symbol")]
        
        if tickers and use_cache:
            _save_cache(cache_key, "all", tickers)
        
        return tickers
    except Exception:
        return []


def get_available_sectors() -> list[dict]:
    """
    Get list of available sectors with their codes and display names.
    
    Returns:
        [
            {"code": "0010I", "name": "Financial Services", "aliases": ["banking", "finance"]},
            ...
        ]
    """
    sectors = []
    seen_codes = set()
    
    for alias, code in SECTOR_CODE_MAP.items():
        if code not in seen_codes:
            seen_codes.add(code)
            display_name = SECTOR_DISPLAY_NAMES.get(code, alias.title())
            aliases = [k for k, v in SECTOR_CODE_MAP.items() if v == code]
            sectors.append({
                "code": code,
                "name": display_name,
                "aliases": aliases,
            })
    
    return sectors


# ── Scoring Functions ─────────────────────────────────────────────────────────

def calculate_earnings_consistency_score(quarterly: list[dict] | None) -> tuple[int, str | None]:
    """
    Calculate earnings consistency score from quarterly data.
    
    Scoring (max 3 pts):
        - 3 pts: 4+ consecutive positive YoY growth quarters
        - 2 pts: 3 consecutive positive YoY growth
        - 1 pt:  2 consecutive positive YoY growth
        - 0 pts: Inconsistent or negative growth
    
    Returns:
        (score: 0-3, flag: str or None)
    """
    if not quarterly or len(quarterly) < 4:
        return 0, None
    
    # Check YoY growth for recent quarters
    consecutive_positive = 0
    for q in quarterly[:6]:  # Last 6 quarters
        yoy = q.get("yoy")
        if yoy is not None and yoy > 0:
            consecutive_positive += 1
        else:
            break
    
    if consecutive_positive >= 4:
        return 3, f"📈 {consecutive_positive} consecutive quarters of YoY growth"
    elif consecutive_positive >= 3:
        return 2, f"Solid earnings trend ({consecutive_positive}Q positive YoY)"
    elif consecutive_positive >= 2:
        return 1, None
    else:
        # Check for recent decline
        if quarterly[0].get("yoy", 0) < -10:
            return 0, f"⚠ Recent YoY decline: {quarterly[0].get('yoy'):.1f}%"
        return 0, None


def calculate_earnings_momentum_score(quarterly: list[dict] | None) -> tuple[int, str | None]:
    """
    Calculate earnings momentum score from quarterly QoQ/YoY data.
    
    Similar to FMP earnings surprise - looks for acceleration.
    
    Scoring (max 5 pts):
        - 5 pts: Strong acceleration (QoQ > 10% AND YoY > 20%)
        - 4 pts: Good momentum (QoQ > 5% AND YoY > 10%)
        - 3 pts: Positive momentum (QoQ > 0 AND YoY > 0)
        - 2 pts: Mixed (one positive)
        - 1 pt:  Slight decline
        - 0 pts: Both declining
    
    Returns:
        (score: 0-5, flag: str or None)
    """
    if not quarterly or len(quarterly) < 1:
        return 0, None
    
    latest = quarterly[0]
    qoq = latest.get("qoq", 0) or 0
    yoy = latest.get("yoy", 0) or 0
    
    # Strong acceleration
    if qoq > 10 and yoy > 20:
        return 5, f"🚀 Strong earnings momentum (QoQ: +{qoq:.1f}%, YoY: +{yoy:.1f}%)"
    
    # Good momentum
    if qoq > 5 and yoy > 10:
        return 4, f"Strong YoY growth: +{yoy:.1f}%"
    
    # Positive momentum
    if qoq > 0 and yoy > 0:
        return 3, None
    
    # Mixed
    if qoq > 0 or yoy > 0:
        return 2, None
    
    # Slight decline
    if qoq > -10 and yoy > -10:
        return 1, None
    
    # Sharp decline
    return 0, f"⚠ Earnings declining (QoQ: {qoq:.1f}%, YoY: {yoy:.1f}%)"


def calculate_institutional_flow_score(shareholding: list[dict] | None) -> tuple[int, str | None]:
    """
    Calculate institutional flow score from shareholding changes.
    
    Looks for institutional buying (EPF, KWAP, PNB, etc.)
    
    Scoring (max 3 pts):
        - 3 pts: Net institutional buying (3+ acquisitions, few disposals)
        - 2 pts: Some institutional interest
        - 1 pt:  Mixed activity
        - 0 pts: Net selling or no activity
    
    Returns:
        (score: 0-3, flag: str or None)
    """
    if not shareholding or len(shareholding) == 0:
        return 0, None
    
    # Count acquisitions vs disposals in recent transactions
    acquisitions = 0
    disposals = 0
    institutional_buyers = []
    
    # Major institutional holders keywords
    INSTITUTIONS = ["EPF", "KWAP", "PNB", "AMANAH", "PERSARAAN", "TABUNG", "LEMBAGA"]
    
    for txn in shareholding[:10]:  # Last 10 transactions
        txn_type = txn.get("transaction_type", "").lower()
        holder = txn.get("holder", "").upper()
        
        is_institution = any(inst in holder for inst in INSTITUTIONS)
        
        if "acquired" in txn_type or "bought" in txn_type:
            acquisitions += 1
            if is_institution:
                # Extract short name
                for inst in INSTITUTIONS:
                    if inst in holder:
                        institutional_buyers.append(inst)
                        break
        elif "disposed" in txn_type or "sold" in txn_type:
            disposals += 1
    
    net_flow = acquisitions - disposals
    
    if net_flow >= 3 or (acquisitions >= 3 and len(institutional_buyers) >= 2):
        buyers_str = ", ".join(set(institutional_buyers[:3]))
        return 3, f"🏦 Institutional buying ({buyers_str})" if buyers_str else "🏦 Net institutional buying"
    elif net_flow >= 1 or acquisitions >= 2:
        return 2, None
    elif acquisitions >= 1:
        return 1, None
    elif net_flow < -2:
        return 0, "⚠ Net institutional selling"
    
    return 0, None


def calculate_insider_trading_score(insider_deals: list[dict] | None) -> tuple[int, str | None]:
    """
    Calculate insider trading score from director/insider dealings.
    
    Directors buying their own stock is typically a bullish signal.
    
    Scoring (max 3 pts):
        - 3 pts: Multiple director acquisitions, no disposals
        - 2 pts: Net director buying
        - 1 pt:  Mixed activity
        - 0 pts: Net director selling
        - -1 pt: Heavy director selling (penalty)
    
    Returns:
        (score: -1 to 3, flag: str or None)
    """
    if not insider_deals or len(insider_deals) == 0:
        return 0, None
    
    acquisitions = 0
    disposals = 0
    
    for txn in insider_deals[:10]:  # Last 10 transactions
        txn_type = txn.get("transaction_type", "").lower()
        
        if "acquired" in txn_type or "bought" in txn_type:
            acquisitions += 1
        elif "disposed" in txn_type or "sold" in txn_type:
            disposals += 1
    
    net_flow = acquisitions - disposals
    
    if acquisitions >= 2 and disposals == 0:
        return 3, f"👔 Directors buying ({acquisitions} transactions)"
    elif net_flow >= 2:
        return 2, f"Directors net buying"
    elif net_flow >= 1:
        return 1, None
    elif net_flow <= -3:
        return -1, f"⚠ Heavy director selling ({disposals} disposals)"
    elif net_flow < 0:
        return 0, f"⚠ Director selling ({disposals} disposals)"
    
    return 0, None


def get_klse_enhanced_data(ticker: str, use_cache: bool = True) -> dict[str, Any]:
    """
    Get KLSE Screener data formatted for integration with existing scoring.
    
    Returns a dict with enhanced Malaysian stock data:
        {
            "has_klse_data": bool,
            "fundamentals": {...},      # More accurate than yfinance
            "enhanced_fund": {...},     # Parsed numeric fundamentals
            "quarterly": [...],         # Quarterly results
            "shareholding": [...],      # Shareholding changes
            "insider_deals": [...],     # Director/insider trades
            
            # Pre-calculated scores
            "earnings_momentum_score": 0-5,
            "earnings_momentum_flag": str or None,
            "earnings_consistency_score": 0-3,
            "earnings_consistency_flag": str or None,
            "institutional_flow_score": 0-3,
            "institutional_flow_flag": str or None,
            "insider_trading_score": -1 to 3,
            "insider_trading_flag": str or None,
            
            # Enhanced fundamentals (more accurate than yfinance)
            "klse_pe": float or None,
            "klse_roe": float or None,
            "klse_eps": float or None,
            "klse_pb": float or None,
            "klse_div_yield": float or None,
            "klse_sector": str or None,
        }
    """
    result = {
        "has_klse_data": False,
        "ticker": ticker,
        "fundamentals": None,
        "enhanced_fund": None,
        "quarterly": None,
        "shareholding": None,
        "insider_deals": None,
        # Scores
        "earnings_momentum_score": 0,
        "earnings_momentum_flag": None,
        "earnings_consistency_score": 0,
        "earnings_consistency_flag": None,
        "institutional_flow_score": 0,
        "institutional_flow_flag": None,
        "insider_trading_score": 0,
        "insider_trading_flag": None,
        # Enhanced fundamentals
        "klse_pe": None,
        "klse_roe": None,
        "klse_eps": None,
        "klse_pb": None,
        "klse_div_yield": None,
        "klse_sector": None,
        "klse_52wk_low": None,
        "klse_52wk_high": None,
    }
    
    if not KLSE_AVAILABLE:
        return result
    
    # Check if this is a Malaysian stock
    if not ticker.upper().endswith(".KL"):
        return result
    
    # Fetch all data
    fundamentals = fetch_fundamentals(ticker, use_cache)
    enhanced_fund = fetch_enhanced_fundamentals(ticker, use_cache)
    quarterly = fetch_quarterly_financials(ticker, use_cache)
    shareholding = fetch_shareholding_changes(ticker, use_cache)
    insider_deals = fetch_insider_dealings(ticker, use_cache)
    
    # Store raw data
    result["fundamentals"] = fundamentals
    result["enhanced_fund"] = enhanced_fund
    result["quarterly"] = quarterly
    result["shareholding"] = shareholding
    result["insider_deals"] = insider_deals
    
    # Mark as having data if we got fundamentals
    if fundamentals or enhanced_fund:
        result["has_klse_data"] = True
    
    # Extract enhanced fundamentals (more accurate than yfinance)
    if enhanced_fund:
        result["klse_pe"] = enhanced_fund.get("pe_ratio")
        result["klse_roe"] = enhanced_fund.get("roe")
        result["klse_eps"] = enhanced_fund.get("eps")
        result["klse_pb"] = enhanced_fund.get("pb_ratio")
        result["klse_div_yield"] = enhanced_fund.get("dividend_yield")
        result["klse_sector"] = enhanced_fund.get("sector")
        result["klse_52wk_low"] = enhanced_fund.get("52_week_low")
        result["klse_52wk_high"] = enhanced_fund.get("52_week_high")
    elif fundamentals:
        # Fallback to basic fundamentals
        result["klse_pe"] = _parse_number(fundamentals.get("pe_ratio"))
        result["klse_roe"] = _parse_number(fundamentals.get("roe"))
        result["klse_eps"] = _parse_number(fundamentals.get("eps"))
        result["klse_pb"] = _parse_number(fundamentals.get("pb_ratio"))
        result["klse_div_yield"] = _parse_percentage(fundamentals.get("dividend_yield"))
        result["klse_sector"] = fundamentals.get("sector")
    
    # Calculate scores
    if quarterly:
        mom_score, mom_flag = calculate_earnings_momentum_score(quarterly)
        result["earnings_momentum_score"] = mom_score
        result["earnings_momentum_flag"] = mom_flag
        
        cons_score, cons_flag = calculate_earnings_consistency_score(quarterly)
        result["earnings_consistency_score"] = cons_score
        result["earnings_consistency_flag"] = cons_flag
    
    if shareholding:
        inst_score, inst_flag = calculate_institutional_flow_score(shareholding)
        result["institutional_flow_score"] = inst_score
        result["institutional_flow_flag"] = inst_flag
    
    if insider_deals:
        insider_score, insider_flag = calculate_insider_trading_score(insider_deals)
        result["insider_trading_score"] = insider_score
        result["insider_trading_flag"] = insider_flag
    
    return result


def clear_cache() -> int:
    """Clear all KLSE cache files. Returns count of files deleted."""
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


def check_status() -> dict:
    """
    Check KLSE Screener availability.
    
    Returns:
        {
            "available": bool,
            "connected": bool,
            "message": str,
        }
    """
    result = {
        "available": False,
        "connected": False,
        "message": "",
    }
    
    if not KLSE_AVAILABLE:
        result["message"] = "klse-screener-py not installed (pip install klse-screener-py)"
        return result
    
    result["available"] = True
    
    # Test with a known stock
    try:
        test_data = fetch_fundamentals("1155.KL", use_cache=False)
        if test_data and test_data.get("name"):
            result["connected"] = True
            result["message"] = f"Connected! KLSE Screener ready"
        else:
            result["message"] = "Package available but API request failed"
    except Exception as e:
        result["message"] = f"Connection error: {str(e)}"
    
    return result
