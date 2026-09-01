from flask import Flask, request, jsonify
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
app = Flask(__name__)

@app.get("/health")
def health():
    return jsonify(status="ok")

@app.get("/echo")
def echo():
    start = time.time()
    msg = request.args.get("msg", "")
    resp = {"echo": msg}
    logging.info(f'service=A endpoint=/echo status=ok latency_ms={int((time.time()-start)*1000)}')
    return jsonify(resp)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080)
