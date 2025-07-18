@app.post("/get-product-details")
async def get_product_details(request: Request):
    data = await request.json()
    product_name = data.get("productName")

    if not product_name:
        return {"reply": "Missing product name."}

    shopify_domain = "rxsugar.myshopify.com"
    access_token = os.getenv("SHOPIFY_STOREFRONT_ACCESS_TOKEN")

    def build_query(name):
        return {
            "query": f'''
            {{
              products(first: 1, query: "{name}") {{
                edges {{
                  node {{
                    title
                    description
                    variants(first: 1) {{
                      edges {{
                        node {{
                          price {{
                            amount
                            currencyCode
                          }}
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
            '''
        }

    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Storefront-Access-Token": access_token
    }

    # Try multiple fallback queries
    search_attempts = [
        product_name,
        f'title:{product_name}',
        ' '.join(product_name.split()[:2])  # Just "Brownie Mix", etc.
    ]

    for attempt in search_attempts:
        try:
            response = requests.post(
                f"https://{shopify_domain}/api/2023-04/graphql.json",
                json=build_query(attempt),
                headers=headers,
                timeout=10
            )
            result = response.json()

            if "errors" in result:
                print("🛑 Shopify returned errors:", result)
                continue

            edges = result["data"]["products"]["edges"]
            if not edges:
                print(f"❌ No product match found with query: {attempt}")
                continue

            product = edges[0]["node"]
            title = product["title"]
            description = product["description"]
            price_info = product["variants"]["edges"][0]["node"]["price"]
            price = f"{price_info['amount']} {price_info['currencyCode']}"

            return {
                "reply": f"{title}: {description} Price: {price}"
            }

        except Exception as e:
            print("Shopify error during attempt:", attempt, "| Error:", e)

    return {"reply": "Sorry, there was a problem fetching the product info or no matching product was found."}










