#!/usr/bin/env bash
# Sync journal & show P&L (one-shot).
#   ./run_journal.sh            — test mode
#   ./run_journal.sh production — production mode
source "$(cd "$(dirname "$0")" && pwd)/_bootstrap.sh"

export ARGOPTIONS_MODE="${1:-test}"
echo ">> Journal sync (mode: $ARGOPTIONS_MODE)..."
arg-options journal
