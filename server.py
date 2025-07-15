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
            elif run_status.status == "failed":
                return {"error": f"Run failed: {run_status.last_error}"}
            time.sleep(1)

        # Fetch assistant reply
        messages = openai.beta.threads.messages.list(thread_id=thread.id)

        if not messages.data or not messages.data[0].content:
            return {"error": "No reply received from assistant."}

        reply = messages.data[0].content[0].text.value

        return {"reply": reply}

    except Exception as e:
        return {"error": f"Server error: {str(e)}"}


