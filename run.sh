#!/usr/bin/env zsh
# =============================================================================
# Be Richer - Bursa Malaysia Level 1 Screener — Shell Script Shortcuts
#
# Usage:
#   ./run.sh <command> [options]
#
# Examples:
#   ./run.sh klci
#   ./run.sh broad
#   ./run.sh custom 1155.KL 5347.KL 4324.KL
#   ./run.sh refresh
# =============================================================================

# ── resolve paths ─────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$SCRIPT_DIR/.venv/bin/activate"

# ── check venv exists ─────────────────────────────────────────────────────────
if [[ ! -f "$VENV" ]]; then
  echo "❌  Virtual environment not found at: $VENV"
  echo ""
  echo "    Setup instructions:"
  echo "    cd $SCRIPT_DIR"
  echo "    python -m venv .venv"
  echo "    source .venv/bin/activate"
  echo "    pip install -r requirements.txt"
  echo "    pip install -e ."
  exit 1
fi

source "$VENV"

# ── helper ────────────────────────────────────────────────────────────────────
run_screener() {
  echo ""
  echo "▶  python -m bursa_screener $*"
  echo "─────────────────────────────────────────────────────────────────────"
  cd "$SCRIPT_DIR" && python -m bursa_screener "$@"
}

print_usage() {
  cat <<EOF

Be Richer - Bursa Malaysia Level 1 Screener

USAGE
  ./run.sh <command> [extra flags]

COMMANDS
  klci              Scan KLCI 30 constituents (default, ~20s)
  broad             Scan KLCI 30 + mid-cap watchlist (~45 tickers, ~40s)
  full              Scan all tiers including SEA regional
  watchlist         Broad scan, show all groups including REJECT
  custom <tickers>  Analyse specific tickers  e.g. custom 1155.KL 5347.KL
  refresh           Force refresh KLCI constituents from yfinance + run scan

PRESET WATCHLISTS
  banks             Malaysian banking stocks
  plantations       Plantation & commodity stocks
  property          Property developers & REITs
  rerater           Early re-rating candidates (OSK, UOADEV)

UTILITY
  test              Quick smoke test (3 tickers, no CSV)
  show-universe     Display current KLCI universe (from cache/fallback)
  validate          Check all tickers against yfinance (find stale/delisted)
  check             Check Yahoo Finance connectivity
  stats             Show cache statistics

EXTRA FLAGS (append to any command)
  --show-rejected      Include REJECT stocks in the output table
  --no-export          Skip CSV export to results/
  --refresh-universe   Force refresh KLCI constituents from yfinance
  --tier <tier>        Override tier: klci | broad | full

EXAMPLES
  ./run.sh klci
  ./run.sh broad
  ./run.sh refresh                          # refresh universe + scan
  ./run.sh watchlist
  ./run.sh custom 1155.KL 5347.KL 1023.KL 4324.KL 5076.KL
  ./run.sh klci --show-rejected
  ./run.sh broad --no-export

EOF
}

# ── command dispatch ──────────────────────────────────────────────────────────
COMMAND="${1:-help}"
shift || true   # remove first arg so "$@" holds remaining flags / tickers

case "$COMMAND" in

  # ── KLCI 30 only (fast daily/weekly check) ─────────────────────────────────
  klci)
    run_screener --tier klci "$@"
    ;;

  # ── KLCI + mid-cap (recommended weekly scan) ───────────────────────────────
  broad)
    run_screener --tier broad "$@"
    ;;

  # ── all tiers ──────────────────────────────────────────────────────────────
  full)
    run_screener --tier full "$@"
    ;;

  # ── broad scan + show rejected (full picture) ──────────────────────────────
  watchlist)
    run_screener --tier broad --show-rejected "$@"
    ;;

  # ── force refresh KLCI universe + run broad scan ───────────────────────────
  refresh)
    echo "🔄  Refreshing KLCI constituents from yfinance..."
    run_screener --tier klci --refresh-universe "$@"
    ;;

  # ── custom ticker list ─────────────────────────────────────────────────────
  custom)
    if [[ $# -eq 0 ]]; then
      echo "❌  No tickers provided."
      echo "    Usage: ./run.sh custom 1155.KL 5347.KL 4324.KL"
      exit 1
    fi
    run_screener --tickers "$@"
    ;;

  # ── preset watchlists ──────────────────────────────────────────────────────
  banks)
    run_screener --tickers 1155.KL 1023.KL 1082.KL 5819.KL 5183.KL 6033.KL "$@"
    ;;

  plantations)
    run_screener --tickers 4197.KL 1961.KL 2445.KL 4715.KL 5681.KL "$@"
    ;;

  property)
    run_screener --tickers 5200.KL 5109.KL 4324.KL 0072.KL 0082.KL 0078.KL 0138.KL "$@"
    ;;

  rerater)
    run_screener --tickers 5076.KL 5200.KL "$@"
    ;;

  # ── display current universe (no scan) ─────────────────────────────────────
  show-universe)
    cd "$SCRIPT_DIR" && python -c "
from bursa_screener.universe import get_klci_constituents, load_cached_klci, KLCI_FALLBACK, MID_CAP

cached, cached_date = load_cached_klci()
klci = get_klci_constituents()

print()
print('📊 Current KLCI Universe')
print('─' * 60)
if cached_date:
    print(f'   Source: cached ({cached_date.strftime(\"%Y-%m-%d %H:%M\")})')
else:
    print('   Source: fallback (no cache)')
print(f'   Count:  {len(klci)} tickers')
print()
print('   Tickers:')
for i, t in enumerate(klci, 1):
    print(f'     {i:2d}. {t}')
print()
print(f'📋 Mid-cap watchlist: {len(MID_CAP)} tickers')
print('   ' + ', '.join(MID_CAP[:5]) + '...')
print()
"
    ;;

  # ── validate all tickers against yfinance ──────────────────────────────────
  validate)
    echo "🔍 Validating KLCI universe against yfinance..."
    cd "$SCRIPT_DIR" && python -c "
from bursa_screener.universe import get_klci_constituents, validate_universe

klci = get_klci_constituents()
print(f'Validating {len(klci)} tickers...')
print()

valid, results = validate_universe(klci, remove_invalid=False, verbose=True)

print()
invalid = [r for r in results if not r['valid']]
if invalid:
    print(f'⚠️  {len(invalid)} invalid ticker(s) found:')
    for r in invalid:
        print(f'   {r[\"ticker\"]}: {r[\"error\"]}')
else:
    print('✅ All tickers are valid!')
"
    ;;

  # ── check connectivity ─────────────────────────────────────────────────────
  check)
    run_screener --check
    ;;

  # ── show cache stats ───────────────────────────────────────────────────────
  stats)
    run_screener --cache-stats
    ;;

  # ── quick smoke test (3 tickers, no CSV) ───────────────────────────────────
  test)
    run_screener --tickers 1155.KL 5347.KL 1023.KL --no-export
    ;;

  # ── help ───────────────────────────────────────────────────────────────────
  help | --help | -h)
    print_usage
    ;;

  *)
    echo "❌  Unknown command: $COMMAND"
    print_usage
    exit 1
    ;;

esac
