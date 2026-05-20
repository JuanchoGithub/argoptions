#!/usr/bin/env bash
# Launch argoptions TUI in PRODUCTION mode — ⚠️ real orders possible.
source "$(cd "$(dirname "$0")" && pwd)/_bootstrap.sh"

export ARGOPTIONS_MODE=production

echo "╔══════════════════════════════════════════════╗"
echo "║   🔴  PRODUCTION MODE  —  LIVE PPI API      ║"
echo "║                                             ║"
echo "║   ⚠️  REAL ORDERS may be executed if         ║"
echo "║   ⚠️  ALLOW_LIVE_ORDERS=true in .env_prod    ║"
echo "║                                             ║"
echo "║   Press Ctrl+C now to cancel.                ║"
echo "╚══════════════════════════════════════════════╝"
sleep 2

arg-options --prod "$@"
