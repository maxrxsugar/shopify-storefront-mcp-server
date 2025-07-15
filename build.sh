#!/usr/bin/env bash
# build.sh

python -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install --no-cache-dir -r requirements-temp.txt

