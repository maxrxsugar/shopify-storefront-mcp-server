from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp import ServerSession

app = FastAPI()

# ✅ CORS Middleware – must be defined *before* routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://startling-rolypoly-956344.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Health check endpoint
@app.get("/")
async def health_check():
    return {"status": "ok"}

# ✅ CORS preflight handler for POST /mcp
@app.options("/mcp")
async def preflight_mcp():
    return JSONResponse(content={"message": "Preflight OK"})

# ✅ Main MCP handler (JSON-RPC)
@app.post("/mcp")
async def handle_mcp(request: Request):
    try:
        body = await request.json()
        session = await ServerSession.from_fastapi(request)
        response = await session.handle_json_rpc(body)
        return response
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})



