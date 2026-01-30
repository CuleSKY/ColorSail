# CS2ZE CLI Client

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
