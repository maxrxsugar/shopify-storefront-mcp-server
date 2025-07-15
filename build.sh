#!/usr/bin/env bash
# build.sh

# ✅ Create and activate a local virtual environment
python -m venv .venv
source .venv/bin/activate

# ✅ Upgrade pip and install from requirements
pip install --upgrade pip
pip install -r requirements-temp.txt
