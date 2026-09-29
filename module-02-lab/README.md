# Python HTTP Track

## Run with Docker Compose

From this directory, build and start both services:

```bash
docker compose up --build
```

Compose builds each service from its existing Dockerfile. Service A reaches
Service B at `http://service-b:5001` over the default Compose network.

Test the service-to-service call:

```bash
curl "http://127.0.0.1:8081/call-b"
```

Service B can also be reached directly at `http://127.0.0.1:8082/health`.

Stop and remove the containers and network with:

```bash
docker compose down
```

To observe Service A's failure handling, stop only Service B and call Service A
again:

```bash
docker compose stop service-b
curl "http://127.0.0.1:8081/call-b"
```

## Run without Docker

## Run Service A
```bash
cd service-a
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Run Service B (new terminal)
```bash
cd service-b
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Test
```bash
curl "http://127.0.0.1:5000/call-b"
```

Stop Service A and rerun the curl command to observe failure handling.
