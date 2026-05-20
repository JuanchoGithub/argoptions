#!/usr/bin/env bash
# Explicit full setup — same as _bootstrap.sh but with more feedback.
source "$(cd "$(dirname "$0")" && pwd)/_bootstrap.sh"

python -m pytest tests/ -q --tb=short 2>/dev/null && {
    echo ">> All tests passed!"
} || {
    echo ">> Some tests failed — check output above."
}

echo ""
echo "=== Setup complete ==="
echo "Run  ./run.sh        — TUI in test mode (default)"
echo "     ./run_prod.sh   — TUI in production mode"
echo "     ./run_engine.sh — automation engine"
echo "     ./run_test.sh   — run tests"
