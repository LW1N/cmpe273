"""Primary/secondary replication simulation: async propagation, stale reads, and convergence after recovery."""

import logging
import queue
import threading
import time

log = logging.getLogger()

REPLICATION_LAG = 0.5  # seconds each update takes to reach the secondary
POLL_INTERVAL = 0.2


class Replica:
    def __init__(self, name, stock):
        self.name = name
        self.stock = stock

    def apply(self, stock):
        log.info("%s applied stock %d -> %d", self.name, self.stock, stock)
        self.stock = stock


class Primary(Replica):
    """Accepts writes and queues each one for asynchronous propagation to the secondary."""

    def __init__(self, name, stock, replication_log):
        super().__init__(name, stock)
        self.replication_log = replication_log

    def write(self, stock):
        log.info("client write stock=%d to %s", stock, self.name)
        self.apply(stock)
        self.replication_log.put(stock)
        log.info("%s queued stock=%d for replication", self.name, stock)


class Replicator(threading.Thread):
    """Ships queued updates from the primary to the secondary. Can be paused to simulate a delayed link."""

    def __init__(self, replication_log, secondary):
        super().__init__(daemon=True)
        self.replication_log = replication_log
        self.secondary = secondary
        self.running = threading.Event()
        self.running.set()

    def pause(self):
        log.warning("replication to %s PAUSED", self.secondary.name)
        self.running.clear()

    def resume(self):
        log.info("replication to %s RESUMED", self.secondary.name)
        self.running.set()

    def run(self):
        while True:
            stock = self.replication_log.get()
            self.running.wait()
            time.sleep(REPLICATION_LAG)
            log.info("replicating stock=%d to %s", stock, self.secondary.name)
            self.secondary.apply(stock)


def read(replica):
    log.info("client read %s -> stock=%d", replica.name, replica.stock)
    return replica.stock


def wait_until_converged(primary, secondary):
    """Client polls the secondary until it matches the primary, logging each read along the way."""
    target = read(primary)
    while read(secondary) != target:
        time.sleep(POLL_INTERVAL)
    log.info("CONVERGED %s=%d %s=%d", primary.name, primary.stock, secondary.name, secondary.stock)


def replication_test(primary, secondary):
    log.info("=== Test 1: replication (write stock=10 to primary) ===")
    primary.write(10)
    wait_until_converged(primary, secondary)


def stale_read_test(primary, secondary, replicator):
    log.info("=== Test 2: stale read (pause replication, write stock=9) ===")
    replicator.pause()
    primary.write(9)
    log.info("waiting %.1fs, longer than the normal replication lag", REPLICATION_LAG * 3)
    time.sleep(REPLICATION_LAG * 3)
    primary_stock = read(primary)
    secondary_stock = read(secondary)
    if secondary_stock != primary_stock:
        log.warning("STALE READ: %s=%d but %s=%d", primary.name, primary_stock, secondary.name, secondary_stock)


def recovery_test(primary, secondary, replicator):
    log.info("=== Test 3: recovery and convergence (resume replication) ===")
    replicator.resume()
    wait_until_converged(primary, secondary)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s.%(msecs)03d %(message)s", datefmt="%H:%M:%S")
    replication_log = queue.Queue()
    primary = Primary("primary", 0, replication_log)
    secondary = Replica("secondary", 0)
    replicator = Replicator(replication_log, secondary)
    replicator.start()

    replication_test(primary, secondary)
    stale_read_test(primary, secondary, replicator)
    recovery_test(primary, secondary, replicator)


if __name__ == "__main__":
    main()
