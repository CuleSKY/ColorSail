# Redis Session Audit & Deployment Guide (CS2ZE)

## Scope
This audit focuses on **post-login session stability and security** when using Redis-backed server-side sessions in a Cloudflare + domestic CDN multi-layer deployment. It does **not** discuss first-time login success rate or architectural changes.

---

## Audit Conclusions (Checklist)

### 1) APP_SECRET_KEY enforcement (no fallback)
**Status: Enforced.**  
The app **fails fast** if `APP_SECRET_KEY`/`SECRET_KEY` is missing or equals `change-me`, which prevents multi-instance drift and invalid session signatures across restarts.  
**Impact:** All instances must share the **same** secret to keep session cookies valid across restarts or scaled replicas.  
**Reference:** `app.py` secret enforcement logic.

### 2) Redis connection failure behavior
**Status: Enforced (fail-fast).**  
On startup, the Redis client performs `PING`. If Redis is unreachable or misconfigured, the app raises a runtime error and **does not silently fall back** to another session backend.  
**Impact:** Prevents production from running with unintended session storage (which could cause logouts after restart).  
**Reference:** `app.py` Redis initialization.

### 3) Session TTL + rolling refresh
**Status: Enabled.**  
`PERMANENT_SESSION_LIFETIME` defaults to 30 days and `SESSION_REFRESH_EACH_REQUEST=True`.  
**Effect:** User activity renews TTL (rolling), achieving stable long-lived sessions.  
**Reference:** `app.py` session config.

### 4) Redis eviction policy risk
**Status: Requires ops configuration.**  
If Redis uses `allkeys-lru` or `volatile-lru`, sessions can be evicted under memory pressure (random logouts).  
**Recommendation:**  
- Preferred: `maxmemory-policy noeviction`  
- Acceptable with TTL-based keys: `maxmemory-policy volatile-ttl`  
**Action:** Configure in `redis.conf` and monitor memory.

### 5) Redis persistence
**Status: Requires ops configuration.**  
If Redis restarts without persistence, all sessions are lost.  
**Recommendation:**  
- Enable AOF (`appendonly yes`) for durability.  
- Keep a conservative RDB snapshot (`save 900 1`, etc.).  
**Risk Mitigation:** With AOF, Redis restarts do not invalidate all sessions.

### 6) Cookie security attributes
**Status: Enforced.**  
Cookies are **HttpOnly**, **Secure**, **SameSite=Lax**, **Path=/**, and have **Max-Age** aligned with session lifetime.  
**Domain:** Host-only by default under canonical `example.com`; **no cookie Domain** unless explicitly set.  
**Note:** Lax is required for Steam OpenID's top-level redirects to preserve cookies (Strict can cause session loss).

### 7) CDN/cache behavior and Set-Cookie retention
**Status: Enforced in source; CDN must honor.**  
The app applies `Cache-Control: no-store` to `/auth/*`, `/api/steam/*`, `/api/me`, and `/logout` responses.  
**Required CDN rules:**  
- Bypass cache for those paths.  
- Preserve `Set-Cookie` headers through both CDN layers.

---

## Required Environment Variables (Production)

```bash
# REQUIRED
APP_SECRET_KEY="a-strong-random-secret-64+chars"
REDIS_URL="redis://127.0.0.1:6379/0"

# OPTIONAL (defaults shown)
SESSION_LIFETIME_DAYS="30"
SESSION_COOKIE_DOMAIN=""  # keep empty for host-only (example.com)
SESSION_COOKIE_DOMAIN_ALLOW_CROSS_SUBDOMAIN="false"
CANONICAL_HOST="example.com"
CANONICAL_SCHEME="https"
```

> Do **not** set `SESSION_COOKIE_DOMAIN=.example.com` unless explicitly required and `SESSION_COOKIE_DOMAIN_ALLOW_CROSS_SUBDOMAIN=true`.

---

## Redis Configuration (redis.conf)

Recommended minimal production config:

```conf
bind 127.0.0.1
protected-mode yes
port 6379

# Memory safety (avoid random session eviction)
maxmemory 1gb
maxmemory-policy noeviction

# Persistence (prevent total logout on restart)
appendonly yes
appendfsync everysec
save 900 1
save 300 10
save 60 10000
```

---

## systemd service (Redis)

```ini
[Unit]
Description=Redis
After=network.target

[Service]
User=redis
Group=redis
ExecStart=/usr/bin/redis-server /etc/redis/redis.conf
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## systemd service (CS2ZE app)

```ini
[Unit]
Description=CS2ZE Web
After=network.target redis.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/cs2ze
Environment="APP_SECRET_KEY=YOUR_LONG_RANDOM_SECRET"
Environment="REDIS_URL=redis://127.0.0.1:6379/0"
Environment="SESSION_LIFETIME_DAYS=30"
Environment="CANONICAL_HOST=example.com"
Environment="CANONICAL_SCHEME=https"
ExecStart=/usr/bin/gunicorn -w 4 -k gevent -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## CDN Administrator Checklist (must-do)

1) **Bypass cache** for:
   - `/auth/*`
   - `/api/steam/*`
   - `/api/me`
   - `/logout`
2) **Preserve `Set-Cookie`** headers end-to-end.  
3) **Avoid bot challenges** on `/api/steam/login` and `/api/steam/callback` (allowlist or skip challenge).

---

## Minimal Acceptance Checklist (copy/paste)

1) Login successful -> **refresh page** -> still logged in.  
2) Close browser -> reopen -> still logged in.  
3) Wait overnight (or simulate by extending session) -> still logged in.  
4) `/auth/me` response includes `Cache-Control: no-store`.  
5) Steam domain unreachable -> existing session **still valid** (no forced logout).  
6) CDN edge inspection confirms `Set-Cookie` preserved on login/callback responses.



