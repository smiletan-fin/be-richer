"""
News Fetcher — Aggregates news from multiple sources for Malaysian stocks.

Sources:
1. KLSE Screener - Malaysian market news (primary for .KL stocks)
2. yfinance - Yahoo Finance news (international coverage)

Returns standardized news items with:
- title, summary, date, source, url
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yfinance as yf

# KLSE Screener integration
try:
    import klse_screener as klse
    KLSE_AVAILABLE = True
except ImportError:
    KLSE_AVAILABLE = False

# ── Configuration ─────────────────────────────────────────────────────────────
CACHE_DIR = Path(__file__).parent / "cache" / "news"
CACHE_HOURS = 2  # News cache expires faster (2 hours)
MAX_NEWS_ITEMS = 10  # Max news items per source


# ── Caching ───────────────────────────────────────────────────────────────────

def _get_cache_path(ticker: str, source: str) -> Path:
    """Get cache file path for news."""
    safe_ticker = ticker.replace(".", "_").replace("/", "_")
    return CACHE_DIR / f"{safe_ticker}_{source}.json"


def _is_cache_valid(cache_path: Path) -> bool:
    """Check if cache file exists and is fresh."""
    if not cache_path.exists():
        return False
    try:
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < timedelta(hours=CACHE_HOURS)
    except (OSError, ValueError):
        return False


def _load_cache(ticker: str, source: str) -> list[dict] | None:
    """Load cached news if valid."""
    cache_path = _get_cache_path(ticker, source)
    if not _is_cache_valid(cache_path):
        return None
    try:
        with open(cache_path) as f:
            data = json.load(f)
        return data.get("news", [])
    except (json.JSONDecodeError, IOError):
        return None


def _save_cache(ticker: str, source: str, news: list[dict]) -> None:
    """Save news to cache."""
    cache_path = _get_cache_path(ticker, source)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = {
            "ticker": ticker,
            "source": source,
            "cached_at": datetime.now().isoformat(),
            "news": news,
        }
        with open(cache_path, "w") as f:
            json.dump(data, f, default=str)
    except IOError:
        pass


# ── News Fetchers ─────────────────────────────────────────────────────────────

def fetch_klse_news(ticker: str, use_cache: bool = True) -> list[dict]:
    """
    Fetch news from KLSE Screener.
    
    Returns list of news items:
        [
            {
                "title": "...",
                "summary": "...",
                "date": "2026-11-26",
                "source": "KLSE Screener",
                "url": "https://...",
            },
            ...
        ]
    """
    if not KLSE_AVAILABLE:
        return []
    
    # Check cache
    if use_cache:
        cached = _load_cache(ticker, "klse")
        if cached is not None:
            return cached
    
    # Convert ticker format: 1155.KL -> 1155
    code = ticker.replace(".KL", "").replace(".kl", "")
    
    try:
        raw_news = klse.get_klse_news_raw(code)
        if not raw_news:
            return []
        
        news = []
        for item in raw_news[:MAX_NEWS_ITEMS]:
            # Parse date
            date_str = item.get("date", "")
            try:
                # Format: "2026-11-26 08:23:00"
                if date_str:
                    dt = datetime.strptime(date_str.split()[0], "%Y-%m-%d")
                    date_str = dt.strftime("%Y-%m-%d")
            except (ValueError, IndexError):
                date_str = date_str[:10] if date_str else "Unknown"
            
            news.append({
                "title": item.get("title", "")[:200],  # Truncate long titles
                "summary": item.get("excerpt", "")[:300],
                "date": date_str,
                "source": "KLSE Screener",
                "url": item.get("url", ""),
            })
        
        # Cache results
        if use_cache and news:
            _save_cache(ticker, "klse", news)
        
        return news
    except Exception:
        return []


def fetch_yahoo_news(ticker: str, use_cache: bool = True) -> list[dict]:
    """
    Fetch news from Yahoo Finance via yfinance.
    
    Returns list of news items:
        [
            {
                "title": "...",
                "summary": "...",
                "date": "2026-11-26",
                "source": "Bloomberg",
                "url": "https://...",
            },
            ...
        ]
    """
    # Check cache
    if use_cache:
        cached = _load_cache(ticker, "yahoo")
        if cached is not None:
            return cached
    
    try:
        yf_ticker = yf.Ticker(ticker)
        raw_news = yf_ticker.news
        
        if not raw_news:
            return []
        
        news = []
        for item in raw_news[:MAX_NEWS_ITEMS]:
            # Navigate nested structure (yfinance changed format)
            content = item.get("content", item)  # Fallback to item if no content key
            
            # Extract fields
            title = content.get("title", item.get("title", ""))
            summary = content.get("summary", content.get("description", ""))
            
            # Parse date
            pub_date = content.get("pubDate", item.get("providerPublishTime", ""))
            if isinstance(pub_date, (int, float)):
                # Unix timestamp
                date_str = datetime.fromtimestamp(pub_date).strftime("%Y-%m-%d")
            elif isinstance(pub_date, str) and pub_date:
                # ISO format: "2026-11-25T06:08:49Z"
                try:
                    dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                    date_str = dt.strftime("%Y-%m-%d")
                except ValueError:
                    date_str = pub_date[:10]
            else:
                date_str = "Unknown"
            
            # Extract source/provider
            provider = content.get("provider", {})
            if isinstance(provider, dict):
                source = provider.get("displayName", "Yahoo Finance")
            else:
                source = "Yahoo Finance"
            
            # Extract URL
            url_data = content.get("canonicalUrl", content.get("clickThroughUrl", {}))
            if isinstance(url_data, dict):
                url = url_data.get("url", "")
            else:
                url = item.get("link", "")
            
            if title:  # Only add if we have a title
                news.append({
                    "title": title[:200],
                    "summary": summary[:300] if summary else "",
                    "date": date_str,
                    "source": source,
                    "url": url,
                })
        
        # Cache results
        if use_cache and news:
            _save_cache(ticker, "yahoo", news)
        
        return news
    except Exception:
        return []


def fetch_all_news(ticker: str, use_cache: bool = True) -> dict[str, Any]:
    """
    Fetch news from all available sources and combine.
    
    Returns:
        {
            "ticker": "1155.KL",
            "total_count": 15,
            "sources": ["KLSE Screener", "Yahoo Finance"],
            "news": [
                {
                    "title": "...",
                    "summary": "...",
                    "date": "2026-11-26",
                    "source": "KLSE Screener",
                    "url": "...",
                },
                ...
            ],
            "klse_news": [...],  # Raw KLSE news
            "yahoo_news": [...],  # Raw Yahoo news
        }
    """
    result = {
        "ticker": ticker,
        "total_count": 0,
        "sources": [],
        "news": [],
        "klse_news": [],
        "yahoo_news": [],
    }
    
    # Fetch from KLSE Screener (for Malaysian stocks)
    if ticker.upper().endswith(".KL"):
        klse_news = fetch_klse_news(ticker, use_cache)
        if klse_news:
            result["klse_news"] = klse_news
            result["sources"].append("KLSE Screener")
    
    # Fetch from Yahoo Finance
    yahoo_news = fetch_yahoo_news(ticker, use_cache)
    if yahoo_news:
        result["yahoo_news"] = yahoo_news
        result["sources"].append("Yahoo Finance")
    
    # Combine and deduplicate by title similarity
    all_news = result["klse_news"] + result["yahoo_news"]
    
    # Sort by date (newest first)
    def parse_date(item):
        try:
            return datetime.strptime(item.get("date", "1900-01-01"), "%Y-%m-%d")
        except ValueError:
            return datetime(1900, 1, 1)
    
    all_news.sort(key=parse_date, reverse=True)
    
    # Simple deduplication by title
    seen_titles = set()
    deduped = []
    for item in all_news:
        title_key = item["title"].lower()[:50]  # First 50 chars for comparison
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            deduped.append(item)
    
    result["news"] = deduped[:15]  # Limit to 15 combined news items
    result["total_count"] = len(result["news"])
    
    return result


def format_news_for_prompt(news_data: dict[str, Any], max_items: int = 10) -> str:
    """
    Format news data for inclusion in AI prompt.
    
    Returns a formatted string section for the AI prompt.
    """
    if not news_data or not news_data.get("news"):
        return """
