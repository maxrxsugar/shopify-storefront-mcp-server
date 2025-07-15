#!/usr/bin/env bash
# build.sh

# ✅ Create and activate a local virtual environment
python -m venv .venv
source .venv/bin/activate

# ✅ Upgrade pip
pip install --upgrade pip

# ✅ Install requirements, which should include mcp==1.11.0
pip install -r requirements-temp.txt
