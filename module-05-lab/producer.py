"""Order Producer publishes order messages to a durable RabbitMQ queue."""

import argparse
import json
import logging
import os
import random
import uuid

import pika

QUEUE = "orders"
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "127.0.0.1")
ITEMS = ["sku-123", "sku-456", "sku-789"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s producer %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger()
logging.getLogger("pika").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=6, help="number of orders to publish")
    parser.add_argument("--duplicate", action="store_true", help="republish the last message with the same event_id")
    args = parser.parse_args()

    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE, durable=True)

    messages = [
        {
            "event_id": str(uuid.uuid4()),
            "order_id": f"order-{n}",
            "item_id": random.choice(ITEMS),
            "quantity": random.randint(1, 5),
        }
        for n in range(1, args.count + 1)
    ]
    if args.duplicate and messages:
        messages.append(dict(messages[-1]))

    for message in messages:
        channel.basic_publish(
            exchange="",
            routing_key=QUEUE,
            body=json.dumps(message),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=pika.DeliveryMode.Persistent),
        )
        log.info("published event_id=%s order_id=%s item_id=%s quantity=%d",
                 message["event_id"], message["order_id"], message["item_id"], message["quantity"])
    connection.close()


if __name__ == "__main__":
    main()
