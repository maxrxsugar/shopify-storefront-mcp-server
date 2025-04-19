import os
import httpx
import json
import sys
import asyncio
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from typing import Any, Dict, Optional, List

# Use absolute path to the script's directory instead of relying on current working directory
script_dir = os.path.dirname(os.path.abspath(__file__))

# Look for .env file using absolute path
env_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=env_path)

# Shopify Configuration
SHOPIFY_STOREFRONT_ACCESS_TOKEN = os.getenv("SHOPIFY_STOREFRONT_ACCESS_TOKEN")
SHOPIFY_STORE_NAME = os.getenv("SHOPIFY_STORE_NAME")
SHOPIFY_STOREFRONT_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2025-04")  # Default to latest API version

# Validate essential configuration
if not all([SHOPIFY_STOREFRONT_ACCESS_TOKEN, SHOPIFY_STORE_NAME]):
    print("ERROR: Shopify Storefront credentials not found in .env file.", file=sys.stderr)
    # In a real app, you might exit or raise an exception

# Construct the Shopify Storefront GraphQL endpoint
SHOPIFY_STOREFRONT_API_URL = f"https://{SHOPIFY_STORE_NAME}.myshopify.com/api/{SHOPIFY_STOREFRONT_API_VERSION}/graphql.json"

# Initialize MCP server
mcp = FastMCP("shopify_storefront", version="0.1.0")
print("Shopify Storefront MCP Server initialized.", file=sys.stderr)

async def execute_shopify_storefront_graphql(query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Makes an authenticated GraphQL request to Shopify's Storefront API.
    Handles authentication and error checking.
    """
    if not SHOPIFY_STOREFRONT_ACCESS_TOKEN:
        return {"errors": [{"message": "Server missing Shopify Storefront access token."}]}
    
    if not SHOPIFY_STORE_NAME:
        return {"errors": [{"message": "Shopify store name not configured."}]}

    headers = {
        "X-Shopify-Storefront-Access-Token": SHOPIFY_STOREFRONT_ACCESS_TOKEN,
        "Content-Type": "application/json",
        "User-Agent": "MCPShopifyStorefrontServer/0.1.0"
    }

    # Optionally add buyer IP if provided
    buyer_ip = os.getenv("SHOPIFY_BUYER_IP")
    if buyer_ip:
        headers["Shopify-Storefront-Buyer-IP"] = buyer_ip

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                SHOPIFY_STOREFRONT_API_URL,
                headers=headers,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()  # Raise HTTP errors (4xx, 5xx)
            result = response.json()
            
            # Check for GraphQL errors within the response body
            if "errors" in result:
                print(f"GraphQL Errors detected", file=sys.stderr)
            
            return result
        except httpx.RequestError as e:
            print(f"HTTP Request Error", file=sys.stderr)
            return {"errors": [{"message": "HTTP Request Error connecting to Shopify Storefront"}]}
        except httpx.HTTPStatusError as e:
            print(f"HTTP Status Error: {e.response.status_code}", file=sys.stderr)
            # Special handling for 430 Security Rejection which is specific to Storefront API
            if e.response.status_code == 430:
                return {"errors": [{"message": "Shopify Security Rejection. Ensure Buyer IP headers are correct."}]}
            return {"errors": [{"message": f"HTTP Status Error: {e.response.status_code}"}]}
        except Exception as e:
            print(f"Error during Shopify Storefront request", file=sys.stderr)
            return {"errors": [{"message": "An unexpected error occurred"}]}

@mcp.tool()
async def storefront_execute_graphql(query: str, variables: Dict[str, Any] = None) -> str:
    """
    Use this tool to query Shopify store data through the Shopify Storefront API.
    Perfect for building customer-facing shopping experiences with access to products, collections, and cart management.
    
    This tool executes arbitrary GraphQL queries/mutations with the Shopify Storefront API, providing
    access to all available public-facing store data for building shopping experiences.
    
    ## Common Operation Patterns

    ### Fetching products
    ```graphql
    query GetProducts {
      products(first: 5) {
        edges {
          node {
            id
            title
            description
            priceRange {
              minVariantPrice {
                amount
                currencyCode
              }
            }
            images(first: 1) {
              edges {
                node {
                  url
                }
              }
            }
          }
        }
      }
    }
    ```

    ### Fetching a single product by handle
    ```graphql
    query GetProduct($handle: String!) {
      product(handle: $handle) {
        id
        title
        description
        availableForSale
        variants(first: 5) {
          edges {
            node {
              id
              title
              price {
                amount
                currencyCode
              }
              availableForSale
            }
          }
        }
      }
    }
    ```
    Variables: `{"handle": "my-product-handle"}`

    ### Creating a cart
    ```graphql
    mutation CreateCart {
      cartCreate {
        cart {
          id
          checkoutUrl
        }
        userErrors {
          field
          message
        }
      }
    }
    ```

    ### Adding items to a cart
    ```graphql
    mutation AddToCart($cartId: ID!, $lines: [CartLineInput!]!) {
      cartLinesAdd(cartId: $cartId, lines: $lines) {
        cart {
          id
          lines(first: 10) {
            edges {
              node {
                id
                quantity
                merchandise {
                  ... on ProductVariant {
                    id
                    title
                  }
                }
              }
            }
          }
          estimatedCost {
            totalAmount {
              amount
              currencyCode
            }
          }
        }
        userErrors {
          field
          message
        }
      }
    }
    ```
    Variables: `{"cartId": "gid://shopify/Cart/123", "lines": [{"merchandiseId": "gid://shopify/ProductVariant/456", "quantity": 1}]}`

    Args:
        query: The complete GraphQL query or mutation to execute.
        variables: Optional dictionary of variables for the query.

    Returns:
        JSON string containing the complete response from Shopify Storefront API.
    """
    # Make the API call
    result = await execute_shopify_storefront_graphql(query, variables)

    # Return the raw result as JSON
    return json.dumps(result)

if __name__ == "__main__":
    print("Starting Shopify Storefront MCP server...", file=sys.stderr)
    # Basic check before running
    if not all([SHOPIFY_STOREFRONT_ACCESS_TOKEN, SHOPIFY_STORE_NAME]):
        print("WARNING: Cannot make API calls, Shopify Storefront credentials missing.", file=sys.stderr)
        print("Set SHOPIFY_STOREFRONT_ACCESS_TOKEN and SHOPIFY_STORE_NAME in .env file.", file=sys.stderr)
    
    try:
        mcp.run(transport='stdio')
        print("Server stopped.", file=sys.stderr)
    except Exception as e:
        print(f"Error running server: {e}", file=sys.stderr) 