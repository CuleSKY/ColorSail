import re
import threading
import time
import requests
from watcher_targets import upsert_target, update_status, list_targets, mark_stale_and_cleanup
from watcher_utils import now_ts


def _match_keywords(name, include_keywords, exclude_keywords):
    low = name.casefold()
    if include_keywords:
        if not any(k.casefold() in low for k in include_keywords):
            return False
    if exclude_keywords:
        if any(k.casefold() in low for k in exclude_keywords):
            return False
    return True


def _extract_ip_port(item):
    for key in ('ConnectUrl', 'ConnectUrl2', 'connect_url', 'connectUrl', 'connecturl', 'addr', 'address', 'Address'):
        value = item.get(key)
        if isinstance(value, str):
            m = re.search(r'(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})', value)
            if m:
                return m.group(1), int(m.group(2))
    ip = item.get('ip') or item.get('IP') or item.get('host') or item.get('Host')
    port = item.get('port') or item.get('Port')
    if ip and port:
        return str(ip), int(port)
    return None, None


def _extract_name(item):
    for key in ('name', 'Name', 'hostname', 'HostName', 'server_name', 'ServerName'):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Unknown"


class ExgDiscovery:
    def __init__(self, communities):
        self.communities = communities
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=2)

    def _run(self):
        sessions = {}
        last_refresh = {}
        while not self.stop_event.is_set():
            now = time.time()
            for comm in self.communities:
                if not comm.get('enabled'):
                    continue
                refresh_seconds = int(comm.get('refresh_seconds') or 30)
                last = last_refresh.get(comm['id'], 0)
                if now - last < refresh_seconds:
                    continue
                last_refresh[comm['id']] = now
                api_url = comm.get('api_url')
                if not api_url:
                    continue
                session = sessions.get(api_url)
                if session is None:
                    session = requests.Session()
                    sessions[api_url] = session
                include_keywords = comm.get('include_keywords') or []
                exclude_keywords = comm.get('exclude_keywords') or []
                ttl_seconds = int(comm.get('ttl_seconds') or 60)
                seen = set()
                missing_names = []
                try:
                    resp = session.get(api_url, timeout=6)
                    data = resp.json() if resp.ok else []
                except Exception:
                    data = []
                if isinstance(data, dict):
                    data = data.get('servers') or data.get('data') or []
                if not isinstance(data, list):
                    data = []
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    name = _extract_name(item)
                    if not _match_keywords(name, include_keywords, exclude_keywords):
                        continue
                    ip, port = _extract_ip_port(item)
                    if ip and port:
                        server_key = f"{ip}:{port}"
                        seen.add(server_key)
                        meta = {
                            "server_key": server_key,
                            "ip": ip,
                            "port": port,
                            "name": name,
                            "players": item.get('players') or item.get('Players') or 0,
                            "max_players": item.get('max_players') or item.get('MaxPlayers') or 64,
                            "game": comm.get('game') or "cs2",
                            "community_id": comm.get('id'),
                            "source_type": "exg_api",
                            "updated_at": now_ts(),
                            "last_seen_ts": now_ts(),
                            "state": "active"
                        }
                        upsert_target(meta)
                    else:
                        missing_names.append(name)
                if missing_names:
                    targets = list_targets()
                    for name in missing_names:
                        matches = [t for t in targets if t.get('community_id') == comm.get('id') and t.get('source_type') == 'exg_api' and t.get('name') == name]
                        if len(matches) == 1:
                            update_status(matches[0]['server_key'], state='missing', last_seen_ts=now_ts())
                mark_stale_and_cleanup(comm.get('id'), 'exg_api', seen, ttl_seconds)
            time.sleep(0.5)
