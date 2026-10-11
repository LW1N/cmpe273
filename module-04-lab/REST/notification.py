"""Consume OrderCreated events and represent confirmations as log messages."""

import logging
import os
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
DELIVERIES = {}
DELIVERIES_LOCK = threading.Lock()


@app.get("/health")
def health():
    return jsonify(status="ok", service="notification")


@app.post("/v1/events")
def consume_event():
    event = request.get_json(silent=True)
    if (
        not isinstance(event, dict)
        or event.get("event_type") != "OrderCreated"
        or any(
            not isinstance(event.get(field), str) or not event[field].strip()
            for field in ("event_id", "order_id", "recipient", "item_id", "created_at")
        )
        or type(event.get("quantity")) is not int
        or event["quantity"] < 1
    ):
        return jsonify(error="invalid_event"), 400

    with DELIVERIES_LOCK:
        if event["event_id"] in DELIVERIES:
            return jsonify(DELIVERIES[event["event_id"]]), 200
        delivery = {
            "event_id": event["event_id"],
            "order_id": event["order_id"],
            "recipient": event["recipient"],
            "message": f"Order {event['order_id']} created: {event['quantity']} x {event['item_id']}.",
            "status": "logged",
            "delivered_at": datetime.now(timezone.utc).isoformat(),
        }
        app.logger.info("notification recipient=%s message=%s", delivery["recipient"], delivery["message"])
        DELIVERIES[event["event_id"]] = delivery
    return jsonify(delivery), 201


@app.get("/v1/notifications/<event_id>")
def get_notification(event_id):
    with DELIVERIES_LOCK:
        delivery = DELIVERIES.get(event_id)
    if delivery is None:
        return jsonify(error="notification_not_found"), 404
    return jsonify(delivery)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5002")), threaded=True)
