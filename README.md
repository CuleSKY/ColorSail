# CS2ZE Server

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you plan to use the EXG CN fetcher, install Playwright's Chromium runtime:

```bash
python -m playwright install --with-deps chromium
```

## Deployment notes

AutoJoin is implemented outside the website backend (client/standalone service). The website backend does not host AutoJoin.

## Map translation auto-fill

- `map_translations.json` is **deprecated** and no longer the primary path for map lookups.
- Traditional Chinese (`zh_tw`) is derived from Simplified (`zh_cn`) via OpenCC (`opencc-python-reimplemented`).

## EXG CN fetcher self-check

From the repo root, confirm the rendered EXG maplist can be fetched and parsed:

```bash
python -m tools.map_sidecar.sidecar cn-fetch --dry-run
```

The output should include a `record_count` and a short preview. Systemd should be able to run:

```bash
python -m tools.map_sidecar.sidecar cn-fetch
```

Check `journalctl` for a success log entry if running under systemd.

## Map sidecar pipeline (EXG 鈫?MySQL 鈫?exports)

### Data flow (authoritative order)

```
EXG (authoritative) 鈫?CN fetcher 鈫?overseas ingest 鈫?MySQL (authoritative snapshot)
鈫?exporter (systemd timer) 鈫?map_index.json + time.json
```

- EXG is the sole authority for cooldown deadlines and map metadata.
- MySQL stores **only the latest EXG calibration snapshot**.
- Redis is best-effort cache only; Redis failures must not break ingest.
- `map_index.json` is for user search only and must be `dict[map_key]` with `map_cn`, `deadline`, `achievement`.
- `map_cn` defaults to `zh_cn` (fallback to map key). `zh_tw` is derived via OpenCC and is not used for index lookups.

### Module responsibilities (old + current, preserved)

- **EXG fetcher (CN)**: `tools/map_sidecar/cn_fetcher.py` (Playwright fetch + HTML parse) and legacy `tools/map_sidecar/exg_cn_pipeline.py` / `tools/map_sidecar/exg_maplist.py`.
- **Normalize / convert**: `tools/normalize_maplist_from_html.py` (HTML 鈫?normalized records) and CN fetcher parsing helpers.
- **CN 鈫?overseas ingest client**: `tools/map_sidecar/cn_fetcher.py` / `tools/map_sidecar/exg_cn_pipeline.py` (`post_payload`/`post_normalized_payload`).
- **Overseas ingest server**: `tools/map_sidecar/ingest_server.py` (schema validation + MySQL write).
- **MySQL write module**: `tools/map_sidecar/db.py`.
- **map_index/time exporter**: `tools/map_sidecar/exporter.py` + `tools/map_sidecar/sidecar.py` (`refresh-index`).

### Cooldown normalization rules (strict)

- EXG `deadline` is parsed in **Asia/Shanghai**.
- Cooldown stored as **epoch seconds (UTC, int)** in MySQL (`cooldown_end_epoch`).
- `deadline == null` is only allowed when EXG explicitly has no cooldown.
- Parse failures must return **400** in ingest (never write null on parse failure).

### Frontend time calibration

- Exporter also writes `time.json` as `{ "server_now_epoch": <int> }`.
- Frontend must use `time.json` for cooldown countdowns (not `Date.now()`).

### Environment variables

**Overseas ingest + exporter**
- `PROJECT_ROOT` (default: `/opt/1panel/www/sites/example.com/NERV_CS2ZE`)
- `MYSQL_HOST`, `MYSQL_PORT` (default `3306`), `MYSQL_DB`, `MYSQL_USER`, `MYSQL_PASSWORD`
- `REDIS_URL` (preferred) or `REDIS_HOST` + `REDIS_PORT` + `REDIS_PASSWORD`
- `MAIN_SERVERS_JSON_URL` (default: `https://example.com/servers.json`)
- `STATIC_DIR_NAME` (default: `static`)
- `MAP_SIDECAR_LOG_DIR` (default: `<PROJECT_ROOT>/logs`)
- Ingest server: `INGEST_TOKEN`, `INGEST_BIND_HOST`, `INGEST_BIND_PORT`, `INGEST_ALLOWLIST`, `INGEST_MAX_BYTES`, `INGEST_REQUEST_TIMEOUT_SECONDS`
- `EXG_HEALTH_MAX_AGE_SECONDS` (default: `7200`)

