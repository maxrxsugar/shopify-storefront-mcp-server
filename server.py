from mcp import assistant_app  # not mcp.fastapi

app = assistant_app()

@app.get("/test")
def test():
    return {"status": "MCP server is running"}
