from mcp.server.fastmcp import FastMCP

fastmcp = FastMCP()
app = fastmcp.app  # ✅ This is the real ASGI app that Uvicorn needs
