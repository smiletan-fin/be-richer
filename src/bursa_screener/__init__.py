# Bursa Malaysia Level 1 Screener
"""
Be Richer - Automated stock screener for Bursa Malaysia (and Southeast Asia) equities.

Usage:
    from bursa_screener import run
    run(tier="klci")
    
    # Single stock analysis:
    from bursa_screener import analyze_stock
    result = analyze_stock("1155.KL")
    print(result.ai_prompt)
    
    # Or via CLI:
    python -m bursa_screener
    be-richer --tier broad
    be-richer --analyze MAYBANK
"""

from .screener import run, main

# Stock analyzer for single-stock deep analysis
try:
    from .stock_analyzer import analyze_stock, StockAnalysis
    _ANALYZER_AVAILABLE = True
except ImportError:
    _ANALYZER_AVAILABLE = False
    analyze_stock = None
    StockAnalysis = None

__version__ = "1.1.0"
__all__ = ["run", "main", "analyze_stock", "StockAnalysis"]
