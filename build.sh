#!/usr/bin/env bash
# build.sh

# ✅ Create and activate a local virtual environment
python -m venv .venv
source .venv/bin/activate

# ✅ Upgrade pip
pip install --upgrade pip

# ❌ REMOVE this line if it still exists
# pip install --force-reinstall mcp==1.10.1  <-- DELETE this

# ✅ Install from clean requirements
pip install -r requirements-temp.txt
