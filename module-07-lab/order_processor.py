"""Order processing simulation: versioned event ordering, duplicates, missing events, and fencing tokens."""

import itertools
import logging

log = logging.getLogger()


class Order:
    """Applies versioned updates strictly in order, buffering early arrivals and ignoring duplicates."""

    def __init__(self, order_id):
        self.order_id = order_id
        self.version = 0
        self.status = None
        self.pending = {}  # version -> event that arrived before its predecessor
        self.highest_token = 0

    def missing_versions(self):
        if not self.pending:
            return []
        return [v for v in range(self.version + 1, max(self.pending)) if v not in self.pending]

    def receive(self, event):
        version = event["version"]
        log.info("received order_id=%s version=%d status=%s", self.order_id, version, event["status"])

        if version <= self.version or version in self.pending:
            log.warning("duplicate order_id=%s version=%d; ignoring (current version=%d)",
                        self.order_id, version, self.version)
            return

        if version > self.version + 1:
            self.pending[version] = event
            log.warning("out of order order_id=%s version=%d buffered as pending; waiting for version(s) %s",
                        self.order_id, version, self.missing_versions())
            return

        self._apply(event)
        # The gap may now be filled, so drain any buffered versions that follow.
        while self.version + 1 in self.pending:
            self._apply(self.pending.pop(self.version + 1))

    def write(self, worker, token, event):
        """Worker write guarded by a fencing token: a token older than the newest one seen is rejected."""
        if token < self.highest_token:
            log.warning("REJECTED %s token=%d order_id=%s version=%d: stale token (highest seen=%d)",
                        worker, token, self.order_id, event["version"], self.highest_token)
            return
        self.highest_token = token
        log.info("accepted %s token=%d order_id=%s", worker, token, self.order_id)
        self.receive(event)

    def _apply(self, event):
        log.info("applied order_id=%s version=%d status %s -> %s",
                 self.order_id, event["version"], self.status, event["status"])
        self.version = event["version"]
        self.status = event["status"]

    def log_state(self):
        log.info("state order_id=%s version=%d status=%s pending=%s missing=%s",
                 self.order_id, self.version, self.status, sorted(self.pending), self.missing_versions())


class LockService:
    """Grants a lease on an order with a fencing token that increases on every grant."""

    def __init__(self):
        self._tokens = itertools.count(1)

    def acquire(self, worker, order_id):
        token = next(self._tokens)
        log.info("lock granted to %s on order_id=%s token=%d", worker, order_id, token)
        return token


def event(order_id, version, status):
    return {"order_id": order_id, "version": version, "status": status}


def ordering_test():
    log.info("=== Test 1: versioned ordering and duplicates (deliver v2, v1, v2 again) ===")
    order = Order("order-1")
    order.receive(event("order-1", 2, "PAID"))
    order.receive(event("order-1", 1, "CREATED"))
    order.receive(event("order-1", 2, "PAID"))
    order.log_state()


def missing_event_test():
    log.info("=== Test 2: missing event (deliver v1, then v3 while v2 never arrives) ===")
    order = Order("order-2")
    order.receive(event("order-2", 1, "CREATED"))
    order.receive(event("order-2", 3, "SHIPPED"))
    order.log_state()


def stale_worker_test():
    log.info("=== Test 3: stale worker rejected by fencing token ===")
    locks = LockService()
    order = Order("order-3")
    order.receive(event("order-3", 1, "CREATED"))

    token_a = locks.acquire("worker-A", "order-3")
    log.info("worker-A pauses (e.g. GC pause) and its lease expires before it writes")
    token_b = locks.acquire("worker-B", "order-3")
    order.write("worker-B", token_b, event("order-3", 2, "PAID"))
    log.info("worker-A resumes, still believing it holds the lock")
    order.write("worker-A", token_a, event("order-3", 3, "SHIPPED"))
    order.write("worker-B", token_b, event("order-3", 3, "SHIPPED"))
    order.log_state()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    ordering_test()
    missing_event_test()
    stale_worker_test()


if __name__ == "__main__":
    main()
