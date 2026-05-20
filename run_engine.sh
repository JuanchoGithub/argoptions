#!/usr/bin/env bash
# Run the automation engine.
#   ./run_engine.sh           — continuous loop, test mode
#   ./run_engine.sh --prod    — continuous loop, production
#   ./run_engine.sh --once    — single cycle, then exit
source "$(cd "$(dirname "$0")" && pwd)/_bootstrap.sh"

PROD_FLAG=""
ONCE_FLAG=""
for arg in "$@"; do
    case "$arg" in
        --prod) PROD_FLAG="--prod"; export ARGOPTIONS_MODE=production ;;
        --once) ONCE_FLAG="--once" ;;
        -h|--help) echo "Usage: $0 [--prod] [--once]" ; exit 0 ;;
    esac
done

if [ -n "$PROD_FLAG" ]; then
    echo "╔══════════════════════════════════════════════╗"
    echo "║   🔴 ENGINE — PRODUCTION                     ║"
    echo "╚══════════════════════════════════════════════╝"
else
    export ARGOPTIONS_MODE=test
    echo "╔══════════════════════════════════════════════╗"
    echo "║   ENGINE — TEST mode                         ║"
    echo "╚══════════════════════════════════════════════╝"
fi

arg-options run $PROD_FLAG $ONCE_FLAG
