from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import openai
import os
import time
import requests
import json
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# ✅ CORS fix
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://startling-rolypoly-956344.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
openai.api_key = os.getenv("OPENAI_API_KEY")

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
        print("📩 User message received:", message)

        # Create thread
        thread = openai.beta.threads.create()
        print("🧵 Created thread:", thread.id)

        # Add user message
        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=message
        )
        print("💬 Message added to thread")

        # Start assistant run
        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID
        )
        print("🚀 Assistant run started:", run.id)

        # 🌀 Loop: handle tool calls if required
        while True:
            run_status = openai.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            print("🔁 Run status:", run_status.status)

            if run_status.status == "requires_action":
                tool_calls = run_status.required_action.submit_tool_outputs.tool_calls
                tool_outputs = []

                for call in tool_calls:
                    func_name = call.function.name
                    args = json.loads(call.function.arguments)

                    print(f"🔧 Function call: {func_name} with args: {args}")

                    if func_name == "getProductDetails":
                        # ✅ Call Render endpoint (not localhost)
                        response = requests.post(
                            "https://rxshopifympc.onrender.com/get-product-details",
                            json=args
                        )
                        result = response.json()
                        print("📬 Shopify function result:", result)

                        tool_outputs.append({
                            "tool_call_id": call.id,
                            "output": result["reply"]
                        })

                # Submit tool outputs back to OpenAI
                print("📤 Submitting tool outputs...")
                run = openai.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread.id,
                    run_id=run.id,
                    tool_outputs=tool_outputs
                )

            elif run_status.status == "completed":
                print("✅ Assistant run completed.")
                break
            elif run_status.status == "failed":
                print("❌ Assistant run failed.")
                return {"error": f"Run failed: {run_status.last_error}"}

            time.sleep(1)

        # Fetch assistant reply
        messages = openai.beta.threads.messages.list(thread_id=thread.id)

        if not messages.data or not messages.data[0].content:
            return {"error": "No reply received from assistant."}

        reply = messages.data[0].content[0].text.value
        print("🧠 Final assistant reply:", reply)

        return {"reply": reply}

    except Exception as e:
        print("💥 Server error:", str(e))
        return {"error": f"Server error: {str(e)}"}


@app.post("/get-product-details")
async def get_product_details(request: Request):
    data = await request.json()
    product_name = data.get("productName")

    if not product_name:
        return {"reply": "Missing product name."}

    shopify_domain = "rxsugar.myshopify.com"
    access_token = os.getenv("SHOPIFY_STOREFRONT_ACCESS_TOKEN")

    query = '''
    {
      products(first: 1, query: "%s") {
        edges {
          node {
            title
            description
            variants(first: 1) {
              edges {
                node {
                  price {
                    amount
                    currencyCode
                  }
                }
              }
            }
          }
        }
      }
    }
    ''' % product_name

    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Storefront-Access-Token": access_token
    }

    try:
        response = requests.post(
            f"https://{shopify_domain}/api/2023-04/graphql.json",
            json={"query": query},
            headers=headers
        )
        result = response.json()
        product = result["data"]["products"]["edges"][0]["node"]

        title = product["title"]
        description = product["description"]
        price_info = product["variants"]["edges"][0]["node"]["price"]
        price = f"{price_info['amount']} {price_info['currencyCode']}"

        return {
            "reply": f"{title}: {description} Price: {price}"
        }

    except Exception as e:
        print("Shopify error:", e)
        return {"reply": "Sorry, there was a problem fetching the product info."}



