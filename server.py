from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from mcp import ServerSession

app = FastAPI()

# CORS config to allow Netlify origin
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
    session = ServerSession()  # ✅ Use constructor instead of .create()
    response_bytes = await session.handle_json_rpc_bytes(body)
    return Response(content=response_bytes, media_type="application/json")



