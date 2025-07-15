from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from mcp import ServerSession

app = FastAPI()

# ✅ CORSMiddleware setup
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
        session = await ServerSession.from_fastapi(request)
        response = await session.run()
        return Response(content=response, media_type="application/json")

    except Exception as e:
        print(f"❌ MCP session error: {e}")
        return Response(content=b'{"error": "Internal MCP failure"}', media_type="application/json", status_code=500)
