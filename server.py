from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from mcp import ServerSession

app = FastAPI()

# CORS setup to allow Netlify frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://startling-rolypoly-956344.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional health check
@app.get("/")
async def health_check():
    return {"status": "ok"}

# Main MCP handler endpoint
@app.post("/mcp")
async def handle_mcp(request: Request):
    body = await request.body()
    session = ServerSession.create()
    response_bytes = await session.handle_json_rpc_bytes(body)
    return Response(content=response_bytes, media_type="application/json")




