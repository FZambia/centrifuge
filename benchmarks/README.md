Tools for benchmarking Centrifuge
=================================

Scalability benchmark
---------------------

![scalability](https://raw.github.com/FZambia/centrifuge/master/benchmarks/scalability.png "scalability benchmark")

Command used to run:

```bash
go run benchmark.go ws://localhost:8080/connection/websocket PROJECT_ID SECRET_KEY 4000 200 50
```

Nginx was used as load balancer and websocket proxy.

Description:

This test was made to show how Centrifuge scales when new instances added. One message was sent to every connected
client, then average time of message delivery calculated.

Conclusions:

* More instances of Centrifuge reduce message latency
* Redis is the winner
* ZeroMQ surprisingly slow
* XSUB/XPUB proxy choice isn't important when there is no high loads.