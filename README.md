# NERV CS2ZE (Open Source Edition)

This repository is a sanitized minimal release of the CS2ZE web project.
It is intended for open-source sharing, local development, and reference deployment.

## What is included

- Flask backend (`app.py`, `main_app.py`, `admin_app.py`)
- Vue 3 frontend source (`frontend/`)
- Static/template assets (`static/`, `templates/`)
- Map sidecar pipeline tools (`tools/map_sidecar/`)
- Documentation for embed/client protocol and session deployment (`docs/`)
- Example secret/config files (`secrets.example.json`, `config.example.json`)

## What is removed or sanitized

- Real production tokens
- Real Steam/OpenID secrets
- Real private server addresses and domains
- Any environment-specific sensitive values

Use only the example files, then create your own local secrets.

## Quick start

### 1) Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Frontend

```bash
cd frontend
npm ci
npm run dev
```

To build production assets:

```bash
cd frontend
npm ci
npm run build
```

### 3) Run services locally

Main site:

```bash
gunicorn -w 1 -b 127.0.0.1:5000 wsgi_main:application
```

Admin site:

```bash
gunicorn -w 1 -b 127.0.0.1:5001 wsgi_admin:application
```

## Configuration

- Copy `secrets.example.json` to `secrets.json` and fill your local values.
- Copy `config.example.json` to `config.json` and adjust for your environment.
- Never commit real secrets to git.

## Map sidecar pipeline

Data flow:

```text
EXG source -> CN fetcher -> overseas ingest -> MySQL snapshot
-> exporter -> static/map_index.json + static/time.json
```

Key modules:

- `tools/map_sidecar/cn_fetcher.py`
- `tools/map_sidecar/ingest_server.py`
- `tools/map_sidecar/exporter.py`
- `tools/map_sidecar/sidecar.py`

## Embedding and protocol docs

- `docs/embed_servers.md`
- `docs/client-protocol.md`
- `docs/redis_session_audit.md`

## Security checklist before publishing

1. Ensure `.gitignore` excludes secrets, logs, and session artifacts.
2. Rotate all production tokens and API keys used in the old repo.
3. Confirm no private domains/IPs remain in tracked files.
4. Run a secret scan before pushing public commits.

## Notes

- This edition is intentionally minimal.
- Some internal scripts remain for compatibility but may need environment-specific setup.
- Frontend and backend defaults are safe placeholders.
