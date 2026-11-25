# 📊 Be Richer Stock Screener - Scoring Guide

> **For beginners**: This guide explains how the stock screener evaluates stocks and what each term means. No prior investing knowledge required!

---

## 🎯 Quick Overview

The screener gives each stock **two main scores**:

| Score Type | What It Measures | Max Points |
|------------|------------------|------------|
| **Fundamental Score** | Is this a good business? | 65-79 pts |
| **Technical Score** | Is now a good time to buy? | 25 pts |
| **Total Score** | Combined rating | 90-104 pts |

Based on these scores, stocks are classified into 4 categories:

| Category | Meaning | Criteria |
|----------|---------|----------|
| 🟢 **READY TO BUY** | Strong company + Price going up | Fundamental ≥52, Technical ≥18 |
| 🟡 **EARLY RE-RATING** | Strong company, price hasn't caught up | Fundamental ≥52, Technical 12-17 |
| 🔵 **WATCHLIST** | Average company, needs improvement | Fundamental 40-51 |
| 🔴 **REJECT** | Warning signs detected | Fundamental <40 or major red flags |

---

## 📈 Part 1: Fundamental Score (Business Quality)

**What it answers**: *"Is this company making money and growing?"*

The fundamental score looks at **how healthy the business is**. Think of it like a health checkup for a company.

### A. Earnings Quality (Max 10 points)

**What it means**: Is the company actually making real money, or just showing fake profits on paper?

| Term | Simple Explanation |
|------|-------------------|
| **PE Ratio (Price-to-Earnings)** | How many years of profits would it take to "pay back" the stock price. Lower = cheaper. Example: PE of 10 means if you bought the whole company, it would take 10 years of profits to get your money back. |
| **OCF/Net Income Ratio** | Cash Conversion - Are profits turning into actual cash? Companies can manipulate profit numbers, but cash is hard to fake. |

**Scoring**:
- 8 points: PE well below industry average (undervalued)
- 6 points: PE below industry average
- 4 points: PE slightly above average
- 2 points: PE expensive vs industry
- +2 bonus: Strong cash conversion (OCF > 80% of profits)

---

### B. Earnings Growth (Max 10 points)

**What it means**: Is the company growing its profits?

| Term | Simple Explanation |
|------|-------------------|
| **EPS Growth** | Earnings Per Share Growth - How much profits increased compared to last year. +25% means profits grew by a quarter. |
| **Revenue Growth** | Sales Growth - How much total sales increased. If a company sells more stuff, that's usually good! |

**Scoring**:
- 10 points: ≥25% growth (excellent, like top tech companies)
- 8 points: ≥15% growth (solid)
- 5 points: ≥8% growth (decent)
- 3 points: ≥0% growth (flat but not declining)
- 0 points: Negative growth (profits shrinking ⚠️)

**Why it matters**: Growing companies usually see their stock prices rise over time. A company with declining profits often sees its stock price fall.

---

### C. ROE - Return on Equity (Max 10 points)

**What it means**: How efficiently is management using shareholder money to generate profits?

**Simple analogy**: If you gave the company RM100, ROE tells you how much profit they made with it.
- ROE of 18% = They turned your RM100 into RM118 profit
- ROE of 5% = They only made RM5 profit from your RM100

| ROE Level | Assessment | Points |
|-----------|------------|--------|
| ≥18% | Excellent - Very efficient management | 10 |
| 14-17% | Good | 8 |
| 10-13% | Fair | 6 |
| 6-9% | Weak | 4 |
| 0-5% | Poor | 2 |
| Negative | Losing money | 0 |

---

### D. Financial Health (Max 10 points)

**What it means**: Does the company have too much debt? Can it survive tough times?

| Term | Simple Explanation |
|------|-------------------|
| **Net Gearing** | Debt-to-Equity ratio. How much the company owes vs what it owns. Lower = safer. |
| **Net Cash** | When a company has more cash than debt. This is the safest! |

**Scoring**:
| Gearing Level | What It Means | Points |
|---------------|---------------|--------|
| Negative (Net Cash) | More cash than debt - very safe! | 10 |
| 0 to 0.2 | Low debt - healthy | 8 |
| 0.2 to 0.5 | Moderate debt - acceptable | 6 |
| 0.5 to 1.0 | Elevated debt - monitor | 4 |
| >1.0 | High debt - risky ⚠️ | 1 |

