"""Run with: python -m unittest discover -s REST -v."""

import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import requests

import order

REST_DIR = Path(__file__).resolve().parent


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


class IndependentProcessTests(unittest.TestCase):
    def start_service(self, filename, port, **configuration):
        log = tempfile.TemporaryFile(mode="w+")
        self.addCleanup(log.close)
        process = subprocess.Popen(
            [sys.executable, str(REST_DIR / filename)],
            env={**os.environ, "PORT": str(port), **configuration},
            stdout=log,
            stderr=log,
        )
        self.addCleanup(self.stop_service, process)
        url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                log.seek(0)
                self.fail(f"{filename} exited during startup:\n{log.read()}")
            try:
                if requests.get(f"{url}/health", timeout=0.2).status_code == 200:
                    return process, url
            except requests.RequestException:
                pass
            time.sleep(0.05)
        self.fail(f"{filename} failed to become healthy")

    @staticmethod
    def stop_service(process):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

    def test_order_lifecycle_dependency_failure_and_recovery(self):
        inventory_port = free_port()
        inventory_process, inventory_url = self.start_service("inventory.py", inventory_port)
        order_process, order_url = self.start_service(
            "order.py", free_port(), INVENTORY_URL=inventory_url
        )
        self.assertNotEqual(inventory_process.pid, order_process.pid)

        def submit(payload):
            return requests.post(f"{order_url}/v1/orders", json=payload, timeout=3)

        response = submit({"item_id": "sku-123", "quantity": 2})
        self.assertEqual(response.status_code, 201)
        created = response.json()
        self.assertEqual(created["status"], "created")
        self.assertEqual(response.headers["X-Request-ID"], created["request_id"])
        tracked = requests.get(order_url + response.headers["Location"], timeout=3)
        self.assertEqual(tracked.status_code, 200)
        self.assertEqual(tracked.json()["order_id"], created["order_id"])
        print("\nAvailable item: HTTP 201; tracking: HTTP 200", flush=True)

        for payload in ({"item_id": "sku-456"}, {"item_id": "sku-123", "quantity": 8}):
            response = submit(payload)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["error"], "item_unavailable")
        self.assertEqual(submit({"item_id": "unknown"}).status_code, 404)
        for payload in ([], {}, {"item_id": "sku-123", "quantity": True},
                        {"item_id": "sku-123", "quantity": 0},
                        {"item_id": "sku-123", "quantity": "2"}):
            self.assertEqual(submit(payload).status_code, 400)
        print("Unavailable item: HTTP 409; unknown item: HTTP 404; invalid orders: HTTP 400", flush=True)

        # Stop the actual dependency process, then send a real HTTP order request.
        self.stop_service(inventory_process)
        response = submit({"item_id": "sku-123", "quantity": 1})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], "dependency_unavailable")
        print(f"Inventory stopped: HTTP {response.status_code} {response.text.strip()}", flush=True)
        self.assertIsNone(order_process.poll())
        health = requests.get(f"{order_url}/health", timeout=3)
        self.assertEqual(health.status_code, 200)
        tracked = requests.get(f"{order_url}/v1/orders/{created['order_id']}", timeout=3)
        self.assertEqual(tracked.status_code, 200)
        print(f"Order remains running: HTTP {health.status_code} {health.text.strip()}", flush=True)

        self.start_service("inventory.py", inventory_port)
        self.assertEqual(submit({"item_id": "sku-123"}).status_code, 201)
        print("Inventory restarted: next order returns HTTP 201", flush=True)

    def test_notification_queue_recovery_and_duplicate_delivery(self):
        _, inventory_url = self.start_service("inventory.py", free_port())
        notification_port = free_port()
        notification_url = f"http://127.0.0.1:{notification_port}"
        order_process, order_url = self.start_service(
            "order.py", free_port(), INVENTORY_URL=inventory_url,
            NOTIFICATION_URL=notification_url,
        )

        def submit():
            response = requests.post(
                f"{order_url}/v1/orders",
                json={"item_id": "sku-123", "quantity": 2, "recipient": "alice"},
                timeout=3,
            )
            self.assertEqual(response.status_code, 201)
            return response.json()

        def wait_for_delivery(created):
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                response = requests.get(
                    f"{notification_url}/v1/notifications/{created['order_id']}", timeout=1
                )
                if response.status_code == 200:
                    delivery = response.json()
                    self.assertEqual(delivery["recipient"], "alice")
                    self.assertEqual(delivery["status"], "logged")
                    return delivery
                self.assertEqual(response.status_code, 404)
                time.sleep(0.05)
            self.fail("Queued notification was not delivered")

        created = submit()  # Notification has not started; creation must still succeed.
        notification_process, _ = self.start_service("notification.py", notification_port)
        delivery = wait_for_delivery(created)
        event = {
            "event_id": created["order_id"], "event_type": "OrderCreated",
            "order_id": created["order_id"], "recipient": "alice",
            "item_id": created["item_id"], "quantity": created["quantity"],
            "created_at": created["created_at"],
        }
        response = requests.post(f"{notification_url}/v1/events", json=event, timeout=3)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), delivery)  # No second delivery timestamp.
        self.assertEqual(requests.post(
            f"{notification_url}/v1/events", json={"event_type": "Unknown"}, timeout=3
        ).status_code, 400)

        self.stop_service(notification_process)
        queued = submit()
        self.assertIsNone(order_process.poll())
        self.start_service("notification.py", notification_port)
        wait_for_delivery(queued)
        print("\nNotification stopped: order HTTP 201; restart: queued confirmation logged; duplicate: HTTP 200", flush=True)


class DependencyContractTests(unittest.TestCase):
    def test_timeout_does_not_create_order(self):
        with patch("order.requests.get", side_effect=requests.Timeout):
            before = len(order.ORDERS)
            response = order.app.test_client().post(
                "/v1/orders", json={"item_id": "sku-123"}
            )
        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json["error"], "dependency_timeout")
        self.assertEqual(len(order.ORDERS), before)

    def test_bad_dependency_responses_do_not_create_orders(self):
        for status, body in (
            (500, {}),
            (200, {"item_id": "sku-123", "available": 7}),
            (200, {"item_id": "sku-123", "available": 7, "is_available": False}),
            (200, ["invalid"]),
        ):
            with self.subTest(status=status, body=body):
                with patch("order.requests.get") as get:
                    dependency = get.return_value.__enter__.return_value
                    dependency.status_code = status
                    dependency.json.return_value = body
                    before = len(order.ORDERS)
                    response = order.app.test_client().post(
                        "/v1/orders", json={"item_id": "sku-123"}
                    )
                self.assertEqual(response.status_code, 502)
                self.assertEqual(len(order.ORDERS), before)


if __name__ == "__main__":
    unittest.main()
