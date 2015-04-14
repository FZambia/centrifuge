Centrifuge client's application example
=======================================

First, run Centrifuge, create new project and namespace `public` in it with `publish` permission
and then run this app with correct Centrifuge address, project id and project secret key:

```bash
python main.py --port=3000 --centrifuge=localhost:8000 --project_key=PROJECT_KEY --project_secret=PROJECT_SECRET
```

Then visit `http://localhost:3000` and select SockJS or pure websocket example.
