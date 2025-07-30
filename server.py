from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import openai
import os
import time
import requests
import json
import re
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# ✅ CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://startling-rolypoly-956344.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Environment Config
ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
openai.api_key = os.getenv("OPENAI_API_KEY")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_STOREFRONT_ACCESS_TOKEN")
SHOPIFY_STORE_DOMAIN = os.getenv("SHOPIFY_STORE_DOMAIN")

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

        thread = openai.beta.threads.create()
        print("🧵 Created thread:", thread.id)

        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=message
        )
        print("💬 Message added to thread")

        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID
        )
        print("🚀 Assistant run started:", run.id)

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
                        try:
                            response = requests.post(
                                "https://rxshopifympc.onrender.com/get-product-details",
                                json=args,
                                timeout=30
                            )
                            result = response.json()
                            print("📬 Shopify function result:", result)

                            tool_outputs.append({
                                "tool_call_id": call.id,
                                "output": result.get("reply", "No reply provided.")
                            })
                        except Exception as e:
                            print("❌ Error calling function endpoint:", str(e))
                            tool_outputs.append({
                                "tool_call_id": call.id,
                                "output": "Sorry, there was an issue fetching the product details."
                            })

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
    product_name = data.get("productName", "").strip().lower()

    if not product_name:
        return {"reply": "Missing product name."}

    product_mappings = {
        "cereal": "rxsugar-cereal-pro",
        "cereals": "rxsugar-cereal-pro",
        "sweetener": "rxsugar-allulose-sugar-2-pound-canister",
        "allulose": "rxsugar-allulose-sugar-2-pound-canister",
        "sugar": "rxsugar-allulose-sugar-2-pound-canister",
        "fiber": "rxsugar-fiber-pro",
        "gummies": "rxsugar-gummies-pro",
        "glp": "craving-control-natural-glp-1-boost-bundle",
        "sampler": "rxsugar-cereal-pro-sampler-pack",
        "cocoa crunch": "rxsugar-cereal-pro-cocoa-crunch",
        "golden crunch": "rxsugar-cereal-pro-golden-crunch",
        "brownie": "rxsugar-keto-brownie-mix",
        "mint brownie": "rxsugar-mint-brownie-swealthy-snax-caddy",
        "snack": "rxsugar-swealthy-snax",
        "snacks": "rxsugar-swealthy-snax",
        "caramel": "rxsugar-caramel-swealthy-snax-caddy",
        "vanilla": "rxsugar-vanilla-creme-swealthy-snax-caddy",
        "chocolate": "rxsugar-chocolate-swealthy-snax-caddy",
        "stix": "rxsugar-swealthy-stix",
        "protien": "rxsugar-gummies-pro",
        "vitamine": "rxsugar-gummies-pro"
    }

    mapped_handle = product_mappings.get(product_name)
    if not mapped_handle:
        for keyword, handle in product_mappings.items():
            if re.search(rf"\\b{re.escape(keyword)}\\b", product_name):
                mapped_handle = handle
                break

    if mapped_handle:
        print(f"🔁 Mapped '{product_name}' to handle '{mapped_handle}'")
        product_name = mapped_handle

    query = f'''
    {{
      productByHandle(handle: "{product_name}") {{
        title
        description
        productType
        tags
        availableForSale
        images(first: 5) {{
          edges {{ node {{ url altText }} }}
        }}
        variants(first: 5) {{
          edges {{
            node {{
              title
              availableForSale
              price {{ amount currencyCode }}
            }}
          }}
        }}
      }}
    }}
    '''

    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Storefront-Access-Token": SHOPIFY_ACCESS_TOKEN
    }

    try:
        response = requests.post(
            SHOPIFY_STORE_DOMAIN,
            json={"query": query},
            headers=headers,
            timeout=40
        )
        result = response.json()
        print("🔍 Raw Shopify response:", result)

        product = result.get("data", {}).get("productByHandle")
        if not product:
            print(f"🛑 No product found for handle: {product_name}")
            return {"reply": f"Sorry, I couldn't find that product in our store."}

        images = [img["node"] for img in product.get("images", {}).get("edges", [])]
        variants = [v["node"] for v in product.get("variants", {}).get("edges", [])]

        enriched_data = {
            "title": product.get("title"),
            "description": product.get("description"),
            "available": product.get("availableForSale"),
            "productType": product.get("productType"),
            "tags": product.get("tags"),
            "images": images,
            "variants": variants
        }

        return {"reply": json.dumps(enriched_data, indent=2)}

    except Exception as e:
        print("❌ Shopify error:", str(e))
        return {"reply": "Sorry, there was a problem fetching the product info."}











