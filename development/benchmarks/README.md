Benchmarking Centrifuge
=======================

Scalability benchmark
---------------------

![scalability](https://raw.github.com/FZambia/centrifuge/master/benchmarks/scalability.png "scalability benchmark")

[Google spreedsheet with this chart and data](https://docs.google.com/spreadsheet/ccc?key=0Ao60NPCQC6LgdDkxU1JNQjE3NUpORjM4Yk0wSFdOZ3c&usp=drive_web#gid=1)

Command used to run benchmark:

```bash
go run benchmark.go ws://localhost:8080/connection/websocket PROJECT_KEY PROJECT_SECRET 4000 200 50
```

Nginx was used as load balancer and websocket proxy.

Description:

This test was made to show how Centrifuge scales when new instances added. One message was sent to every connected
client, then average time of message delivery calculated.

There was no a goal of load testing Centifuge in this benchmark, I just wanted to show that when new instances of Centrifuge added message latency reduces.

Conclusions:

* More instances of Centrifuge reduce message latency
* Redis is the winner
* ZeroMQ surprisingly slow
* XSUB/XPUB proxy choice isn't important when there is no high loads.
