#!/usr/bin/env bash
# build.sh

# Create and activate virtual env
python -m venv .venv
source .venv/bin/activate

# Clean install deps
pip install --upgrade pip
pip install -r requirements-temp.txt

