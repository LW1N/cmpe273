import logging
import os
import time
from flask import Flask, jsonify, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Inventory alone owns stock quantities. Availability queries are read-only.
STOCK = {"sku-123": 7, "sku-456": 0, "sku-789": 3}

@app.get("/health")
def health():
    return jsonify(status="ok", service="inventory")

@app.get("/v1/items/<item_id>")
def get_item(item_id):
    request_id = request.headers.get("X-Request-ID", "none")
    try:
        quantity = int(request.args.get("quantity", "1"))
        if quantity < 1:
            raise ValueError()
    except ValueError:
        return jsonify(error="invalid_quantity"), 400
    try:
        delay_ms = int(request.args.get("delay_ms", "0"))
        if not 0 <= delay_ms <= 3000:
            raise ValueError()
    except ValueError:
        return jsonify(error="invalid_delay"), 400
    app.logger.info("request_id=%s event=started", request_id)
    time.sleep(delay_ms / 1000)
    app.logger.info("request_id=%s event=finished", request_id)
    if item_id not in STOCK:
        return jsonify(error="item_not_found"), 404
    # Retain the original integer `available` field for the copied checkout client.
    return jsonify(item_id=item_id, available=STOCK[item_id],
                   is_available=STOCK[item_id] >= quantity)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5001")), threaded=True)
