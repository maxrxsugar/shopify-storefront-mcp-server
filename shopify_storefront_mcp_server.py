from mcp import AssistantApp

app = AssistantApp()

@app.prompt("hello")
def handle_hello(query, context):
    return "Hey there! I'm working 🎉"

if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("shopify_storefront_mcp_server:app", host="0.0.0.0", port=port)
