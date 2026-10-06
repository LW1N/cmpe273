# gRPC Inventory example

Checkout (the Order service) exposes an HTTP endpoint on port 5000 and calls
Inventory over gRPC on port 50051. Inventory returns seven available units for
`sku-123`; any other item ID returns gRPC `NOT_FOUND`.

The `GetItem` operation checks availability; it does not reserve or decrement stock.
`inventory.proto` defines the request, response, and service contract.

## Setup

Run these commands from the lab directory with Python 3.10 or newer:

```bash
cd gRPC
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. inventory.proto
```

The last command generates `inventory_pb2.py` (message classes) and
`inventory_pb2_grpc.py` (client stub and server interface). Generate these before
starting either service, and regenerate them whenever the contract changes.

## Start the services

In the first terminal, from the `gRPC` directory:

```bash
source .venv/bin/activate
python inventory.py
```

In a second terminal, navigate to the same `gRPC` directory:

```bash
source .venv/bin/activate
python checkout.py
```

Stop the original HTTP Checkout service first if it is already using port 5000.
These examples use a local, unencrypted gRPC channel for development.
To point Checkout at another Inventory host, set `INVENTORY_TARGET`:

```bash
INVENTORY_TARGET=127.0.0.1:50051 python checkout.py
```

## Try the endpoints

Run these commands in a third terminal:

```bash
# Checkout health: HTTP 200
curl -i http://127.0.0.1:5000/health

# Success: HTTP 200, item_id=sku-123, available=7
curl -i http://127.0.0.1:5000/v1/availability/sku-123

# Missing item: HTTP 404, error=item_not_found
curl -i http://127.0.0.1:5000/v1/availability/sku-missing

# Slow Inventory: HTTP 504, error=dependency_timeout
curl -i 'http://127.0.0.1:5000/v1/availability/sku-123?delay_ms=1000'

# Invalid delay: HTTP 400, error=invalid_delay
curl -i 'http://127.0.0.1:5000/v1/availability/sku-123?delay_ms=-1'
```

For a dependency failure, stop Inventory with Ctrl-C while leaving Checkout
running, then repeat the success request. Expect HTTP 503 with
`error=dependency_unavailable`. Restart Inventory to restore successful calls.

Availability responses include a `request_id` in JSON and an `X-Request-ID`
header. Checkout forwards that ID as gRPC metadata so logs can be correlated.
Inventory has no HTTP endpoint; use Checkout for these curl checks.

## Deadline and errors

Checkout sets `timeout=0.6` on `GetItem`, giving the entire RPC a 600 ms deadline.
When that deadline expires, the client receives `DEADLINE_EXCEEDED`. Inventory
also stops its simulated delay when the RPC is cancelled.

| Situation | gRPC status | Checkout HTTP status | JSON error |
| --- | --- | --- | --- |
| Unknown item ID | `NOT_FOUND` | 404 | `item_not_found` |
| Delay outside 0–3000 ms | `INVALID_ARGUMENT` | 400 | `invalid_delay` |
| RPC exceeds 600 ms | `DEADLINE_EXCEEDED` | 504 | `dependency_timeout` |
| Inventory cannot be reached | `UNAVAILABLE` | 503 | `dependency_unavailable` |
| Other RPC error or invalid response | Other status / response validation | 502 | `dependency_bad_response` |

Checkout rejects malformed or out-of-range delays before calling Inventory.
Inventory independently validates the range for callers using gRPC directly.

Here an unavailable item means an unknown ID, matching the original Inventory
service. If a future reservation operation rejects an existing item for
insufficient stock, `FAILED_PRECONDITION` is an appropriate status.
