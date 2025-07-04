# shopify_storefront_mcp_server.py

import os
from fastapi import FastAPI
from mcp.server import Server  # <- core MCP integration
import uvicorn

app = FastAPI()

# Set up MCP (assuming you have a valid .env or env vars for it)
server = Server(app)

@app.get("/")
async def root():
    return {"message": "Shopify MCP server is running!"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("shopify_storefront_mcp_server:app", host="0.0.0.0", port=port, reload=False)
