from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import openai
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# (Optional) Set Assistant ID from environment variable or hardcoded string
ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")

app = FastAPI()

# Enable CORS for your Netlify frontend
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
    message = data.get("message", "")

    if not message.strip():
        return {"error": "Message content must be non-empty."}

    try:
        # Create a new thread (or replace with persistent thread ID if desired)
        thread = openai.beta.threads.create()

        # Add the user's message to the thread
        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=message
        )

        # Run the assistant
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

        # Retrieve the assistant's reply
        messages = openai.beta.threads.messages.list(thread_id=thread.id)
        latest_message = messages.data[0].content[0].text.value

        return {"reply": latest_message}

    except Exception as e:
        return {"error": str(e)}

        "content": assistant_messages[0] if assistant_messages else "No response from assistant."
    }
