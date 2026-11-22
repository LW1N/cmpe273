"""Payment service: charges an order, with an optional delay to simulate a slow dependency."""

import logging
import os
import time

from flask import Flask, jsonify, request

DELAY_MS = int(os.environ.get("PAYMENT_DELAY_MS", "0"))

app = Flask(__name__)
log = logging.getLogger("payment")


@app.post("/payments")
def pay():
    trace_id = request.headers.get("X-Trace-ID", "none")
    order = request.get_json()
    started = time.monotonic()
    log.info("trace_id=%s event=started order_id=%s amount=%s delay_ms=%d",
             trace_id, order.get("order_id"), order.get("amount"), DELAY_MS)
    time.sleep(DELAY_MS / 1000)
    latency_ms = (time.monotonic() - started) * 1000
    log.info("trace_id=%s event=finished status=200 latency_ms=%.1f", trace_id, latency_ms)
    return jsonify(order_id=order.get("order_id"), payment="paid")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("werkzeug").setLevel(logging.ERROR)  # its access lines duplicate our request logs
    app.run(host="127.0.0.1", port=5001)
