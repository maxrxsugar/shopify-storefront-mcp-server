from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from mcp import chat

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Can replace with ["https://startling-rolypoly-956344.netlify.app"] for stricter security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "MCP server is live!"}

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    try:
        body = await request.json()
        response = await chat(body)
        return response
    except Exception as e:
        print(f"❌ MCP processing error: {e}")
        return {"error": str(e)}

