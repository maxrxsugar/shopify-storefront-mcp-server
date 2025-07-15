from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from mcp import chat  # ✅ This works with mcp==1.11.0 from PyPI

app = FastAPI()

# ✅ Replace with your actual Netlify frontend URL (no trailing slash)
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
