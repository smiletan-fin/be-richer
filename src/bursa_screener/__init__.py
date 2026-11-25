# Bursa Malaysia Level 1 Screener
"""
Be Richer - Automated stock screener for Bursa Malaysia (and Southeast Asia) equities.

Usage:
    from bursa_screener import run
    run(tier="klci")
    
    # Or via CLI:
    python -m bursa_screener
    be-richer --tier broad
"""

from .screener import run, main

__version__ = "1.0.0"
__all__ = ["run", "main"]
