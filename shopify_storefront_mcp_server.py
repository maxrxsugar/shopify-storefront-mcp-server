#!/usr/bin/env python3
"""
Shopify Storefront MCP Server — dynamic discovery edition
=========================================================

This **single file** replaces your previous hard‑coded MCP server.  It adds

* **`shopify.discover`** – Given *any* URL, decide if it's a Shopify storefront
  and (if so) harvest & validate any *public* Storefront Access Tokens*.
* **`shopify.storefront_graphql`** – Run an authenticated Storefront GraphQL query using a
  supplied `(host, token)` pair *or* fall back on credentials in `.env`.

> \* Public tokens are read‑only; many stores keep them server‑side, so discovery
> will legitimately return none in that case.

IMPORTANT: This server is ONLY for the Shopify Storefront API, which provides
public-facing, limited access to store data. It is NOT for the Admin API,
which requires different authentication and provides complete store management.

The code keeps compatibility with **FastMCP** & async `httpx` while removing the
mandatory env‑var requirement.  Agents can now:

1. `shopify.discover { url:"https://jackarcher.com" }`  → returns host & token.
2. `shopify.storefront_graphql { mode:"execute", host:"jackarcher.myshopify.com", token:"…", query:"…" }`

Install & run
-------------
```bash
pip install fastmcp mcp-sdk httpx bs4 python-dotenv
python shopify_mcp_server.py
```
The server speaks MCP on STDIO by default (compatible with the `mcp` CLI and
OpenAI function‑calling agents).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

###############################################################################
# Environment & constants
###############################################################################

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(SCRIPT_DIR, ".env"))

ENV_TOKEN: Optional[str] = os.getenv("SHOPIFY_STOREFRONT_ACCESS_TOKEN")
ENV_STORE: Optional[str] = os.getenv("SHOPIFY_STORE_NAME")
DEFAULT_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2025-04")

###############################################################################
# FastMCP server setup
###############################################################################

mcp = FastMCP("shopify_storefront", version="0.3.0")
print("Shopify Storefront API MCP server initialized.", file=sys.stderr)

###############################################################################
# Heuristic patterns for discovery
###############################################################################

HDR_PREFIXES = (
    "x‑shopify",  # most common
    "x‑shop",     # shardid / stage
    "x‑shardid",
    "x‑sorting-hat",
)
HTML_MARKERS = (
    re.compile(r"cdn\.shopify(?:cdn)?\.net|cdn\.shopify\.com", re.I),
    re.compile(r"class=[\"'][^\"']*shopify-section", re.I),
    re.compile(r"window\.Shopify|Shopify\.theme", re.I),
    re.compile(r"[a-zA-Z0-9-]+\.myshopify\.com", re.I),  # Added myshopify domain pattern
)

# Enhanced token patterns
TOKEN_PATTERNS = [
    # Standard 32-char hex tokens
    re.compile(r"\b([a-f0-9]{32})\b", re.I),
    # Support for other common token lengths (24-64 chars)
    re.compile(r"\b([a-f0-9]{24,64})\b", re.I),
    # JWT-style tokens (for newer implementations)
    re.compile(r"\"(eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,})\"", re.I)
]

# Myshopify domain patterns for more thorough detection
MYSHOPIFY_PATTERNS = [
    re.compile(r"[\"'](https?://)?([a-zA-Z0-9][a-zA-Z0-9-]*\.myshopify\.com)[\"'/]", re.I),
    re.compile(r"\b(https?://)?([a-zA-Z0-9][a-zA-Z0-9-]*\.myshopify\.com)\b", re.I),
    re.compile(r"[\"']myshopify_domain[\"']\s*:\s*[\"']([^\"']+)[\"']", re.I),
]

###############################################################################
# Async HTTP helpers
###############################################################################

DEFAULT_HEADERS = {
    "User-Agent": "ShopifyMCP/0.2 (+https://example.com)"
}


aio_client: Optional[httpx.AsyncClient] = None

async def get_client() -> httpx.AsyncClient:
    global aio_client
    if aio_client is None:
        aio_client = httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=15.0)
    return aio_client


async def fetch_text(url: str) -> str:
    client = await get_client()
    resp = await client.get(url, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


async def fetch_head(url: str) -> httpx.Headers:
    client = await get_client()
    resp = await client.head(url, follow_redirects=True)
    return resp.headers


###############################################################################
# Discovery core logic (async)
###############################################################################

def _is_shopify(headers: httpx.Headers, html: str) -> bool:
    hdr_hit = any(h.lower().startswith(HDR_PREFIXES) for h in headers)
    html_hit = any(rx.search(html) for rx in HTML_MARKERS)
    return hdr_hit or html_hit


def _canonical_host(html: str, fallback: str) -> str:
    """
    Extract the canonical Shopify store domain, preferring the myshopify.com domain.
    
    Checks multiple patterns and locations to find the canonical myshopify domain.
    """
    # Look for myshopify domain in HTML/JS with enhanced patterns
    for pattern in MYSHOPIFY_PATTERNS:
        m = pattern.search(html)
        if m:
            # Extract the domain from the match group (either group 1 or 2 depending on the pattern)
            domain = m.group(2) if len(m.groups()) > 1 and m.group(2) else m.group(1)
            return domain.lower()
    
    # Check for Shopify.shop in JavaScript
    shop_pattern = re.search(r"Shopify\.shop\s*=\s*[\"']([^\"']+)[\"']", html)
    if shop_pattern:
        shop = shop_pattern.group(1)
        if ".myshopify.com" in shop:
            return shop.lower()
        else:
            # If we have a shop name but not the full domain, construct it
            return f"{shop}.myshopify.com".lower()
            
    # Legacy pattern
    m = re.search(r"([\w-]+\.myshopify\.com)", html, re.I)
    if m:
        return m.group(1).lower()
        
    # Fallback to parsed host
    return fallback.lower()


def _token_candidates(text: str):
    """Enhanced token candidate detection with better context awareness"""
    lower = text.lower()
    
    # Common variable/field names for tokens
    token_contexts = [
        "storefront", "token", "access_token", "accesstoken", 
        "apikey", "api_key", "shopify", "graphql", "storefrontaccesstoken",
        "x-shopify", "publicaccesstoken", "client_id", "clientid"
    ]
    
    # Look for tokens in initialization patterns
    init_patterns = [
        r"ShopifyBuy\.buildClient\({[^}]*}",
        r"createClient\({[^}]*}",
        r"Shopify\.loadFeatures\({[^}]*}",
        r"new Client\({[^}]*}",
        r"fetch\([^)]*\"/api/[^\"]*\""
    ]
    
    # Check all token patterns
    candidates = []
    for pattern in TOKEN_PATTERNS:
        for m in pattern.finditer(text):
            # Expand window size to catch more context
            window = lower[max(0, m.start() - 100) : m.end() + 100]
            
            # Check for any token context
            if any(ctx in window for ctx in token_contexts):
                candidates.append(m.group(1))
            
            # Check if token is part of initialization pattern
            for init in init_patterns:
                if re.search(init, window):
                    candidates.append(m.group(1))
    
    return candidates


async def _validate_token(host: str, token: str, api_version: str = DEFAULT_API_VERSION) -> Dict[str, Any]:
    """Enhanced validation that returns token capabilities, not just validity"""
    client = await get_client()
    
    # Simple schema validation (existing approach)
    schema_query = {"query": "{__schema{queryType{name}}}"}
    
    # Product access validation 
    product_query = {"query": "{products(first:1){edges{node{id}}}}"}
    
    # Cart mutation validation
    cart_mutation = {
        "query": "mutation{cartCreate(input:{}){cart{id}}}"
    }
    
    results = {
        "valid": False,
        "permissions": [],
        "access_denied_errors": []
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Storefront-Access-Token": token,
    }
    
    try:
        # Test schema access
        schema_resp = await client.post(
            f"https://{host}/api/{api_version}/graphql.json",
            headers=headers,
            json=schema_query,
        )
        
        if schema_resp.status_code == 200 and "__schema" in schema_resp.text:
            results["valid"] = True
            
            # Add comprehensive permission testing
            permission_tests = [
                # Basic permissions
                {"name": "unauthenticated_read_product_listings", 
                 "query": "{products(first:1){edges{node{id}}}}"},
                {"name": "cart_create", 
                 "query": "mutation{cartCreate(input:{}){cart{id}}}"},
                {"name": "unauthenticated_read_content", 
                 "query": "{shop{name description}}"},
                {"name": "unauthenticated_read_customer", 
                 "query": "mutation{customerAccessTokenCreate(input:{email:\"test@example.com\",password:\"test\"}){customerUserErrors{message}}}"},
                {"name": "unauthenticated_read_collection_listings", 
                 "query": "{collections(first:1){edges{node{id}}}}"},
                # Discovery permissions
                {"name": "product_types_access", 
                 "query": "{productTypes(first:1){edges{node}}}"},
                {"name": "search_access", 
                 "query": "{search(query:\"test\",types:PRODUCT,first:1){edges{node{__typename}}}}"},
                {"name": "metafields_access", 
                 "query": "{shop{metafields(first:1){edges{node{id}}}}}"},
            ]
            
            for test in permission_tests:
                try:
                    resp = await client.post(
                        f"https://{host}/api/{api_version}/graphql.json",
                        headers=headers,
                        json={"query": test["query"]},
                    )
                    
                    # Check if query succeeded without access errors
                    if resp.status_code == 200 and "errors" not in resp.json():
                        results["permissions"].append(test["name"])
                    elif resp.status_code == 200:
                        # Check for specific error types in response
                        errors = resp.json().get("errors", [])
                        if any("Access denied" in error.get("message", "") for error in errors):
                            # Store which specific access was denied
                            results["access_denied_errors"].append(test["name"])
                except Exception:
                    pass
                
    except Exception:
        return results
        
    return results


def generate_api_guidance(permissions: List[str], access_denied: List[str]) -> Dict[str, Any]:
    """Generate guidance for AI agents based on discovered permissions"""
    
    guidance = {
        "recommended_approaches": [],
        "fallback_strategies": [],
        "operations_to_avoid": [],
        "example_queries": {},
    }
    
    # Map permissions to recommended operation patterns
    if "unauthenticated_read_product_listings" in permissions:
        guidance["recommended_approaches"].append({
            "name": "Direct Product Queries",
            "description": "You can directly query products, variants, and collections"
        })
        guidance["example_queries"]["product_query"] = """
        {
          products(first: 10) {
            edges {
              node {
                id
                title
                variants(first: 1) {
                  edges {
                    node {
                      id
                    }
                  }
                }
              }
            }
          }
        }
        """
    
    if "cart_create" in permissions:
        guidance["recommended_approaches"].append({
            "name": "Cart Operations",
            "description": "You can create carts and add items with known variant IDs"
        })
        guidance["example_queries"]["cart_create"] = """
        mutation {
          cartCreate(
            input: {
              lines: [
                {
                  quantity: 1
                  merchandiseId: "gid://shopify/ProductVariant/VARIANT_ID"
                }
              ]
            }
          ) {
            cart {
              id
              checkoutUrl
            }
          }
        }
        """
    
    # Add fallback strategies for common restrictions
    if "unauthenticated_read_product_listings" not in permissions and "product_types_access" in permissions:
        guidance["fallback_strategies"].append({
            "limitation": "No direct product listing access",
            "strategy": "Use productTypes + search query approach",
            "example": """
            # Step 1: Get product types
            {
              productTypes(first: 10) {
                edges {
                  node
                }
              }
            }
            
            # Step 2: Search using product types
            {
              search(query: "TypeName", types: [PRODUCT], first: 3) {
                edges {
                  node {
                    ... on Product {
                      id
                      title
                      variants(first: 1) {
                        edges {
                          node {
                            id
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
            """
        })
    
    # Add operations to avoid based on access_denied errors
    for denied in access_denied:
        if denied == "unauthenticated_read_product_listings":
            guidance["operations_to_avoid"].append({
                "operation": "Direct product queries",
                "reason": "Token lacks product listing permissions",
                "suggestion": "Try using search with product types instead"
            })
    
    return guidance


async def capture_network_tokens(url: str) -> List[str]:
    """Capture tokens from network requests by emulating browser behavior"""
    # This would ideally use a headless browser solution
    # For this MCP server, we can implement a simpler version:
    
    candidates = []
    client = await get_client()
    
    # Simulate page visit to trigger initial requests
    resp = await client.get(url)
    
    # Look for GraphQL endpoints in HTML
    soup = BeautifulSoup(resp.text, "html.parser")
    fetch_patterns = [
        r"fetch\(['\"](https://[^'\"]+graphql[^'\"]*)['\"]",
        r"url:\s*['\"](https://[^'\"]+graphql[^'\"]*)['\"]",
        r"endpoint:\s*['\"](https://[^'\"]+graphql[^'\"]*)['\"]"
    ]
    
    for script in soup.find_all("script"):
        if not script.string:
            continue
        for pattern in fetch_patterns:
            for match in re.finditer(pattern, script.string):
                endpoint = match.group(1)
                # Check window around this endpoint for tokens
                window = script.string[max(0, match.start() - 200):match.end() + 200]
                for token_pattern in TOKEN_PATTERNS:
                    for token_match in token_pattern.finditer(window):
                        candidates.append(token_match.group(1))
    
    return candidates


async def discover_shopify(url: str, max_assets: int = 30) -> Dict[str, Any]:
    """Enhanced discovery function with all improvements"""
    result: Dict[str, Any] = {
        "shopify": False,
        "host": None,
        "tokens_valid": [],
        "tokens_ranked": [],  # New field showing tokens by capability
        "tokens_invalid": [],
        "notes": [],
    }

    # Initial fetch (HTML) + HEAD (headers)
    try:
        html, headers = await asyncio.gather(fetch_text(url), fetch_head(url))
    except Exception as exc:
        result["notes"].append(f"initial fetch failed: {exc}")
        return result

    if not _is_shopify(headers, html):
        return result  # not a Shopify storefront

    result["shopify"] = True
    result["host"] = _canonical_host(html, urllib.parse.urlparse(url).netloc)

    # Collect asset URLs
    soup = BeautifulSoup(html, "html.parser")
    assets: List[str] = []
    for tag in soup.find_all(["script", "link"]):
        src = tag.get("src") or tag.get("href")
        if not src:
            continue
        if re.search(r"(cdn\.shopify|/assets/)", src):
            assets.append(urllib.parse.urljoin(url, src))
        if len(assets) >= max_assets:
            break

    # Scan HTML for token candidates
    candidates = set(_token_candidates(html))
    
    # Add specific checks for structured data
    json_ld = soup.find_all("script", type="application/ld+json")
    for script in json_ld:
        try:
            if script.string:
                candidates.update(_token_candidates(script.string))
        except Exception:
            pass
    
    # Check meta tags specifically
    for meta in soup.find_all("meta"):
        if meta.get("content") and len(meta.get("content", "")) > 20:  # Reasonable token length
            candidates.update(_token_candidates(meta.get("content", "")))
    
    # Add checks for data attributes - fixed selector
    for elem in soup.find_all():
        for attr_name, value in elem.attrs.items():
            if attr_name.startswith("data-") and isinstance(value, str) and len(value) > 20:
                candidates.update(_token_candidates(value))
    
    # Check for config objects
    config_patterns = [
        r"window\.[A-Za-z0-9_]+\s*=\s*({[^;]+});",
        r"var\s+[A-Za-z0-9_]+\s*=\s*({[^;]+});",
        r"const\s+[A-Za-z0-9_]+\s*=\s*({[^;]+});"
    ]
    
    for pattern in config_patterns:
        for match in re.finditer(pattern, html):
            candidates.update(_token_candidates(match.group(1)))

    # Scan assets for token candidates
    client = await get_client()
    for asset_url in assets:
        try:
            txt = (await client.get(asset_url)).text
            candidates.update(_token_candidates(txt))
        except Exception as exc:
            result["notes"].append(f"asset error: {asset_url} – {exc}")

    # Try to capture tokens from network requests
    try:
        network_tokens = await capture_network_tokens(url)
        candidates.update(network_tokens)
    except Exception as exc:
        result["notes"].append(f"network token capture error: {exc}")

    # Validate tokens with enhanced validation
    for tok in candidates:
        validation = await _validate_token(result["host"], tok)
        if validation["valid"]:
            result["tokens_valid"].append(tok)
            result["tokens_ranked"].append({
                "token": tok,
                "permissions": validation["permissions"]
            })
        else:
            result["tokens_invalid"].append(tok)
    
    # Sort tokens by capability
    result["tokens_ranked"].sort(key=lambda x: len(x["permissions"]), reverse=True)

    return result

###############################################################################
# MCP Resources for generic customer data
###############################################################################

# This section implements MCP resources for customer data
# These resources allow clients to access customer information in a standardized way
# through the MCP protocol. The resources are:
#
# - customer://name - The customer's full name (text/plain)
# - customer://email - The customer's email address (text/plain)
# - customer://phone - The customer's phone number (text/plain)
# - customer://shipping_address - The customer's shipping address (application/json)
# - customer://billing_address - The customer's billing address (application/json)
# - customer://profile - The customer's complete profile (application/json)
#
# The resources are backed by persistent storage in user_data/customer.json
# and can be updated using the update_customer_data tool.

# Helper function to load user data from persistent storage
def load_user_data():
    """Load user data from the user_data directory."""
    user_data_path = os.path.join(SCRIPT_DIR, "user_data")
    
    # Create user_data directory if it doesn't exist
    if not os.path.exists(user_data_path):
        os.makedirs(user_data_path)
    
    # Load customer data file if it exists
    customer_data_path = os.path.join(user_data_path, "customer.json")
    if os.path.exists(customer_data_path):
        with open(customer_data_path, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

# Helper function to save user data to persistent storage
def save_user_data(data):
    """Save user data to the user_data directory."""
    user_data_path = os.path.join(SCRIPT_DIR, "user_data")
    
    # Create user_data directory if it doesn't exist
    if not os.path.exists(user_data_path):
        os.makedirs(user_data_path)
    
    # Save customer data
    customer_data_path = os.path.join(user_data_path, "customer.json")
    with open(customer_data_path, "w") as f:
        json.dump(data, f, indent=2)

# Customer personal information
@mcp.resource(
    uri="customer://name",
    name="Customer Name",
    description="The customer's full name",
    mime_type="text/plain"
)
def customer_name():
    data = load_user_data()
    return data.get("name", "")

@mcp.resource(
    uri="customer://email",
    name="Customer Email",
    description="The customer's email address",
    mime_type="text/plain"
)
def customer_email():
    data = load_user_data()
    return data.get("email", "")

@mcp.resource(
    uri="customer://phone",
    name="Customer Phone",
    description="The customer's phone number",
    mime_type="text/plain"
)
def customer_phone():
    data = load_user_data()
    return data.get("phone", "")

# Customer shipping information
@mcp.resource(
    uri="customer://shipping_address",
    name="Shipping Address",
    description="The customer's shipping address",
    mime_type="application/json"
)
def customer_shipping_address():
    data = load_user_data()
    return data.get("shipping_address", {})

# Customer billing information
@mcp.resource(
    uri="customer://billing_address",
    name="Billing Address",
    description="The customer's billing address",
    mime_type="application/json"
)
def customer_billing_address():
    data = load_user_data()
    return data.get("billing_address", {})

# Complete customer data
@mcp.resource(
    uri="customer://profile",
    name="Customer Profile",
    description="The customer's complete profile information",
    mime_type="application/json"
)
def customer_profile():
    return load_user_data()

# Consolidated customer data tool for all CRUD operations
@mcp.tool()
async def customer_data(
    operation: str,
    field: Optional[str] = None,
    value: Optional[Any] = None,
    shipping_address: Optional[Dict[str, Any]] = None,
    billing_address: Optional[Dict[str, Any]] = None,
    custom_fields: Optional[Dict[str, Any]] = None,
) -> str:
    """Consolidated tool for all customer data operations (Create, Read, Update, Delete).
    
    This tool provides a unified interface for managing customer information.
    It can read, update, or delete specific fields, or retrieve the entire customer profile.
    
    Args:
        operation: The operation to perform - one of:
                  - "get": Get customer data (specific field or all data)
                  - "update": Update customer data (specific field or address)
                  - "delete": Delete a specific field or all data
        field: The specific field to operate on (for get/update/delete operations).
               Can be "name", "email", "phone", "shipping_address", "billing_address", 
               or any custom field name, or None to operate on the entire profile.
        value: The value to set (for update operations).
        shipping_address: Updated shipping address (for update operations).
        billing_address: Updated billing address (for update operations).
        custom_fields: Dictionary of custom fields to add/update (for update operations).
    
    Returns:
        JSON string containing the requested data or operation result
    """
    # Load customer data
    data = load_user_data()
    
    # GET operation - retrieve customer data
    if operation.lower() == "get":
        if field is None:
            # Return the entire profile
            return json.dumps(data)
        elif field in ["name", "email", "phone", "shipping_address", "billing_address"]:
            # Return a specific standard field
            return json.dumps({"field": field, "value": data.get(field, "")})
        else:
            # Return a custom field or empty if it doesn't exist
            return json.dumps({"field": field, "value": data.get(field, "")})
    
    # UPDATE operation - update customer data
    elif operation.lower() == "update":
        updates_made = False
        
        # Update a specific field
        if field is not None and value is not None:
            data[field] = value
            updates_made = True
        
        # Update shipping address
        if shipping_address is not None:
            # Handle migration from street to address1/address2 if needed
            if "shipping_address" in data and "street" in data["shipping_address"] and "address1" not in shipping_address:
                shipping_address["address1"] = data["shipping_address"]["street"]
            data["shipping_address"] = shipping_address
            updates_made = True
        
        # Update billing address
        if billing_address is not None:
            # Handle migration from street to address1/address2 if needed
            if "billing_address" in data and "street" in data["billing_address"] and "address1" not in billing_address:
                billing_address["address1"] = data["billing_address"]["street"]
            data["billing_address"] = billing_address
            updates_made = True
        
        # Update custom fields
        if custom_fields is not None:
            for key, value in custom_fields.items():
                data[key] = value
                updates_made = True
        
        # Save data if updates were made
        if updates_made:
            save_user_data(data)
            return json.dumps({"status": "success", "message": "Customer data updated", "data": data})
        else:
            return json.dumps({"error": "No updates provided"})
    
    # DELETE operation - delete customer data
    elif operation.lower() == "delete":
        if field is None:
            # Delete all customer data
            empty_data = {}
            save_user_data(empty_data)
            return json.dumps({"status": "success", "message": "All customer data deleted"})
        elif field in ["name", "email", "phone", "shipping_address", "billing_address"]:
            # Delete a specific standard field
            if field in data:
                del data[field]
                save_user_data(data)
                return json.dumps({"status": "success", "message": f"Field '{field}' deleted", "data": data})
            else:
                return json.dumps({"status": "warning", "message": f"Field '{field}' not found"})
        else:
            # Delete a custom field
            if field in data:
                del data[field]
                save_user_data(data)
                return json.dumps({"status": "success", "message": f"Field '{field}' deleted", "data": data})
            else:
                return json.dumps({"status": "warning", "message": f"Field '{field}' not found"})
    
    else:
        return json.dumps({"error": f"Unknown operation: {operation}"})

###############################################################################
# FastMCP server setup
###############################################################################

print("Shopify Storefront API MCP server initialized.", file=sys.stderr)


@mcp.tool()
async def shopify_discover(url: str) -> str:
    """Detect if a URL belongs to a Shopify storefront and discover authentication tokens with usage guidance.
    
    This tool analyzes any given URL to determine if it's powered by Shopify, extracts
    the canonical Shopify domain (.myshopify.com), and discovers any public Storefront API
    access tokens embedded in the page or its assets. It also provides guidance on how to
    effectively use the discovered tokens based on their permissions.
    
    IMPORTANT: This tool discovers tokens for the Shopify Storefront API only, not the Admin API.
    The Storefront API is a public-facing API with limited capabilities, primarily focused on
    browsing products, creating carts, and managing checkouts.
    
    Args:
        url: Full URL of any page on the suspected Shopify store. This can be the home page,
             a product page, collection page, or any other page on the domain.
    
    Returns:
        JSON string with the following structure:
        {
            "shopify": true/false,              // Whether this is a Shopify storefront
            "host": "example.myshopify.com",    // The canonical Shopify domain
            "tokens_valid": ["token1", ...],    // List of valid public access tokens
            "tokens_ranked": [                  // Tokens ranked by their capabilities
                {
                    "token": "token1",
                    "permissions": ["read_products", "cart_create", ...]
                },
                ...
            ],
            "tokens_invalid": [...],            // Tokens found but invalid
            "notes": [...],                     // Optional processing notes
            "api_guidance": [                   // Guidance for API usage
                {
                    "token": "token1",
                    "guidance": {
                        "recommended_approaches": [...],
                        "fallback_strategies": [...],
                        "operations_to_avoid": [...],
                        "example_queries": {...}
                    }
                }
            ]
        }
    
    Example:
        To check a suspected Shopify store:
        shopify_discover(url="https://example-store.com")
        
        In subsequent API calls, use the discovered host and token with shopify_storefront_graphql:
        shopify_storefront_graphql(
            mode="execute",
            host="example.myshopify.com",
            token="discovered_token",
            query="{ shop { name } }"
        )
        
        For full Storefront API capabilities analysis:
        shopify_storefront_graphql(
            mode="introspect",
            host="example.myshopify.com",
            token="discovered_token"
        )
    """
    result = await discover_shopify(url)
    
    # Add API usage guidance for each valid token
    if result["tokens_valid"]:
        result["api_guidance"] = []
        
        for token_info in result["tokens_ranked"]:
            token = token_info["token"]
            permissions = token_info.get("permissions", [])
            access_denied = token_info.get("access_denied_errors", [])
            
            guidance = generate_api_guidance(permissions, access_denied)
            
            result["api_guidance"].append({
                "token": token,
                "guidance": guidance
            })
    
    return json.dumps(result)


@mcp.tool()
async def shopify_storefront_graphql(
    mode: str,
    host: Optional[str] = None,
    token: Optional[str] = None,
    query: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
    api_version: str = DEFAULT_API_VERSION,
) -> str:
    """Execute Shopify Storefront GraphQL operations with intelligent guidance.
    
    This unified tool provides multiple modes for interacting with Shopify's Storefront API
    (NOT the Admin API) and offers intelligent guidance based on permissions and errors encountered.
    
    IMPORTANT: This tool is ONLY for the Shopify Storefront API, which is a public-facing, read-focused API 
    with limited mutation capabilities. It is NOT for the Admin API, which requires different authentication 
    and provides complete store management capabilities.
    
    The Storefront API allows you to:
    - Query products, collections, and shop information
    - Create and manage shopping carts
    - Process checkout for customers
    - Search products and collections
    
    Args:
        mode: Operating mode - one of:
              - "execute": Run a specific GraphQL query or mutation
              - "test": Test a query and get guidance if it fails
              - "introspect": Analyze accessible API operations and get workflow recommendations
        host: The Shopify store domain (e.g., "example.myshopify.com")
              If omitted, falls back to .env credentials
        token: The Storefront API access token (NOT an Admin API token)
              If omitted, falls back to .env credentials
        query: The GraphQL query/mutation to execute (required for "execute" and "test" modes)
        variables: Optional variables for the GraphQL query/mutation
        api_version: Shopify API version to use (defaults to 2025-04)
    
    Returns:
        JSON string with the operation result and guidance
    
    Typical Usage Patterns for Storefront API:
        
    1. Basic Query/Mutation:
       ```
       shopify_storefront_graphql(
           mode="execute",
           host="example.myshopify.com",
           token="your_storefront_token",
           query="{ shop { name } }"
       )
       ```
    
    2. Testing a Query (with Guidance):
       ```
       shopify_storefront_graphql(
           mode="test",
           host="example.myshopify.com",
           token="your_storefront_token",
           query="{ products(first: 5) { edges { node { id title } } } }"
       )
       ```
       
    3. API Capability Introspection:
       ```
       shopify_storefront_graphql(
           mode="introspect",
           host="example.myshopify.com",
           token="your_storefront_token"
       )
       ```
    
    When direct product access is denied, try the alternative pattern:
    
    ```
    # First get product types
    shopify_storefront_graphql(
        mode="execute",
        host="example.myshopify.com", 
        token="your_storefront_token",
        query="{ productTypes(first: 10) { edges { node } } }"
    )
    
    # Then search by product type
    shopify_storefront_graphql(
        mode="execute",
        host="example.myshopify.com",
        token="your_storefront_token",
        query='''
        {
          search(query: "TypeName", types: [PRODUCT], first: 5) {
            edges {
              node {
                ... on Product {
                  id
                  title
                  variants(first: 1) { edges { node { id } } }
                }
              }
            }
          }
        }
        '''
    )
    ```
    """
    host = host or (f"{ENV_STORE}.myshopify.com" if ENV_STORE else None)
    token = token or ENV_TOKEN

    if not all([host, token]):
        return json.dumps({"errors": [{"message": "Missing host and/or token"}]})

    headers = {
        "X-Shopify-Storefront-Access-Token": token,
        "Content-Type": "application/json",
        "User-Agent": "ShopifyMCP/0.3",
    }
    
    client = await get_client()
    
    # Handle different operating modes
    if mode == "execute":
        if not query:
            return json.dumps({"errors": [{"message": "Query is required for execute mode"}]})
            
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            resp = await client.post(
                f"https://{host}/api/{api_version}/graphql.json",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.text  # already JSON
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            msg = "Shopify Security Rejection" if code == 430 else f"HTTP {code}"
            return json.dumps({"errors": [{"message": msg}]})
        except Exception as exc:
            return json.dumps({"errors": [{"message": f"Unexpected error: {exc}"}]})
    
    elif mode == "test":
        if not query:
            return json.dumps({"errors": [{"message": "Query is required for test mode"}]})
            
        result = {
            "success": False,
            "data": None,
            "errors": None,
            "guidance": None
        }
        
        try:
            resp = await client.post(
                f"https://{host}/api/{api_version}/graphql.json",
                headers=headers,
                json={"query": query},
            )
            
            response_json = resp.json()
            result["data"] = response_json.get("data")
            result["errors"] = response_json.get("errors")
            
            if resp.status_code == 200 and not response_json.get("errors"):
                result["success"] = True
            else:
                # Generate guidance based on error types
                result["guidance"] = analyze_errors_and_suggest(query, response_json.get("errors", []))
        
        except Exception as e:
            result["errors"] = [{"message": str(e)}]
            result["guidance"] = {"suggestion": "Network or server error occurred. Check your host and token."}
        
        return json.dumps(result)
    
    elif mode == "introspect":
        # Test key schema components with simple queries
        test_components = [
            {"name": "shop", "query": "{shop{name}}"},
            {"name": "products", "query": "{products(first:1){edges{node{id}}}}"},
            {"name": "collections", "query": "{collections(first:1){edges{node{id}}}}"},
            {"name": "productTypes", "query": "{productTypes(first:1){edges{node}}}"},
            {"name": "search", "query": "{search(query:\"test\",types:PRODUCT,first:1){edges{node{__typename}}}}"},
            {"name": "cart_create", "query": "mutation{cartCreate(input:{}){cart{id}}}"},
            {"name": "checkout_create", "query": "mutation{checkoutCreate(input:{}){checkout{id}}}"},
            {"name": "customer_create", "query": "mutation{customerCreate(input:{email:\"test@example.com\",password:\"test\"}){customerUserErrors{message}}}"},
            {"name": "product_recommendations", "query": "{productRecommendations(productId:\"gid://shopify/Product/1\"){id}}"},
        ]
        
        results = {
            "accessible_components": [],
            "inaccessible_components": [],
            "recommended_operations": [],
            "example_queries": {},
            "workflow_guidance": {}
        }
        
        for component in test_components:
            try:
                resp = await client.post(
                    f"https://{host}/api/{api_version}/graphql.json",
                    headers=headers,
                    json={"query": component["query"]},
                )
                
                response_json = resp.json()
                if resp.status_code == 200 and not any("Access denied" in error.get("message", "") 
                                                    for error in response_json.get("errors", [])):
                    results["accessible_components"].append(component["name"])
                else:
                    results["inaccessible_components"].append(component["name"])
            except Exception:
                results["inaccessible_components"].append(component["name"])
        
        # Generate comprehensive workflow guidance
        guidance = generate_guidance_from_components(
            results["accessible_components"],
            results["inaccessible_components"]
        )
        
        results["workflow_guidance"] = guidance
        
        # Add example queries for discovered accessible components
        if "products" in results["accessible_components"]:
            results["example_queries"]["product_query"] = """
            {
              products(first: 10) {
                edges {
                  node {
                    id
                    title
                    description
                    handle
                    images(first: 1) {
                      edges {
                        node {
                          url
                        }
                      }
                    }
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
              }
            }
            """
        
        if "productTypes" in results["accessible_components"] and "search" in results["accessible_components"]:
            results["recommended_operations"].append({
                "operation": "Discover products via productTypes and search",
                "description": "When direct product access is restricted, use product types to guide search"
            })
            results["example_queries"]["product_discovery"] = """
            # Step 1: Get product types
            {
              productTypes(first: 10) {
                edges {
                  node
                }
              }
            }
            
            # Step 2: Search using those types
            {
              search(query: "Coffee", types: [PRODUCT], first: 3) {
                edges {
                  node {
                    ... on Product {
                      id
                      title
                      variants(first: 1) {
                        edges {
                          node {
                            id
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
            """
        
        if "cart_create" in results["accessible_components"]:
            results["example_queries"]["cart_creation"] = """
            mutation {
              cartCreate(
                input: {
                  lines: [
                    {
                      quantity: 1
                      merchandiseId: "gid://shopify/ProductVariant/VARIANT_ID"
                    }
                  ]
                }
              ) {
                cart {
                  id
                  checkoutUrl
                  estimatedCost {
                    totalAmount {
                      amount
                      currencyCode
                    }
                  }
                }
              }
            }
            """
        
        return json.dumps(results)
    
    else:
        return json.dumps({"errors": [{"message": f"Invalid mode: {mode}. Must be one of: execute, test, introspect"}]})


def analyze_errors_and_suggest(query: str, errors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze GraphQL errors and suggest alternatives"""
    guidance = {
        "suggestions": [],
        "alternative_queries": []
    }
    
    for error in errors:
        error_msg = error.get("message", "")
        
        # Access denied errors
        if "Access denied" in error_msg:
            required_scope = error.get("extensions", {}).get("requiredAccess", "")
            
            if "unauthenticated_read_product_listings" in required_scope:
                if "products" in query:
                    guidance["suggestions"].append(
                        "Token lacks permissions to access products directly. Try using search instead."
                    )
                    guidance["alternative_queries"].append("""
                    # First get product types
                    {
                      productTypes(first: 10) {
                        edges {
                          node
                        }
                      }
                    }
                    
                    # Then search by type
                    {
                      search(query: "Type", types: [PRODUCT], first: 3) {
                        edges {
                          node {
                            ... on Product {
                              id
                              title
                              variants(first: 1) {
                                edges {
                                  node {
                                    id
                                  }
                                }
                              }
                            }
                          }
                        }
                      }
                    }
                    """)
            
            # Add more specialized error handlers
        
        # Syntax errors
        elif "Syntax Error" in error_msg:
            guidance["suggestions"].append("GraphQL syntax error in query. Check for missing brackets or commas.")
    
    return guidance


def generate_guidance_from_components(accessible: List[str], inaccessible: List[str]) -> Dict[str, Any]:
    """Generate structured guidance based on component accessibility"""
    guidance = {
        "summary": "",
        "recommended_workflow": [],
        "warnings": []
    }
    
    # Determine token capabilities based on accessible components
    if "products" in accessible:
        guidance["summary"] = "This token has good product access capabilities."
        guidance["recommended_workflow"] = [
            "1. Query products directly",
            "2. Get variant IDs from product queries",
            "3. Create cart with selected variants"
        ]
    elif "productTypes" in accessible and "search" in accessible:
        guidance["summary"] = "This token has limited access but can discover products via search."
        guidance["recommended_workflow"] = [
            "1. Query product types to discover categories",
            "2. Use search with product types to find products",
            "3. Extract variant IDs from search results",
            "4. Create cart with discovered variant IDs"
        ]
    elif "cart_create" in accessible and "products" not in accessible:
        guidance["summary"] = "This token can only create carts but cannot access products directly."
        guidance["recommended_workflow"] = [
            "1. Try to discover products through alternative means",
            "2. If product discovery fails, you'll need to know variant IDs from another source",
            "3. Create cart with known variant IDs only"
        ]
        guidance["warnings"].append(
            "Product discovery is severely limited. You may need variant IDs from another source."
        )
    
    return guidance

###############################################################################
# __main__ entry‑point
###############################################################################

if __name__ == "__main__":
    if not ENV_STORE or not ENV_TOKEN:
        print("ℹ️  ENV credentials not set – server will rely on runtime host/token.", file=sys.stderr)
    try:
        mcp.run(transport="stdio")
    finally:
        if aio_client:
            asyncio.run(aio_client.aclose())
