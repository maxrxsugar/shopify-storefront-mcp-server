#!/usr/bin/env bash
# build.sh

# ✅ Create and activate a local virtual environment
python -m venv .venv
source .venv/bin/activate

# ✅ Upgrade pip
pip install --upgrade pip

# ✅ Install dependencies with token-authenticated MCP
pip install --no-cache-dir "git+https://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@github.com/openai/mcp.git@main"
pip install -r requirements-temp.txt

