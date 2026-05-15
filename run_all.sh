#!/usr/bin/env bash
set -e

# Install dependencies
pip3 install -e \.\[dev\]

# Run tests
pytest

