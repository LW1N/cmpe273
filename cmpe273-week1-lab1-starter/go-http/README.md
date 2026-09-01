# Go HTTP Track

## Run Service A
```bash
cd service-a
go mod init service-a
go run .
```

## Run Service B (new terminal)
```bash
cd service-b
go mod init service-b
go run .
```

## Test
```bash
curl "http://127.0.0.1:8081/call-echo?msg=hello"
```

Stop Service A and rerun the curl command to observe failure handling.
