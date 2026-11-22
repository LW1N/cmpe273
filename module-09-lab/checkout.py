"""Checkout service: calls Payment with a timeout and records request logs, latency, and success/failure counts."""

import logging
import threading
import time
import uuid

import requests
from flask import Flask, jsonify, request

PAYMENT_URL = "http://127.0.0.1:5001/payments"
PAYMENT_TIMEOUT_S = 1.0

app = Flask(__name__)
log = logging.getLogger("checkout")
metrics = {"requests_total": 0, "success_total": 0, "failure_total": 0, "last_latency_ms": 0.0}
metrics_lock = threading.Lock()


@app.post("/checkout")
def checkout():
    trace_id = uuid.uuid4().hex
    order = request.get_json()
    started = time.monotonic()
    log.info("trace_id=%s event=started order_id=%s", trace_id, order.get("order_id"))
    try:
        response = requests.post(PAYMENT_URL, json=order,
                                 headers={"X-Trace-ID": trace_id}, timeout=PAYMENT_TIMEOUT_S)
        response.raise_for_status()
        body, status = response.json(), 200
    except requests.Timeout:
        body, status = {"error": "payment_timeout"}, 504
    except requests.RequestException:
        body, status = {"error": "payment_unavailable"}, 502
    latency_ms = round((time.monotonic() - started) * 1000, 1)

    with metrics_lock:
        metrics["requests_total"] += 1
        metrics["success_total" if status == 200 else "failure_total"] += 1
        metrics["last_latency_ms"] = latency_ms
    log.log(logging.INFO if status == 200 else logging.ERROR,
            "trace_id=%s event=finished status=%d latency_ms=%.1f error=%s",
            trace_id, status, latency_ms, body.get("error"))
    return jsonify(**body, trace_id=trace_id), status


@app.get("/metrics")
def get_metrics():
    with metrics_lock:
        snapshot = dict(metrics)
    snapshot["error_rate"] = round(snapshot["failure_total"] / max(snapshot["requests_total"], 1), 2)
    return jsonify(snapshot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("werkzeug").setLevel(logging.ERROR)  # its access lines duplicate our request logs
    app.run(host="127.0.0.1", port=5000)
