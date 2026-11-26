# Be Richer - Bursa Malaysia Stock Screener

Automated stock screener for Bursa Malaysia (and Southeast Asia) equities using industry-standard scoring methodologies.

---

## What It Does

**Level 1** is the automated screening layer. It fetches price history and fundamental data via
`yfinance` (enhanced by **KLSE Screener** for Malaysian stocks), scores every stock against an industry-aligned **90-109 point framework**, and classifies each into one of four groups:

| Group | Criteria | Meaning |
|-------|----------|---------|
| 🟢 READY TO BUY | Fund ≥ 52 AND Tech ≥ 18/25 | Strong fundamentals + confirmed uptrend |
| 🟡 EARLY RE-RATING | Fund ≥ 52 AND Tech 12-17/25 | Strong fundamentals, momentum building |
| 🔵 WATCHLIST | Fund 40-51 | Decent fundamentals, monitor for upgrades |
| 🔴 REJECT | Fund < 40 or red flags | Weak fundamentals or warning signs |

Results are printed as a rich terminal table and exported to both CSV and HTML reports.

---

## Scoring Framework

The scoring system is aligned with proven methodologies: **CAN SLIM**, **Piotroski F-Score**, and **Minervini SEPA**.

### Fundamental Score — 65-84 pts (depending on data sources)

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

#### Analyst Target Prices (most stocks)

| Factor | Max | Description |
|--------|-----|-------------|
| **Analyst Target** | 5 | Upside potential to mean target price + consensus rating |

#### KLSE Screener Enhanced (Malaysian stocks only)

| Factor | Max | Description |
|--------|-----|-------------|
| **Earnings Momentum** | 5 | QoQ/YoY growth from quarterly data |
| **Earnings Consistency** | 3 | Consecutive growth quarters |
| **Institutional Flow** | 3 | EPF/KWAP/PNB buying signals |
| **Insider Trading** | 3 | Director buying/selling signals |

#### FMP Enhanced (US stocks only)

| Factor | Max | Description |
|--------|-----|-------------|
| **Earnings Surprises** | 5 | Beat/miss streak (US stocks only) |

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

# Sector filter (NEW!)
be-richer --sector banking --html
be-richer --sector technology --html
be-richer --list-sectors           # Show available sectors

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

Run the screener directly from GitHub without setting up locally.

### Available Workflows

| Workflow | Trigger | Description |
|----------|---------|-------------|
| **Sector Stock Screener** | Manual + Saturday 8am MYT | Scan by sector (banking, technology, etc.) |
| **Position Analyzer** | Manual | Analyze your stock position (hold/take profit/cut loss) |

### KLCI Screener Workflow

1. Go to **Actions** tab in your repository
2. Select **"Sector Stock Screener"** workflow
3. Click **"Run workflow"**
4. Choose sector and tier options
5. Download HTML report from **Artifacts** when complete

### Sector Screener Workflow (NEW!)

Scan individual sectors or all sectors in parallel:

1. Go to **Actions** tab → **"Sector Stock Screener"**
2. Click **"Run workflow"**
3. Select sector from dropdown:
   - `banking`, `technology`, `plantation`, `property`
   - `healthcare`, `consumer`, `industrials`, `energy`, `reit`
   - `construction`, `utilities`, `telecommunications`, `transportation`
   - `all-sectors` — runs ALL sectors in parallel (9 jobs)
4. Download reports from **Artifacts**

**Scheduled Runs:**
- Every **Saturday at 8:00 AM Malaysia Time** — all sectors scanned automatically
- Reports available for 30 days in Artifacts

**Example Use Cases:**
- Quick morning check: Run `banking` sector only (~15 seconds)
- Weekend analysis: Run `all-sectors` to scan entire market (~2-3 minutes)
- Sector rotation: Compare `technology` vs `consumer` performance

The workflows use dependency caching to minimize run time (~30 seconds per sector).

### Position Analyzer Workflow (NEW!)

Analyze your existing stock positions directly from GitHub:

1. Go to **Actions** tab → **"Position Analyzer"**
2. Click **"Run workflow"**
3. Enter your position details:
   - **Ticker**: Stock code (e.g., `1155.KL` for Maybank)
   - **Entry Price**: Your buy price (e.g., `9.50`)
   - **Shares**: Number of shares held (default: 1000)
4. Download reports from **Artifacts**

**What you get:**
- 📊 **HTML Report** — Full analysis with embedded AI prompt
- 🤖 **AI Prompt** — Ready to paste into ChatGPT/Claude
- 📄 **JSON Data** — Raw data for programmatic use

**Example Use Cases:**
- Check if it's time to take profit on a winning position
- Decide whether to cut loss on an underwater position
- Get AI-powered analysis with market context

---

## Position Analyzer (NEW!)

