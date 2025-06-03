from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from . import mcp
from .utils import ROOT_DIR


def load_user_data() -> Dict[str, Any]:
    """Load user data from the user_data directory."""
    user_data_path = os.path.join(ROOT_DIR, "user_data")
    if not os.path.exists(user_data_path):
        os.makedirs(user_data_path)
    customer_data_path = os.path.join(user_data_path, "customer.json")
    if os.path.exists(customer_data_path):
        with open(customer_data_path, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def save_user_data(data: Dict[str, Any]) -> None:
    """Save user data to the user_data directory."""
    user_data_path = os.path.join(ROOT_DIR, "user_data")
    if not os.path.exists(user_data_path):
        os.makedirs(user_data_path)
    customer_data_path = os.path.join(user_data_path, "customer.json")
    with open(customer_data_path, "w") as f:
        json.dump(data, f, indent=2)


@mcp.resource(uri="customer://name", name="Customer Name", description="The customer's full name", mime_type="text/plain")
def customer_name() -> str:
    data = load_user_data()
    return data.get("name", "")


@mcp.resource(uri="customer://email", name="Customer Email", description="The customer's email address", mime_type="text/plain")
def customer_email() -> str:
    data = load_user_data()
    return data.get("email", "")


@mcp.resource(uri="customer://phone", name="Customer Phone", description="The customer's phone number", mime_type="text/plain")
def customer_phone() -> str:
    data = load_user_data()
    return data.get("phone", "")


@mcp.resource(uri="customer://shipping_address", name="Shipping Address", description="The customer's shipping address", mime_type="application/json")
def customer_shipping_address() -> Dict[str, Any]:
    data = load_user_data()
    return data.get("shipping_address", {})


@mcp.resource(uri="customer://billing_address", name="Billing Address", description="The customer's billing address", mime_type="application/json")
def customer_billing_address() -> Dict[str, Any]:
    data = load_user_data()
    return data.get("billing_address", {})


@mcp.resource(uri="customer://profile", name="Customer Profile", description="The customer's complete profile information", mime_type="application/json")
def customer_profile() -> Dict[str, Any]:
    return load_user_data()


@mcp.tool()
async def customer_data(
    operation: str,
    field: Optional[str] = None,
    value: Optional[Any] = None,
    shipping_address: Optional[Dict[str, Any]] = None,
    billing_address: Optional[Dict[str, Any]] = None,
    custom_fields: Optional[Dict[str, Any]] = None,
) -> str:
    """CRUD operations for local customer data."""
    data = load_user_data()

    if operation.lower() == "get":
        if field is None:
            return json.dumps(data)
        return json.dumps({"field": field, "value": data.get(field, "")})

    elif operation.lower() == "update":
        updates_made = False
        if field is not None and value is not None:
            data[field] = value
            updates_made = True
        if shipping_address is not None:
            if "shipping_address" in data and "street" in data["shipping_address"] and "address1" not in shipping_address:
                shipping_address["address1"] = data["shipping_address"]["street"]
            data["shipping_address"] = shipping_address
            updates_made = True
        if billing_address is not None:
            if "billing_address" in data and "street" in data["billing_address"] and "address1" not in billing_address:
                billing_address["address1"] = data["billing_address"]["street"]
            data["billing_address"] = billing_address
            updates_made = True
        if custom_fields is not None:
            for key, val in custom_fields.items():
                data[key] = val
                updates_made = True
        if updates_made:
            save_user_data(data)
            return json.dumps({"status": "success", "message": "Customer data updated", "data": data})
        return json.dumps({"error": "No updates provided"})

    elif operation.lower() == "delete":
        if field is None:
            save_user_data({})
            return json.dumps({"status": "success", "message": "All customer data deleted"})
        if field in data:
            del data[field]
            save_user_data(data)
            return json.dumps({"status": "success", "message": f"Field '{field}' deleted", "data": data})
        return json.dumps({"status": "warning", "message": f"Field '{field}' not found"})

    return json.dumps({"error": f"Unknown operation: {operation}"})
