Tools for benchmarking Centrifuge
=================================

Scalability benchmark
---------------------

![scalability](https://raw.github.com/FZambia/centrifuge/master/benchmarks/scalability.png "scalability benchmark")


Conclusions:

* More instances of Centrifuge make message latency better
* Redis is the winner
* XSUB/XPUB proxy choice isn't important when there is no high loads.