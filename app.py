
import os
import re
import secrets
from threading import Lock

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from paypal_service import (
    PayPalError,
    create_order,
    capture_order,
)

# Load variables from .env
load_dotenv()

app = Flask(__name__)

# In-memory tracking for this demo only.
# Production applications should use a database.
orders_lock = Lock()
known_orders = {}
captured_orders = {}


@app.get("/")
def index():
    """Render the checkout page with the public PayPal Client ID."""
    client_id = os.getenv("PAYPAL_CLIENT_ID")

    if not client_id:
        return (
            "PAYPAL_CLIENT_ID is missing. Check your .env file.",
            500,
        )

    return render_template(
        "index.html",
        config_client_id=client_id,
    )


@app.get("/health")
def health():
    """Simple endpoint to check whether Flask is running."""
    return jsonify({"status": "ok"}), 200


@app.post("/api/orders")
def create_paypal_order():
    """Create a PayPal Sandbox order for the demo product."""
    try:
        # The server controls the amount; do not trust a price
        # supplied by the browser.
        order = create_order()

        order_id = order.get("id")
        if not order_id:
            app.logger.error("PayPal create-order response had no order ID.")
            return jsonify({"error": "PayPal did not return an order ID."}), 502

        with orders_lock:
            known_orders[order_id] = {
                "created": True,
                "captured": False,
            }

        return jsonify({"id": order_id}), 201

    except PayPalError as exc:
        app.logger.warning("PayPal create-order failed: %s", exc)
        return jsonify({
            "error": "Unable to create PayPal order.",
            "details": str(exc),
        }), 502

    except Exception:
        app.logger.exception("Unexpected create-order error")
        return jsonify({"error": "An unexpected server error occurred."}), 500


@app.post("/api/orders/<order_id>/capture")
def capture_paypal_order(order_id):
    """Capture an existing order created by this demo application."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", order_id):
        return jsonify({"error": "Invalid order ID."}), 400

    with orders_lock:
        order_info = known_orders.get(order_id)

        if not order_info:
            return jsonify({
                "error": "Unknown order. Create an order before capturing it."
            }), 404

        if order_info["captured"]:
            return jsonify({
                "error": "This order has already been captured."
            }), 409

        # Mark as being captured to prevent simultaneous duplicate requests.
        order_info["captured"] = True

    try:
        result = capture_order(order_id)

        status = result.get("status", "UNKNOWN")
        if status != "COMPLETED":
            with orders_lock:
                known_orders[order_id]["captured"] = False

            return jsonify({
                "error": "PayPal has not confirmed a completed payment.",
                "status": status,
                "details": result,
            }), 409

        with orders_lock:
            captured_orders[order_id] = result

        return jsonify({
            "id": order_id,
            "status": status,
            "details": result,
        }), 200

    except PayPalError as exc:
        with orders_lock:
            if order_id in known_orders:
                known_orders[order_id]["captured"] = False

        app.logger.warning("PayPal capture failed: %s", exc)
        return jsonify({
            "error": "Unable to capture PayPal payment.",
            "details": str(exc),
        }), 502

    except Exception:
        with orders_lock:
            if order_id in known_orders:
                known_orders[order_id]["captured"] = False

        app.logger.exception("Unexpected capture-order error")
        return jsonify({"error": "An unexpected server error occurred."}), 500


@app.post("/api/orders/<order_id>/cancel")
def cancel_paypal_order(order_id):
    """Acknowledge checkout cancellation; no payment is captured."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", order_id):
        return jsonify({"error": "Invalid order ID."}), 400

    with orders_lock:
        if order_id not in known_orders:
            return jsonify({"error": "Unknown order."}), 404

        if known_orders[order_id]["captured"]:
            return jsonify({
                "error": "This order has already been captured."
            }), 409

    return jsonify({
        "id": order_id,
        "status": "CANCELLED",
        "message": "Checkout cancelled. No capture was requested.",
    }), 200


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "Endpoint not found."}), 404


@app.errorhandler(405)
def method_not_allowed(_error):
    return jsonify({"error": "HTTP method not allowed."}), 405


if __name__ == "__main__":
    # Local development only. Do not enable debug mode in production.
    app.run(
        host="127.0.0.1",
        port=int(os.getenv("PORT", "5000")),
        debug=False,
    )