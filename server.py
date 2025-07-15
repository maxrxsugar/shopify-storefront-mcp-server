from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from mcp.fastapi import chat

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://startling-rolypoly-956344.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    body = await request.json()
    return await chat(body)
