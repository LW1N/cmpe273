"""Order owns order records and consults Inventory over HTTP."""

import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
INVENTORY_URL = os.environ.get("INVENTORY_URL", "http://127.0.0.1:5001").rstrip("/")
ORDERS = {}
ORDERS_LOCK = threading.Lock()


def result(body, status, request_id):
    response = jsonify(**body, request_id=request_id)
    response.status_code = status
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
def health():
    return jsonify(status="ok", service="order")


@app.post("/v1/orders")
def create_order():
    request_id = str(uuid.uuid4())
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return result({"error": "invalid_order", "message": "A JSON object is required."}, 400, request_id)
    item_id = data.get("item_id")
    quantity = data.get("quantity", 1)
    if (
        not isinstance(item_id, str)
        or not item_id.strip()
        or len(item_id) > 100
        or "/" in item_id
        or type(quantity) is not int
        or quantity < 1
    ):
        return result({"error": "invalid_order", "message": "Provide an item_id and a positive integer quantity."}, 400, request_id)

    try:
        with requests.get(
            f"{INVENTORY_URL}/v1/items/{quote(item_id, safe='')}",
            params={"quantity": quantity},
            headers={"X-Request-ID": request_id},
            timeout=(0.2, 0.6),
            allow_redirects=False,
        ) as response:
            if response.status_code == 404:
                return result({"error": "item_not_found"}, 404, request_id)
            if response.status_code != 200:
                return result({"error": "dependency_bad_response"}, 502, request_id)
            inventory = response.json()
            if (
                not isinstance(inventory, dict)
                or inventory.get("item_id") != item_id
                or type(inventory.get("is_available")) is not bool
                or type(inventory.get("available")) is not int
                or inventory["available"] < 0
                or inventory["is_available"] != (inventory["available"] >= quantity)
            ):
                raise ValueError("Invalid inventory representation")
    except requests.Timeout:
        app.logger.warning("request_id=%s error=dependency_timeout", request_id)
        return result({"error": "dependency_timeout"}, 504, request_id)
    except ValueError:
        return result({"error": "dependency_bad_response"}, 502, request_id)
    except requests.RequestException:
        app.logger.warning("request_id=%s error=dependency_unavailable", request_id)
        return result({"error": "dependency_unavailable"}, 503, request_id)

    if not inventory["is_available"]:
        return result({"error": "item_unavailable", "item_id": item_id}, 409, request_id)

    order = {
        "order_id": str(uuid.uuid4()),
        "item_id": item_id,
        "quantity": quantity,
        "status": "created",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with ORDERS_LOCK:
        ORDERS[order["order_id"]] = order
    # Represents the event production point; no notification transport is implemented.
    app.logger.info("event=OrderCreated order_id=%s request_id=%s", order["order_id"], request_id)
    response = result(order, 201, request_id)
    response.headers["Location"] = f"/v1/orders/{order['order_id']}"
    return response


@app.get("/v1/orders/<order_id>")
def get_order(order_id):
    with ORDERS_LOCK:
        order = ORDERS.get(order_id)
    if order is None:
        return jsonify(error="order_not_found"), 404
    return jsonify(order)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), threaded=True)
