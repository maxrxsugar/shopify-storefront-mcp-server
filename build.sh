#!/usr/bin/env bash
# build.sh

# ✅ Set up virtual environment
python -m venv .venv
source .venv/bin/activate

# ✅ Clean install with no cache to avoid old MCP versions
pip install --upgrade pip
pip install --no-cache-dir -r requirements-temp.txt
