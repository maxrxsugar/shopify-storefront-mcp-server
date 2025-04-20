# Shopify Storefront MCP Server

This server provides access to the Shopify Storefront API via MCP, allowing AI assistants to query and interact with your Shopify store data.

## Features

- Access to product, collection, and inventory data
- Cart creation and management
- Support for GraphQL queries and mutations
- Automatic token handling and validation
- Easy integration with MCP-compatible AI assistants

## Setup Instructions

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and configure your environment variables
4. Generate a Storefront API token via Shopify Admin (see below)
5. Run the server: `python shopify_storefront_mcp_server.py`

## Environment Variables

Create a `.env` file using the provided `.env.example` as a template:

```
# Required
SHOPIFY_STOREFRONT_ACCESS_TOKEN=your_storefront_token
SHOPIFY_STORE_NAME=your-store-name

# Optional
SHOPIFY_API_VERSION=2025-04
SHOPIFY_BUYER_IP=127.0.0.1
```

## Generating a Storefront API Token

1. Log in to your Shopify admin
2. Go to **Apps and sales channels** > **Develop apps** > **Create an app**
3. Name your app (e.g., "MCP Storefront")
4. Go to **API credentials** > **Configure Storefront API scopes**
5. Select necessary scopes:
   - `unauthenticated_read_product_listings`
   - `unauthenticated_read_product_inventory`
   - `unauthenticated_read_product_pricing`
   - `unauthenticated_write_checkouts`
   - `unauthenticated_read_content`
6. Save and copy the generated Storefront API access token
7. Add the token to your `.env` file as `SHOPIFY_STOREFRONT_ACCESS_TOKEN`

## Usage Examples

Running with the MCP server:

```
python shopify_storefront_mcp_server.py
```

The server exposes the following MCP tools:

- `storefront_execute_graphql`: Execute GraphQL queries against the Storefront API
- `get_storefront_token_status`: Check the status of your configured tokens

## Troubleshooting

If you encounter authentication errors:

1. Verify token format: Storefront API tokens should start with `shpsa_` (newer) or `shpat_` (older)
2. Check store name: Ensure SHOPIFY_STORE_NAME is correct (without .myshopify.com)
3. Check API version: Make sure the API version is supported
4. Test token: Use cURL to test your token directly:
   ```
   curl -X POST \
     https://your-store.myshopify.com/api/2025-04/graphql.json \
     -H "Content-Type: application/json" \
     -H "X-Shopify-Storefront-Access-Token: your_token" \
     -d '{"query": "query { shop { name } }"}'
   ```
5. Regenerate token: If issues persist, create a new token with proper scopes

## Security Considerations

- Never commit your `.env` file or any files containing API tokens
- Use environment variables for all sensitive information
- Consider setting up IP restrictions in your Shopify Admin
- Review the permissions granted to your Storefront API token

