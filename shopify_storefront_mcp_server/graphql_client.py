from __future__ import annotations
from typing import Any, Dict, Optional

from .utils import (
    DEFAULT_API_VERSION,
    ENV_STORE,
    ENV_TOKEN,
    DEFAULT_HEADERS,
    get_http_client,
)

class GraphQLClient:
    """Async Shopify Storefront GraphQL client."""

    def __init__(
        self,
        host: Optional[str] = None,
        token: Optional[str] = None,
        api_version: str = DEFAULT_API_VERSION,
    ) -> None:
        self.host = host or (f"{ENV_STORE}.myshopify.com" if ENV_STORE else None)
        self.token = token or ENV_TOKEN
        self.api_version = api_version

    async def execute(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.host or not self.token:
            raise ValueError("Missing host and/or token")

        headers = {
            "X-Shopify-Storefront-Access-Token": self.token,
            "Content-Type": "application/json",
            **DEFAULT_HEADERS,
        }
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        client = await get_http_client()
        resp = await client.post(
            f"https://{self.host}/api/{self.api_version}/graphql.json",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()
