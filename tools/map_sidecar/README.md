# Map Sidecar

This sidecar owns **all write paths** for map metadata, exports, and workshop images. The Flask main server stays read-only and continues to serve `/servers.json` even if the sidecar is offline.

## Environment variables (overseas sidecar)

Required:
- `MYSQL_HOST`
- `MYSQL_PORT` (default: `3306`)
- `MYSQL_DB`
- `MYSQL_USER`
- `MYSQL_PASSWORD`

Optional:
- `REDIS_URL` (preferred) or `REDIS_HOST` + `REDIS_PORT` + `REDIS_PASSWORD`
- `MAIN_SERVERS_JSON_URL` (default: `https://www.cs2ze.org/servers.json`)
- `PROJECT_ROOT` (default: `/opt/1panel/www/sites/www.cs2ze.org/NERV_CS2ZE`)
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

## Environment variables (CN fetcher)

Required:
- `OVERSEAS_INGEST_URL` (e.g. `https://www.cs2ze.org/sidecar/exg/ingest`)
- `INGEST_TOKEN`
- `PROJECT_ROOT` (where this repo is deployed on the CN machine)

Optional:
- `EXG_MAPLIST_URL` (default: `https://list.darkrp.cn:9000/serverlist/cs2maplist`)
- `FETCH_TIMEOUT_SECONDS` (default: `15`)
- `RETENTION_HOURS` (default: `72`)
- `DEBUG` (`true` to retain EXG HTML snapshots)

## Commands

Overseas sidecar:
```bash
python tools/map_sidecar/map_sidecar.py poll-servers
python tools/map_sidecar/map_sidecar.py ingest-exg   # disabled on overseas hosts
python tools/map_sidecar/map_sidecar.py exg-health
python tools/map_sidecar/map_sidecar.py refresh-index
python tools/map_sidecar/map_sidecar.py fetch-images
python tools/map_sidecar/ingest_server.py
```

CN fetcher:
```bash
python tools/map_sidecar/cn_fetcher.py
python tools/map_sidecar/cn_fetcher.py --dry-run
```

## Systemd (overseas)

Copy only the overseas unit/timer files and enable them. The units already point to
`/opt/1panel/www/sites/www.cs2ze.org/NERV_CS2ZE/.venv/bin/python`; adjust the paths if your
deployment differs.

```bash
sudo cp tools/map_sidecar/systemd/map-sidecar-servers.service /etc/systemd/system/
sudo cp tools/map_sidecar/systemd/map-sidecar-servers.timer /etc/systemd/system/
sudo cp tools/map_sidecar/systemd/map-sidecar-exg.service /etc/systemd/system/
sudo cp tools/map_sidecar/systemd/map-sidecar-exg.timer /etc/systemd/system/
sudo cp tools/map_sidecar/systemd/map-sidecar-index-refresh.service /etc/systemd/system/
sudo cp tools/map_sidecar/systemd/map-sidecar-index-refresh.timer /etc/systemd/system/
sudo cp tools/map_sidecar/systemd/map-sidecar-images.service /etc/systemd/system/
sudo cp tools/map_sidecar/systemd/map-sidecar-images.timer /etc/systemd/system/
sudo cp tools/map_sidecar/systemd/map-sidecar-ingest.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now map-sidecar-ingest.service
sudo systemctl enable --now map-sidecar-servers.timer
sudo systemctl enable --now map-sidecar-exg.timer
sudo systemctl enable --now map-sidecar-index-refresh.timer
sudo systemctl enable --now map-sidecar-images.timer
```

## Systemd (CN fetcher)

```bash
sudo cp tools/map_sidecar/systemd/exg-fetcher-cn.service /etc/systemd/system/
sudo cp tools/map_sidecar/systemd/exg-fetcher-cn.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now exg-fetcher-cn.timer
```

## Example environment files

Overseas `/etc/default/map-sidecar`:
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

CN `/etc/default/exg-fetcher`:
```bash
PROJECT_ROOT=/opt/cs2ze/NERV_CS2ZE
EXG_MAPLIST_URL=https://list.darkrp.cn:9000/serverlist/cs2maplist
OVERSEAS_INGEST_URL=https://www.cs2ze.org/sidecar/exg/ingest
INGEST_TOKEN=REPLACE_ME
FETCH_TIMEOUT_SECONDS=15
RETENTION_HOURS=72
DEBUG=false
```

## Curl examples (overseas ingest endpoint)

```bash
curl -i -X POST https://www.cs2ze.org/sidecar/exg/ingest \
  -H 'Authorization: Bearer REPLACE_ME' \
  -H 'Content-Type: application/json' \
  -d '{"source":"exg_maplist","fetched_at_epoch":1710000000,"records":[{"map":"de_dust2","name_zh_cn":"沙漠2","duration_raw":"60","cooldown_end_epoch":1710003600,"workshop_id":123456,"workshop_url":"https://steamcommunity.com/sharedfiles/filedetails/?id=123456","achievement":"Win 10 rounds"}]}'
```

```bash
curl -i -X POST https://www.cs2ze.org/sidecar/exg/ingest \
  -H 'Authorization: Bearer WRONG_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"records":[]}'
```

## Notes

- `map_translations.json` and `map_index.json` are written atomically to the project root.
- EXG HTML is only retained under `tools/map_sidecar/debug/exg_html/` on the **CN fetcher** when `DEBUG=true` or parsing fails; files older than `RETENTION_HOURS` are deleted automatically.
- Workshop images are saved as lowercase `<map_key>.jpg` under `<PROJECT_ROOT>/<STATIC_DIR_NAME>/maps/`.
- Overseas hosts do **not** fetch the EXG HTML directly; ingestion happens via the HTTP sidecar endpoint.
