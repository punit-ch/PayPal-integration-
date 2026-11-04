import os
import uuid

import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv(
    "PAYPAL_BASE_URL",
    "https://api-m.sandbox.paypal.com",
).rstrip("/")

CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
CURRENCY = os.getenv("PAYPAL_CURRENCY", "USD")

if not CLIENT_ID or not CLIENT_SECRET:
    raise RuntimeError(
        "Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in .env"
    )


class PayPalError(Exception):
    pass


def get_access_token():
    try:
        response = requests.post(
            f"{BASE_URL}/v1/oauth2/token",
            auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
            data={"grant_type": "client_credentials"},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except (requests.RequestException, ValueError, KeyError):
        raise PayPalError("Could not authenticate with PayPal.")


def paypal_request(method, path, payload=None, request_id=None):
    token = get_access_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    if request_id:
        headers["PayPal-Request-Id"] = request_id

    try:
        response = requests.request(
            method,
            f"{BASE_URL}{path}",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json() if response.content else {}
    except (requests.RequestException, ValueError):
        raise PayPalError("PayPal could not complete the request.")


def create_order():
    # Demo product: the amount is controlled by the server.
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": "demo-product",
                "description": "PayPal Sandbox Demo Product",
                "amount": {
                    "currency_code": CURRENCY,
                    "value": "5.00",
                },
            }
        ],
    }

    # A unique request ID makes retries of this creation request safer.
    return paypal_request(
        "POST",
        "/v2/checkout/orders",
        payload=payload,
        request_id=str(uuid.uuid4()),
    )


def capture_order(order_id, request_id):
    return paypal_request(
        "POST",
        f"/v2/checkout/orders/{order_id}/capture",
        payload={},
        request_id=request_id,
    )