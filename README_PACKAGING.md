# CS2ZE CLI Packaging

This CLI client is fully standalone and can be packaged as a Windows executable with PyInstaller.

## Prerequisites

```bash
python -m pip install -r client/requirements.txt
python -m pip install pyinstaller
```

## Build

```bash
pyinstaller --onefile --name cs2ze client/main.py
```

The executable will be created under `dist/cs2ze.exe`.

## Configuration

The client reads the following environment variables (and **only** these):

- `CS2ZE_SERVER_LIST_URL` (optional override)
- `CS2ZE_WATCHER_URL` (optional)
- `CS2ZE_AUTH_TOKEN` (optional)

If `CS2ZE_SERVER_LIST_URL` is not set or is invalid, the client will prompt for a server list URL, test-fetch it immediately, and save it to `client/config.json` (relative to the working directory, or next to the executable when frozen) on success.

You can also override the server list URL for a single run:

```bash
cs2ze --server-list-url https://example.com/servers.json list
```
