from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from mcp import ServerSession

app = FastAPI()

# ✅ CORS for Netlify
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://startling-rolypoly-956344.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def health_check():
    return {"status": "ok"}

@app.options("/mcp")
async def options_handler():
    return Response(status_code=200)

@app.post("/mcp")
async def handle_mcp(request: Request):
    print("✅ /mcp endpoint hit")
    try:
        body = await request.body()

        # ✅ This is the only valid call for MCP 1.10.1
        session = ServerSession.create()
        response = await session.handle_json_rpc_bytes(body)

        return Response(content=response, media_type="application/json")

    except Exception as e:
        print(f"❌ MCP processing error: {e}")
        return Response(
            content=b'{"error": "MCP session failed"}',
            media_type="application/json",
            status_code=500
        )

