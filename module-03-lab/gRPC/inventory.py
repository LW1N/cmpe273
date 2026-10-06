import logging
import threading
from concurrent import futures

import grpc
import inventory_pb2
import inventory_pb2_grpc

logging.basicConfig(level=logging.INFO)


class InventoryService(inventory_pb2_grpc.InventoryServiceServicer):
    def GetItem(self, request, context):
        metadata = dict(context.invocation_metadata())
        request_id = metadata.get("x-request-id", "none")

        if not 0 <= request.delay_ms <= 3000:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invalid_delay")

        logging.info("request_id=%s event=started", request_id)

        # Stop simulated work when the client cancels or its deadline expires.
        cancelled = threading.Event()
        if not context.add_callback(cancelled.set):
            context.abort(grpc.StatusCode.CANCELLED, "request_cancelled")
        if cancelled.wait(request.delay_ms / 1000):
            context.abort(grpc.StatusCode.CANCELLED, "request_cancelled")

        if request.item_id != "sku-123":
            context.abort(grpc.StatusCode.NOT_FOUND, "item_not_found")

        logging.info("request_id=%s event=finished", request_id)
        return inventory_pb2.GetItemResponse(
            item_id=request.item_id,
            available=7,
        )


if __name__ == "__main__":
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(
        InventoryService(), server
    )
    server.add_insecure_port("127.0.0.1:50051")
    server.start()
    logging.info("Inventory listening on 127.0.0.1:50051")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(grace=1).wait()
