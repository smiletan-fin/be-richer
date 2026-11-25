# Be Richer - Bursa Malaysia Stock Screener

Automated stock screener for Bursa Malaysia (and Southeast Asia) equities using industry-standard scoring methodologies.

---

## What It Does

**Level 1** is the automated screening layer. It fetches price history and fundamental data via
`yfinance`, scores every stock against an industry-aligned 90-point framework, and classifies each into one of four groups:

| Group | Criteria | Meaning |
|-------|----------|---------|
| 🟢 READY TO BUY | Fund ≥ 52/65 AND Tech ≥ 18/25 | Strong fundamentals + confirmed uptrend |
| 🟡 EARLY RE-RATING | Fund ≥ 52/65 AND Tech 12-17/25 | Strong fundamentals, momentum building |
| 🔵 WATCHLIST | Fund 40-51/65 | Decent fundamentals, monitor for upgrades |
| 🔴 REJECT | Fund < 40/65 or red flags | Weak fundamentals or warning signs |

Results are printed as a rich terminal table and exported to both CSV and HTML reports.

---

## Scoring Framework

The scoring system is aligned with proven methodologies: **CAN SLIM**, **Piotroski F-Score**, and **Minervini SEPA**.

### Fundamental Score — 65 pts

| Factor | Max | Description |
|--------|-----|-------------|
| Earnings Quality | 10 | PE reasonableness + OCF conversion |
| **Earnings Growth** | 10 | YoY EPS growth (CAN SLIM: >25% is excellent) |
| ROE / ROIC | 10 | Return on equity tiers |
| Financial Health | 10 | Gearing/debt levels |
| Valuation | 12 | PE vs sector benchmark + P/B |
| Operating Cash Flow | 5 | OCF yield |
| Dividends | 3 | Reduced weight (growth stocks don't pay) |
| **Improving Fundamentals** | 5 | Piotroski-style momentum checks |

### Technical Score — 25 pts

| Factor | Max | Description |
|--------|-----|-------------|
| 20-day Moving Average | 3 | Price vs MA20 + trend |
| 50-day Moving Average | 3 | Price vs MA50 + stacking |
| 200-day Moving Average | 3 | Long-term trend |
| RSI (14-period) | 2 | Momentum indicator |
| MACD | 2 | Trend direction |
| Volume | 3 | Volume patterns on price moves |
| Breakout / Base | 2 | Near highs detection |
| Support / Resistance | 2 | Support level holding |
| **Relative Strength** | 3 | Stock vs KLCI index performance |
| **52-Week Position** | 2 | Minervini template alignment |

---

## Quick Start

### Installation

```bash
# Clone the repository
cd /path/to/be-richer

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install as editable package (recommended)
pip install -e .
```

### Usage

```bash
# Using CLI entry point (after pip install -e .)
be-richer
be-richer --tier broad
be-richer --tickers 1155.KL 5347.KL 4715.KL

# Generate HTML report (recommended)
be-richer --tier klci --html

# Or using Python module
python -m bursa_screener
python -m bursa_screener --tier klci --html
```

### Shell Script Shortcuts

```bash
# Make executable
chmod +x run.sh

# Run with shortcuts
./run.sh klci          # KLCI 30 only
./run.sh broad         # KLCI + mid-cap
./run.sh custom 1155.KL 5347.KL  # Custom tickers
./run.sh banks         # Banking stocks preset
./run.sh test          # Quick smoke test
```

---

## GitHub Actions (Automated Runs)

Run the screener directly from GitHub without setting up locally:

1. Go to **Actions** tab in your repository
2. Select **"KLCI Stock Screener"** workflow
3. Click **"Run workflow"**
4. Choose tier (klci/broad/full) and options
5. Download HTML report from **Artifacts** when complete

The workflow uses dependency caching to minimize run time (~30 seconds for KLCI tier).

---

## Command Line Options

```bash
# Universe tiers
be-richer --tier klci    # KLCI 30 (~30 tickers, fastest)
be-richer --tier broad   # KLCI 30 + mid-cap (~45 tickers)
be-richer --tier full    # All tiers including SEA regional

# Custom tickers
be-richer --tickers 1155.KL 5347.KL 1023.KL

# Output options
be-richer --html             # Generate interactive HTML report
be-richer --show-rejected    # Include REJECT stocks in output
be-richer --no-export        # Skip CSV export

# Cache management
be-richer --check            # Check Yahoo Finance connectivity
be-richer --cache-stats      # Show cache statistics
be-richer --clear-cache      # Clear all cached data
be-richer --no-cache         # Bypass cache (not recommended)
be-richer --refresh-universe # Force refresh KLCI constituents
```

---

## HTML Report Features

The `--html` flag generates a beautiful, self-contained HTML report with:

- 📊 **Summary cards** showing classification counts
- 📋 **Interactive sortable table** with all metrics
- 📚 **Strategy explainer** — collapsible section explaining the scoring methodology
- 🌙 **Dark theme** — easy on the eyes
- 📱 **Mobile responsive** — works on any device
- 🔍 **New metrics displayed**: EPS Growth, RS Ratio, 52-Week Position

---

## Data Source & Limitations

| Item | Detail |
|------|--------|
| Price data | `yfinance` — 15-min delayed |
| Fundamentals | Yahoo Finance scraped data — may lag filings by a few days |
| Forward PE / analyst estimates | Sparse for small-cap Bursa names |
| OCF for banks | yfinance OCF is unreliable for Financial Services; scored on net income proxy |

### ⚠️ Yahoo Finance Rate Limiting

Yahoo Finance aggressively rate-limits free API access. The screener includes caching (4-24 hours) to minimize API calls.

**If you see "No data" errors:**
1. Wait 15-30 minutes (rate limits reset)
2. Use cached data (automatic)
3. Try a different network/IP

---

## Project Structure

```
be-richer/
├── src/
│   └── bursa_screener/
│       ├── __init__.py       # Package entry point
│       ├── __main__.py       # Allow python -m bursa_screener
│       ├── screener.py       # CLI entry point
│       ├── universe.py       # Stock universe (KLCI, mid-cap, SEA)
│       ├── data_fetcher.py   # yfinance wrapper + caching
│       ├── technicals.py     # 25-point technical scorer
│       ├── fundamentals.py   # 65-point fundamental scorer
│       ├── ranker.py         # Classification + sorting
│       ├── reporter.py       # Rich terminal output + CSV
│       ├── html_reporter.py  # HTML report generator
│       └── config/           # Sector PE benchmarks
├── .github/
│   └── workflows/
│       └── klci-scan.yml     # GitHub Actions workflow
├── results/                  # CSV/HTML exports (auto-created)
├── pyproject.toml            # Project configuration
├── requirements.txt          # Dependencies
├── run.sh                    # Shell shortcuts
└── README.md                 # This file
```

---

## Output Files

Every run saves timestamped files to `results/`:

```
results/bursa_screen_20261125_0930.csv
results/bursa_screen_20261125_0930.html
```

**CSV columns**: `ticker, name, price, fundamental, technical, catalyst, total,
pe_ttm, pb, roe, net_gearing, div_yield, earnings_growth, rs_ratio, adv_30d, 
week_return, month_return, rsi, vol_ratio, 52wk_position, tech_status, classification`

---

## Adding Tickers

Edit `src/bursa_screener/universe.py` and add tickers to the appropriate list.
Yahoo Finance uses the `.KL` suffix for all Bursa Malaysia stocks.

```python
# Example — add to MID_CAP list
MID_CAP = [
    "5076.KL",   # OSK Holdings
    "5200.KL",   # UOA Development
    "1234.KL",   # Your new ticker
    ...
]
```

---

## Roadmap

| Level | Status | Description |
|-------|--------|-------------|
| Level 1 | ✅ Done | Automated screener — technicals + fundamentals (90-point system) |
| Level 1.5 | ✅ Done | HTML reports, GitHub Actions, industry-aligned scoring |
| Level 2 | 🔜 Planned | LLM deep analysis — catalyst scoring, Core EPS normalization |
| Level 3 | 🔜 Planned | Weekly scheduler, Telegram/email alerts, portfolio tracker |

---

## License

MIT License - see LICENSE file for details.
