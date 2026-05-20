#!/usr/bin/env bash
# Build option chain (one-shot).
#   ./run_chain.sh            — test mode
#   ./run_chain.sh production — production mode
source "$(cd "$(dirname "$0")" && pwd)/_bootstrap.sh"

export ARGOPTIONS_MODE="${1:-test}"
echo ">> Building chain (mode: $ARGOPTIONS_MODE)..."
arg-options chain
