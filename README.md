# Lab 1
## How to run locally
- Ensure you have Go installed
- Need to have 2 terminals open
- Both terminals:
  - cd cmpe273-week1-lab1-starter
  - cd go-http
- Terminal 1:
  - cd service-a
  - go mod init service-a
  - go run .
- Terminal 2:
  - cd service-b
  - go mod init service-b
  - go run .

## Screenshots
![alt text](docs/Lab1.png "Success/Failure Runs")

## Why is this distributed?
Both the services are isolated and run independently on the same machine on the same network. If one service fails, it does not affect both services. There is proper error handling for such a scenario and the other service continues to run properly.