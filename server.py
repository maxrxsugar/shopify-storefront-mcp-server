from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from mcp import ServerSession

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
        body = await request.body()

        session = ServerSession()
        result = await session.run(body)

        return Response(content=result, media_type="application/json")

    except Exception as e:
        print(f"❌ MCP processing error: {e}")
        return Response(
            content=b'{"error": "MCP session failed"}',
            media_type="application/json",
            status_code=500
        )

