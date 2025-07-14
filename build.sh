#!/usr/bin/env bash

# Clean up old environments (optional but clean)
rm -rf .venv || true

# Upgrade pip and reinstall from scratch
pip install --upgrade pip

# Install correct version of MCP and other deps
pip install mcp==1.10.1
pip install -r requirements-temp.txt
