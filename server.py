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
    session = await ServerSession.from_fastapi(request)  # ✅ Proper async init
    response_bytes = await session.run()
    return Response(content=response_bytes, media_type="application/json")


