from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import openai
import os
from dotenv import load_dotenv
import time

load_dotenv()

# Load environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")

app = FastAPI()

# Configure CORS for Netlify frontend
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
async def mcp_handler(request: Request):
    data = await request.json()
    message = data.get("message", "").strip()

    if not message:
        return {"error": "Message content must be non-empty."}

    try:
        # Create thread
        thread = openai.beta.threads.create()

        # Add message
        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=message
        )

        # Start assistant run
        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID
        )

        # Poll for completion
        while True:
            run_status = openai.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            if run_status.status == "completed":
                break
            time.sleep(1)

        # Get final message
        messages = openai.beta.threads.messages.list(thread_id=thread.id)
        reply = messages.data[0].content[0].text.value

        return {"reply": reply}

    except Exception as e:
        return {"error": str(e)}

