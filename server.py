from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
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
    body = await request.body()
    session = ServerSession.create()
    response = await session.handle_json_rpc_bytes(body)
    return response





