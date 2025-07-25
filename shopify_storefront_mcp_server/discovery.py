from __future__ import annotations

import asyncio
import json
import re
import urllib.parse
from typing import Any, Dict, List

from bs4 import BeautifulSoup

from . import mcp
from .graphql_client import GraphQLClient
from .utils import (
    DEFAULT_API_VERSION,
    get_http_client,
)

# Heuristic patterns for discovery
HDR_PREFIXES = (
    "x‑shopify",
    "x‑shop",
    "x‑shardid",
    "x‑sorting-hat",
)
HTML_MARKERS = (
    re.compile(r"cdn\.shopify(?:cdn)?\.net|cdn\.shopify\.com", re.I),
    re.compile(r"class=[\"'][^\"']*shopify-section", re.I),
    re.compile(r"window\.Shopify|Shopify\.theme", re.I),
    re.compile(r"[a-zA-Z0-9-]+\.myshopify\.com", re.I),
)

TOKEN_PATTERNS = [
    re.compile(r"\b([a-f0-9]{32})\b", re.I),
    re.compile(r"\b([a-f0-9]{24,64})\b", re.I),
    re.compile(r"\"(eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,})\"", re.I),
]

MYSHOPIFY_PATTERNS = [
    re.compile(r"[\"'](https?://)?([a-zA-Z0-9][a-zA-Z0-9-]*\.myshopify\.com)[\"'/]", re.I),
    re.compile(r"\b(https?://)?([a-zA-Z0-9][a-zA-Z0-9-]*\.myshopify\.com)\b", re.I),
    re.compile(r"[\"']myshopify_domain[\"']\s*:\s*[\"']([^\"']+)[\"']", re.I),
]