**CN fetcher**
- `PROJECT_ROOT` (default: current working directory)
- `EXG_MAPLIST_URL` (default: `https://example.com/serverlist/cs2maplist`)
- `OVERSEAS_INGEST_URL`
- `INGEST_TOKEN`
- `FETCH_TIMEOUT_SECONDS` (default: `15`)
- `RETENTION_HOURS` (default: `72`)
- `DEBUG` (optional)

### systemd examples (exporter timer)

```ini
[Unit]
Description=CS2ZE Map Sidecar - Refresh map_index.json every 60 seconds

[Timer]
OnBootSec=45s
OnUnitActiveSec=60s
Unit=map-sidecar-index-refresh.service
```

```ini
[Unit]
Description=CS2ZE Map Sidecar - Refresh map_index.json if DB changed
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/opt/1panel/www/sites/example.com/NERV_CS2ZE
EnvironmentFile=/etc/default/map-sidecar
ExecStart=/opt/1panel/www/sites/example.com/NERV_CS2ZE/.venv/bin/python -m tools.map_sidecar.sidecar refresh-index
```

### Common errors & remediation

- **Redis NOAUTH / connection errors**: ingest should still return 200; Redis failures only log warnings.
- **400 schema errors**: payload must include `source`, `fetched_at_epoch` (int), and `records[]` schema.
- **workshop.id** must be a string; use `"0"` when unavailable.
- **`deadline == null` semantics**: only allowed when EXG explicitly reports no cooldown; parse failures must not write null.

### Data examples

**records payload**
```json
{
  "source": "exg_maplist",
  "fetched_at_epoch": 1710000000,
  "records": [
    {
      "map": "de_dust2",
      "name_zh": "娌欐紶2",
      "difficulty": "鏈爣娉?,
      "tags": [],
      "cooldown": {
        "duration_raw": "60",
        "deadline": "2024/03/10 12:00"
      },
      "achievement": "Win 10 rounds",
      "workshop": {
        "id": "123456789",
        "url": "https://example.com/sharedfiles/filedetails/?id=123456789"
      }
    }
  ]
}
```

**map_index.json**
```json
{
  "de_dust2": {
    "map_cn": "娌欐紶2",
    "deadline": 1710043200,
    "achievement": "Win 10 rounds"
  }
}
```

**time.json**
```json
{
  "server_now_epoch": 1710000123
}
```

## Admin notes

- Admin routes are intended to be served from `admin.example.com` behind Cloudflare Access; `/admin` on `example.com` returns 404.

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
    server_name example.com example.com;

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
    server_name admin.example.com;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Frontend (Vite + Vue)

Install and run the dev server (Vite only):

```bash
cd frontend
npm ci
npm run dev
```

Build production assets (Flask serves `/static`):

```bash
cd frontend
npm ci
npm run build
```

Run the Flask/Gunicorn main site (serves the compiled assets from `/static/assets`):

```bash
gunicorn -w 1 -b 127.0.0.1:5000 wsgi_main:application
```

Production deploy notes:
- Vite outputs to `static/assets/` (manifest + hashed JS/CSS).
- Copy `static/assets/` to the server alongside the Flask app, and keep `/static/` (logos, `/static/maps/`) intact.
- Serve `/static/assets/*` with long-lived immutable caching; keep HTML/templates short/no-cache so updated bundles load.

Caching guidance:
- `/static/assets/*` should be cached long-term (immutable).
- `/` or `/index.html` should be short-cache or no-cache so templates refresh promptly.

## Required environment variables

- `CS2ZE_BASE_URL` (optional, default `http://localhost:5000`)
- `CS2ZE_TIMEOUT` (optional, request timeout in seconds, default `6`)


