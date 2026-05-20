#!/usr/bin/env bash
# Show account balances and positions (one-shot).
#   ./run_status.sh            — test mode
#   ./run_status.sh production — production mode
source "$(cd "$(dirname "$0")" && pwd)/_bootstrap.sh"

export ARGOPTIONS_MODE="${1:-test}"
echo ">> Account status (mode: $ARGOPTIONS_MODE)..."
arg-options status