async def fetch_text(url: str) -> str:
    client = await get_http_client()
    resp = await client.get(url, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


async def fetch_head(url: str):
    client = await get_http_client()
    resp = await client.head(url, follow_redirects=True)
    return resp.headers


def _is_shopify(headers, html: str) -> bool:
    hdr_hit = any(h.lower().startswith(HDR_PREFIXES) for h in headers)
    html_hit = any(rx.search(html) for rx in HTML_MARKERS)
    return hdr_hit or html_hit


def _canonical_host(html: str, fallback: str) -> str:
    for pattern in MYSHOPIFY_PATTERNS:
        m = pattern.search(html)
        if m:
            domain = m.group(2) if len(m.groups()) > 1 and m.group(2) else m.group(1)
            return domain.lower()
    shop_pattern = re.search(r"Shopify\.shop\s*=\s*[\"']([^\"']+)[\"']", html)
    if shop_pattern:
        shop = shop_pattern.group(1)
        if ".myshopify.com" in shop:
            return shop.lower()
        return f"{shop}.myshopify.com".lower()
    m = re.search(r"([\w-]+\.myshopify\.com)", html, re.I)
    if m:
        return m.group(1).lower()
    return fallback.lower()


def _token_candidates(text: str):
    lower = text.lower()
    token_contexts = [
        "storefront",
        "token",
        "access_token",
        "accesstoken",
        "apikey",
        "api_key",
        "shopify",
        "graphql",
        "storefrontaccesstoken",
        "x-shopify",
        "publicaccesstoken",
        "client_id",
        "clientid",
    ]
    init_patterns = [
        r"ShopifyBuy\.buildClient\({[^}]*}",
        r"createClient\({[^}]*}",
        r"Shopify\.loadFeatures\({[^}]*}",
        r"new Client\({[^}]*}",
        r"fetch\([^)]*\"/api/[^\"]*\"",
    ]
    candidates: List[str] = []
    for pattern in TOKEN_PATTERNS:
        for m in pattern.finditer(text):
            window = lower[max(0, m.start() - 100) : m.end() + 100]
            if any(ctx in window for ctx in token_contexts):
                candidates.append(m.group(1))
            for init in init_patterns:
                if re.search(init, window):
                    candidates.append(m.group(1))
    return candidates


async def _validate_token(host: str, token: str, api_version: str = DEFAULT_API_VERSION) -> Dict[str, Any]:
    client = GraphQLClient(host=host, token=token, api_version=api_version)
    results = {"valid": False, "permissions": [], "access_denied_errors": []}
    schema_query = {"query": "{__schema{queryType{name}}}"}
    permission_tests = [
        {"name": "unauthenticated_read_product_listings", "query": "{products(first:1){edges{node{id}}}}"},
        {"name": "cart_create", "query": "mutation{cartCreate(input:{}){cart{id}}}"},
        {"name": "unauthenticated_read_content", "query": "{shop{name description}}"},
        {"name": "unauthenticated_read_customer", "query": "mutation{customerAccessTokenCreate(input:{email:\"test@example.com\",password:\"test\"}){customerUserErrors{message}}}"},
        {"name": "unauthenticated_read_collection_listings", "query": "{collections(first:1){edges{node{id}}}}"},
        {"name": "product_types_access", "query": "{productTypes(first:1){edges{node}}}"},
        {"name": "search_access", "query": "{search(query:\"test\",types:PRODUCT,first:1){edges{node{__typename}}}}"},
        {"name": "metafields_access", "query": "{shop{metafields(first:1){edges{node{id}}}}}"},
    ]
    try:
        resp = await client.execute(schema_query["query"])
        if "__schema" in json.dumps(resp):
            results["valid"] = True
            for test in permission_tests:
                try:
                    data = await client.execute(test["query"])
                    if data and "errors" not in data:
                        results["permissions"].append(test["name"])
                except Exception:
                    results["access_denied_errors"].append(test["name"])
    except Exception:
        return results
    return results


def generate_api_guidance(permissions: List[str], access_denied: List[str]) -> Dict[str, Any]:
    guidance = {"recommended_approaches": [], "fallback_strategies": [], "operations_to_avoid": [], "example_queries": {}}
    if "unauthenticated_read_product_listings" in permissions:
        guidance["recommended_approaches"].append({"name": "Direct Product Queries", "description": "You can directly query products, variants, and collections"})
        guidance["example_queries"]["product_query"] = "{ products(first: 10) { edges { node { id title variants(first: 1) { edges { node { id } } } } } } }"
    if "cart_create" in permissions:
        guidance["recommended_approaches"].append({"name": "Cart Operations", "description": "You can create carts and add items with known variant IDs"})
        guidance["example_queries"]["cart_create"] = "mutation { cartCreate( input: { lines: [ { quantity: 1 merchandiseId: \"gid://shopify/ProductVariant/VARIANT_ID\" } ] } ) { cart { id checkoutUrl } } }"
    if "unauthenticated_read_product_listings" not in permissions and "product_types_access" in permissions:
        guidance["fallback_strategies"].append({"limitation": "No direct product listing access", "strategy": "Use productTypes + search query approach", "example": "{ productTypes(first: 10) { edges { node } } } { search(query: \"TypeName\", types: [PRODUCT], first: 3) { edges { node { ... on Product { id title variants(first: 1) { edges { node { id } } } } } } } }"})
    for denied in access_denied:
        if denied == "unauthenticated_read_product_listings":
            guidance["operations_to_avoid"].append({"operation": "Direct product queries", "reason": "Token lacks product listing permissions", "suggestion": "Try using search with product types instead"})
    return guidance


async def capture_network_tokens(url: str) -> List[str]:
    candidates: List[str] = []
    client = await get_http_client()
    resp = await client.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    fetch_patterns = [
        r"fetch\(['\"](https://[^'\"]+graphql[^'\"]*)['\"]",
        r"url:\s*['\"](https://[^'\"]+graphql[^'\"]*)['\"]",
        r"endpoint:\s*['\"](https://[^'\"]+graphql[^'\"]*)['\"]",
    ]
    for script in soup.find_all("script"):
        if not script.string:
            continue
        for pattern in fetch_patterns:
            for match in re.finditer(pattern, script.string):
                window = script.string[max(0, match.start() - 200):match.end() + 200]
                for token_pattern in TOKEN_PATTERNS:
                    for token_match in token_pattern.finditer(window):
                        candidates.append(token_match.group(1))
    return candidates


async def discover_shopify(url: str, max_assets: int = 30) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "shopify": False,
        "host": None,
        "tokens_valid": [],
        "tokens_ranked": [],
        "tokens_invalid": [],
        "notes": [],
    }
    try:
        html, headers = await asyncio.gather(fetch_text(url), fetch_head(url))
    except Exception as exc:
        result["notes"].append(f"initial fetch failed: {exc}")
        return result
    if not _is_shopify(headers, html):
        return result
    result["shopify"] = True
    result["host"] = _canonical_host(html, urllib.parse.urlparse(url).netloc)

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

    candidates = set(_token_candidates(html))

    json_ld = soup.find_all("script", type="application/ld+json")
    for script in json_ld:
        if script.string:
            candidates.update(_token_candidates(script.string))

    for meta in soup.find_all("meta"):
        if meta.get("content") and len(meta.get("content", "")) > 20:
            candidates.update(_token_candidates(meta.get("content", "")))

    for elem in soup.find_all():
        for attr_name, value in elem.attrs.items():
            if attr_name.startswith("data-") and isinstance(value, str) and len(value) > 20:
                candidates.update(_token_candidates(value))

    config_patterns = [
        r"window\.[A-Za-z0-9_]+\s*=\s*({[^;]+});",
        r"var\s+[A-Za-z0-9_]+\s*=\s*({[^;]+});",
        r"const\s+[A-Za-z0-9_]+\s*=\s*({[^;]+});",
    ]
    for pattern in config_patterns:
        for match in re.finditer(pattern, html):
            candidates.update(_token_candidates(match.group(1)))

    client = await get_http_client()
    for asset_url in assets:
        try:
            txt = (await client.get(asset_url)).text
            candidates.update(_token_candidates(txt))
        except Exception as exc:
            result["notes"].append(f"asset error: {asset_url} – {exc}")

    try:
        network_tokens = await capture_network_tokens(url)
        candidates.update(network_tokens)
    except Exception as exc:
        result["notes"].append(f"network token capture error: {exc}")

    for tok in candidates:
        validation = await _validate_token(result["host"], tok)
        if validation["valid"]:
            result["tokens_valid"].append(tok)
            result["tokens_ranked"].append({"token": tok, "permissions": validation["permissions"]})
        else:
            result["tokens_invalid"].append(tok)

    result["tokens_ranked"].sort(key=lambda x: len(x["permissions"]), reverse=True)
    return result


@mcp.tool()
async def shopify_discover(url: str) -> str:
    result = await discover_shopify(url)
    if result["tokens_valid"]:
        result["api_guidance"] = []
        for token_info in result["tokens_ranked"]:
            token = token_info["token"]
            permissions = token_info.get("permissions", [])
            access_denied = token_info.get("access_denied_errors", [])
            guidance = generate_api_guidance(permissions, access_denied)
            result["api_guidance"].append({"token": token, "guidance": guidance})
    return json.dumps(result)