**Why it matters**: Companies with too much debt can go bankrupt during economic downturns. Net cash companies can survive and even buy competitors during tough times.

---

### E. Valuation (Max 12 points)

**What it means**: Is the stock price cheap or expensive compared to what the company is worth?

| Term | Simple Explanation |
|------|-------------------|
| **PE Ratio** | Price ÷ Earnings. How much you pay for each RM1 of profit. |
| **P/B Ratio (Price-to-Book)** | Price ÷ Book Value. If the company sold everything and paid all debts, would you get more or less than you paid? P/B < 1 means you're paying less than the company's assets are worth. |

**PE Scoring** (Max 7 points):
- 7 pts: 30%+ discount to industry average
- 5 pts: 15-30% discount
- 4 pts: At or slightly below average
- 2 pts: 0-20% premium
- 1 pt: >20% premium (expensive)

**P/B Scoring** (Max 5 points):
- 5 pts: P/B < 0.7 (deep value - buying assets cheap)
- 4 pts: P/B 0.7-1.0
- 3 pts: P/B 1.0-1.5
- 2 pts: P/B 1.5-2.5
- 1 pt: P/B 2.5-4.0
- 0 pts: P/B > 4.0 (very expensive)

---

### F. Cash Flow (Max 5 points)

**What it means**: Is the company generating real cash from operations?

| Term | Simple Explanation |
|------|-------------------|
| **Operating Cash Flow (OCF)** | Actual cash coming in from the business. More reliable than "profit" which can include non-cash items. |
| **FCF Yield** | Free Cash Flow ÷ Market Cap. How much cash the company generates relative to its stock price. |

**Scoring**:
- 5 pts: FCF Yield ≥8% (excellent cash generation)
- 4 pts: FCF Yield 5-8%
- 3 pts: FCF Yield 3-5%
- 2 pts: FCF Yield 1-3%
- 1 pt: Positive but low
- 0 pts: Negative cash flow ⚠️

---

### G. Dividends (Max 3 points)

**What it means**: Does the company share profits with shareholders?

| Term | Simple Explanation |
|------|-------------------|
| **Dividend Yield** | Annual dividend ÷ Stock price. If a stock costs RM10 and pays RM0.50 yearly dividend, yield = 5%. |

**Scoring**:
- 3 pts: ≥5% yield (high income)
- 2 pts: 2-5% yield (good income)
- 1 pt: 0.5-2% yield (modest)
- 0 pts: No dividend (not necessarily bad - growth companies reinvest)

**Note**: Many great growth companies pay no dividends because they reinvest profits to grow faster. Low dividend isn't a red flag!

---

### H. Improving Fundamentals (Max 5 points)

**What it means**: Are things getting better? (Piotroski F-Score style checks)

You get 1 point for each positive sign:
1. ✓ Positive ROE (company is profitable)
2. ✓ Positive operating cash flow
3. ✓ Cash flow higher than reported profit (quality earnings)
4. ✓ Low or decreasing debt
5. ✓ Positive earnings growth

4-5 points = Strong momentum ✓

---

### I. Analyst Target (Max 5 points)

**What it means**: What do professional stock analysts think?

| Term | Simple Explanation |
|------|-------------------|
| **Target Price** | The price analysts think the stock should be worth in 12 months. |
| **Upside/Downside** | Percentage difference between current price and target. +20% upside = analysts think it could rise 20%. |
| **Recommendation** | Buy, Hold, or Sell rating from analysts. |

**Scoring**:
- 4 pts: ≥20% upside potential
- 3 pts: 10-20% upside
- 2 pts: 5-10% upside
- 1 pt: 0-5% upside
- 0 pts: Negative (stock above target)
- +1 bonus: Strong Buy consensus

---

### J-M. KLSE Enhanced Scores (Malaysian Stocks Only, Max 14 points)

For Malaysian stocks, we get extra data from KLSE Screener:

#### J. Earnings Momentum (Max 5 points)
**What it measures**: Is profit growth accelerating?
- Looks at Quarter-over-Quarter (QoQ) and Year-over-Year (YoY) growth
- Accelerating growth (this quarter better than last) = higher score

#### K. Earnings Consistency (Max 3 points)
**What it measures**: How many quarters in a row has the company grown?
- 3+ consecutive growth quarters = 3 points
- Consistent growth is more reliable than one-time spikes