═══════════════════════════════════════════════════════════════════════════════
                        RECENT NEWS & ANNOUNCEMENTS
═══════════════════════════════════════════════════════════════════════════════

No recent news available for this stock.

Note: News data may be limited for smaller companies or during low-activity periods.
"""
    
    news_items = news_data["news"][:max_items]
    sources = ", ".join(news_data.get("sources", ["Unknown"]))
    
    section = f"""
═══════════════════════════════════════════════════════════════════════════════
                        RECENT NEWS & ANNOUNCEMENTS
═══════════════════════════════════════════════════════════════════════════════

Sources: {sources}
Total Articles: {news_data.get('total_count', len(news_items))}

"""
    
    for i, item in enumerate(news_items, 1):
        title = item.get("title", "No title")
        date = item.get("date", "Unknown date")
        source = item.get("source", "Unknown")
        summary = item.get("summary", "")
        
        section += f"[{i}] {title}\n"
        section += f"    📅 {date} | 📰 {source}\n"
        if summary:
            # Truncate long summaries
            summary_text = summary[:200] + "..." if len(summary) > 200 else summary
            section += f"    {summary_text}\n"
        section += "\n"
    
    section += """
─────────────────────────────────────────────────────────────────────────────────
NEWS ANALYSIS INSTRUCTIONS:
─────────────────────────────────────────────────────────────────────────────────

