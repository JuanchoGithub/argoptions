#!/usr/bin/env bash
# Run screening (one-shot).
#   ./run_screen.sh            — test mode
#   ./run_screen.sh production — production mode
source "$(cd "$(dirname "$0")" && pwd)/_bootstrap.sh"

export ARGOPTIONS_MODE="${1:-test}"
echo ">> Running screening (mode: $ARGOPTIONS_MODE)..."
arg-options screen
