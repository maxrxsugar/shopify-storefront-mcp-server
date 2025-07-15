#!/usr/bin/env bash
# build.sh

# ✅ Create and activate a local virtual environment
python -m venv .venv
source .venv/bin/activate

# ✅ Clean install of all dependencies including MCP
pip install --upgrade pip
pip uninstall -y mcp || true  # Make sure old version is gone
pip install -r requirements-temp.txt
