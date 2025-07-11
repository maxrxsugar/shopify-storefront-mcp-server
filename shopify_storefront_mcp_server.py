from mcp import assistant_app
from fastapi import FastAPI

app = assistant_app()

@app.get("/test")
def test():
    return {"status": "MCP server is running"}