Analyze your existing stock positions to determine whether to hold, take profit, or cut loss.

### Features

- **P&L Calculation**: Track profit/loss per share, percentage, and total value
- **Trend Analysis**: Identify if the stock is in uptrend, downtrend, or sideways movement
- **Support/Resistance Levels**: Key price levels for decision making
- **Action Recommendation**: HOLD, TAKE PROFIT, CUT LOSS, ADD MORE, or PARTIAL PROFIT
- **AI-Ready Prompt**: Comprehensive prompt for deeper LLM analysis

### Usage

```bash
# Basic position analysis
be-richer --position 1155.KL --entry 9.50

# With custom share count
be-richer --position 1155.KL --entry 9.50 --shares 1000

# Analyze a losing position
be-richer --position 5347.KL --entry 25.00 --shares 500
```

### Output

The position analyzer generates:

1. **Console Output**: Quick summary with P&L, trend analysis, scores, and recommendation
2. **HTML Report**: Beautiful, self-contained report with all analysis details
3. **AI Prompt**: Ready-to-use prompt for ChatGPT/Claude for deeper analysis
4. **JSON Data**: Raw data for programmatic access

### Recommendation Logic

| Condition | Recommendation |
|-----------|----------------|
| Profit ≥20% + Strong technicals | **TAKE PROFIT** (consider partial) |
| Profit ≥20% + Weak trend | **TAKE PROFIT** (lock gains before reversal) |
| Profit 10-20% + Strong uptrend | **PARTIAL PROFIT** (take some, let rest run) |
| Profit <10% + Uptrend | **HOLD** (momentum building) |
| Loss <5% + Uptrend | **HOLD** (normal volatility) |
| Loss 5-15% + Weak/Down trend | **CUT LOSS** (preserve capital) |
| Loss >15% | **CUT LOSS** (significant deterioration) |
| Small profit + Sideways | **HOLD** (wait for clearer direction) |
| Any profit + Strong scores | **ADD MORE** (averaging up opportunity) |

### Sample Output

```
╭────────────────────────── 📊 Position Analysis ──────────────────────────╮
│ 1155.KL - Malayan Banking Berhad                                         │
╰──────────────────────────────────────────────────────────────────────────╯
           💰 Position P&L           
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
┃ Metric          ┃           Value ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
│ Entry Price     │       RM 9.5000 │
│ Current Price   │      RM 10.1600 │
│ P&L %           │          +6.95% │
│ Total P&L       │      RM +660.00 │
│ Status          │    SMALL PROFIT │
└─────────────────┴─────────────────┘
╭───────────────────────── 🎯 Recommendation ──────────────────────────────╮
│ HOLD - Wait for clearer direction                                        │
╰──────────────────────────────────────────────────────────────────────────╯
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

# Sector filter (NEW!)
be-richer --sector banking           # Banking stocks only
be-richer --sector technology        # Tech stocks
be-richer --sector plantation        # Plantation stocks
be-richer --list-sectors             # Show all available sectors

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

# Position Analyzer (NEW!)
be-richer --position 1155.KL --entry 9.50           # Analyze position
be-richer --position 1155.KL --entry 9.50 --shares 500  # Custom shares

# FMP (US stocks only - disabled by default)
be-richer --tickers AAPL MSFT --fmp --html   # Enable FMP for US stocks
```

---

## Data Sources

### Primary: Yahoo Finance + yfinance
- Price history, moving averages, RSI, MACD
- Basic fundamentals (PE, PB, ROE, etc.)
- Analyst target prices and recommendations
- 15-minute delayed data

### Enhanced: KLSE Screener (Malaysian stocks)

> **🟢 KLSE Screener is automatically enabled for Malaysian stocks (.KL tickers)**

KLSE Screener provides enhanced data specifically for Malaysian stocks:

| Data Type | Description |
|-----------|-------------|
| **Quarterly Financials** | QoQ and YoY growth rates from actual quarterly reports |
| **Shareholding Changes** | Tracks EPF, KWAP, PNB, and other institutional buying/selling |
| **Insider Dealings** | Director buying/selling transactions |
| **More Accurate Fundamentals** | PE, ROE, EPS often more reliable than yfinance |

**Benefits for Malaysian Stock Scoring (+14 pts maximum):**
- **Earnings Momentum** (+5 pts): Strong QoQ/YoY growth = higher score
- **Earnings Consistency** (+3 pts): Multiple consecutive growth quarters = stability signal
- **Institutional Flow** (+3 pts): EPF/KWAP/PNB buying = smart money following
- **Insider Trading** (+3 pts): Directors buying = bullish signal; selling = warning

**Package:** `klse-screener-py` (automatically installed with requirements.txt)

### Analyst Target Prices (via yfinance)

> **🟢 Analyst data is automatically included for stocks with analyst coverage**

