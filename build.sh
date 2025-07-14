#!/usr/bin/env bash
# 🔁 Full clean install with MCP v1.10.1

# 🧹 Remove previous virtual environment (forces clean MCP install)
rm -rf .venv || true

# 🔄 Reinstall in fresh environment
pip install --upgrade pip
pip install --force-reinstall mcp==1.10.1
pip install -r requirements-temp.txt
