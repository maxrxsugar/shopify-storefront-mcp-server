from __future__ import annotations
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

# Load environment variables
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

ENV_TOKEN: Optional[str] = os.getenv("SHOPIFY_STOREFRONT_ACCESS_TOKEN")
ENV_STORE: Optional[str] = os.getenv("SHOPIFY_STORE_NAME")
DEFAULT_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2025-04")

DEFAULT_HEADERS = {
    "User-Agent": "ShopifyMCP/0.2 (+https://example.com)"
}

_http_client: Optional[httpx.AsyncClient] = None

async def get_http_client() -> httpx.AsyncClient:
    """Return a shared AsyncClient instance."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=15.0)
    return _http_client


def get_existing_http_client() -> Optional[httpx.AsyncClient]:
    """Return the client if it has been created."""
    return _http_client