Analyst consensus data from yfinance includes:
- **Target Mean/Median Price**: Average analyst price target
- **Target High/Low**: Range of analyst targets
- **Number of Analysts**: Coverage breadth
- **Recommendation**: Strong Buy / Buy / Hold / Sell

**Benefits (+5 pts maximum):**
- **20%+ upside to target**: 4-5 pts
- **10-20% upside**: 3 pts
- **5-10% upside**: 2 pts
- **Below target**: 0-1 pts (warning flag if significantly overvalued)

### Optional: Financial Modeling Prep (US stocks only)

> **⚠️ Note: FMP is disabled by default and only works for US stocks.**  
> FMP has no coverage for Malaysian stocks (.KL). Use `--fmp` flag only when screening US stocks.

**Setup (only needed for US stocks):**
1. Register for free API key at [financialmodelingprep.com](https://financialmodelingprep.com/)
2. Create `.env` file in project root: `FMP_API_KEY=your_key_here`
3. For GitHub Actions: Add `FMP_API_KEY` to repository secrets
4. Run with `--fmp` flag: `be-richer --tickers AAPL MSFT --fmp`

**Limitations:**
- FMP free tier: 250 API calls/day, limit=5 records per request
- **Malaysian stocks (.KL) have NO FMP coverage**
- US stock support is experimental

---

## HTML Report Features

The `--html` flag generates a beautiful, self-contained HTML report with:

- 📊 **Summary cards** showing classification counts
- 📋 **Interactive sortable table** with all metrics
- 📈 **Analyst targets**: Target price, upside %, recommendation
- 📡 **KLSE Enhanced data**: QoQ%, YoY%, Momentum, Institutional Flow, Insider Trading
- 📚 **Strategy explainer** — collapsible section explaining the scoring methodology
- 🌙 **Dark theme** — easy on the eyes
- 📱 **Mobile responsive** — works on any device

---

## ⚠️ Yahoo Finance Rate Limiting

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
│       ├── __init__.py        # Package entry point
│       ├── __main__.py        # Allow python -m bursa_screener
│       ├── screener.py        # CLI entry point
│       ├── universe.py        # Stock universe (KLCI, mid-cap, SEA, sector filter)
│       ├── data_fetcher.py    # yfinance wrapper + caching
│       ├── klse_fetcher.py    # KLSE Screener API client (Malaysian stocks)
│       ├── fmp_fetcher.py     # FMP API client (US stocks only)
│       ├── technicals.py      # 25-point technical scorer
│       ├── fundamentals.py    # 65-84 point fundamental scorer
│       ├── ranker.py          # Classification + sorting
│       ├── reporter.py        # Rich terminal output + CSV
│       ├── html_reporter.py   # HTML report generator
│       ├── news_fetcher.py    # Google News fetcher for AI analysis
│       ├── position_analyzer.py  # Position P&L and decision support (NEW!)
│       ├── config/            # Sector PE benchmarks
│       └── cache/             # yfinance, KLSE, FMP cache (auto-created)
├── .github/
│   └── workflows/
│       └── sector-scan.yml    # GitHub Actions: Sector-based screener
├── results/                   # CSV/HTML exports (auto-created)
├── .env                       # FMP API key (not committed)
├── pyproject.toml             # Project configuration
├── requirements.txt           # Dependencies
├── run.sh                     # Shell shortcuts
└── README.md                  # This file
```

---

## Output Files

Every run saves timestamped files to `results/`:

```
results/bursa_screen_20261125_0930.csv
results/bursa_screen_20261125_0930.html
```

**CSV columns**: `ticker, name, price, fundamental, technical, catalyst, total,
pe_ttm, pb, roe, net_gearing, div_yield, earnings_growth, earnings_surprise, 
analyst_target, analyst_upside, analyst_score, analyst_rec,
klse_qoq, klse_yoy, klse_momentum, klse_consistency, klse_institutional, klse_insider,
rs_ratio, adv_30d, week_return, month_return, rsi, vol_ratio, 52wk_position, 
tech_status, classification, has_fmp, has_klse, has_analyst`

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
| Level 1.6 | ✅ Done | KLSE Screener integration (+14 pts for Malaysian stocks) |
| Level 1.7 | ✅ Done | Analyst target prices (+5 pts), insider trading, sector filter |
| Level 1.8 | 🔸 Partial | FMP integration (disabled by default - US stocks only) |
| Level 1.9 | ✅ Done | Position Analyzer — P&L tracking, trend analysis, AI-ready prompts |
| Level 2 | 🔜 Planned | LLM deep analysis — catalyst scoring, Core EPS normalization |
| Level 3 | 🔜 Planned | Weekly scheduler, Telegram/email alerts, portfolio tracker |

---

## License

MIT License - see LICENSE file for details.
