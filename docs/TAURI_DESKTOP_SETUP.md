# CS2ZE Tauri Desktop Setup (Windows)

This guide explains how the Windows desktop client (Svelte + Vite + Tauri) mirrors the web app runtime behavior, including remote JSON loading, caching, and local-only map subscriptions.

## 1) Project resource layout (source of truth)

### Repo-root `static/`
- **Location:** `/workspace/NERV_CS2ZE/static/`
- **Contents:** App logo and community icons (e.g. `nerv_logo.png`, community logo assets).
- **Usage:** These files are served at `/static/**` in dev and bundled into the desktop build output.
- **Important:** `/static/maps` is ignored (no server card images are used).

### JSON resources (remote + cached)
- **Remote sources:**
  - `config.json`
  - `language.json`
  - `map_translations.json`
- **Base URL:** Derived from the “Server source” setting (default: `https://www.cs2ze.org`).
- **Caching:** Each resource is cached with ETag and persisted for offline fallback:
  - **Browser:** `localStorage` cache entries.
  - **Tauri:** app data directory cache via `@tauri-apps/plugin-fs`.

## 2) How to run (exact commands)

### Frontend dev (Vite)
```bash
npm --prefix frontend run dev
```

### Tauri dev
```bash
cargo tauri dev
```

### Production build (optional)
```bash
cargo tauri build
```

### Required tools
- **Node.js** (for Vite dev/build)
- **Rust toolchain** (stable) + **cargo-tauri**

## 3) Settings behavior and defaults

### Server source (base URL)
- **Default:** `https://www.cs2ze.org`
- **Input normalization:**
  - If the user inputs a host without scheme, it is normalized to `https://<host>`.
  - Any extra path is ignored; the normalized value is stored as the origin.
- **Used for:**
  - `https://<base>/servers.json`
  - `https://<base>/config.json`
  - `https://<base>/language.json` (unless overridden by `config.json`)
  - `https://<base>/map_translations.json`

### Settings storage
- **localStorage** is the source of truth for the base URL, UI language, view mode, theme, etc.
- **Cached remote JSON** is stored in localStorage (browser) or app data cache (Tauri).

### Language selection
- Changing the language selection updates UI strings immediately.
- The language pack is loaded from the URL in `config.json` when present; otherwise from `/language.json` at the base URL.

## 4) Network/CORS explanation (important)

### Why CORS happens in Vite dev
Browser dev requests to `https://www.cs2ze.org/servers.json` are blocked by CORS because they are cross-origin from `http://localhost:5173`.

### How CORS is avoided
- **Vite dev:** requests are routed through a local proxy path.
  - Frontend hits `http://localhost:5173/__proxy/servers.json`.
  - Vite proxy forwards `/__proxy/**` to `https://www.cs2ze.org/**`.
- **Tauri runtime:** uses native HTTP via `@tauri-apps/plugin-http`, bypassing browser CORS entirely.

### Example URLs to verify in DevTools
- **Vite dev (browser):** `GET http://localhost:5173/__proxy/servers.json`
- **Tauri runtime:** `GET https://www.cs2ze.org/servers.json` (native HTTP)

## 5) Map subscriptions (map_subs) data format and rules

### Storage key
- **localStorage key:** `map_subs`

### Data format examples
```json
[{"map":"ze_xxx","comms":["all"]}]
```
```json
[{"map":"ze_xxx","comms":["exg","fys","zed"]}]
```

### Rules
- **No default selection:** user must choose communities explicitly before confirming.
- **“all” overrides:** selecting `all` overwrites any other selections and is persisted as `["all"]`.
- **Specific comms clear “all”:** selecting any specific comm removes `all`.

### How to test
1. Search for a map, select it.
2. Choose communities (or “all”).
3. Confirm the subscription.
4. Verify `map_subs` in localStorage and remove items to confirm persistence.

## 6) Verification checklist (copy‑pastable)

- [ ] `GET http://localhost:5173/static/nerv_logo.png` returns **200** in Vite dev.
- [ ] `GET /servers.json` loads without CORS errors in Vite dev (via `/__proxy`).
- [ ] Tauri dev loads `servers.json` via native HTTP.
- [ ] Language toggle updates UI immediately and persists after restart.
- [ ] Map subscriptions add/remove works and persists (`map_subs`).

## 7) Troubleshooting

### CORS errors in dev
- Confirm that requests are hitting `/__proxy/...` in the Network tab.
- If not, check the Vite proxy configuration in `frontend/vite.config.ts`.

### Broken images under `/static`
- Ensure `http://localhost:5173/static/nerv_logo.png` returns 200 in dev.
- Confirm `frontend/dist/static/` exists after a build (do not commit build output).

### Missing `cargo tauri` or plugin errors
- Install **cargo-tauri** and ensure the Rust toolchain is available.
- If plugins are missing, check `src-tauri/Cargo.toml` and run `cargo tauri dev` again.

### Cache weirdness
- Clear **localStorage** in the dev tools Application tab.
- For Tauri, delete the app’s cache directory under the app data folder.

## 8) Repo hygiene

Do **NOT** commit or generate:
- `dist/`, `build/`, `target/`
- Binaries: `.exe`, `.msi`, `.dmg`, `.app`, `.zip`
- Screenshots or Playwright outputs

If `.gitignore` entries are added in the future, do **not** ignore repo‑root `static/`.
