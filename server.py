from fastapi import FastAPI, Request
from mcp import ServerSession

app = FastAPI()

@app.get("/")
async def health_check():
    return {"status": "ok"}

@app.post("/mcp")
async def handle_mcp(request: Request):
    body = await request.json()
    session = ServerSession()
    response = await session.handle_json_rpc(body)
    return response
