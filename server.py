# server.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")
assistant_id = os.getenv("ASSISTANT_ID")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://startling-rolypoly-956344.netlify.app"],  # your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/mcp")
async def mcp_handler(request: Request):
    data = await request.json()
    message = data.get("message", "")

    # Step 1: Create a thread
    thread = openai.beta.threads.create()

    # Step 2: Send the user message
    openai.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=message
    )

    # Step 3: Run the assistant
    run = openai.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id,
    )

    # Step 4: Poll until complete
    while True:
        run_status = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run_status.status == "completed":
            break
        elif run_status.status == "failed":
            return {"error": "Run failed"}
    
    # Step 5: Retrieve messages
    messages = openai.beta.threads.messages.list(thread_id=thread.id)
    assistant_messages = [
        m.content[0].text.value for m in messages.data if m.role == "assistant"
    ]

    # ✅ Return structured response for frontend
    return {
        "role": "assistant",
        "content": assistant_messages[0] if assistant_messages else "No response from assistant."
    }
