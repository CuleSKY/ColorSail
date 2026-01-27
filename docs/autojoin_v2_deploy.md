# AutoJoin v2 Deployment Notes (Main Site + WebSocket)

This project adds an isolated AutoJoin v2 subsystem:
- HTTP control: `/api/autojoin/start`, `/api/autojoin/joined`, `/api/autojoin/stop`
- Watcher event ingestion: `/api/watcher/event` (HMAC verified)
- WebSocket push: `/ws/autojoin`

The existing stable web pages/routes must remain unchanged.

## 1. Topology (Production)
Cloudflare -> OpenResty (80/443) -> Gunicorn (localhost:5000) -> Flask app

## 2. WebSocket requirement (CRITICAL)
The endpoint `/ws/autojoin` requires WebSocket support end-to-end:
- Gunicorn must run with a WebSocket-capable worker class (flask-sock).
- OpenResty must forward Upgrade/Connection headers correctly.
- Cloudflare must allow WebSocket (default allowed, but WAF/rate rules may block).

If Gunicorn runs with the default sync worker, `/ws/autojoin` will NOT work.

## 3. Gunicorn recommended launch
Use a WebSocket-capable worker (gevent) so WebSocket can function.

Example:
    gunicorn -k gevent -w 1 -b 127.0.0.1:5000 app:app

Notes:
- Start with `-w 1` and increase if needed after validation.
- If you previously used sync workers, switching to gevent may change concurrency behavior.
  Prefer a staged rollout and monitor latency/error rates.

## 4. OpenResty / Nginx reverse proxy configuration (WS)
In the server block proxying to Gunicorn (localhost:5000), ensure:

- HTTP/1.1 is used upstream
- Upgrade + Connection headers are passed
- `proxy_read_timeout` is long enough for WS (e.g. 300s)
- cache is disabled for `/ws/autojoin`

Example (location-level, safest):
    location /ws/autojoin {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        proxy_buffering off;
    }

For all other routes (existing web), keep the current stable proxy config unchanged.

## 5. Session/Cookie requirement for WS auth
The WS auth binds the connection to `steam_id` from the existing session.
Therefore:
- The WebSocket handshake MUST carry session cookies.
- OpenResty/Cloudflare must NOT strip cookies for `/ws/autojoin`.
- If you run multiple app instances behind a load balancer, you may need sticky sessions,
  otherwise WS and HTTP requests may hit different instances and event delivery can break.

## 6. Watcher event security (HMAC + anti-replay)
Watcher events are accepted only if the HMAC signature and timestamp are valid.

Headers:
- `X-Watcher-Id`
- `X-Watcher-Ts` (unix seconds)
- `X-Watcher-Signature`

Signature format (exact):
    HMAC(secret, ts + "\n" + path + "\n" + raw_body)

Notes:
- The watcher uses the path `/api/watcher/event` when signing.
- Timestamps must be within ±60s of the main site clock; older/newer will be rejected.
- Ensure `WATCHER_HMAC_SECRET` is set on the main site, and `main_site.hmac_secret` is set on the watcher.
- Optionally restrict `/api/watcher/event` at OpenResty to internal IP ranges even though HMAC exists.

## 7. Watcher service auth (shared token)
Main site -> watcher HTTP calls (`/v1/autojoin/*`) require a shared token:
- Main site must set `WATCHER_SHARED_TOKEN`.
- Watcher must set `http.shared_token` in `watcher_config.json`.

## 8. Cloudflare notes
- Ensure WebSockets are enabled (default).
- Avoid applying aggressive WAF/rate limits to `/ws/autojoin`.
- `/api/watcher/event` should NOT be publicly reachable; expose it only internally if possible.

## 9. Quick validation checklist
1) Connect to the site and confirm existing web directory works unchanged.
2) From a logged-in Prime user, open a WS connection to `/ws/autojoin`:
   - It should connect and stay open (no immediate close).
3) Start AutoJoin via `/api/autojoin/start` and verify events are delivered via WS.
4) Confirm that the watcher HMAC signature rejects invalid events.
5) Confirm `X-Watcher-Ts` outside ±60s is rejected.
