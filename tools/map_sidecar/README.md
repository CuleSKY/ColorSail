# Map Sidecar

This sidecar owns **all write paths** for map metadata, exports, and workshop images. The Flask main server stays read-only and continues to serve `/servers.json` even if the sidecar is offline.

## Deployment split

### Overseas host (ingest + exports)
- Runs the HTTP ingest server (receives EXG payloads from CN).
- Runs poller/export jobs via systemd timers.
- **Does not** fetch EXG HTML directly.

### CN host (EXG fetcher)
- Fetches/parses EXG HTML locally.
- Posts payloads to the overseas ingest endpoint.

## Environment variables

### Overseas `/etc/default/map-sidecar`
Required:
- `PROJECT_ROOT` (default: `/opt/1panel/www/sites/www.cs2ze.org/NERV_CS2ZE`)
- `MYSQL_HOST`
- `MYSQL_PORT` (default: `3306`)
- `MYSQL_DB`
- `MYSQL_USER`
- `MYSQL_PASSWORD`

Optional:
- `REDIS_URL` (preferred) or `REDIS_HOST` + `REDIS_PORT` + `REDIS_PASSWORD`
- `MAIN_SERVERS_JSON_URL` (default: `https://www.cs2ze.org/servers.json`)
- `STATIC_DIR_NAME` (default: `static`)
- `MAP_SIDECAR_LOG_DIR` (default: `<PROJECT_ROOT>/logs`)
- `DEBUG` (`true` to retain EXG HTML snapshots in the CN fetcher)

Ingest HTTP server settings:
- `INGEST_TOKEN` (**required**)
- `INGEST_BIND_HOST` (default: `0.0.0.0`)
- `INGEST_BIND_PORT` (default: `8082`)
- `INGEST_ALLOWLIST` (optional, comma-separated IPs/CIDRs)
- `INGEST_MAX_BYTES` (default: `1048576`)
- `INGEST_REQUEST_TIMEOUT_SECONDS` (default: `10`)
- `EXG_HEALTH_MAX_AGE_SECONDS` (default: `7200`)

Example `/etc/default/map-sidecar`:
```bash
PROJECT_ROOT=/opt/1panel/www/sites/www.cs2ze.org/NERV_CS2ZE
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DB=cs2ze
MYSQL_USER=cs2ze
MYSQL_PASSWORD=REPLACE_ME
REDIS_URL=redis://127.0.0.1:6379/0
MAIN_SERVERS_JSON_URL=https://www.cs2ze.org/servers.json
MAP_SIDECAR_LOG_DIR=/opt/1panel/www/sites/www.cs2ze.org/NERV_CS2ZE/logs
INGEST_TOKEN=REPLACE_ME
INGEST_BIND_HOST=0.0.0.0
INGEST_BIND_PORT=8082
INGEST_ALLOWLIST=203.0.113.10/32
INGEST_MAX_BYTES=1048576
INGEST_REQUEST_TIMEOUT_SECONDS=10
EXG_HEALTH_MAX_AGE_SECONDS=7200
```

### CN `/etc/default/exg-fetcher`
Required:
- `PROJECT_ROOT` (default: current working directory)
- `OVERSEAS_INGEST_URL` (e.g. `https://www.cs2ze.org/sidecar/exg/ingest`)
- `INGEST_TOKEN`

Optional:
- `EXG_MAPLIST_URL` (default: `https://list.darkrp.cn:9000/serverlist/cs2maplist`)
- `FETCH_TIMEOUT_SECONDS` (default: `15`)
- `RETENTION_HOURS` (default: `72`)
- `DEBUG` (`true` to retain EXG HTML snapshots)

Example `/etc/default/exg-fetcher`:
```bash
PROJECT_ROOT=/opt/cs2ze/NERV_CS2ZE
EXG_MAPLIST_URL=https://list.darkrp.cn:9000/serverlist/cs2maplist
OVERSEAS_INGEST_URL=https://www.cs2ze.org/sidecar/exg/ingest
INGEST_TOKEN=REPLACE_ME
FETCH_TIMEOUT_SECONDS=15
RETENTION_HOURS=72
DEBUG=false
```

