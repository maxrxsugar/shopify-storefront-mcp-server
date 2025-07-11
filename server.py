from fastapi import FastAPI
from mcp.routes.assistant import assistant_router

app = FastAPI()
app.include_router(assistant_router, prefix="/assistant")
