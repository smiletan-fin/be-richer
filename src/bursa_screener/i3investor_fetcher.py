"""
i3investor Fetcher - Malaysian Stock News & Sentiment from i3investor.com

Fetches:
- News & blog articles
- Price targets from analysts
- Forum discussion activity (Hot Stocks score)

No API key required - uses public web scraping.
"""

import logging
import re
import ssl
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# User agent to identify our requests
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
_BASE_URL = "https://klse.i3investor.com"
_TIMEOUT = 20.0

# Create SSL context that doesn't verify certificates (i3investor has SSL issues)
_SSL_CONTEXT = ssl.create_default_context()
_SSL_CONTEXT.check_hostname = False
_SSL_CONTEXT.verify_mode = ssl.CERT_NONE

# Try to use requests if available (better for JS-heavy sites)
try:
    import requests
    from urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


@dataclass
class I3Article:
    """An article/blog post from i3investor."""
    date: str
    title: str
    source: str
    url: str
    article_type: str  # 'blog', 'news', 'price_target'


@dataclass
class I3PriceTarget:
    """Analyst price target from i3investor."""
    date: str
    source: str  # e.g., 'RHB-OSK', 'TA', 'HLG'
    call: str    # 'BUY', 'HOLD', 'SELL'
    target_price: float
    title: str
    url: str


@dataclass
class I3Sentiment:
    """Aggregated sentiment data from i3investor."""
    ticker: str
    stock_name: str
    news_count: int
    articles: list[I3Article]
    price_targets: list[I3PriceTarget]
    hot_score: Optional[int]  # Trending score from "Hot Stocks Today"
    latest_news_date: Optional[str]
    
    # Derived sentiment
    buy_calls: int = 0
    hold_calls: int = 0
    sell_calls: int = 0
    avg_target_price: Optional[float] = None


def _extract_stock_code(ticker: str) -> str:
    """Extract stock code from ticker (e.g., '1155.KL' -> '1155')."""
    return ticker.replace('.KL', '').strip()


