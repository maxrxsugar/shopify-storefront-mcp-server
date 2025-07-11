from mcp.integrations.fastapi import create_assistant_app
from fastapi import FastAPI

app = create_assistant_app()

@app.get("/test")
def test():
    return {"status": "MCP server is running"}
