# Be Richer - Bursa Malaysia Stock Screener

Automated stock screener for Bursa Malaysia (and Southeast Asia) equities.

---

## What It Does

**Level 1** is the automated screening layer. It fetches price history and fundamental data via
`yfinance`, scores every stock against a two-part framework, and classifies each into one of four groups:

| Group | Meaning |
|---|---|
| 🟢 READY TO BUY | Fundamental ≥ 50/60 AND Technical ≥ 14/20 |
| 🟡 EARLY RE-RATING | Fundamental ≥ 50/60 AND Technical 9–13/20 |
| 🔵 WATCHLIST | Fundamental 40–49/60 |
| 🔴 REJECT | Fundamental < 40/60 or hard-reject flag triggered |

Results are printed as a rich terminal table and exported to `results/bursa_screen_<timestamp>.csv`.

---

## Scoring Framework

### Fundamental Score — 60 pts

| Factor | Max |
|---|---|
| A. Earnings Quality | 15 |
| B. ROE / ROIC | 10 |
| C. Financial Health (gearing) | 10 |
| D. Valuation Margin of Safety (PE + PB vs sector) | 15 |
| E. Operating Cash Flow yield | 5 |
| F. Dividends / Capital Returns | 5 |

### Technical Score — 20 pts

| Factor | Max |
|---|---|
| 20-day Moving Average | 3 |
| 50-day Moving Average | 3 |
| 200-day Moving Average | 3 |
| RSI (14-period) | 2 |
| MACD | 2 |
| Volume vs 30D ADV | 3 |
| Breakout / Base Formation | 2 |
| Support / Resistance | 2 |

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

# Or using Python module
python -m bursa_screener
python -m bursa_screener --tier broad
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

## Command Line Options

```bash
# Universe tiers
be-richer --tier klci    # KLCI 30 (~30 tickers, fastest)
be-richer --tier broad   # KLCI 30 + mid-cap (~45 tickers)
be-richer --tier full    # All tiers including SEA regional

# Custom tickers
be-richer --tickers 1155.KL 5347.KL 1023.KL

# Output options
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

## Data Source & Limitations

| Item | Detail |
|---|---|
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
│       ├── __init__.py      # Package entry point
│       ├── __main__.py      # Allow python -m bursa_screener
│       ├── screener.py      # CLI entry point
│       ├── universe.py      # Stock universe (KLCI, mid-cap, SEA)
│       ├── data_fetcher.py  # yfinance wrapper + caching
│       ├── technicals.py    # 20-point technical scorer
│       ├── fundamentals.py  # 60-point fundamental scorer
│       ├── ranker.py        # Classification + sorting
│       ├── reporter.py      # Rich terminal output + CSV
│       └── config/          # Sector PE benchmarks
├── results/                 # CSV exports (auto-created)
├── pyproject.toml           # Project configuration
├── requirements.txt         # Dependencies
├── run.sh                   # Shell shortcuts
└── README.md               # This file
```

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

## CSV Export

Every run saves a timestamped CSV to `results/`:

```
results/bursa_screen_20261125_0930.csv
```

Columns: `ticker, name, price, fundamental, technical, catalyst, total,
pe_ttm, pb, roe, net_gearing, div_yield, adv_30d, week_return, month_return,
rsi, vol_ratio, tech_status, classification`

---

## Roadmap

| Level | Status | Description |
|---|---|---|
| Level 1 | ✅ Done | Automated screener — technicals + fundamentals |
| Level 2 | 🔜 Planned | LLM deep analysis — catalyst scoring, Core EPS normalization |
| Level 3 | 🔜 Planned | Weekly scheduler, Telegram/email alerts, portfolio tracker |

---

## License

MIT License - see LICENSE file for details.
