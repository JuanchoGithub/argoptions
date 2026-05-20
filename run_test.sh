#!/usr/bin/env bash
# Run the full test suite.
source "$(cd "$(dirname "$0")" && pwd)/_bootstrap.sh"

python -m pytest tests/ -v "$@"
