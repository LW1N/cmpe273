import logging
import time
from flask import Flask, jsonify, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.get("/health")
def health():
    return jsonify(status="ok", service="inventory")

@app.get("/v1/items/<item_id>")
def get_item(item_id):
    request_id = request.headers.get("X-Request-ID", "none")
    try:
        delay_ms = int(request.args.get("delay_ms", "0"))
        if not 0 <= delay_ms <= 3000:
            raise ValueError()
    except ValueError:
        return jsonify(error="invalid_delay"), 400
    app.logger.info("request_id=%s event=started", request_id)
    time.sleep(delay_ms / 1000)
    app.logger.info("request_id=%s event=finished", request_id)
    if item_id != "sku-123":
        return jsonify(error="item_not_found"), 404
    return jsonify(item_id=item_id, available=7)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, threaded=True)