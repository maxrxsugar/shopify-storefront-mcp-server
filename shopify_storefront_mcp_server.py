from fastapi import FastAPI
from mcp.server import Server  # core MCP integration

app = FastAPI()

# Set up MCP (assumes valid .env or env vars for MCP)
server = Server(app)

@app.get("/")
async def root():
    return {"message": "Shopify MCP server is running!"}
