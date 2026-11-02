import json
import os
import signal
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

POD = socket.gethostname()
STOCK = {"sku-123": 42, "sku-456": 7}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/ready":
            ready = not os.path.exists("/tmp/unready")
            self.reply(200 if ready else 503, {"ready": ready})
        elif self.path == "/inventory":
            self.reply(200, {"pod": POD, "stock": STOCK})
        else:
            self.reply(404, {"error": "not found"})

    def reply(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        if self.path != "/ready":
            print(f"[{POD}] {fmt % args}", flush=True)


signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