#### L. Institutional Flow (Max 3 points)
**What it measures**: Are big investors (EPF, KWAP, PNB) buying or selling?
- Net institutional buying = "Smart money" is confident
- Net institutional selling = Caution warranted

#### M. Insider Trading (Max 3 points)
**What it measures**: Are company directors buying their own stock?
- Directors buying = They believe in the company (bullish)
- Directors selling = Could be a warning sign

---

## 📉 Part 2: Technical Score (Timing)

**What it answers**: *"Is now a good time to buy, or should I wait?"*

The technical score looks at **price trends and momentum**. Even a great company can be a bad investment if you buy at the wrong time!

### Price vs Moving Averages (Max 9 points total)

| Term | Simple Explanation |
|------|-------------------|
| **Moving Average (MA)** | The average price over a period. 20MA = average of last 20 days. |
| **Price above MA** | Current price is higher than the average - generally bullish. |
| **MA Rising** | The average itself is going up - trend is strong. |

#### 20-Day MA (Max 3 points)
Short-term trend indicator (about 1 month)
- 3 pts: Price above 20MA AND 20MA is rising
- 2 pts: Price above 20MA
- 1 pt: Price within 2% below 20MA
- 0 pts: Price well below 20MA

#### 50-Day MA (Max 3 points)
Medium-term trend indicator (about 2.5 months)
- 3 pts: Price above 50MA AND 20MA above 50MA AND 50MA rising
- 2 pts: Price above 50MA AND 20MA above 50MA
- 1 pt: Price above 50MA
- 0 pts: Price below 50MA

#### 200-Day MA (Max 3 points)
Long-term trend indicator (about 10 months)
- 3 pts: Price above 200MA AND 50MA above 200MA
- 2 pts: Price above 200MA
- 1 pt: Price within 5% of 200MA
- 0 pts: Price below 200MA

**Golden Cross**: When 50MA crosses above 200MA - strong bullish signal!

---

### RSI - Relative Strength Index (Max 2 points)

**What it means**: Is the stock overbought or oversold?

RSI ranges from 0 to 100:
| RSI Range | Meaning |
|-----------|---------|
| >70 | Overbought - might pull back soon |
| 50-70 | Bullish momentum - healthy uptrend |
| 40-50 | Neutral/recovering |
| 30-40 | Weak |
| <30 | Oversold - might bounce soon |

**Scoring**:
- 2 pts: RSI 50-70 (bullish, not overbought)
- 1 pt: RSI 40-50 or >70 (recovering or overbought)
- 0 pts: RSI <40 (weak momentum)

---

### MACD - Moving Average Convergence Divergence (Max 2 points)

**What it means**: Is momentum building or fading?

| Term | Simple Explanation |
|------|-------------------|
| **MACD Line** | Difference between fast and slow moving averages |
| **Signal Line** | A smoothed version of the MACD line |
| **Bullish Crossover** | MACD crosses above Signal - buying momentum |

**Scoring**:
- 2 pts: MACD above Signal AND MACD above zero (strong momentum)
- 1 pt: MACD above Signal but below zero (improving)
- 0 pts: MACD below Signal (weakening)

---

### Volume (Max 3 points)

**What it means**: Are lots of people buying? Volume confirms price moves.

| Term | Simple Explanation |
|------|-------------------|
| **ADV (Average Daily Volume)** | Typical number of shares traded per day |
| **Volume Ratio** | Recent volume ÷ Average volume. >1.5x = unusually high |

**Scoring**:
- 3 pts: Volume ≥1.5x average AND price rising (accumulation)
- 2 pts: Volume ≥1.2x average AND price rising
- 1 pt: Normal volume
- 0 pts: Low volume (lack of interest)

**Why it matters**: Price rises on heavy volume are more reliable. Price rises on light volume might be temporary.

---

### Breakout Pattern (Max 2 points)

**What it means**: Is the stock about to break to new highs?

| Term | Simple Explanation |
|------|-------------------|
| **Breakout** | Price moving above a previous high/resistance level |
| **Consolidation** | Price moving sideways in a tight range before a potential move |

**Scoring**:
- 2 pts: Within 3% of 3-month high (potential breakout)
- 1 pt: Consolidating near recent highs (building base)
- 0 pts: Far from highs

---

### Support Holding (Max 2 points)

