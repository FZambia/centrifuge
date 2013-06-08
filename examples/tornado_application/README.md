Centrifuge client's application example
=======================================

First, run Centrifuge, create new project and bidirectional category "python" in it
and then run this app with correct Centrifuge address, project id and project secret key:

```bash
python main.py --port=3000 --centrifuge=localhost:8000 --project_id=PROJECT_ID --secret_key=SECRET
```

Then visit `http://localhost:3000` and select SockJS or pure websocket example.
