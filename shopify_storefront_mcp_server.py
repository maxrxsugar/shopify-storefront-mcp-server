from mcp import assistant_app
from fastapi import FastAPI

# Create your assistant app
app = assistant_app()

# Optional: add a test route to make sure server boots
@app.get("/test")
def test():
    return {"status": "MCP server is running"}