**What it means**: Is the stock holding above key price levels, or breaking down?

| Term | Simple Explanation |
|------|-------------------|
| **Support** | A price level where the stock tends to stop falling and bounce |
| **Holding support** | Stock isn't making new lows - buyers stepping in |

**Scoring**:
- 2 pts: Holding recent support AND closed green AND positive monthly return
- 1 pt: Holding support
- 0 pts: Breaking down through support

---

### Relative Strength vs Index (Max 3 points)

**What it means**: Is this stock doing better or worse than the overall market (KLCI)?

| RS Ratio | Meaning |
|----------|---------|
| ≥1.5 | Strong - beating market by 50%+ |
| 1.2-1.5 | Good - outperforming by 20%+ |
| 1.0-1.2 | Neutral - about same as market |
| <1.0 | Weak - underperforming market |

**Scoring**:
- 3 pts: RS ≥1.5 (market leader)
- 2 pts: RS ≥1.2 (outperforming)
- 1 pt: RS ≥1.0 (at par)
- 0 pts: RS <1.0 (lagging)

**Why it matters**: In uptrends, buy the leaders, not the laggards!

---

### 52-Week Position (Max 2 points)

**What it means**: Where is the price relative to its yearly range? (Minervini template)

| Criteria | Explanation |
|----------|-------------|
| >25% above 52-week low | Stock has recovered from lows |
| Within 25% of 52-week high | Stock is near its highs |

**Scoring**:
- 2 pts: Both criteria met (the "sweet spot")
- 1 pt: One criteria met
- 0 pts: Neither met

**The "Sweet Spot"**: The best stocks to buy are ones that:
1. Have already proven strength (not at rock bottom)
2. Still have room to grow (not at the very top)

---

## 🚫 Hard Reject Flags

Some issues are so serious that stocks are automatically rejected:

| Flag | Why It's Bad |
|------|--------------|
| **PN17/GN3** | Malaysian regulatory alert - company in financial distress |
| **Negative PE** | Company is losing money |
| **Negative ROE** | Shareholders losing value |
| **High Net Gearing (>1.0)** | Dangerous debt levels |
| **Negative Operating Cash Flow** | Burning cash |
| **Negative Earnings Growth** | Profits declining |

---

## 📋 Technical Status Labels

Based on the technical score, stocks get a status label:

| Score | Status | What It Means |
|-------|--------|---------------|
| ≥18/25 | **Confirmed Uptrend** | Strong momentum, good timing |
| 12-17/25 | **Early Re-Rating** | Momentum building, watch for confirmation |
| <12/25 | **Downtrend/Value Trap** | Poor timing, even if fundamentals are good |

---

## 🎓 Key Takeaways for Beginners

### The Perfect Stock Has:
1. ✅ Strong fundamentals (profitable, growing, low debt)
2. ✅ Good technicals (price trending up, volume confirming)
3. ✅ Fair valuation (not overpriced)
4. ✅ Positive momentum (things getting better, not worse)

### Warning Signs to Avoid:
- ❌ Negative earnings or ROE
- ❌ High debt (gearing >1.0)
- ❌ Declining profits
- ❌ Price below all moving averages
- ❌ Directors/institutions selling

### The Golden Rule:
**A great company at the wrong price is a bad investment.**
**An average company at a great price might be a good investment.**

The screener helps you find: **Great companies at fair prices with good momentum.**

---

## 📚 Glossary of Terms

| Term | Simple Definition |
|------|-------------------|
| **Bear Market** | When stock prices are falling overall |
| **Bull Market** | When stock prices are rising overall |
| **Dividend** | Cash payment from company to shareholders |
| **EPS** | Earnings Per Share - Profit divided by number of shares |
| **Market Cap** | Total value of all shares (share price × number of shares) |
| **P/E Ratio** | Price to Earnings - How much you pay per RM1 of profit |
| **P/B Ratio** | Price to Book - Stock price vs company's net assets |
| **ROE** | Return on Equity - Profit relative to shareholder investment |
| **Volume** | Number of shares traded |
| **Volatility** | How much the price moves up and down |
| **YoY** | Year over Year - Comparing to same period last year |
| **QoQ** | Quarter over Quarter - Comparing to previous quarter |

---

*Last updated: November 2026*
*Be Richer Stock Screener - Making investing accessible for everyone*
