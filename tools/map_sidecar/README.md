# Map Sidecar

This sidecar owns **all write paths** for map metadata, exports, and workshop images. The Flask main server stays read-only and continues to serve `/servers.json` even if the sidecar is offline.

## Environment variables

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
- `DEBUG` (`true` to retain EXG HTML snapshots for debugging)

## Commands

```bash
python -m tools.map_sidecar.main poll-servers
python -m tools.map_sidecar.main ingest-exg
python -m tools.map_sidecar.main refresh-index
python -m tools.map_sidecar.main fetch-images
```

## Systemd timers

Copy the unit/timer files from `tools/map_sidecar/systemd/` to `/etc/systemd/system/` and enable them:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now map-sidecar-servers.timer
sudo systemctl enable --now map-sidecar-exg.timer
sudo systemctl enable --now map-sidecar-index-refresh.timer
sudo systemctl enable --now map-sidecar-images.timer
```

## Notes

- `map_translations.json` and `map_index.json` are written atomically to the project root.
- EXG HTML is only retained under `tools/map_sidecar/debug/exg_html/` when `DEBUG=true` or parsing fails; files older than 72 hours are deleted automatically.
- Workshop images are saved as lowercase `<map_key>.jpg` under `<PROJECT_ROOT>/<STATIC_DIR_NAME>/maps/`.
