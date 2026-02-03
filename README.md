# CS2ZE Server

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Deployment notes

See `docs/autojoin_v2_deploy.md` for AutoJoin v2 deployment requirements and WebSocket proxying notes.

## Admin notes

- Admin routes are intended to be served from `admin.cs2ze.org` behind Cloudflare Access; `/admin` on `www.cs2ze.org` returns 404.

## Local runtime (main + admin split)

Run the main site and admin panel as separate services:

```bash
gunicorn -w 1 -b 127.0.0.1:5000 wsgi_main:application
```

```bash
gunicorn -w 1 -b 127.0.0.1:5001 wsgi_admin:application
```

### Nginx vhosts (deployment intent)

```nginx
server {
    listen 80;
    server_name www.cs2ze.org cs2ze.org;

    location /admin {
        return 404;
    }

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name admin.cs2ze.org;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Frontend (Vite + Vue)

Install and run the dev server:

```bash
cd frontend
npm install
npm run dev
```

Build production assets (Flask serves `/static`):

```bash
cd frontend
npm run build
```

Caching guidance:
- `/static/assets/*` should be cached long-term (immutable).
- `/` or `/index.html` should be short-cache or no-cache so templates refresh promptly.

## Required environment variables

- `CS2ZE_BASE_URL` (optional, default `http://localhost:5000`)
- `CS2ZE_SESSION_COOKIE` (required for Prime/AutoJoin watcher access)
  - Example: `CS2ZE_SESSION_COOKIE="session=YOUR_SESSION_COOKIE"`
  - Use the `session` cookie value from a logged-in browser session.
- `CS2ZE_TIMEOUT` (optional, request timeout in seconds, default `6`)
