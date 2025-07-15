from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.fastapi import mcp_router

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

# ✅ Mount the MCP router directly
app.include_router(mcp_router, prefix="/mcp")
