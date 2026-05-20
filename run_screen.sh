#!/usr/bin/env bash
# Run screening (one-shot).
#   ./run_screen.sh            — test mode with stored data
#   ./run_screen.sh production — production mode with stored data
#   ./run_screen.sh --live    — test mode with live API
#   ./run_screen.sh production --live — production mode with live API
source "$(cd "$(dirname "$0")" && pwd)/_bootstrap.sh"

ARGOPTIONS_MODE="${1:-test}"
USE_STORED="${2:-}"

if [ "$USE_STORED" = "--live" ]; then
    echo ">> Running screening with LIVE API (mode: $ARGOPTIONS_MODE)..."
    if [ "$ARGOPTIONS_MODE" = "production" ]; then
        arg-options screen --prod
    else
        arg-options screen
    fi
else
    echo ">> Running screening with STORED data (mode: $ARGOPTIONS_MODE)..."
    if [ "$ARGOPTIONS_MODE" = "production" ]; then
        arg-options screen --prod --stored
    else
        arg-options screen --stored
    fi
fi
