#!/usr/bin/env bash
# build.sh

# ✅ Create and activate a local virtual environment
python -m venv .venv
source .venv/bin/activate

# ✅ Upgrade pip and force clean install of dependencies
pip install --upgrade pip
pip install --force-reinstall mcp==1.10.1
pip install -r requirements-temp.txt
