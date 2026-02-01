# CS2ZE CLI Client

## CS2ZE Desktop Client (Tauri v2 + Svelte)

### How to run (Windows 11)

**Prerequisites**

- Node.js 18+
- Rust (stable)
- Tauri v2 system dependencies (see https://tauri.app)

**Install**

```bash
cd frontend
npm install
cd ../src-tauri
cargo build
```

**Dev run**

```bash
cd frontend
npm run dev
```

```bash
cd src-tauri
cargo tauri dev
```

**Build**

```bash
cd frontend
npm run build
```

```bash
cd src-tauri
cargo tauri build
```

### How to test (Windows 11)

1. **200 vs 304 behavior (ETag)**
   - Use a proxy (e.g. Fiddler) to verify the `If-None-Match` header and confirm 304 responses do not change the snapshot or AutoJoin/subscription events.
2. **Jitter interval (6–10s)**
   - Watch the Diagnostics page for `next poll` timestamps; verify the delta is within 6–10 seconds.
3. **Network errors/backoff**
   - Temporarily block network access to `servers.json` and confirm backoff grows exponentially (cap 60s) in Diagnostics/status bar.
4. **Map subscriptions**
   - Add a subscription for a server+map, restart the app, and confirm a single startup notification appears.
   - Change the server map and ensure notifications only fire on map changes that match subscriptions.
5. **AutoJoin**
   - Arm AutoJoin for a server and verify Idle → Waiting → Cooldown transitions when criteria are met.
   - Confirm the client automatically copies the connect address and attempts to open Steam with no user confirmation.
   - Let Cooldown expire and verify the loop returns to Waiting.
   - Stop AutoJoin and ensure timers clear.
   - Watch the AutoJoin page and server details pane for cooldown remaining seconds.
6. **Diagnostics copy report**
   - Use “Copy report” and paste into a text editor to confirm the report includes URL, status, ETag, jitter, backoff, and diff summary.
7. **Steam URI failure logging**
   - Disconnect Steam or block `steam://` handling and trigger AutoJoin.
   - Check the application logs/stderr for a line beginning with `Failed to open Steam URI`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Deployment notes

See `docs/autojoin_v2_deploy.md` for AutoJoin v2 deployment requirements and WebSocket proxying notes.

## Admin + client scaffolding notes

- Admin routes are intended to be served from `admin.cs2ze.org` behind Cloudflare Access; `/admin` on `www.cs2ze.org` returns 404.
- The new `client_app/` package contains **scaffolding only** for a future desktop client and is not packaged or wired into the web runtime.

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

## Required environment variables

- `CS2ZE_BASE_URL` (optional, default `http://localhost:5000`)
- `CS2ZE_SESSION_COOKIE` (required for Prime/AutoJoin watcher access)
  - Example: `CS2ZE_SESSION_COOKIE="session=YOUR_SESSION_COOKIE"`
  - Use the `session` cookie value from a logged-in browser session.
- `CS2ZE_TIMEOUT` (optional, request timeout in seconds, default `6`)

## Commands

### List servers

```bash
python -m client.main list
```

Example output:

```
#   Server                           Players      Latency
0   Example Server                   12/64        24.5 ms (icmp)
```

### Probe one server

```bash
python -m client.main probe 0
python -m client.main probe 203.0.113.10:27015
```

Example output:

```
Server: Example Server (203.0.113.10:27015)
ICMP: ok 22.1 ms
A2S: ok 34.8 ms
Display: 22.1 ms (icmp)
```

### Start AutoJoin

```bash
python -m client.main autojoin 0
```

### Stop AutoJoin

```bash
python -m client.main stop
```
