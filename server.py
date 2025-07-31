from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import openai
import os
import time
import requests
import json
import re
from fastapi.testclient import TestClient
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
client = TestClient(app)  # ✅ Internal FastAPI client for calling endpoints directly

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
                            response = client.post("/get-product-details", json=args)
                            result = response.json()
                            print("📬 Shopify function result:", result)

                            tool_outputs.append({
                                "tool_call_id": call.id,
                                "output": result.get("reply", "No reply provided.")
                            })
                        except Exception as e:
                            print("❌ Internal call error:", str(e))
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
        # 🥣 Cereals
        "cereal": "rxsugar-cereal-pro",
        "cereals": "rxsugar-cereal-pro",
        "breakfast": "rxsugar-cereal-pro",
        "breakfast food": "rxsugar-cereal-pro",
        "morning snack": "rxsugar-cereal-pro",
        "cereal bundle": "rxsugar-cereal-pro",
        "chocolate cereal": "rxsugar-cereal-pro-cocoa-crunch",
        "golden cereal": "rxsugar-cereal-pro-golden-crunch",
        "sampler": "rxsugar-cereal-pro-sampler-pack",

        # 🍬 Gummies / Bundle
        "gummies": "rxsugar-gummies-pro",
        "vitamins": "rxsugar-gummies-pro",
        "probiotic": "rxsugar-gummies-pro",
        "glp gummies": "rxsugar-gummies-pro",
        "glp-1": "craving-control-natural-glp-1-boost-bundle",

        # 🍫 Swealthy Snax
        "snack": "rxsugar-swealthy-snax",
        "snacks": "rxsugar-swealthy-snax",
        "candy": "rxsugar-swealthy-snax",
        "candy bar": "rxsugar-swealthy-snax",
        "healthy candy": "rxsugar-swealthy-snax",
        "sweet bar": "rxsugar-swealthy-snax",
        "chocolate snack": "rxsugar-chocolate-swealthy-snax-caddy",
        "mint snack": "rxsugar-mint-brownie-swealthy-snax-caddy",
        "caramel snack": "rxsugar-caramel-swealthy-snax-caddy",
        "vanilla snack": "rxsugar-vanilla-creme-swealthy-snax-caddy",

        # 🍰 Brownie Mix
        "brownie": "rxsugar-keto-brownie-mix",
        "brownie mix": "rxsugar-keto-brownie-mix",
        "glp brownie": "rxsugar-keto-brownie-mix",

        # 💧 Allulose + Stix
        "sweetener": "rxsugar-allulose-sugar-2-pound-canister",
        "allulose": "rxsugar-allulose-sugar-2-pound-canister",
        "sugar": "rxsugar-allulose-sugar-2-pound-canister",
        "stix": "rxsugar-swealthy-stix",

        # 🌾 Fiber
        "fiber": "rxsugar-fiber-pro",
        "fiber pro": "rxsugar-fiber-pro",
        "prebiotic": "rxsugar-fiber-pro",
        "digestive health": "rxsugar-fiber-pro",
        "high fiber": "rxsugar-fiber-pro"
    }

    mapped_handle = product_mappings.get(product_name)
    if not mapped_handle:
        for keyword, handle in product_mappings.items():
            if re.search(rf"\b{re.escape(keyword)}\b", product_name):
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

        images = product.get("images", {}).get("edges", [])
        variants = product.get("variants", {}).get("edges", [])

        image_html = "<br>".join([
            f'<img src="{img["node"]["url"]}" alt="Product Image" style="max-width:300px;" />'
            for img in images
        ])
        price_html = "<ul>" + "".join([
            f'<li><strong>{v["node"]["title"]}</strong>: ${v["node"]["price"]["amount"]} {v["node"]["price"]["currencyCode"]}</li>'
            for v in variants
        ]) + "</ul>"

        html_body = f'''
        <h3>{product['title']}</h3>
        <p>{product['description']}</p>
        <p><strong>Available:</strong> {'Yes' if product['availableForSale'] else 'No'}</p>
        <p><strong>Price Options:</strong>{price_html}</p>
        <p>{image_html}</p>
        <p><a href="https://www.rxsugar.com/products/{product_name}" target="_blank">🔗 View on Store</a></p>
        '''

        return {"reply": html_body.strip()}

    except Exception as e:
        print("❌ Shopify error:", str(e))
        return {"reply": "Sorry, there was a problem fetching the product info."}









