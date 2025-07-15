from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.integrations.fastapi import chat  # ✅ This works with mcp >= 1.11.0

app = FastAPI()

# ✅ CORS for Netlify frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://startling-rolypoly-956344.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Simple health check
@app.get("/")
def root():
    return {"status": "ok"}

# ✅ Use MCP's built-in router
app.include_router(chat.router, prefix="/mcp")


