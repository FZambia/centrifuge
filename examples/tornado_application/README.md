Centrifuge client's application example
=======================================

First, run Centrifuge, create new project and bidirectional category "bee" in it
and then run this app with correct Centrifuge address, secret and public project keys:

```bash
python main.py --port=3000 --centrifuge=localhost:8000 --public_key=PUBLIC --secret_key=SECRET
```

Go to `http://localhost:3000` for SockJS client example or `http://localhost:3000/ws` for
pure websocket example.