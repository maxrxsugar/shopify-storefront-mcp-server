#!/usr/bin/env python3
"""
Shopify Storefront MCP Server — dynamic discovery edition
=========================================================

This **single file** replaces your previous hard‑coded MCP server.  It adds

* **`shopify.discover`** – Given *any* URL, decide if it’s a Shopify storefront
  and (if so) harvest & validate any *public* Storefront Access Tokens*.
* **`shopify.graphql`** – Run an authenticated Storefront GraphQL query using a
  supplied `(host, token)` pair *or* fall back on credentials in `.env`.

> \* Public tokens are read‑only; many stores keep them server‑side, so discovery
> will legitimately return none in that case.

The code keeps compatibility with **FastMCP** & async `httpx` while removing the
mandatory env‑var requirement.  Agents can now:

1. `shopify.discover { url:"https://jackarcher.com" }`  → returns host & token.
2. `shopify.graphql  { host:"jackarcher.myshopify.com", token:"…", query:"…" }`

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
)
TOKEN_RE = re.compile(r"\b([a-f0-9]{32})\b", re.I)

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
    # Look for myshopify domain in HTML/JS first
    m = re.search(r"([\w-]+\.myshopify\.com)", html, re.I)
    if m:
        return m.group(1).lower()
    # Fallback to parsed host
    return fallback.lower()


def _token_candidates(text: str):
    lower = text.lower()
    for m in TOKEN_RE.finditer(text):
        window = lower[max(0, m.start() - 50) : m.end() + 50]
        if "storefront" in window and "token" in window:
            yield m.group(1)


async def _validate_token(host: str, token: str, api_version: str = DEFAULT_API_VERSION) -> bool:
    client = await get_client()
    payload = {"query": "{__schema{queryType{name}}}"}
    try:
        resp = await client.post(
            f"https://{host}/api/{api_version}/graphql.json",
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Storefront-Access-Token": token,
            },
            json=payload,
        )
        return resp.status_code == 200 and "__schema" in resp.text
    except httpx.RequestError:
        return False


async def discover_shopify(url: str, max_assets: int = 20) -> Dict[str, Any]:
    """Return discovery dict as described in doc‑string."""
    result: Dict[str, Any] = {
        "shopify": False,
        "host": None,
        "tokens_valid": [],
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

    # Scan HTML + assets for token candidates
    candidates = set(_token_candidates(html))
    client = await get_client()
    for asset_url in assets:
        try:
            txt = (await client.get(asset_url)).text
            candidates.update(_token_candidates(txt))
        except Exception as exc:
            result["notes"].append(f"asset error: {asset_url} – {exc}")

    # Validate tokens
    for tok in candidates:
        if await _validate_token(result["host"], tok):
            result["tokens_valid"].append(tok)
        else:
            result["tokens_invalid"].append(tok)

    return result

###############################################################################
# FastMCP server setup
###############################################################################

mcp = FastMCP("shopify_storefront", version="0.2.0")
print("Shopify Storefront MCP server initialized.", file=sys.stderr)


@mcp.tool()
async def shopify_discover(url: str) -> str:
    """Detect Shopify storefront, return host & any public Storefront tokens.

    Args:
        url: Full URL of the page to inspect (home‑page, product, collection…).

    Returns:
        JSON string with keys: shopify, host, tokens_valid, tokens_invalid, notes.
    """
    result = await discover_shopify(url)
    return json.dumps(result)


@mcp.tool()
async def shopify_storefront_graphql(
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    host: Optional[str] = None,
    token: Optional[str] = None,
    api_version: str = DEFAULT_API_VERSION,
) -> str:
    """Execute a Storefront GraphQL query.

    *If* `host` & `token` are omitted we fall back to `.env` credentials.
    """

    host = host or (f"{ENV_STORE}.myshopify.com" if ENV_STORE else None)
    token = token or ENV_TOKEN

    if not all([host, token]):
        return json.dumps({"errors": [{"message": "Missing host and/or token"}]})

    headers = {
        "X-Shopify-Storefront-Access-Token": token,
        "Content-Type": "application/json",
        "User-Agent": "ShopifyMCP/0.2",
    }
    payload: Dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables

    client = await get_client()
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
