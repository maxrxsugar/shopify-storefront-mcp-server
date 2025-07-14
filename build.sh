#!/usr/bin/env bash
# 🔁 Full clean install with MCP v1.10.1

# Remove previous installations
rm -rf .venv || true

# Reinstall in fresh environment
pip install --upgrade pip
pip install --upgrade mcp==1.10.1
pip install -r requirements-temp.txt
