Benchmarking Centrifuge
=======================

To run benchmark allow publish into channel and execute:

```bash
go run benchmark.go ws://localhost:8000/connection/websocket development secret 4000 1000 50
```

To connect N client which just read messages from connection:

```bash
go run connections.go ws://localhost:8000/connection/websocket development secret 100
```
