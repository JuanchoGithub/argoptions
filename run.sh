#!/usr/bin/env bash
# Launch argoptions TUI in TEST (sandbox) mode — default, always safe.
source "$(cd "$(dirname "$0")" && pwd)/_bootstrap.sh"

export ARGOPTIONS_MODE=test

echo "╔══════════════════════════════════════════════╗"
echo "║   argoptions  —  TEST MODE  (sandbox)       ║"
echo "║   No live orders. PPI sandbox only.         ║"
echo "╚══════════════════════════════════════════════╝"

arg-options "$@"
