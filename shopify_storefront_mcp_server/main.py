from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, Dict, List, Optional

from . import mcp
from .graphql_client import GraphQLClient
from .utils import DEFAULT_API_VERSION, ENV_STORE, ENV_TOKEN, get_http_client, get_existing_http_client


@mcp.tool()
async def shopify_storefront_graphql(
    mode: str,
    host: Optional[str] = None,
    token: Optional[str] = None,
    query: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
    api_version: str = DEFAULT_API_VERSION,
) -> str:
    """Execute Shopify Storefront GraphQL queries."""
    host = host or (f"{ENV_STORE}.myshopify.com" if ENV_STORE else None)
    token = token or ENV_TOKEN
    if not all([host, token]):
        return json.dumps({"errors": [{"message": "Missing host and/or token"}]})

    client = GraphQLClient(host=host, token=token, api_version=api_version)

    if mode == "execute":
        if not query:
            return json.dumps({"errors": [{"message": "Query is required for execute mode"}]})
        try:
            data = await client.execute(query, variables)
            return json.dumps(data)
        except Exception as exc:
            return json.dumps({"errors": [{"message": str(exc)}]})

    elif mode == "test":
        if not query:
            return json.dumps({"errors": [{"message": "Query is required for test mode"}]})
        result = {"success": False, "data": None, "errors": None, "guidance": None}
        try:
            data = await client.execute(query)
            result["data"] = data.get("data")
            result["errors"] = data.get("errors")
            if data.get("errors") is None:
                result["success"] = True
            else:
                result["guidance"] = analyze_errors_and_suggest(query, data.get("errors"))
        except Exception as exc:
            result["errors"] = [{"message": str(exc)}]
            result["guidance"] = {"suggestion": "Network or server error occurred"}
        return json.dumps(result)

    elif mode == "introspect":
        test_components = [
            {"name": "shop", "query": "{shop{name}}"},
            {"name": "products", "query": "{products(first:1){edges{node{id}}}}"},
            {"name": "collections", "query": "{collections(first:1){edges{node{id}}}}"},
            {"name": "productTypes", "query": "{productTypes(first:1){edges{node}}}"},
            {"name": "search", "query": "{search(query:\"test\",types:PRODUCT,first:1){edges{node{__typename}}}}"},
            {"name": "cart_create", "query": "mutation{cartCreate(input:{}){cart{id}}}"},
        ]
        results = {
            "accessible_components": [],
            "inaccessible_components": [],
        }
        for comp in test_components:
            try:
                data = await client.execute(comp["query"])
                if data.get("errors"):
                    results["inaccessible_components"].append(comp["name"])
                else:
                    results["accessible_components"].append(comp["name"])
            except Exception:
                results["inaccessible_components"].append(comp["name"])
        guidance = generate_guidance_from_components(
            results["accessible_components"],
            results["inaccessible_components"],
        )
        results["workflow_guidance"] = guidance
        return json.dumps(results)

    return json.dumps({"errors": [{"message": f"Invalid mode: {mode}"}]})


def analyze_errors_and_suggest(query: str, errors: List[Dict[str, Any]]) -> Dict[str, Any]:
    guidance = {"suggestions": [], "alternative_queries": []}
    for error in errors:
        msg = error.get("message", "")
        if "Access denied" in msg and "products" in query:
            guidance["suggestions"].append(
                "Token lacks permissions to access products directly. Try using search instead."
            )
    return guidance


def generate_guidance_from_components(accessible: List[str], inaccessible: List[str]) -> Dict[str, Any]:
    guidance = {"summary": "", "recommended_workflow": [], "warnings": []}
    if "products" in accessible:
        guidance["summary"] = "This token has good product access capabilities."
        guidance["recommended_workflow"] = [
            "1. Query products directly",
            "2. Get variant IDs from product queries",
            "3. Create cart with selected variants",
        ]
    elif "productTypes" in accessible and "search" in accessible:
        guidance["summary"] = "This token has limited access but can discover products via search."
        guidance["recommended_workflow"] = [
            "1. Query product types to discover categories",
            "2. Use search with product types to find products",
            "3. Extract variant IDs from search results",
        ]
    elif "cart_create" in accessible and "products" not in accessible:
        guidance["summary"] = "This token can only create carts but cannot access products directly."
        guidance["warnings"].append(
            "Product discovery is severely limited. You may need variant IDs from another source."
        )
    return guidance


def main() -> None:
    if not ENV_STORE or not ENV_TOKEN:
        print("ℹ️  ENV credentials not set – server will rely on runtime host/token.", file=sys.stderr)
    try:
        mcp.run(transport="stdio")

    finally:
        client = get_existing_http_client()
        if client:
            asyncio.run(client.aclose())
if __name__ == "__main__":
    main()
