from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from mcp import ServerSession

app = FastAPI()

# CORS setup for Netlify
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
        response_data = b""

        async def read_stream():
            return body

        async def write_stream(data: bytes):
            nonlocal response_data
            response_data = data

        # ✅ This is the valid call signature for your version
        session = ServerSession(read_stream, write_stream, init_options={})
        await session.run()

        return Response(content=response_data, media_type="application/json")

    except Exception as e:
        print(f"❌ MCP processing error: {e}")
        return Response(
            content=b'{"error": "MCP session failed"}',
            media_type="application/json",
            status_code=500
        )

