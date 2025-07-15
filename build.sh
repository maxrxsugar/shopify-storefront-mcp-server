#!/usr/bin/env bash
# build.sh

python -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements-temp.txt
