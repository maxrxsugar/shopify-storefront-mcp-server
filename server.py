from mcp.server.fastmcp import FastMCP

fastmcp = FastMCP()
app = fastmcp.asgi  # ✅ This is the correct attribute to pass to Uvicorn
