#!/usr/bin/env bash
# build.sh

# ✅ Create and activate a local virtual environment
python -m venv .venv
source .venv/bin/activate

# ✅ Upgrade pip
pip install --upgrade pip

# ✅ Install MCP directly from GitHub using the token
pip install "mcp @ git+https://${GITHUB_TOKEN}@github.com/openai/mcp.git@main"

# ✅ Install the rest of the dependencies
pip install -r requirements-temp.txt
