Tools for benchmarking Centrifuge
=================================

To run client `autobahn` and `Twisted` required

```bash
pip install autobahn
```

To run client:

```bash
python client.py ws://localhost:8000/connection/websocket 522affad78b83c2c0a199800 dba28f4f9b413181575530d9804b07 1
```

argv[1] - websocket endpoint
argv[2] - project ID
argv[3] - project secret key
argv[4] - num connections


1) Trough 200 clients: 16-19 sec

2) After refactor and using single ZeroMQ socket - 13 sec
