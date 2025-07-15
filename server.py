from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from mcp import ServerSession

app = FastAPI()

# CORS config for Netlify
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
    # Manual setup for MCP 1.10.1
    body = await request.body()

    async def read_stream():
        return body

    async def write_stream(data: bytes):
        nonlocal response_data
        response_data = data

    response_data = b""

    session = ServerSession(read_stream, write_stream, init_options={})
    await session.run()
    return Response(content=response_data, media_type="application/json")
