#!/usr/bin/env bash
# Cron-friendly: runs one engine cycle, logs to data/logs/.
#   ./run_cron.sh              — test mode
#   ./run_cron.sh --prod       — production mode
# Install in crontab:
#   */15 * * * * /path/to/argoptions/run_cron.sh
source "$(cd "$(dirname "$0")" && pwd)/_bootstrap.sh"

PROD_FLAG=""
for arg in "$@"; do
    case "$arg" in --prod) PROD_FLAG="--prod"; export ARGOPTIONS_MODE=production ;; esac
done
export ARGOPTIONS_MODE="${ARGOPTIONS_MODE:-test}"

LOG_DIR="data/logs"
mkdir -p "$LOG_DIR"
LOGFILE="$LOG_DIR/engine-$(date +%Y%m%d).log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] engine cycle start (mode: $ARGOPTIONS_MODE)" >> "$LOGFILE"
arg-options run $PROD_FLAG --once >> "$LOGFILE" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] engine cycle end" >> "$LOGFILE"
