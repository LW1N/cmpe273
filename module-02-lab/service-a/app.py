import os
import requests
from flask import Flask, jsonify

app = Flask(__name__)
service_b_url = os.environ.get("SERVICE_B_URL", "http://service-b:5001")

@app.get("/health")
def health():
    return jsonify(status="ok", service="a")

@app.get("/call-b")
def call_b():
    try:
        response = requests.get(f"{service_b_url}/health", timeout=2)
        return jsonify(service="a", dependency=response.json())
    except requests.RequestException as exc:
        app.logger.warning("dependency failure: %s", exc)
        return jsonify(service="a", dependency="unavailable"), 503

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)