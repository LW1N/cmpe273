import logging
import os
import time
import uuid

import grpc
from flask import Flask, jsonify, request

import inventory_pb2
import inventory_pb2_grpc

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
INVENTORY_TARGET = os.environ.get("INVENTORY_TARGET", "127.0.0.1:50051")

# Reuse the channel and stub across requests.
channel = grpc.insecure_channel(INVENTORY_TARGET)
inventory = inventory_pb2_grpc.InventoryServiceStub(channel)

ERROR_MAPPING = {
    grpc.StatusCode.NOT_FOUND: ("item_not_found", 404),
    grpc.StatusCode.INVALID_ARGUMENT: ("invalid_delay", 400),
    grpc.StatusCode.DEADLINE_EXCEEDED: ("dependency_timeout", 504),
    grpc.StatusCode.UNAVAILABLE: ("dependency_unavailable", 503),
}


@app.get("/health")
def health():
    return jsonify(status="ok", service="checkout")


@app.get("/v1/availability/<item_id>")
def availability(item_id):
    request_id = str(uuid.uuid4())
    started = time.monotonic()
    status = 500
    try:
        delay_ms = int(request.args.get("delay_ms", "0"))
        if not 0 <= delay_ms <= 3000:
            raise ValueError("invalid_delay")

        response = inventory.GetItem(
            inventory_pb2.GetItemRequest(item_id=item_id, delay_ms=delay_ms),
            timeout=0.6,  # Order/Checkout → Inventory deadline: 600 ms.
            metadata=(("x-request-id", request_id),),
        )
        if response.item_id != item_id or response.available < 0:
            body, status = {"error": "dependency_bad_response"}, 502
        else:
            body, status = {
                "item_id": response.item_id,
                "available": response.available,
            }, 200
    except ValueError:
        body, status = {"error": "invalid_delay"}, 400
    except grpc.RpcError as exc:
        error, status = ERROR_MAPPING.get(
            exc.code(), ("dependency_bad_response", 502)
        )
        body = {"error": error}
    finally:
        elapsed_ms = round((time.monotonic() - started) * 1000, 1)
        app.logger.info(
            "request_id=%s status=%s elapsed_ms=%s",
            request_id, status, elapsed_ms,
        )

    result = jsonify(**body, request_id=request_id)
    result.status_code = status
    result.headers["X-Request-ID"] = request_id
    return result


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, threaded=True)