## Manual commands

Overseas:
```bash
.venv/bin/python -m tools.map_sidecar.sidecar poll-servers
.venv/bin/python -m tools.map_sidecar.sidecar refresh-index
.venv/bin/python -m tools.map_sidecar.sidecar fetch-images
.venv/bin/python -m tools.map_sidecar.sidecar exg-health
.venv/bin/python -m tools.map_sidecar.sidecar ingest-server
```

CN fetcher:
```bash
.venv/bin/python -m tools.map_sidecar.sidecar cn-fetch
.venv/bin/python -m tools.map_sidecar.sidecar cn-fetch --dry-run
```

## One-command start/stop (standalone daemon)

```bash
python tools/map_sidecar/sidecar_daemon.py start
python tools/map_sidecar/sidecar_daemon.py stop
python tools/map_sidecar/sidecar_daemon.py status
python tools/map_sidecar/sidecar_daemon.py foreground
```

## Validation examples

Ingest endpoint (wrong token -> 401):
```bash
curl -i -X POST https://www.cs2ze.org/sidecar/exg/ingest \
  -H 'Authorization: Bearer WRONG_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"records":[]}'
```

Ingest endpoint (correct token -> 200):
```bash
curl -i -X POST https://www.cs2ze.org/sidecar/exg/ingest \
  -H 'Authorization: Bearer REPLACE_ME' \
  -H 'Content-Type: application/json' \
  -d '{"source":"exg_maplist","fetched_at_epoch":1710000000,"records":[{"map":"de_dust2","name_zh_cn":"沙漠2","duration_raw":"60","cooldown_end_epoch":1710003600,"workshop_id":123456,"workshop_url":"https://steamcommunity.com/sharedfiles/filedetails/?id=123456","achievement":"Win 10 rounds"}]}'
```

CN dry-run preview:
```bash
.venv/bin/python -m tools.map_sidecar.sidecar cn-fetch --dry-run
```

## Systemd install

### Overseas
```bash
sudo cp tools/map_sidecar/systemd/map-sidecar-ingest.service /etc/systemd/system/
sudo cp tools/map_sidecar/systemd/map-sidecar-servers.service /etc/systemd/system/
sudo cp tools/map_sidecar/systemd/map-sidecar-servers.timer /etc/systemd/system/
sudo cp tools/map_sidecar/systemd/map-sidecar-exg.service /etc/systemd/system/
sudo cp tools/map_sidecar/systemd/map-sidecar-exg.timer /etc/systemd/system/
sudo cp tools/map_sidecar/systemd/map-sidecar-index-refresh.service /etc/systemd/system/
sudo cp tools/map_sidecar/systemd/map-sidecar-index-refresh.timer /etc/systemd/system/
sudo cp tools/map_sidecar/systemd/map-sidecar-images.service /etc/systemd/system/
sudo cp tools/map_sidecar/systemd/map-sidecar-images.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now map-sidecar-ingest.service
sudo systemctl enable --now map-sidecar-servers.timer
sudo systemctl enable --now map-sidecar-exg.timer
sudo systemctl enable --now map-sidecar-index-refresh.timer
sudo systemctl enable --now map-sidecar-images.timer
```

### CN fetcher
```bash
sudo cp tools/map_sidecar/systemd/exg-fetcher-cn.service /etc/systemd/system/
sudo cp tools/map_sidecar/systemd/exg-fetcher-cn.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now exg-fetcher-cn.timer
```

## Notes

- `map_translations.json` and `map_index.json` are written atomically to the project root.
- EXG HTML is retained under `tools/map_sidecar/debug/exg_html/` on the **CN fetcher** when `DEBUG=true` or parsing fails; files older than `RETENTION_HOURS` are deleted automatically.
- Workshop images are saved as lowercase `<map_key>.jpg` under `<PROJECT_ROOT>/<STATIC_DIR_NAME>/maps/`.
- Overseas hosts do **not** fetch the EXG HTML directly; ingestion happens via the HTTP sidecar endpoint.
