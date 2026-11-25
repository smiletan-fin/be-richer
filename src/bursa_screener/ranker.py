"""
Ranker — combines technical + fundamental scores, applies your
classification rules, and returns a sorted candidate list.

Classification thresholds (from your spec):
    READY TO BUY     : fundamental ≥ 50, technical ≥ 14
    EARLY RE-RATING  : fundamental ≥ 50, technical 9–13
    WATCHLIST        : fundamental 40–49
    REJECT           : fundamental < 40 or hard reject flags

Note: catalyst score (20 pts) is NOT computed in Level 1 — it requires
LLM analysis in Level 2.  We placeholder it as None so the output
table is already structured for Level 2 enrichment.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .fundamentals import FundamentalScore
from .technicals import TechnicalScore


# ── hard reject flags ─────────────────────────────────────────────────────────
HARD_REJECT_KEYWORDS = [
    "PN17", "GN3", "Negative PE", "Negative ROE",
    "High net gearing", "Negative operating cash flow",
]


@dataclass
class StockResult:
    ticker:     str
    long_name:  str | None

    fund:  FundamentalScore
    tech:  TechnicalScore

    # Level 2 placeholders
    catalyst_score: int | None = None

    @property
    def fundamental_score(self) -> int:
        return self.fund.total

    @property
    def technical_score(self) -> int:
        return self.tech.total

    @property
    def total_score(self) -> int:
        base = self.fundamental_score + self.technical_score
        if self.catalyst_score is not None:
            return base + self.catalyst_score
        return base

    @property
    def hard_reject(self) -> bool:
        for flag in self.fund.flags:
            for kw in HARD_REJECT_KEYWORDS:
                if kw in flag:
                    return True
        return False

    @property
    def classification(self) -> str:
        fs = self.fundamental_score
        ts = self.technical_score

        if self.hard_reject and fs < 35:
            return "REJECT"

        if fs >= 50:
            if ts >= 14:
                return "READY TO BUY"
            elif ts >= 9:
                return "EARLY RE-RATING"
            else:
                return "WATCHLIST"
        elif fs >= 40:
            return "WATCHLIST"
        else:
            return "REJECT"

    @property
    def classification_emoji(self) -> str:
        return {
            "READY TO BUY":    "🟢",
            "EARLY RE-RATING": "🟡",
            "WATCHLIST":       "🔵",
            "REJECT":          "🔴",
        }.get(self.classification, "⚪")

    def as_row(self) -> dict:
        """Flat dict for tabular display / CSV export."""
        return {
            "ticker":          self.ticker,
            "name":            (self.long_name or "")[:28],
            "price":           f"RM {self.tech.price:.3f}" if self.tech.price else "N/A",
            "fundamental":     f"{self.fundamental_score}/60",
            "technical":       f"{self.technical_score}/20",
            "catalyst":        f"{self.catalyst_score}/20" if self.catalyst_score is not None else "—",
            "total":           f"{self.total_score}",
            "pe_ttm":          f"{self.fund.pe_ttm:.1f}x"   if self.fund.pe_ttm   else "N/A",
            "pb":              f"{self.fund.pb:.2f}x"        if self.fund.pb       else "N/A",
            "roe":             f"{self.fund.roe_pct:.1f}%"   if self.fund.roe_pct  else "N/A",
            "net_gearing":     f"{self.fund.net_gearing:.2f}" if self.fund.net_gearing is not None else "N/A",
            "div_yield":       f"{self.fund.div_yield_pct:.1f}%" if self.fund.div_yield_pct else "N/A",
            "adv_30d":         f"{self.tech.adv_30d:,.0f}",
            "week_return":     f"{self.tech.week_return:+.1f}%",
            "month_return":    f"{self.tech.month_return:+.1f}%",
            "rsi":             f"{self.tech.rsi_val:.0f}",
            "vol_ratio":       f"{self.tech.volume_ratio:.2f}x",
            "tech_status":     self.tech.status,
            "classification":  self.classification,
        }


def rank_stocks(results: list[StockResult]) -> list[StockResult]:
    """
    Sort by classification priority, then by combined score descending.

    Order: READY TO BUY → EARLY RE-RATING → WATCHLIST → REJECT
    """
    priority = {
        "READY TO BUY":    0,
        "EARLY RE-RATING": 1,
        "WATCHLIST":       2,
        "REJECT":          3,
    }
    return sorted(
        results,
        key=lambda r: (priority.get(r.classification, 9), -r.total_score),
    )


def build_results(
    raw_data: dict[str, dict],
    fund_scores: dict[str, FundamentalScore],
    tech_scores: dict[str, TechnicalScore],
) -> list[StockResult]:
    """
    Combine fetched data and scores into StockResult objects.

    raw_data format (from data_fetcher.batch_fetch):
        { ticker: { "price_df": ..., "fundamentals": { "long_name": ... } } }
    """
    results: list[StockResult] = []
    for ticker in fund_scores:
        fund = fund_scores[ticker]
        tech = tech_scores.get(ticker, TechnicalScore(ticker=ticker))
        long_name = (raw_data.get(ticker, {}).get("fundamentals", {}) or {}).get("long_name")
        results.append(StockResult(ticker=ticker, long_name=long_name, fund=fund, tech=tech))
    return rank_stocks(results)
