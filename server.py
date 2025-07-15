from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastapi import ServerSession

app = FastAPI()

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

@app.post("/mcp")
async def handle_mcp(request: Request):
    print("✅ /mcp endpoint hit")

    try:
        session = ServerSession.create()
        response = await session.handle(request)
        return response  # Already a proper FastAPI Response

    except Exception as e:
        print(f"❌ MCP processing error: {e}")
        return Response(
            content=b'{"error": "MCP session failed"}',
            media_type="application/json",
            status_code=500
        )