def _fetch_page(url: str) -> Optional[str]:
    """Fetch a page with retry logic."""
    
    # Try requests first if available
    if _HAS_REQUESTS:
        for attempt in range(3):
            try:
                resp = requests.get(url, headers={"User-Agent": _UA}, timeout=_TIMEOUT, verify=False)
                resp.raise_for_status()
                return resp.text
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    wait = min(60, 10 * (attempt + 1))
                    logger.warning(f"i3investor rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    continue
                elif e.response.status_code == 404:
                    logger.warning(f"i3investor page not found: {url}")
                    return None
                else:
                    logger.warning(f"i3investor HTTP error: {e}")
                    return None
            except requests.exceptions.RequestException as e:
                logger.warning(f"i3investor fetch error: {e}")
                if attempt < 2:
                    time.sleep(2)
                    continue
                return None
        return None
    
    # Fallback to urllib
    req = Request(url, headers={"User-Agent": _UA})
    
    for attempt in range(3):
        try:
            with urlopen(req, timeout=_TIMEOUT, context=_SSL_CONTEXT) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except HTTPError as e:
            if e.code == 429:  # Rate limited
                wait = min(60, 10 * (attempt + 1))
                logger.warning(f"i3investor rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            elif e.code == 404:
                logger.warning(f"i3investor page not found: {url}")
                return None
            else:
                logger.warning(f"i3investor HTTP error {e.code}: {url}")
                return None
        except (URLError, TimeoutError) as e:
            logger.warning(f"i3investor fetch error: {e}")
            if attempt < 2:
                time.sleep(2)
                continue
            return None
    
    return None


def _parse_news_blogs(html: str, stock_code: str) -> list[I3Article]:
    """Parse news and blog articles from the news-blogs page."""
    import html as html_module
    
    articles = []
    
    # i3investor uses multiple patterns for articles
    # Pattern 1: Date followed by linked title
    # <a href="/web/blog/detail/...">Title</a>
    
    # Find all blog/news links with their dates
    # The HTML has patterns like:
    # 2026-11-26
    # <a href="...">Title</a>
    
    # Pattern for dates
    date_pattern = r'(\d{4}-\d{2}-\d{2})'
    dates = re.findall(date_pattern, html)
    
    # Pattern for article links
    link_pattern = r'<a[^>]*href="(/web/blog/detail/[^"]+)"[^>]*>([^<]+)</a>'
    links = re.findall(link_pattern, html)
    
    # Also try markdown-style links from rendered content
    md_pattern = r'\[([^\]]+)\]\((/web/blog/detail/[^)]+)\)'
    md_links = re.findall(md_pattern, html)
    
    # Combine both patterns
    all_links = [(url, title) for url, title in links] + [(url, title) for title, url in md_links]
    
    # Match dates with links (they appear in sequence)
    seen_titles = set()
    date_idx = 0
    
    for url, title in all_links:
        # Decode HTML entities
        title = html_module.unescape(title).strip()
        
        # Skip duplicates and generic content
        if title in seen_titles or len(title) < 10:
            continue
        
        title_lower = title.lower()
        
        # Skip market pulse and daily commentary (too generic)
        if any(skip in title_lower for skip in [
            'market pulse', 'daily newswatch', 'market commentary', 
            'daily brief', 'market updates', 'morning brief'
        ]):
            continue
        
        seen_titles.add(title)
        
        # Try to get the date
        date = dates[date_idx] if date_idx < len(dates) else datetime.now().strftime('%Y-%m-%d')
        date_idx += 1
        
        # Determine article type
        if 'price target' in title_lower or 'tp:' in title_lower or 'rm' in title_lower and ('buy' in title_lower or 'hold' in title_lower or 'sell' in title_lower):
            article_type = 'price_target'
        elif 'blog' in url:
            article_type = 'blog'
        else:
            article_type = 'news'
        
        # Extract source from URL path
        source = 'i3investor'
        url_parts = url.split('/')
        if len(url_parts) > 4:
            source = url_parts[4]  # e.g., 'ceomorningbrief', 'taresearch'
        
        full_url = f"{_BASE_URL}{url}" if not url.startswith('http') else url
        
        articles.append(I3Article(
            date=date,
            title=title,
            source=source,
            url=full_url,
            article_type=article_type
        ))
    
    return articles[:20]  # Limit to 20 most recent


def _parse_price_targets(html: str, stock_code: str) -> list[I3PriceTarget]:
    """Parse price targets from the price-target page or news content."""
    targets = []
    seen = set()
    
    # Pattern 1: "Source : RHB-OSK, Price Call : BUY, Price Target : 11.50"
    pattern1 = r'Source\s*:\s*([^,]+),\s*Price Call\s*:\s*(\w+),\s*Price Target\s*:\s*([\d.]+)'
    matches1 = re.findall(pattern1, html)
    
    for source, call, target in matches1:
        key = (source.strip(), call.upper(), target)
        if key not in seen:
            seen.add(key)
            try:
                targets.append(I3PriceTarget(
                    date=datetime.now().strftime('%Y-%m-%d'),
                    source=source.strip(),
                    call=call.upper().strip(),
                    target_price=float(target),
                    title=f"{source.strip()} - {call.upper()} RM{target}",
                    url=f"{_BASE_URL}/web/stock/analysis-price-target/{stock_code}"
                ))
            except (ValueError, IndexError):
                continue
    
    # Pattern 2: From article titles like "MAYBANK (HOLD) - Dividends..." or "MAYBANK (BUY; TP: RM11.10)"
    pattern2 = r'\((?:Price Call\s*:\s*)?(\w+)(?:\s*[;,]\s*TP\s*:\s*RM?([\d.]+))?\)'
    for match in re.finditer(pattern2, html, re.IGNORECASE):
        call = match.group(1).upper()
        if call in ('BUY', 'HOLD', 'SELL', 'NEUTRAL'):
            target_price = float(match.group(2)) if match.group(2) else None
            if target_price:
                key = ('unknown', call, str(target_price))
                if key not in seen:
                    seen.add(key)
                    targets.append(I3PriceTarget(
                        date=datetime.now().strftime('%Y-%m-%d'),
                        source='i3investor',
                        call=call,
                        target_price=target_price,
                        title=f"{call} @ RM{target_price}",
                        url=f"{_BASE_URL}/web/stock/analysis-price-target/{stock_code}"
                    ))
    
    # Pattern 3: "BUY @ RM11.50" or "TP: RM11.50"
    pattern3 = r'(BUY|HOLD|SELL|NEUTRAL)\s*[@:]\s*RM?\s*([\d.]+)'
    for match in re.finditer(pattern3, html, re.IGNORECASE):
        call = match.group(1).upper()
        target_price = float(match.group(2))
        key = ('pattern3', call, str(target_price))
        if key not in seen:
            seen.add(key)
            targets.append(I3PriceTarget(
                date=datetime.now().strftime('%Y-%m-%d'),
                source='i3investor',
                call=call,
                target_price=target_price,
                title=f"{call} @ RM{target_price}",
                url=f"{_BASE_URL}/web/stock/analysis-price-target/{stock_code}"
            ))
    
    return targets


def _parse_hot_score(html: str, stock_code: str) -> Optional[int]:
    """Extract hot stock score if the stock is trending."""
    # Look for the stock in "Hot Stocks Today" section
    # Pattern: MAYBANK 358 (stock name followed by score)
    
    # First find if our stock code is mentioned
    pattern = rf'\[?{stock_code}\]?\s*(\d+)'
    match = re.search(pattern, html, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    
    return None


def fetch_i3investor_sentiment(ticker: str) -> Optional[I3Sentiment]:
    """
    Fetch sentiment data from i3investor for a Malaysian stock.
    
    Args:
        ticker: Stock ticker (e.g., '1155.KL' or '1155')
    
    Returns:
        I3Sentiment object with news, price targets, and sentiment analysis
    """
    stock_code = _extract_stock_code(ticker)
    
    # Fetch news/blogs page
    news_url = f"{_BASE_URL}/web/stock/news-blogs/{stock_code}"
    news_html = _fetch_page(news_url)
    
    if not news_html:
        logger.warning(f"Could not fetch i3investor data for {ticker}")
        return None
    
    # Parse articles
    articles = _parse_news_blogs(news_html, stock_code)
    
    # Initialize price targets
    price_targets = []
    
    # Fetch price target page separately for better data
    pt_url = f"{_BASE_URL}/web/stock/analysis-price-target/{stock_code}"
    pt_html = _fetch_page(pt_url)
    if pt_html:
        price_targets = _parse_price_targets(pt_html, stock_code)
    
    # Also try to get price targets from news if none found
    if not price_targets:
        price_targets = _parse_price_targets(news_html, stock_code)
    
    # Get hot score from overview page
    overview_url = f"{_BASE_URL}/web/stock/overview/{stock_code}"
    overview_html = _fetch_page(overview_url)
    
    hot_score = None
    stock_name = ticker
    
    if overview_html:
        hot_score = _parse_hot_score(overview_html, stock_code)
        
        # Try to extract stock name
        name_match = re.search(r'##### ([A-Z][A-Z\s]+(?:BHD|BERHAD)?)', overview_html)
        if name_match:
            stock_name = name_match.group(1).strip()
        
        # Also try price targets from overview
        if not price_targets:
            price_targets = _parse_price_targets(overview_html, stock_code)
    
    # Calculate sentiment metrics
    buy_calls = sum(1 for pt in price_targets if pt.call == 'BUY')
    hold_calls = sum(1 for pt in price_targets if pt.call in ('HOLD', 'NEUTRAL'))
    sell_calls = sum(1 for pt in price_targets if pt.call == 'SELL')
    
    avg_target = None
    if price_targets:
        avg_target = sum(pt.target_price for pt in price_targets) / len(price_targets)
    
    latest_date = articles[0].date if articles else None
    
    return I3Sentiment(
        ticker=ticker,
        stock_name=stock_name,
        news_count=len(articles),
        articles=articles,
        price_targets=price_targets,
        hot_score=hot_score,
        latest_news_date=latest_date,
        buy_calls=buy_calls,
        hold_calls=hold_calls,
        sell_calls=sell_calls,
        avg_target_price=avg_target
    )


def format_i3_for_prompt(sentiment: I3Sentiment, limit: int = 10) -> str:
    """
    Format i3investor sentiment data for inclusion in AI prompts.
    
    Args:
        sentiment: I3Sentiment object
        limit: Maximum number of articles to include
    
    Returns:
        Formatted string for prompt injection
    """
    if not sentiment:
        return ""
    
    lines = [f"## i3investor Sentiment for {sentiment.ticker} ({sentiment.stock_name})"]
    lines.append("")
    
    # Summary metrics
    lines.append("### Sentiment Summary")
    if sentiment.hot_score:
        lines.append(f"- **Hot Stock Score:** {sentiment.hot_score} (trending on i3investor)")
    
    if sentiment.price_targets:
        lines.append(f"- **Analyst Calls:** {sentiment.buy_calls} BUY, {sentiment.hold_calls} HOLD, {sentiment.sell_calls} SELL")
        if sentiment.avg_target_price:
            lines.append(f"- **Average Target Price:** RM {sentiment.avg_target_price:.2f}")
    
    lines.append(f"- **Recent News Count:** {sentiment.news_count} articles")
    if sentiment.latest_news_date:
        lines.append(f"- **Latest News:** {sentiment.latest_news_date}")
    lines.append("")
    
    # Price targets
    if sentiment.price_targets:
        lines.append("### Recent Analyst Price Targets")
        for pt in sentiment.price_targets[:5]:
            lines.append(f"- **{pt.source}**: {pt.call} @ RM {pt.target_price:.2f}")
        lines.append("")
    
    # Recent news
    if sentiment.articles:
        lines.append("### Recent News & Analysis")
        for article in sentiment.articles[:limit]:
            # Skip generic market updates
            lines.append(f"- [{article.date}] {article.title}")
        lines.append("")
    
    return "\n".join(lines)


def get_i3_sentiment_score(sentiment: I3Sentiment) -> dict:
    """
    Calculate a sentiment score from i3investor data.
    
    Returns:
        Dict with 'score' (0-10), 'signal' (BULLISH/NEUTRAL/BEARISH), and 'details'
    """
    if not sentiment:
        return {'score': 5, 'signal': 'NEUTRAL', 'details': 'No i3investor data available'}
    
    score = 5.0  # Start neutral
    details = []
    
    # Factor 1: Analyst calls (+/- 2 points)
    if sentiment.price_targets:
        total_calls = sentiment.buy_calls + sentiment.hold_calls + sentiment.sell_calls
        if total_calls > 0:
            buy_ratio = sentiment.buy_calls / total_calls
            sell_ratio = sentiment.sell_calls / total_calls
            
            if buy_ratio >= 0.7:
                score += 2
                details.append(f"Strong buy consensus ({sentiment.buy_calls}/{total_calls})")
            elif buy_ratio >= 0.5:
                score += 1
                details.append(f"Majority buy calls ({sentiment.buy_calls}/{total_calls})")
            elif sell_ratio >= 0.5:
                score -= 1.5
                details.append(f"Majority sell/hold calls")
    
    # Factor 2: Hot stock score (+/- 1 point)
    if sentiment.hot_score:
        if sentiment.hot_score >= 500:
            score += 1
            details.append(f"High trending score ({sentiment.hot_score})")
        elif sentiment.hot_score >= 300:
            score += 0.5
            details.append(f"Moderate trending ({sentiment.hot_score})")
    
    # Factor 3: News activity (+/- 1 point)
    if sentiment.news_count >= 10:
        score += 0.5
        details.append(f"High news activity ({sentiment.news_count} articles)")
    elif sentiment.news_count <= 2:
        score -= 0.5
        details.append(f"Low news coverage ({sentiment.news_count} articles)")
    
    # Clamp score
    score = max(0, min(10, score))
    
    # Determine signal
    if score >= 7:
        signal = 'BULLISH'
    elif score <= 3:
        signal = 'BEARISH'
    else:
        signal = 'NEUTRAL'
    
    return {
        'score': round(score, 1),
        'signal': signal,
        'details': '; '.join(details) if details else 'No significant signals'
    }


# Simple test
if __name__ == "__main__":
    import sys
    
    ticker = sys.argv[1] if len(sys.argv) > 1 else "1155.KL"
    print(f"\nFetching i3investor data for {ticker}...")
    
    sentiment = fetch_i3investor_sentiment(ticker)
    
    if sentiment:
        print(f"\nStock: {sentiment.stock_name}")
        print(f"News Count: {sentiment.news_count}")
        print(f"Hot Score: {sentiment.hot_score}")
        print(f"Price Targets: {len(sentiment.price_targets)}")
        print(f"  BUY: {sentiment.buy_calls}, HOLD: {sentiment.hold_calls}, SELL: {sentiment.sell_calls}")
        if sentiment.avg_target_price:
            print(f"  Avg Target: RM {sentiment.avg_target_price:.2f}")
        
        print("\n" + "="*50)
        print(format_i3_for_prompt(sentiment))
        
        print("\n" + "="*50)
        score_data = get_i3_sentiment_score(sentiment)
        print(f"Sentiment Score: {score_data['score']}/10 ({score_data['signal']})")
        print(f"Details: {score_data['details']}")
    else:
        print("Failed to fetch data")
