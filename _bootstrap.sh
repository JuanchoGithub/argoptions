# ============================================================
# _bootstrap.sh — Shared setup for all argoptions run scripts
# Sources this from every run_*.sh so each script is
# self-bootstrapping. Run any script and it just works.
# ============================================================
set -euo pipefail

BOOTSTRAP_DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
cd "$BOOTSTRAP_DIR"

# ---- Auto-create venv ----
if [ ! -d ".venv" ]; then
    echo ">> No .venv found — creating one with uv..."
    uv venv
    source .venv/bin/activate
    echo ">> Installing argoptions + dependencies..."
    uv pip install -e ".[dev]" --quiet
else
    source .venv/bin/activate
fi

# ---- Ensure pip-installed (in case deps changed) ----
# Quiet, fast if already up to date
uv pip install -e ".[dev]" --quiet 2>/dev/null || true

# ---- Ensure example config files exist ----
mkdir -p config data

if [ ! -f "config/settings.yaml" ] && [ -f "config/settings.example.yaml" ]; then
    cp config/settings.example.yaml config/settings.yaml
    echo ">> Created config/settings.yaml from example"
fi

if [ ! -f "config/screening.yaml" ] && [ -f "config/screening.example.yaml" ]; then
    cp config/screening.example.yaml config/screening.yaml
    echo ">> Created config/screening.yaml from example"
fi

if [ ! -f "config/strategies.yaml" ]; then
    echo "# argoptions — defined via the TUI config screens" > config/strategies.yaml
    echo "strategies: []" >> config/strategies.yaml
fi

# ---- Check env files ----
if [ ! -f ".env_test" ]; then
    echo "⚠️  No .env_test found — create one with your PPI sandbox credentials."
    echo "   See .env_test.example or the PPI_API.md docs."
fi

if [ ! -f ".env_prod" ]; then
    echo "ℹ️  No .env_prod found. Production mode (--prod) requires it."
fi
