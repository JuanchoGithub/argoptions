#!/usr/bin/env bash
set -e

# Install dependencies
pip install -e \.\[dev\]

# Run tests
pytest