When analyzing the news above, consider:

1. **Sentiment Analysis**: Is the overall news sentiment positive, negative, or neutral?

2. **Material Events**: Identify any material events that could impact the stock:
   - Earnings announcements or guidance changes
   - Management changes or corporate restructuring
   - Regulatory actions or legal issues
   - M&A activity or strategic partnerships
   - Product launches or market expansion

3. **Catalyst Assessment**: 
   - Are there upcoming catalysts mentioned (earnings dates, product launches)?
   - Have recent catalysts already been priced into the stock?

4. **Risk Identification**:
   - Any red flags or concerns mentioned?
   - Sector-wide issues that could affect this stock?

5. **Market Perception**:
   - How is the market/analysts viewing this company?
   - Any divergence between news sentiment and stock price action?

Include your news analysis in the relevant sections of your report.
"""
    
    return section


def format_news_for_html(news_data: dict[str, Any], max_items: int = 5) -> str:
    """
    Format news data for HTML report display.
    
    Returns HTML snippet for the news section.
    """
    if not news_data or not news_data.get("news"):
        return """
        <div class="section">
            <div class="section-title">📰 Recent News</div>
            <p style="color: var(--text-muted);">No recent news available for this stock.</p>
        </div>
        """
    
    news_items = news_data["news"][:max_items]
    
    html = """
        <div class="section">
            <div class="section-title">📰 Recent News</div>
            <div class="news-list">
    """
    
    for item in news_items:
        title = item.get("title", "No title")
        date = item.get("date", "")
        source = item.get("source", "")
        url = item.get("url", "")
        summary = item.get("summary", "")[:150]
        
        html += f"""
                <div class="news-item" style="margin-bottom: 15px; padding: 15px; background: var(--bg-tertiary); border-radius: 10px;">
                    <div style="font-weight: 600; margin-bottom: 5px;">
                        {'<a href="' + url + '" target="_blank" style="color: var(--blue); text-decoration: none;">' if url else ''}{title}{'</a>' if url else ''}
                    </div>
                    <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 8px;">
                        📅 {date} | 📰 {source}
                    </div>
                    {f'<div style="font-size: 0.85rem; color: var(--text-secondary);">{summary}{"..." if len(summary) >= 150 else ""}</div>' if summary else ''}
                </div>
        """
    
    html += """
            </div>
        </div>
    """
    
    return html


def clear_cache() -> int:
    """Clear all news cache files. Returns count of files deleted."""
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
