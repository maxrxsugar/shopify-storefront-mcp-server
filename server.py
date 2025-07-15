from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")
assistant_id = os.getenv("ASSISTANT_ID")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://startling-rolypoly-956344.netlify.app"],  # ✅ update if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    data = await request.json()
    user_input = data.get("message")

    if not user_input:
        return {"error": "Missing 'message' in request body."}

    # Step 1: Create a new thread
    thread = openai.beta.threads.create()

    # Step 2: Add the user's message to the thread
    openai.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_input,
    )

    # Step 3: Run the assistant
    run = openai.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id,
    )

    # Step 4: Wait for the run to complete (polling)
    import time
    while True:
        run_status = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run_status.status in ["completed", "failed", "cancelled"]:
            break
        time.sleep(1)

    # Step 5: Get the response message
    messages = openai.beta.threads.messages.list(thread_id=thread.id)
    response = next(
        (msg for msg in reversed(messages.data) if msg.role == "assistant"), None
    )

    return {"reply": response.content[0].text.value if response else "No reply."}
