"""Order Worker consumes order messages, skips duplicates, and ACKs after processing."""

import argparse
import fcntl
import json
import logging
import os
import time

import pika

QUEUE = "orders"
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "127.0.0.1")
PROCESSED_FILE = os.environ.get("PROCESSED_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "processed_events.txt"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default=f"worker-{os.getpid()}")
    parser.add_argument("--crash-after-receive", action="store_true",
                        help="exit on the first message before sending its ACK")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format=f"%(asctime)s {args.name} %(message)s", datefmt="%H:%M:%S")
    log = logging.getLogger()
    logging.getLogger("pika").setLevel(logging.WARNING)

    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE, durable=True)
    # One unacknowledged message per worker, so work is shared between competing consumers.
    channel.basic_qos(prefetch_count=1)

    def on_message(ch, method, properties, body):
        order = json.loads(body)
        event_id = order["event_id"]
        log.info("received event_id=%s order_id=%s redelivered=%s",
                 event_id, order["order_id"], method.redelivered)

        if args.crash_after_receive:
            log.warning("simulated crash before ACK for order_id=%s", order["order_id"])
            os._exit(1)

        # The file lock makes check, process, and record atomic across worker processes.
        with open(PROCESSED_FILE, "a+") as processed:
            fcntl.flock(processed, fcntl.LOCK_EX)
            processed.seek(0)
            if event_id in processed.read().split():
                log.warning("duplicate detected event_id=%s order_id=%s; skipping business action",
                            event_id, order["order_id"])
            else:
                log.info("processing order_id=%s item_id=%s quantity=%d",
                         order["order_id"], order["item_id"], order["quantity"])
                time.sleep(1)  # simulated business action, e.g. reserving inventory
                processed.write(event_id + "\n")
                processed.flush()
                log.info("processed order_id=%s", order["order_id"])

        ch.basic_ack(delivery_tag=method.delivery_tag)
        log.info("ACK sent event_id=%s", event_id)

    channel.basic_consume(queue=QUEUE, on_message_callback=on_message)
    log.info("waiting for messages on queue=%s", QUEUE)
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    connection.close()


if __name__ == "__main__":
    main()
