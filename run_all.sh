#!/usr/bin/env bash
set -e

# Create a virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    uv venv
fi

# Activate the virtual environment
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
uv pip install -e .[dev]

# Run tests
echo "Running tests..."
pytest

# Run the app
echo "Starting the app..."
export ARG_OPTIONS_ENV=arg_options/.env
arg-options interactive