#!/usr/bin/env bash

python -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install --upgrade mcp==1.10.1
pip install -r requirements-temp.txt
