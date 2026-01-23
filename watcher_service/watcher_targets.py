import threading
from watcher_utils import now_ts

_TARGETS = {}
_LOCK = threading.Lock()


def _sanitize_meta(meta):
    ts = now_ts()
    server_key = meta.get('server_key')
    ip = meta.get('ip')
    port = meta.get('port')
    if not server_key and ip and port:
        server_key = f"{ip}:{port}"
    if not server_key:
        return None
    return {
        "server_key": server_key,
        "ip": ip or meta.get('server_key', '').split(':')[0],
        "port": int(port) if port is not None else int(server_key.split(':')[1]),
        "name": meta.get('name') or "Unknown",
        "players": int(meta.get('players') or 0),
        "max_players": int(meta.get('max_players') or 64),
        "game": meta.get('game') or "cs2",
        "community_id": meta.get('community_id') or "",
        "source_type": meta.get('source_type') or "",
        "updated_at": int(meta.get('updated_at') or ts),
        "last_seen_ts": int(meta.get('last_seen_ts') or ts),
        "state": meta.get('state') or "active",
        "a2s_unavailable": bool(meta.get('a2s_unavailable') or False)
    }


def upsert_target(meta):
    clean = _sanitize_meta(meta)
    if not clean:
        return None
    with _LOCK:
        existing = _TARGETS.get(clean['server_key'], {})
        merged = {**existing, **clean}
        _TARGETS[clean['server_key']] = merged
        return dict(merged)


def update_status(server_key, **kwargs):
    with _LOCK:
        existing = _TARGETS.get(server_key)
        if not existing:
            return None
        existing.update(kwargs)
        existing['updated_at'] = int(kwargs.get('updated_at') or now_ts())
        _TARGETS[server_key] = existing
        return dict(existing)


def get_target(server_key):
    with _LOCK:
        target = _TARGETS.get(server_key)
        return dict(target) if target else None


def list_targets():
    with _LOCK:
        return [dict(v) for v in _TARGETS.values()]


def mark_stale_and_cleanup(community_id, source_type, seen_keys, ttl_seconds):
    now = now_ts()
    with _LOCK:
        keys = [k for k, v in _TARGETS.items() if v.get('community_id') == community_id and v.get('source_type') == source_type]
        for key in keys:
            target = _TARGETS.get(key)
            if not target:
                continue
            if key in seen_keys:
                continue
            target['state'] = 'stale'
            _TARGETS[key] = target
            last_seen = int(target.get('last_seen_ts') or 0)
            if last_seen and now - last_seen > ttl_seconds:
                _TARGETS.pop(key, None)
