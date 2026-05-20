#!/usr/bin/env bash
# Show active orders (one-shot).
#   ./run_orders.sh            — test mode
#   ./run_orders.sh production — production mode
source "$(cd "$(dirname "$0")" && pwd)/_bootstrap.sh"

export ARGOPTIONS_MODE="${1:-test}"
echo ">> Active orders (mode: $ARGOPTIONS_MODE)..."
arg-options orders
