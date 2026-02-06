import json
import time
import sqlite3
import requests
import os
import threading
import colorsys
import socket
import urllib3
import hashlib
import hmac
import ipaddress
import secrets
import re
import atexit
import tempfile
from flask import current_app, abort, make_response
from pathlib import Path
from collections import deque, OrderedDict
from types import MappingProxyType
from urllib.parse import urlencode
from datetime import datetime
from datetime import timedelta
from flask import Flask, render_template, jsonify, request, redirect, session, url_for, make_response, abort
from jinja2 import TemplateNotFound
from flask_session import Session
from redis import Redis
from flask_sock import Sock
from werkzeug.middleware.proxy_fix import ProxyFix
import a2s
from apscheduler.schedulers.background import BackgroundScheduler
from concurrent.futures import ThreadPoolExecutor
try:
    from opencc import OpenCC
except Exception:
    OpenCC = None

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

STATIC_DIR = 'static'
if not os.path.isdir(STATIC_DIR) and os.path.isdir('Static'):
    STATIC_DIR = 'Static'

app = Flask(__name__, static_folder=STATIC_DIR)
SECRET_KEY = os.environ.get('APP_SECRET_KEY') or os.environ.get('SECRET_KEY')
if not SECRET_KEY or SECRET_KEY == 'change-me':
    raise RuntimeError("APP_SECRET_KEY/SECRET_KEY must be set to a fixed non-default value.")
app.secret_key = SECRET_KEY
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
sock = Sock(app)

VITE_MANIFEST_PATH = os.path.join(app.static_folder, 'assets', 'manifest.json')
_vite_manifest_cache = None
_vite_manifest_mtime = 0.0


def _load_vite_manifest():
    global _vite_manifest_cache, _vite_manifest_mtime
    if not os.path.exists(VITE_MANIFEST_PATH):
        return None
    mtime = os.path.getmtime(VITE_MANIFEST_PATH)
    if _vite_manifest_cache is None or mtime != _vite_manifest_mtime:
        with open(VITE_MANIFEST_PATH, 'r', encoding='utf-8') as handle:
            _vite_manifest_cache = json.load(handle)
        _vite_manifest_mtime = mtime
    return _vite_manifest_cache


def vite_manifest(entry='index.html'):
    dev_server = os.environ.get('VITE_DEV_SERVER')
    if dev_server and app.debug:
        dev_server = dev_server.rstrip('/')
        dev_entry = 'src/main.ts' if entry.endswith('.html') else entry
        return {
            'js': f"{dev_server}/{dev_entry}",
            'css': []
        }
    manifest = _load_vite_manifest()
    if not manifest:
        raise RuntimeError(
            "Vite manifest not found. Run `cd frontend && npm run build` or set VITE_DEV_SERVER for dev."
        )
    if entry not in manifest:
        raise KeyError(f"Vite manifest entry missing: {entry}")
    chunk = manifest[entry]
    js_path = f"/static/assets/{chunk['file']}"
    css_paths = [f"/static/assets/{css}" for css in chunk.get('css', [])]
    return {
        'js': js_path,
        'css': css_paths
    }


app.jinja_env.globals['vite_manifest'] = vite_manifest

FRAGMENT_CACHE_SECONDS = 86400

#SEO优化
SEO_DATA = {
    'zh-CN': {
        'title': 'NERV CS2ZE Browser - CS2 僵尸逃跑服务器列表',
        'desc': '实时查询 CS2 Zombie Escape (ZE) 服务器列表、在线人数、地图翻译及历史数据统计。支持国内外社区。',
        'keywords': 'CS2, ZE, 僵尸逃跑, 服务器列表, 地图翻译, NERV, 社区统计'
    },
    'zh-TW': {
        'title': 'NERV CS2ZE Browser - CS2 殭屍逃跑伺服器列表',
        'desc': '即時查詢 CS2 Zombie Escape (ZE) 伺服器列表、在線人數、地圖翻譯及歷史數據統計。支援國內外社區。',
        'keywords': 'CS2, ZE, 殭屍逃跑, 伺服器列表, 地圖翻譯, NERV, 社區統計'
    },
    'en': {
        'title': 'NERV CS2ZE Browser - CS2 Zombie Escape Server List & Stats',
        'desc': 'Real-time CS2 Zombie Escape (ZE) server list, player statistics, and historical data. Supporting ALL ZE communities.',
        'keywords': 'CS2, Zombie Escape, ZE, Server List, Map Translation, NERV, CS2 Stats'
    }
}

# --- 基础配置 ---
CONFIG_FILE = 'config.json'
TRANS_FILE = 'map_translations.json'
LANGUAGE_FILE = 'language.json'
DB_FILE = "stats.db"
STATIC_MAP_DIR = os.path.join(STATIC_DIR, 'maps')
PRIME_USERS_FILE = 'prime_users.json'
PRIME_AUDIT_FILE = 'prime_audit.log'
ADMIN_HOSTNAME = "admin.cs2ze.org"
PUBLIC_HOSTNAMES = {"www.cs2ze.org", "cs2ze.org"}
CANONICAL_HOST = os.environ.get('CANONICAL_HOST', 'www.cs2ze.org').strip().lower()
CANONICAL_SCHEME = os.environ.get('CANONICAL_SCHEME', 'https').strip().lower()
CANONICAL_ORIGIN = f"{CANONICAL_SCHEME}://{CANONICAL_HOST}"

# EXG API 地址
EXG_API_URL = "https://list.darkrp.cn:9000/ServerList/CurrentStatus"
EXG_SESSION = requests.Session()
EXG_CACHE = []
EXG_CACHE_UPDATED_AT = 0

os.makedirs(STATIC_MAP_DIR, exist_ok=True)

# --- 全局状态 ---
SERVER_CACHE = {}
SERVER_CACHE_HASH = {}  # per-cid hash to avoid cache churn when payloads are unchanged
SERVER_CACHE_VERSION = 0  # bump when SERVER_CACHE mutates so public caches can rebuild
AGENT_CACHE = {}
AGENT_CACHE_UPDATED_AT = {}
COMMUNITY_META = []
ADMIN_STEAM_IDS = set()
PRIME_USERS_SET = set()
PRIME_USERS_META = {}
PRIME_USERS_LOCK = threading.Lock()
PRIME_RATE_LIMITS = {}
PRIME_RATE_LOCK = threading.Lock()
FYS_COMMUNITY_IDS = set()
MAP_IMAGE_INDEX = {}
MAP_IMAGE_MTIME = 0
MAP_TRANS_CACHE = {}
MAP_TRANS_NORMALIZED = {}
MAP_TRANS_DIRTY = False
MAP_TRANS_LAST_WRITE = 0.0
MAP_TRANS_WRITE_INTERVAL_SECONDS = 15
MAPLIST_NORMALIZED_CACHE = {}
MAPLIST_NORMALIZED_MTIME = 0
MAP_TRANS_LOCK = threading.Lock()
MAPLIST_NORMALIZED_LOCK = threading.Lock()
SERVER_CACHE_LOCK = threading.Lock()
AGENT_CACHE_LOCK = threading.Lock()
PUBLIC_BUILD_LOCK = threading.Lock()
PUBLIC_BUILD_COND = threading.Condition(PUBLIC_BUILD_LOCK)
PUBLIC_BUILDING = False
PUBLIC_BUILD_TARGET_VER = -1
EMPTY_JSON_BYTES = b'{}'
EMPTY_JSON_ETAG = f"\"{hashlib.sha256(EMPTY_JSON_BYTES).hexdigest()}\""
PUBLIC_SERVERS_BYTES = EMPTY_JSON_BYTES  # cached /servers.json payload to avoid per-request serialization
PUBLIC_SERVERS_ETAG = EMPTY_JSON_ETAG
PUBLIC_SERVERS_BUILT_AT = 0.0
PUBLIC_SERVERS_BUILT_VER = -1
API_BUILD_LOCK = threading.Lock()
API_BUILD_COND = threading.Condition(API_BUILD_LOCK)
API_BUILDING = False
API_BUILD_TARGET_VER = -1
API_SERVERS_BYTES = EMPTY_JSON_BYTES
API_SERVERS_ETAG = EMPTY_JSON_ETAG
API_SERVERS_BUILT_AT = 0.0
API_SERVERS_BUILT_VER = -1
CID_CACHE_LOCK = threading.Lock()
CID_SERVERS_CACHE = {}  # per-cid cache for /api/servers/<cid> (version, payload_bytes, etag)
MAP_CACHE_UPDATED_AT = 0
APP_INIT_LOCK = threading.Lock()
APP_INITIALIZED = False
CONFIG_SNAPSHOT = {
    "communities": tuple(),
    "community_meta": tuple(),
    "server_order_index": MappingProxyType({}),
    "admin_steam_ids": frozenset(),
    "fys_ids": frozenset(),
    "stats_export_retention_days": 30
}
CONFIG_SNAPSHOT_MTIME = 0.0
CONFIG_SNAPSHOT_VERSION = 0
CONFIG_SNAPSHOT_LOCK = threading.Lock()
CONFIG_REFRESH_INTERVAL_SECONDS = 2
CONFIG_REFRESHER_STARTED = False
CONFIG_REFRESHER_THREAD = None
CONFIG_SNAPSHOT_ERROR_MTIME = None
CACHE_REFRESH_INTERVAL_SECONDS = 300
DNS_CACHE = {}
DNS_CACHE_LOCK = threading.Lock()
DNS_CACHE_TTL_SECONDS = 300
DNS_CACHE_MAX_ENTRIES = 2048
OPENCC_S2T = OpenCC('s2t') if OpenCC else None
OPENCC_S2HK = OpenCC('s2hk') if OpenCC else None
OPENCC_S2TWP = OpenCC('s2twp') if OpenCC else None

EXG_FETCH_INTERVAL_SECONDS = 10
EXG_VERIFY_SSL = os.environ.get('EXG_VERIFY_SSL', 'true').lower() in ('1', 'true', 'yes')

EXG_STATS_EXCLUDE_KEYWORDS = ("pve", "大厅", "躲猫猫", "mg")
FYS_STATS_INCLUDE_NAME = "僵尸逃跑"
FYS_STATS_EXCLUDE_KEYWORDS = ("大厅", "匪镇谍影", "魔兽混战", "休闲娱乐")
STATS_CACHE_TTL_SECONDS = 10 * 60
STATS_CACHE = None
STATS_CACHE_UPDATED_AT = 0
STATS_EXPORT_RETENTION_DAYS = 30

STEAM_OPENID_ENDPOINT = "https://steamcommunity.com/openid/login"
STEAM_OPENID_NS = "http://specs.openid.net/auth/2.0"
STEAM_AUTH_STATE_TTL_SECONDS = 10 * 60
STEAM_PROFILE_CACHE_TTL_SECONDS = 10 * 60

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_REQUEST_BYTES', 2 * 1024 * 1024))
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=int(os.environ.get('SESSION_LIFETIME_DAYS', '30')))
app.config['SESSION_COOKIE_MAX_AGE'] = int(app.config['PERMANENT_SESSION_LIFETIME'].total_seconds())

cookie_domain_env = os.environ.get('SESSION_COOKIE_DOMAIN')
if cookie_domain_env:
    cookie_domain_env = cookie_domain_env.strip()
    if cookie_domain_env == '.cs2ze.org':
        allow_cross = os.environ.get('SESSION_COOKIE_DOMAIN_ALLOW_CROSS_SUBDOMAIN', '').lower() in ('1', 'true', 'yes')
        if not allow_cross:
            raise RuntimeError("SESSION_COOKIE_DOMAIN=.cs2ze.org is not allowed without explicit opt-in.")
    app.config['SESSION_COOKIE_DOMAIN'] = cookie_domain_env

REDIS_URL = os.environ.get('REDIS_URL', '').strip()
if REDIS_URL:
    app.config['SESSION_TYPE'] = 'redis'
    redis_client = Redis.from_url(REDIS_URL)
    try:
        redis_client.ping()
    except Exception as e:
        raise RuntimeError(f"Redis session backend unavailable: {e}")
    app.config['SESSION_REDIS'] = redis_client
else:
    app.config['SESSION_TYPE'] = 'filesystem'
    session_dir = os.environ.get('SESSION_FILE_DIR', os.path.join(os.getcwd(), 'session_files'))
    os.makedirs(session_dir, exist_ok=True)
    app.config['SESSION_FILE_DIR'] = session_dir
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_PERMANENT'] = True
Session(app)

AGENT_ALLOWED_CIDRS = [cidr.strip() for cidr in os.environ.get('AGENT_ALLOWED_CIDRS', '').split(',') if cidr.strip()]
AGENT_TRUSTED_PROXIES = [cidr.strip() for cidr in os.environ.get('AGENT_TRUSTED_PROXIES', '').split(',') if cidr.strip()]
AGENT_SIGNATURE_TTL_SECONDS = int(os.environ.get('AGENT_SIGNATURE_TTL_SECONDS', '300'))
WATCHER_SERVICE_URL = os.environ.get('WATCHER_SERVICE_URL', 'http://127.0.0.1:5010').rstrip('/')
WATCHER_CN_URL = os.environ.get('WATCHER_CN_URL')
WATCHER_US_URL = os.environ.get('WATCHER_US_URL')
WATCHER_HMAC_SECRET = os.environ.get('WATCHER_HMAC_SECRET')
WATCHER_ALLOWED_IDS = {x.strip() for x in os.environ.get('WATCHER_ALLOWED_IDS', '').split(',') if x.strip()}

# --- 1. 辅助函数 ---
def generate_distinct_colors(n):
    colors = []
    if n < 1: return colors
    for i in range(n):
        hue = i / n 
        rgb = colorsys.hsv_to_rgb(hue, 0.75, 0.95)
        r, g, b = int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255)
        colors.append(f'#{r:02x}{g:02x}{b:02x}')
    return colors

def refresh_local_caches(force=False):
    """刷新地图图片索引和翻译文件"""
    global MAP_IMAGE_INDEX
    global MAP_IMAGE_MTIME
    global MAP_TRANS_CACHE
    global MAP_TRANS_NORMALIZED
    global MAP_TRANS_DIRTY
    global MAPLIST_NORMALIZED_CACHE
    global MAPLIST_NORMALIZED_MTIME
    global MAP_CACHE_UPDATED_AT
    now = int(time.time())
    if not force and (now - MAP_CACHE_UPDATED_AT) < CACHE_REFRESH_INTERVAL_SECONDS:
        return
    try:
        if os.path.exists(STATIC_MAP_DIR):
            dir_mtime = int(os.path.getmtime(STATIC_MAP_DIR))
            if force or dir_mtime != MAP_IMAGE_MTIME:
                files = {}
                # 先遍历一遍，建立基础索引
                for f in os.listdir(STATIC_MAP_DIR):
                    if f.lower().endswith(('.jpg', '.png', '.webp', '.jpeg')):
                        map_name = f.rsplit('.', 1)[0].lower()
                        ext = f.rsplit('.', 1)[1].lower()
        
                    # 逻辑：如果这个地图还没记录，或者新发现的是 webp (由于 webp 体积小，我们希望覆盖掉 jpg/png)
                    if map_name not in files:
                        files[map_name] = f
                    elif ext == 'webp':
                        files[map_name] = f
                MAP_IMAGE_INDEX = files
                MAP_IMAGE_MTIME = dir_mtime
                print(f"[Cache] 已加载 {len(MAP_IMAGE_INDEX)} 个地图图片")
    except Exception as e:
        print(f"[Cache] 图片索引加载失败: {e}")
        MAP_IMAGE_INDEX = {}

    try:
        with MAP_TRANS_LOCK:
            if os.path.exists(TRANS_FILE):
                with open(TRANS_FILE, 'r', encoding='utf-8') as f:
                    raw_trans = json.load(f)
            else:
                raw_trans = {}
            normalized = {}
            cleaned = {}
            for key, value in raw_trans.items():
                if isinstance(value, dict):
                    zh_cn = (value.get('zh_cn') or value.get('cn') or '').strip()
                    zh_tw = (value.get('zh_tw') or value.get('tw') or '').strip()
                    if zh_cn and not zh_tw:
                        zh_tw = convert_to_traditional(zh_cn)
                else:
                    zh_cn = str(value).strip()
                    zh_tw = convert_to_traditional(zh_cn) if zh_cn else ''
                entry = {"zh_cn": zh_cn, "zh_tw": zh_tw}
                cleaned[key] = entry
                normalized_key = normalize_map_name(key)
                if normalized_key and normalized_key not in normalized:
                    normalized[normalized_key] = entry
            MAP_TRANS_CACHE = cleaned
            MAP_TRANS_NORMALIZED = normalized
            MAP_TRANS_DIRTY = False
            print(f"[Cache] 已加载 {len(MAP_TRANS_CACHE)} 个地图翻译")
    except Exception as e:
        print(f"[Cache] 翻译加载失败: {e}")
        MAP_TRANS_CACHE = {}
        MAP_TRANS_NORMALIZED = {}
        MAP_TRANS_DIRTY = False

    try:
        normalized_path = os.path.join(app.static_folder, "data", "maplist_normalized.json")
        if os.path.exists(normalized_path):
            mtime = int(os.path.getmtime(normalized_path))
            if force or mtime != MAPLIST_NORMALIZED_MTIME:
                with MAPLIST_NORMALIZED_LOCK:
                    with open(normalized_path, "r", encoding="utf-8") as handle:
                        data = json.load(handle)
                    if isinstance(data, list):
                        normalized = {}
                        for entry in data:
                            if not isinstance(entry, dict):
                                continue
                            map_key = normalize_map_name(entry.get("map"))
                            if not map_key:
                                continue
                            if map_key in normalized:
                                continue
                            normalized[map_key] = entry
                        MAPLIST_NORMALIZED_CACHE = normalized
                        MAPLIST_NORMALIZED_MTIME = mtime
                        print(f"[Cache] 已加载 {len(MAPLIST_NORMALIZED_CACHE)} 条 EXG maplist 记录")
                    else:
                        raise ValueError("maplist_normalized.json must be a list")
        else:
            MAPLIST_NORMALIZED_CACHE = {}
            MAPLIST_NORMALIZED_MTIME = 0
    except Exception as e:
        print(f"[Cache] EXG maplist 加载失败: {e}")
        MAPLIST_NORMALIZED_CACHE = {}
        MAPLIST_NORMALIZED_MTIME = 0
    MAP_CACHE_UPDATED_AT = now

def convert_to_traditional(text):
    if not text:
        return ''
    try:
        if OPENCC_S2T:
            return OPENCC_S2T.convert(text)
        fallback_map = str.maketrans({
            "汉": "漢",
            "龙": "龍",
            "门": "門",
            "风": "風",
            "画": "畫",
            "楼": "樓",
            "体": "體",
            "云": "雲",
            "战": "戰",
            "峡": "峽",
        })
        return str(text).translate(fallback_map)
    except Exception:
        return text

def ip_in_cidrs(client_ip, cidrs):
    if not cidrs:
        return False
    try:
        ip_obj = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for cidr in cidrs:
        try:
            if ip_obj in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False

def get_client_ip(req):
    remote_ip = req.remote_addr
    if not remote_ip:
        return None
    if AGENT_TRUSTED_PROXIES and ip_in_cidrs(remote_ip, AGENT_TRUSTED_PROXIES):
        forwarded_for = req.headers.get('X-Forwarded-For', '')
        if forwarded_for:
            first_ip = forwarded_for.split(',')[0].strip()
            if first_ip:
                return first_ip
    return remote_ip

def client_ip_allowed(client_ip):
    if not AGENT_ALLOWED_CIDRS:
        return True
    if not client_ip:
        return False
    return ip_in_cidrs(client_ip, AGENT_ALLOWED_CIDRS)

def ensure_csrf_token():
    if session.get('steam_logged_in') and session.get('steam_id'):
        if not session.get('csrf_token'):
            session['csrf_token'] = secrets.token_urlsafe(32)

def validate_csrf_token():
    token = request.form.get('csrf_token', '')
    session_token = session.get('csrf_token', '')
    if not token or not session_token or token != session_token:
        return False
    return True

def is_logged_in():
    steam_id = session.get('steam_id')
    return bool(session.get('steam_logged_in')) and bool(steam_id)

def get_config_snapshot():
    return CONFIG_SNAPSHOT

def is_admin_user():
    steam_id = session.get('steam_id')
    snapshot = get_config_snapshot()
    return is_logged_in() and steam_id in snapshot['admin_steam_ids']

def get_request_host():
    forwarded_host = request.headers.get('X-Forwarded-Host', '')
    host = forwarded_host or request.headers.get('Host', '')
    if not host:
        return ""
    return host.split(',')[0].strip()

def normalize_host(host):
    if not host:
        return ""
    return host.split(':')[0].strip().lower()

def is_admin_host():
    return normalize_host(get_request_host()) == ADMIN_HOSTNAME

def is_public_host():
    return normalize_host(get_request_host()) in PUBLIC_HOSTNAMES

@app.before_request
def enforce_canonical_host():
    if session.get('steam_logged_in'):
        session.permanent = True
    if is_admin_host():
        return None
    host = normalize_host(get_request_host())
    if host and host in PUBLIC_HOSTNAMES and CANONICAL_HOST and host != CANONICAL_HOST:
        scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
        target = f"{scheme}://{CANONICAL_HOST}{request.path}"
        qs = request.query_string.decode()
        if qs:
            target = f"{target}?{qs}"
        return redirect(target, code=301)
    return None

def require_admin():
    if is_admin_host():
        return None
    if not is_admin_user():
        return make_response("Forbidden", 403)
    return None

def is_prime_user():
    steam_id = session.get('steam_id')
    if not is_logged_in():
        return False
    return steam_id in PRIME_USERS_SET

def validate_steam64(value):
    if value is None:
        return None
    normalized = str(value).strip().replace(' ', '')
    if not normalized.isdigit():
        return None
    if len(normalized) < 15 or len(normalized) > 20:
        return None
    return normalized

def make_fast_join_url(game, ip, port):
    appid = 730 if str(game).lower() == 'cs2' else 240
    return f"steam://rungameid/{appid}//+connect%20{ip}:{port}"

def require_valid_origin():
    origin = request.headers.get('Origin', '')
    if not origin:
        return make_response("Forbidden", 403)
    if origin != CANONICAL_ORIGIN:
        return make_response("Forbidden", 403)
    return None

def log_prime_audit(action, admin_id, target_id, result, reason):
    ts = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    line = f"{ts} {action} admin={admin_id} target={target_id} result={result} reason={reason}\n"
    try:
        with open(PRIME_AUDIT_FILE, 'a', encoding='utf-8') as f:
            f.write(line)
    except Exception as e:
        print(f"[PrimeAudit] write failed: {e}")

def load_prime_users():
    global PRIME_USERS_SET, PRIME_USERS_META
    with PRIME_USERS_LOCK:
        if not os.path.exists(PRIME_USERS_FILE):
            data = {"updated_at": int(time.time()), "users": []}
            try:
                with open(PRIME_USERS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[Prime] create file failed: {e}")
        try:
            with open(PRIME_USERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"[Prime] load failed: {e}")
            data = {"updated_at": 0, "users": []}
        users = data.get('users', [])
        prime_set = set()
        prime_meta = {}
        for entry in users:
            if not isinstance(entry, dict):
                continue
            sid = str(entry.get('steam_id', '')).strip()
            if not sid:
                continue
            prime_set.add(sid)
            prime_meta[sid] = {
                "steam_id": sid,
                "persona_name": entry.get('persona_name') or "Unknown",
                "added_by": entry.get('added_by') or "",
                "added_at": int(entry.get('added_at') or 0)
            }
        PRIME_USERS_SET = prime_set
        PRIME_USERS_META = prime_meta

def _write_prime_users_locked():
    data = {
        "updated_at": int(time.time()),
        "users": list(PRIME_USERS_META.values())
    }
    temp_path = f"{PRIME_USERS_FILE}.tmp"
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, PRIME_USERS_FILE)

def write_prime_users():
    with PRIME_USERS_LOCK:
        _write_prime_users_locked()

def fetch_persona_name(steam_id):
    if not steam_id:
        return "Unknown"
    url = f"https://steamcommunity.com/profiles/{steam_id}/?xml=1"
    try:
        resp = requests.get(url, timeout=10)
    except Exception as e:
        print(f"[Prime] persona fetch failed: {e}")
        return "Unknown"
    if resp.status_code != 200:
        print(f"[Prime] persona fetch HTTP {resp.status_code}")
        return "Unknown"
    match = re.search(r"<steamID><!\[CDATA\[(.*?)\]\]></steamID>", resp.text)
    return match.group(1) if match else "Unknown"

def normalize_json(payload):
    if isinstance(payload, MappingProxyType):
        return {key: normalize_json(value) for key, value in payload.items()}
    if isinstance(payload, dict):
        return {key: normalize_json(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [normalize_json(value) for value in payload]
    if isinstance(payload, (set, frozenset)):
        return sorted((normalize_json(value) for value in payload), key=repr)
    if payload is None or isinstance(payload, (str, int, float, bool)):
        return payload
    raise TypeError(f"Unsupported payload type: {type(payload)!r}")

def make_json_response(payload, status=200, cache_control=None):
    payload_normalized = normalize_json(payload)
    payload_json = json.dumps(payload_normalized, ensure_ascii=False, separators=(',', ':'))
    resp = make_response(payload_json, status)
    resp.headers['Content-Type'] = 'application/json; charset=utf-8'
    if cache_control:
        resp.headers['Cache-Control'] = cache_control
    return resp

def is_ip_literal(value):
    if not value:
        return False
    try:
        ipaddress.ip_address(str(value))
        return True
    except ValueError:
        return False

def resolve_connect_ip(hostname):
    if not hostname:
        return None
    now = time.time()
    with DNS_CACHE_LOCK:
        cached = DNS_CACHE.get(hostname)
        if cached and cached[1] > now:
            return cached[0]
    resolved = None
    try:
        resolved = socket.gethostbyname(hostname)
    except Exception:
        resolved = None
    ttl = now + DNS_CACHE_TTL_SECONDS
    with DNS_CACHE_LOCK:
        DNS_CACHE[hostname] = (resolved or hostname, ttl)
        if len(DNS_CACHE) > DNS_CACHE_MAX_ENTRIES:
            expired = [key for key, (_, exp) in DNS_CACHE.items() if exp <= now]
            for key in expired:
                DNS_CACHE.pop(key, None)
            if len(DNS_CACHE) > DNS_CACHE_MAX_ENTRIES:
                for key in list(DNS_CACHE.keys())[:len(DNS_CACHE) - DNS_CACHE_MAX_ENTRIES]:
                    DNS_CACHE.pop(key, None)
    return resolved or hostname

def etag_matches(if_none_match, etag_value):
    if not if_none_match:
        return False
    candidates = [tag.strip() for tag in if_none_match.split(',')]
    return etag_value in candidates or f'W/{etag_value}' in candidates

def make_etag_response(payload, cache_control=None):
    payload_normalized = normalize_json(payload)
    payload_json = json.dumps(payload_normalized, sort_keys=True, separators=(',', ':'))
    etag = hashlib.sha256(payload_json.encode('utf-8')).hexdigest()
    etag_value = f"\"{etag}\""
    if etag_matches(request.headers.get('If-None-Match', ''), etag_value):
        resp = make_response('', 304)
        resp.headers['ETag'] = etag_value
        if cache_control:
            resp.headers['Cache-Control'] = cache_control
        return resp
    resp = make_response(payload_json, 200)
    resp.headers['Content-Type'] = 'application/json'
    resp.headers['ETag'] = etag_value
    if cache_control:
        resp.headers['Cache-Control'] = cache_control
    return resp

def server_sort_key(server):
    if not isinstance(server, dict):
        return ('', '', '', '')
    server_key = server.get('server_key')
    if server_key:
        return (str(server_key), '', '', '')
    display_ip = server.get('display_ip')
    ip = server.get('ip')
    port = server.get('port')
    return (str(display_ip or ''), str(ip or ''), str(port or ''), '')

def server_order_key(server):
    if not isinstance(server, dict):
        return None
    server_key = server.get('server_key')
    if server_key:
        return str(server_key)
    display_ip = server.get('display_ip')
    if display_ip:
        return str(display_ip)
    ip = server.get('ip')
    port = server.get('port')
    if ip is not None and port is not None:
        return f"{ip}:{port}"
    return None

def apply_config_server_order(cid, servers):
    snapshot = get_config_snapshot()
    order_index = snapshot.get('server_order_index')
    if not order_index:
        return servers
    order_map = order_index.get(cid)
    if not order_map or not isinstance(servers, list) or not servers:
        return servers
    buckets = {}
    unmatched = []
    for srv in servers:
        key = server_order_key(srv)
        if key and key in order_map:
            buckets.setdefault(key, []).append(srv)
        else:
            unmatched.append(srv)
    ordered = []
    for key, _ in sorted(order_map.items(), key=lambda item: item[1]):
        ordered.extend(buckets.get(key, []))
    if unmatched:
        ordered.extend(unmatched)
    return ordered

def compute_servers_hash(servers):
    payload_json = json.dumps(normalize_json(servers), sort_keys=True, separators=(',', ':'))
    return hashlib.sha1(payload_json.encode('utf-8')).hexdigest()

def apply_server_cache_updates(updates):
    global SERVER_CACHE_VERSION
    changed_cids = []
    with SERVER_CACHE_LOCK:
        for cid, servers, servers_hash in updates:
            if SERVER_CACHE_HASH.get(cid) == servers_hash:
                # hash unchanged -> skip cache writes to avoid churn/invalidation
                continue
            SERVER_CACHE[cid] = servers
            SERVER_CACHE_HASH[cid] = servers_hash
            changed_cids.append(cid)
        if changed_cids:
            SERVER_CACHE_VERSION += 1  # bump once per batch so public caches rebuild once
    if changed_cids:
        with CID_CACHE_LOCK:
            for cid in changed_cids:
                CID_SERVERS_CACHE.pop(cid, None)
    return changed_cids

def build_servers_payload_bytes():
    snapshot = get_config_snapshot()
    with SERVER_CACHE_LOCK:
        current_version = SERVER_CACHE_VERSION
        data = {cid: list(servers) for cid, servers in SERVER_CACHE.items()}
    ordered = OrderedDict()
    for comm in snapshot['community_meta']:
        cid = comm.get('id')
        if cid:
            ordered[cid] = data.pop(cid, [])
    if data:
        for cid in sorted(data.keys()):
            ordered[cid] = data[cid]
    # Self-check notes:
    # - /servers.json top-level order follows community_meta; extras appended in sorted order.
    # - per-community server list order is preserved from SERVER_CACHE (EXG/config/agent).
    # - payload_bytes/ETag are derived from final bytes for stable 304 handling.
    payload_json = json.dumps(normalize_json(ordered), separators=(',', ':'))
    payload_bytes = payload_json.encode('utf-8')
    etag = hashlib.sha256(payload_bytes).hexdigest()
    etag_value = f"\"{etag}\""
    return payload_bytes, etag_value, current_version

def rebuild_public_servers_cache_if_needed(min_interval=1.0):
    global PUBLIC_SERVERS_BYTES, PUBLIC_SERVERS_ETAG, PUBLIC_SERVERS_BUILT_AT, PUBLIC_SERVERS_BUILT_VER
    global PUBLIC_BUILDING, PUBLIC_BUILD_TARGET_VER
    with SERVER_CACHE_LOCK:
        current_version = SERVER_CACHE_VERSION
    now = time.time()
    with PUBLIC_BUILD_LOCK:
        if PUBLIC_SERVERS_BUILT_VER == current_version:
            return
        if now - PUBLIC_SERVERS_BUILT_AT < min_interval:
            return
        if PUBLIC_BUILDING:
            # 其他并发请求等待短暂窗口或直接复用旧缓存，避免重复构建
            deadline = time.time() + 1.0
            while PUBLIC_BUILDING and time.time() < deadline:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                PUBLIC_BUILD_COND.wait(timeout=remaining)
                if PUBLIC_SERVERS_BUILT_VER == current_version:
                    return
                if time.time() - PUBLIC_SERVERS_BUILT_AT < min_interval:
                    return
            return
        PUBLIC_BUILDING = True
        PUBLIC_BUILD_TARGET_VER = current_version
    payload_bytes = None
    etag_value = None
    build_ok = False
    try:
        payload_bytes, etag_value, current_version = build_servers_payload_bytes()
        build_ok = True
    except Exception as e:
        print(f"[PublicServers] cache build failed: {e}")
    finally:
        with PUBLIC_BUILD_LOCK:
            if build_ok:
                now = time.time()
                PUBLIC_SERVERS_BYTES = payload_bytes
                PUBLIC_SERVERS_ETAG = etag_value
                PUBLIC_SERVERS_BUILT_AT = now
                PUBLIC_SERVERS_BUILT_VER = current_version
            PUBLIC_BUILDING = False
            PUBLIC_BUILD_TARGET_VER = -1
            PUBLIC_BUILD_COND.notify_all()

def rebuild_api_servers_cache_if_needed(min_interval=1.0):
    global API_SERVERS_BYTES, API_SERVERS_ETAG, API_SERVERS_BUILT_AT, API_SERVERS_BUILT_VER
    global API_BUILDING, API_BUILD_TARGET_VER
    with SERVER_CACHE_LOCK:
        current_version = SERVER_CACHE_VERSION
    now = time.time()
    with API_BUILD_LOCK:
        if API_SERVERS_BUILT_VER == current_version:
            return
        if now - API_SERVERS_BUILT_AT < min_interval:
            return
        if API_BUILDING:
            deadline = time.time() + 1.0
            while API_BUILDING and time.time() < deadline:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                API_BUILD_COND.wait(timeout=remaining)
                if API_SERVERS_BUILT_VER == current_version:
                    return
                if time.time() - API_SERVERS_BUILT_AT < min_interval:
                    return
            return
        API_BUILDING = True
        API_BUILD_TARGET_VER = current_version
    payload_bytes = None
    etag_value = None
    build_ok = False
    try:
        payload_bytes, etag_value, current_version = build_servers_payload_bytes()
        build_ok = True
    except Exception as e:
        print(f"[ApiServers] cache build failed: {e}")
    finally:
        with API_BUILD_LOCK:
            if build_ok:
                now = time.time()
                API_SERVERS_BYTES = payload_bytes
                API_SERVERS_ETAG = etag_value
                API_SERVERS_BUILT_AT = now
                API_SERVERS_BUILT_VER = current_version
            API_BUILDING = False
            API_BUILD_TARGET_VER = -1
            API_BUILD_COND.notify_all()

def build_language_payload():
    try:
        if os.path.exists(LANGUAGE_FILE):
            with open(LANGUAGE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                zh_cn = data.get('zh-CN')
                if isinstance(zh_cn, dict):
                    if 'zh-TW' not in data:
                        if OPENCC_S2TWP:
                            data['zh-TW'] = {key: OPENCC_S2TWP.convert(str(value)) for key, value in zh_cn.items()}
                        else:
                            data['zh-TW'] = dict(zh_cn)
                    if 'zh-HK' not in data:
                        if OPENCC_S2HK:
                            data['zh-HK'] = {key: OPENCC_S2HK.convert(str(value)) for key, value in zh_cn.items()}
                        else:
                            data['zh-HK'] = dict(zh_cn)
                return data
    except Exception as e:
        print(f"[Language] 加载失败: {e}")
    return {}

def build_server_snapshot():
    snapshot = get_config_snapshot()
    with SERVER_CACHE_LOCK:
        data = {cid: list(servers) for cid, servers in SERVER_CACHE.items()}
    for comm in snapshot['community_meta']:
        cid = comm.get('id')
        if cid:
            data.setdefault(cid, [])
    return data

def check_prime_rate_limit(admin_id):
    now = time.time()
    with PRIME_RATE_LOCK:
        dq = PRIME_RATE_LIMITS.get(admin_id)
        if dq is None:
            dq = deque()
            PRIME_RATE_LIMITS[admin_id] = dq
        while dq and now - dq[0] > 60:
            dq.popleft()
        if len(dq) >= 20:
            return False
        dq.append(now)
        return True

def set_no_store(response):
    response.headers['Cache-Control'] = 'private, no-store, no-cache, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['Vary'] = 'Cookie'
    return response

def build_embed_csp():
    return (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors https://www.cs2ze.org; "
        "object-src 'none'; "
        "base-uri 'self'"
    )

def build_steam_openid_url():
    state = secrets.token_urlsafe(24)
    session['steam_login_state'] = state
    session['steam_login_created_at'] = int(time.time())
    realm = request.url_root.rstrip('/')
    return_to = url_for('steam_callback', _external=True, state=state)
    params = {
        "openid.ns": STEAM_OPENID_NS,
        "openid.mode": "checkid_setup",
        "openid.return_to": return_to,
        "openid.realm": realm,
        "openid.identity": f"{STEAM_OPENID_NS}/identifier_select",
        "openid.claimed_id": f"{STEAM_OPENID_NS}/identifier_select"
    }
    return f"{STEAM_OPENID_ENDPOINT}?{urlencode(params)}"

def verify_steam_openid(args):
    payload = dict(args)
    payload["openid.mode"] = "check_authentication"
    
    print(f"[SteamDebug] 开始验证 OpenID。参数数量: {len(payload)}")
    
    try:
        # 增加 verify=False 以排除服务器本地 SSL 证书问题
        resp = requests.post(STEAM_OPENID_ENDPOINT, data=payload, timeout=15)
        # print(f"[SteamDebug] Steam API 响应码: {resp.status_code}") # 调试完可注释
        
    except Exception as e:
        print(f"[SteamDebug]  连接 Steam API 失败: {e}")
        return None
    
    if resp.status_code != 200:
        print(f"[SteamDebug]  验证请求 HTTP 失败")
        return None
        
    if "is_valid:true" not in resp.text:
        print(f"[SteamDebug]  Steam 返回验证无效 (is_valid:false)")
        return None
        
    claimed_id = args.get("openid.claimed_id", "")
    
    # --- 修复点：修正了正则表达式，去掉了多余的反斜杠 ---
    match = re.search(r"https?://steamcommunity\.com/openid/id/(\d+)", claimed_id)
    
    if not match:
        print(f"[SteamDebug]  无法从 claimed_id 解析 SteamID: {claimed_id}")
        # 尝试备用正则，防止 Steam URL 格式微变
        match_fallback = re.search(r"/id/(\d+)", claimed_id)
        if match_fallback:
             steam_id = match_fallback.group(1)
             print(f"[SteamDebug]  使用备用正则解析成功: {steam_id}")
             return steam_id
        return None
        
    steam_id = match.group(1)
    print(f"[SteamDebug]  验证成功，SteamID: {steam_id}")
    return steam_id

def render_steam_callback(status, reason, steam_id=None):
    payload = {
        "type": "steam-auth",
        "status": status,
        "reason": reason,
        "steamId": steam_id
    }
    payload_json = json.dumps(payload)
    html = f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Steam Login</title>
</head>
<body>
    <p>Steam login {status}. You can close this window.</p>
    <script>
        (function() {{
            const payload = {payload_json};
            try {{
                if (window.opener && !window.opener.closed) {{
                    console.log("Sending payload to opener:", payload);
                    window.opener.postMessage(payload, "*");
                }} else {{
                    console.error("Window opener lost or closed.");
                    alert("登录状态同步失败：无法连接到主窗口。请刷新主页后重试。");
                }}
            }} catch(e) {{
                console.error("PostMessage failed:", e);
            }}
            
            // 关键修复：延迟 100ms 关闭窗口，确保消息已发出
            setTimeout(function() {{
                window.close();
            }}, 100);
        }})();
    </script>
</body>
</html>"""
    resp = make_response(html)
    resp = set_no_store(resp)
    resp.headers['X-CS2ZE-Auth-Bypass'] = 'steam-callback'
    return resp

def fetch_steam_profile(steam_id):
    if not steam_id:
        return None
    url = f"https://steamcommunity.com/profiles/{steam_id}/?xml=1"
    try:
        resp = requests.get(url, timeout=10)
    except Exception as e:
        print(f"[Steam] 获取资料失败: {e}")
        return None
    if resp.status_code != 200:
        print(f"[Steam] 获取资料失败: {resp.status_code}")
        return None
    text = resp.text
    name_match = re.search(r"<steamID><!\[CDATA\[(.*?)\]\]></steamID>", text)
    avatar_match = re.search(r"<avatarMedium><!\[CDATA\[(.*?)\]\]></avatarMedium>", text)
    return {
        "name": name_match.group(1) if name_match else None,
        "avatar": avatar_match.group(1) if avatar_match else None
    }

def get_cached_steam_profile(steam_id):
    cached = session.get('steam_profile')
    updated_at = session.get('steam_profile_updated_at', 0)
    if cached and updated_at:
        try:
            if int(time.time()) - int(updated_at) < STEAM_PROFILE_CACHE_TTL_SECONDS:
                return cached
        except Exception:
            pass
    profile = fetch_steam_profile(steam_id)
    if profile:
        session['steam_profile'] = profile
        session['steam_profile_updated_at'] = int(time.time())
    return profile

def canonicalize_payload(raw_body):
    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError:
        return None, None
    canonical = json.dumps(parsed, separators=(',', ':'), sort_keys=True)
    return parsed, canonical

def verify_agent_signature(token, timestamp, signature, canonical_body):
    if not token or not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    now = int(time.time())
    if abs(now - ts) > AGENT_SIGNATURE_TTL_SECONDS:
        return False
    expected = hmac.new(token.encode('utf-8'), f"{timestamp}.{canonical_body}".encode('utf-8'), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

def rebuild_translated_index():
    global MAP_TRANS_NORMALIZED
    normalized = {}
    for key, entry in MAP_TRANS_CACHE.items():
        normalized_key = normalize_map_name(key)
        if normalized_key and normalized_key not in normalized:
            normalized[normalized_key] = entry
    MAP_TRANS_NORMALIZED = normalized

def get_exg_maplist_entry(map_name):
    if not map_name:
        return None
    map_clean = normalize_map_name(map_name)
    if not map_clean:
        return None
    with MAPLIST_NORMALIZED_LOCK:
        return MAPLIST_NORMALIZED_CACHE.get(map_clean)

def _maplist_entry_to_translation(entry):
    if not entry:
        return None
    name_zh = str(entry.get("name_zh") or "").strip()
    if not name_zh:
        return None
    return {"zh_cn": name_zh, "zh_tw": convert_to_traditional(name_zh)}

def get_map_translation_entry(map_name):
    if not map_name:
        return None
    if map_name in MAP_TRANS_CACHE:
        return MAP_TRANS_CACHE[map_name]
    maplist_entry = _maplist_entry_to_translation(get_exg_maplist_entry(map_name))
    if maplist_entry:
        return maplist_entry
    map_clean = normalize_map_name(map_name)
    if map_clean and map_clean in MAP_TRANS_CACHE:
        return MAP_TRANS_CACHE[map_clean]
    if map_clean and map_clean in MAP_TRANS_NORMALIZED:
        return MAP_TRANS_NORMALIZED[map_clean]
    return None

def ensure_map_translation_entry(map_raw):
    map_clean = normalize_map_name(map_raw)
    if not map_clean:
        return None
    with MAP_TRANS_LOCK:
        existing = MAP_TRANS_CACHE.get(map_clean) or MAP_TRANS_NORMALIZED.get(map_clean)
        if existing:
            return existing
        entry = {"zh_cn": "", "zh_tw": ""}
        MAP_TRANS_CACHE[map_clean] = entry
        global MAP_TRANS_DIRTY
        MAP_TRANS_DIRTY = True
        return entry

def update_map_translation_entry(map_name, map_display):
    global MAP_TRANS_DIRTY
    map_clean = normalize_map_name(map_name)
    if not map_clean:
        return False
    name = str(map_display or "").strip()
    if not name:
        return False
    with MAP_TRANS_LOCK:
        entry = MAP_TRANS_CACHE.get(map_clean, {"zh_cn": "", "zh_tw": ""})
        if entry.get("zh_cn"):
            return False
        entry["zh_cn"] = name
        entry["zh_tw"] = convert_to_traditional(name) if name else ""
        MAP_TRANS_CACHE[map_clean] = entry
        MAP_TRANS_DIRTY = True
    rebuild_translated_index()
    return True

def maybe_flush_map_translations(force=False):
    global MAP_TRANS_DIRTY, MAP_TRANS_LAST_WRITE
    if not MAP_TRANS_DIRTY:
        return False
    now = time.time()
    if not force and (now - MAP_TRANS_LAST_WRITE) < MAP_TRANS_WRITE_INTERVAL_SECONDS:
        return False
    dir_name = os.path.dirname(TRANS_FILE) or "."
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp.", suffix=".json", dir=dir_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(MAP_TRANS_CACHE, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, TRANS_FILE)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    MAP_TRANS_LAST_WRITE = now
    MAP_TRANS_DIRTY = False
    return True

atexit.register(lambda: maybe_flush_map_translations(force=True))

def normalize_map_name(map_name):
    if not map_name or map_name == "-":
        return None
    map_clean = str(map_name).strip().lower()
    map_clean = map_clean.replace("\\", "/").split("?", 1)[0]
    if map_clean.endswith('.bsp'):
        map_clean = map_clean[:-4]
    if map_clean.startswith("workshop/"):
        parts = map_clean.split("/")
        map_clean = parts[-1] if parts else map_clean
    else:
        map_clean = map_clean.split("/")[-1]
    return map_clean or None

def get_map_image_url(map_name):
    map_clean = normalize_map_name(map_name)
    if not map_clean:
        return None
    filename = MAP_IMAGE_INDEX.get(map_clean)
    if filename:
        return f"/static/maps/{filename}"
    return None

def build_config_snapshot(data):
    communities = []
    if isinstance(data, dict):
        raw_communities = data.get('communities', [])
        if isinstance(raw_communities, list):
            for comm in raw_communities:
                if isinstance(comm, dict):
                    communities.append(MappingProxyType(dict(comm)))
    server_order_index = {}
    for comm in communities:
        server_list = comm.get('servers')
        if not isinstance(server_list, list) or not server_list:
            continue
        cid = str(comm.get('id', '')).strip()
        if not cid:
            continue
        order_map = {}
        for idx, entry in enumerate(server_list):
            if not isinstance(entry, dict):
                continue
            host = entry.get('host')
            port = entry.get('port')
            if host is None or port is None:
                continue
            key = f"{host}:{port}"
            if key not in order_map:
                order_map[key] = idx
        if order_map:
            server_order_index[cid] = MappingProxyType(order_map)
    admin_ids = set()
    if isinstance(data, dict):
        admin_ids = {str(sid).strip() for sid in data.get('admin_steam_ids', []) if str(sid).strip()}
    fys_ids = set()
    for comm in communities:
        cid = str(comm.get('id', '')).strip()
        name = str(comm.get('name', '')).strip()
        short_name = str(comm.get('short_name', '')).strip()
        if cid.casefold() == "fys" or name.casefold() == "fys" or short_name.casefold() == "fys":
            if cid:
                fys_ids.add(cid)
    retention_days = STATS_EXPORT_RETENTION_DAYS
    if isinstance(data, dict):
        candidate = data.get('stats_export_retention_days')
        if isinstance(candidate, int) and candidate > 0:
            retention_days = candidate
    community_meta = [MappingProxyType(entry) for entry in build_community_meta(communities)]
    return {
        "communities": tuple(communities),
        "community_meta": tuple(community_meta),
        "server_order_index": MappingProxyType(server_order_index),
        "admin_steam_ids": frozenset(admin_ids),
        "fys_ids": frozenset(fys_ids),
        "stats_export_retention_days": retention_days
    }

def refresh_config_snapshot(force=False):
    """加载 config.json 并刷新内存快照（仅初始化和后台线程调用）"""
    global CONFIG_SNAPSHOT, CONFIG_SNAPSHOT_MTIME, CONFIG_SNAPSHOT_VERSION, CONFIG_SNAPSHOT_ERROR_MTIME
    global COMMUNITY_META, STATS_EXPORT_RETENTION_DAYS, FYS_COMMUNITY_IDS, ADMIN_STEAM_IDS
    try:
        if os.path.exists(CONFIG_FILE):
            config_mtime = os.path.getmtime(CONFIG_FILE)
        else:
            config_mtime = 0.0
    except Exception as e:
        print(f"[Config] 配置文件检测失败: {e}")
        return False

    if not force and config_mtime == CONFIG_SNAPSHOT_MTIME:
        return False

    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            snapshot = build_config_snapshot(data)
            print(f"[Config] 已加载 {len(snapshot['communities'])} 个社区配置")
        else:
            snapshot = build_config_snapshot({})
            print("[Config] 配置文件不存在")
        with CONFIG_SNAPSHOT_LOCK:
            CONFIG_SNAPSHOT = snapshot
            CONFIG_SNAPSHOT_MTIME = config_mtime
            CONFIG_SNAPSHOT_VERSION += 1
            COMMUNITY_META = list(snapshot['communities'])
            ADMIN_STEAM_IDS = set(snapshot['admin_steam_ids'])
            FYS_COMMUNITY_IDS = set(snapshot['fys_ids'])
            STATS_EXPORT_RETENTION_DAYS = snapshot['stats_export_retention_days']
        CONFIG_SNAPSHOT_ERROR_MTIME = None
        return True
    except Exception as e:
        if CONFIG_SNAPSHOT_ERROR_MTIME != config_mtime:
            print(f"[Config] 加载失败: {e}")
            CONFIG_SNAPSHOT_ERROR_MTIME = config_mtime
        with CONFIG_SNAPSHOT_LOCK:
            CONFIG_SNAPSHOT_MTIME = config_mtime
        return False

def start_config_refresher():
    global CONFIG_REFRESHER_STARTED, CONFIG_REFRESHER_THREAD
    if CONFIG_REFRESHER_STARTED:
        return
    CONFIG_REFRESHER_STARTED = True

    def refresher():
        while True:
            time.sleep(CONFIG_REFRESH_INTERVAL_SECONDS)
            try:
                refresh_config_snapshot()
            except Exception as e:
                print(f"[Config] 刷新线程异常: {e}")

    CONFIG_REFRESHER_THREAD = threading.Thread(target=refresher, name="config-refresher", daemon=True)
    CONFIG_REFRESHER_THREAD.start()

def build_community_meta(communities=None):
    def is_svg_asset(value):
        if not value:
            return False
        value = str(value)
        return value.lower().split('?', 1)[0].endswith('.svg')

    meta = []
    if communities is None:
        snapshot = get_config_snapshot()
        communities = snapshot['communities']
    for c in communities:
        meta.append({
            "id": c['id'],
            "name": c['name'],
            "logo": c.get('logo', ''),
            "logo_light": c.get('logo_light', ''),
            "logo_dark": c.get('logo_dark', ''),
            "logo_is_svg": is_svg_asset(c.get('logo')),
            "logo_light_is_svg": is_svg_asset(c.get('logo_light')),
            "logo_dark_is_svg": is_svg_asset(c.get('logo_dark')),
            "game": c.get('game', 'cs2'),
            "features": c.get('features', []),
            "map_url": c.get('map_cd_url', '') if "map_cd" in c.get('features', []) else "",
            "short_name": c.get('short_name', c['name'])
        })
    return meta

# --- 2. 核心：EXG API 直接抓取（实时数据）---
def fetch_exg_data_from_api():
    """
    直接从 EXG API 获取实时服务器数据
    返回格式与 A2S 查询结果一致
    """
    global EXG_CACHE, EXG_CACHE_UPDATED_AT
    now = int(time.time())
    if EXG_CACHE and (now - EXG_CACHE_UPDATED_AT) < EXG_FETCH_INTERVAL_SECONDS:
        return EXG_CACHE
    servers = []
    success = False
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        
        resp = EXG_SESSION.get(EXG_API_URL, timeout=10, verify=EXG_VERIFY_SSL, headers=headers)
        
        if resp.status_code == 200:
            data = resp.json()
            success = True
            
            # 确保是数组
            if not isinstance(data, list):
                data = [data]
            
            for item in data:
                try:
                    # 解析嵌套结构
                    server_info = item.get('Server', {})
                    status_info = item.get('Status', {})
                    
                    # 提取基础信息
                    ip = server_info.get('Ip')
                    port = server_info.get('Port')
                    
                    if not ip or not port:
                        continue
                    
                    # 服务器名称（优先中文）
                    name = (status_info.get('FullTitle') or 
                           server_info.get('DisplayNameCN') or 
                           server_info.get('DisplayName') or 
                           f"EXG {port}")
                    
                    # 地图信息
                    map_name = status_info.get('Map', '-')
                    map_display = status_info.get('MapDisplayName', '')
                    
                    # 玩家信息
                    current_players = status_info.get('CurrentPlayers', 0)
                    max_players = status_info.get('MaxPlayers', 64)
                    current_bots = status_info.get('CurrentBots', 0)
                    
                    # 构建服务器对象
                    server_obj = {
                        "name": name.strip(),
                        "ip": str(ip).strip(),
                        "connect_ip": str(ip).strip(),
                        "port": int(port),
                        "display_ip": f"{ip}:{port}",
                        "map": map_name,
                        "players": int(current_players),
                        "max_players": int(max_players),
                        "online": True,  # API 返回的都是在线服务器
                        "ping": -1,  # API 不提供 ping
                        "game_type": "cs2"
                    }
                    
                    # 地图图片匹配
                    image_url = get_map_image_url(map_name)
                    if image_url:
                        server_obj['image_url'] = image_url
                    else:
                        server_obj['image_url'] = None
                    
                    entry = ensure_map_translation_entry(map_name)
                    if map_display:
                        update_map_translation_entry(map_name, map_display)
                    maplist_entry = get_exg_maplist_entry(map_name)
                    if entry:
                        server_obj['map_cn'] = entry.get('zh_cn', '')
                        server_obj['map_tw'] = entry.get('zh_tw', '')
                    elif maplist_entry:
                        map_name_zh = str(maplist_entry.get("name_zh") or "").strip()
                        if map_name_zh:
                            server_obj['map_cn'] = map_name_zh
                            server_obj['map_tw'] = convert_to_traditional(map_name_zh)
                    if maplist_entry:
                        server_obj['map_exg'] = {
                            "name_zh": maplist_entry.get("name_zh", ""),
                            "difficulty": maplist_entry.get("difficulty", ""),
                            "tags": maplist_entry.get("tags", []),
                            "cooldown": maplist_entry.get("cooldown", {}),
                            "achievement": maplist_entry.get("achievement", ""),
                            "workshop": maplist_entry.get("workshop", {}),
                        }
                    
                    servers.append(server_obj)
                    
                except Exception as e:
                    continue
            
            EXG_CACHE = servers
            EXG_CACHE_UPDATED_AT = now
            maybe_flush_map_translations()
            print(f"[EXG API] 成功获取 {len(servers)} 个服务器")
                    
        else:
            print(f"[EXG API] HTTP 错误: {resp.status_code}")
            
    except Exception as e:
        print(f"[EXG API] 请求失败: {e}")
    
    if servers:
        return servers
    return EXG_CACHE

# --- 3. 核心：A2S 抓取逻辑（其他社区）---
def fetch_a2s_data(server_cfg, game_type='cs2'):
    """使用 A2S 查询服务器"""
    host = server_cfg['host']
    port = server_cfg['port']
    name = server_cfg.get('name', f"{host}:{port}")
    if is_ip_literal(host):
        resolved_ip = host
    else:
        resolved_ip = resolve_connect_ip(host)
    
    res = {
        "name": name,
        "ip": host,
        "connect_ip": resolved_ip or host,
        "port": port, 
        "display_ip": f"{host}:{port}",
        "map": "-", 
        "players": 0, 
        "max_players": 0,
        "online": False, 
        "ping": -1, 
        "image_url": None, 
        "game_type": game_type
    }
    
    try:
        info = a2s.info((host, port), timeout=2.0)
        
        res.update({
            "online": True,
            "name": info.server_name,
            "map": info.map_name,
            "players": info.player_count,
            "max_players": info.max_players,
            "ping": int(info.ping * 1000) if info.ping > 0 else 0
        })
        
        # 图片匹配
        image_url = get_map_image_url(info.map_name)
        if image_url:
            res['image_url'] = image_url
        
        # 翻译匹配
        entry = ensure_map_translation_entry(info.map_name)
        if entry:
            res['map_cn'] = entry.get('zh_cn', '')
            res['map_tw'] = entry.get('zh_tw', '')
        maplist_entry = get_exg_maplist_entry(info.map_name)
        if maplist_entry and not entry:
            map_name_zh = str(maplist_entry.get("name_zh") or "").strip()
            if map_name_zh:
                res['map_cn'] = map_name_zh
                res['map_tw'] = convert_to_traditional(map_name_zh)
        if maplist_entry:
            res['map_exg'] = {
                "name_zh": maplist_entry.get("name_zh", ""),
                "difficulty": maplist_entry.get("difficulty", ""),
                "tags": maplist_entry.get("tags", []),
                "cooldown": maplist_entry.get("cooldown", {}),
                "achievement": maplist_entry.get("achievement", ""),
                "workshop": maplist_entry.get("workshop", {}),
            }
        maybe_flush_map_translations()
            
    except Exception as e:
        pass
    
    return res

def is_exg_stats_eligible(server):
    name = (server.get("name") or "").strip()
    if not name:
        return True
    normalized = name.casefold()
    return not any(keyword.casefold() in normalized for keyword in EXG_STATS_EXCLUDE_KEYWORDS)

def is_fys_community_id(cid):
    snapshot = get_config_snapshot()
    return cid.casefold() == "fys" or cid in snapshot['fys_ids']

def is_fys_stats_eligible(server):
    name = str(server.get("name", ""))
    if FYS_STATS_INCLUDE_NAME not in name:
        return False
    return not any(keyword in name for keyword in FYS_STATS_EXCLUDE_KEYWORDS)

def count_players_for_stats(cid, servers):
    if cid == "exg":
        return sum(s['players'] for s in servers if s.get('online') and is_exg_stats_eligible(s))
    if is_fys_community_id(cid):
        return sum(s['players'] for s in servers if s.get('online') and is_fys_stats_eligible(s))
    return sum(s['players'] for s in servers if s.get('online'))

def servers_equivalent_for_public(previous, current):
    if len(previous) != len(current):
        return False
    return sorted(previous, key=server_sort_key) == sorted(current, key=server_sort_key)

def fetch_comm_servers(comm):
    """抓取单社区服务器数据（不写缓存）"""
    cid = comm['id']
    now = int(time.time())

    def agent_fallback(reason):
        print(f"[Update] {comm['name']}: {reason}")
        with SERVER_CACHE_LOCK:
            return list(SERVER_CACHE.get(cid, []))

    if comm.get('location') != 'cn':
        server_list = comm.get('servers', [])
        if server_list:
            game = comm.get('game', 'cs2')
            max_workers = min(20, max(1, len(server_list)))
            with ThreadPoolExecutor(max_workers=max_workers) as exe:
                result = list(exe.map(lambda s: fetch_a2s_data(s, game), server_list))
            online_count = sum(1 for s in result if s.get('online'))
            total_players = sum(s['players'] for s in result if s.get('online'))
            print(f"[Update] {comm['name']}: {online_count}/{len(result)} 在线, {total_players} 玩家")
            return result
        return []
    with AGENT_CACHE_LOCK:
        agent_servers = AGENT_CACHE.get(cid)
        agent_updated_at = AGENT_CACHE_UPDATED_AT.get(cid, 0)
    if agent_servers is None:
        return agent_fallback("等待 agent 数据 (cn)")
    if now - agent_updated_at > AGENT_STALE_SECONDS:
        return agent_fallback("agent 数据过期 (cn)")
    online_count = sum(1 for s in agent_servers if s.get('online'))
    total_players = sum(s['players'] for s in agent_servers if s.get('online'))
    print(f"[Update] {comm['name']}: {online_count}/{len(agent_servers)} 在线, {total_players} 玩家 (agent)")
    return list(agent_servers)

def update_single_comm(comm):
    """更新单个社区数据并写入缓存"""
    cid = comm['id']
    result = apply_config_server_order(cid, fetch_comm_servers(comm))
    servers_hash = compute_servers_hash(result)
    changed_cids = apply_server_cache_updates([(cid, result, servers_hash)])
    return bool(changed_cids)


def update_all_data():
    """立即刷新所有社区数据（仅用于启动或手动调用）"""
    refresh_local_caches()
    snapshot = get_config_snapshot()
    updates = []
    for comm in snapshot['communities']:
        cid = comm['id']
        result = apply_config_server_order(cid, fetch_comm_servers(comm))
        updates.append((cid, result, compute_servers_hash(result)))
    apply_server_cache_updates(updates)
    save_stats()
    maybe_flush_map_translations()

# --- 5. 数据库逻辑 ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS player_stats (timestamp INTEGER, community TEXT, count INTEGER)''')
    conn.commit()
    conn.close()

def _get_cf_access_email():
    for header_name, value in request.headers.items():
        if header_name.lower() == "cf-access-authenticated-user-email":
            return value
    return None

def save_stats():
    timestamp = int(time.time())
    with SERVER_CACHE_LOCK:
        snapshot = dict(SERVER_CACHE)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM player_stats WHERE timestamp < ?", (timestamp - 48 * 3600,))
    
    for cid, servers in snapshot.items():
        count = count_players_for_stats(cid, servers)
        c.execute("INSERT INTO player_stats VALUES (?, ?, ?)", (timestamp, cid, count))
        
    conn.commit()
    conn.close()

def export_stats_to_excel():
    try:
        from openpyxl import Workbook
    except Exception as e:
        print(f"[Stats] Excel export skipped: openpyxl not available ({e})")
        return

    stat_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Statistic')
    os.makedirs(stat_dir, exist_ok=True)
    base_name = f"ZEData_{beijing_date().strftime('%Y_%m_%d')}"
    filename = f"{base_name}.xlsx"
    filepath = os.path.join(stat_dir, filename)
    if os.path.exists(filepath):
        suffix = 1
        while True:
            candidate = os.path.join(stat_dir, f"{base_name}_{suffix}.xlsx")
            if not os.path.exists(candidate):
                filepath = candidate
                break
            suffix += 1

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT timestamp, community, count FROM player_stats ORDER BY timestamp ASC")
    rows = c.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "ZE Stats"
    ws.append(["timestamp_utc", "timestamp_beijing", "community", "count"])
    for ts, cid, count in rows:
        ts_utc = datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        ts_bj = (datetime.utcfromtimestamp(ts) + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
        ws.append([ts_utc, ts_bj, cid, count])
    try:
        wb.save(filepath)
        print(f"[Stats] Exported stats to {filepath}")
    except Exception as e:
        print(f"[Stats] Export failed: {e}")

def cleanup_stat_exports():
    stat_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Statistic')
    if not os.path.isdir(stat_dir):
        return
    snapshot = get_config_snapshot()
    cutoff = time.time() - snapshot['stats_export_retention_days'] * 24 * 3600
    for name in os.listdir(stat_dir):
        if not name.startswith('ZEData_') or not name.endswith('.xlsx'):
            continue
        path = os.path.join(stat_dir, name)
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
        except Exception as e:
            print(f"[Stats] Cleanup failed for {path}: {e}")

# --- 6. 任务调度 ---
SCHEDULE_INTERVAL_SECONDS = 10
SCHEDULE_CONFIG_SYNC_SECONDS = 300
SCHEDULE_STATS_SAVE_SECONDS = 60
AGENT_STALE_SECONDS = 60

scheduler = BackgroundScheduler()
scheduler.add_job(export_stats_to_excel, 'interval', hours=48, id='stats_export')
scheduler.add_job(cleanup_stat_exports, 'interval', days=1, id='stats_cleanup')

def schedule_community_jobs():
    """为每个社区建立错位轮询任务"""
    refresh_local_caches()
    snapshot = get_config_snapshot()
    if not snapshot['communities']:
        return
    job_ids = {f"comm_update_{c['id']}" for c in snapshot['communities']}
    for job in scheduler.get_jobs():
        if job.id.startswith("comm_update_") and job.id not in job_ids:
            scheduler.remove_job(job.id)
    spread = SCHEDULE_INTERVAL_SECONDS / max(1, len(snapshot['communities']))
    now = datetime.now()
    for index, comm in enumerate(snapshot['communities']):
        job_id = f"comm_update_{comm['id']}"
        if scheduler.get_job(job_id):
            continue
        offset = index * spread
        scheduler.add_job(
            update_single_comm,
            'interval',
            seconds=SCHEDULE_INTERVAL_SECONDS,
            id=job_id,
            args=[comm],
            next_run_time=now + timedelta(seconds=offset),
            max_instances=1,
            coalesce=True,
            misfire_grace_time=5
        )

def save_stats_snapshot():
    save_stats()
    maybe_flush_map_translations()

scheduler.add_job(schedule_community_jobs, 'interval', seconds=SCHEDULE_CONFIG_SYNC_SECONDS, id='config_sync')
scheduler.add_job(save_stats_snapshot, 'interval', seconds=SCHEDULE_STATS_SAVE_SECONDS, id='stats_snapshot')

def start_scheduler():
    if not scheduler.running:
        schedule_community_jobs()
        scheduler.start()

def initialize_app():
    global APP_INITIALIZED
    if APP_INITIALIZED:
        return
    with APP_INIT_LOCK:
        if APP_INITIALIZED:
            return
        print("\n" + "=" * 70)
        print(" " * 20 + "CS2ZE Browser 服务器")
        print("=" * 70 + "\n")

        init_db()
        refresh_config_snapshot(force=True)
        load_prime_users()
        refresh_local_caches()

        print("\n[Startup] 执行初始数据更新...")
        print("-" * 70)
        update_all_data()
        maybe_flush_map_translations(force=True)
        print("-" * 70)
        print("\n✓ 初始化完成，服务器启动中...\n")

        start_config_refresher()
        start_scheduler()
        APP_INITIALIZED = True

# --- 7. Flask 路由 ---
@app.before_request
def block_admin_routes():
    if request.path.startswith("/admin"):
        abort(404)

@app.after_request
def flush_map_translations_after_request(response):
    maybe_flush_map_translations()
    return response

@app.route('/')
@app.route('/servers')
@app.route('/map-sub')
@app.route('/stats')
@app.route('/feedback')
def index():
    if request.path in {'/map-sub', '/stats', '/feedback'} and not is_logged_in():
        return redirect(url_for('index'))
    # [替换原来的逻辑]
    
    # 1. 处理语言参数
    url_lang = request.args.get('lang')
    render_lang = url_lang if url_lang else 'zh-CN' # 默认为中文，前端会再次进行自动适配
    
    # 简易归一化
    if render_lang.startswith('en'): render_lang = 'en'
    elif 'TW' in render_lang or 'HK' in render_lang: render_lang = 'zh-TW'
    else: render_lang = 'zh-CN'
    
    seo_info = SEO_DATA.get(render_lang, SEO_DATA['zh-CN'])
    
    # 2. 正常的加载逻辑
    view_map = {
        '/': 'servers',
        '/servers': 'servers',
        '/map-sub': 'map_sub',
        '/stats': 'stats',
        '/feedback': 'feedback'
    }
    initial_view = view_map.get(request.path, 'servers')
    snapshot = get_config_snapshot()
    initial_config = [dict(comm) for comm in snapshot['community_meta']]
    for comm in initial_config:
        comm['servers'] = []
    if os.environ.get('PERF_DEBUG') == '1':
        try:
            debug_len = len(json.dumps(initial_config, separators=(',', ':')))
        except Exception:
            debug_len = -1
        print(f"[PerfDebug] index initial_config communities={len(initial_config)} json_len={debug_len}")

    return render_template('index.html', 
                           initial_view=initial_view, 
                           initial_config=initial_config, 
                           server_cache={},
                           seo_info=seo_info,      # 新增SEO
                           current_lang=render_lang, # 新增語言渲染
                           embed_mode=False
                           )

@app.route('/embed/servers')
def embed_servers():
    url_lang = request.args.get('lang')
    render_lang = url_lang if url_lang else 'zh-CN'

    if render_lang.startswith('en'):
        render_lang = 'en'
    elif 'TW' in render_lang or 'HK' in render_lang:
        render_lang = 'zh-TW'
    else:
        render_lang = 'zh-CN'

    seo_info = SEO_DATA.get(render_lang, SEO_DATA['zh-CN'])
    snapshot = get_config_snapshot()
    initial_config = [dict(comm) for comm in snapshot['community_meta']]
    for comm in initial_config:
        comm['servers'] = []

    resp = make_response(render_template(
        'index.html',
        initial_view='servers',
        initial_config=initial_config,
        server_cache={},
        seo_info=seo_info,
        current_lang=render_lang,
        embed_mode=True
    ))
    resp.headers['Content-Security-Policy'] = build_embed_csp()
    resp.headers['X-Frame-Options'] = 'ALLOW-FROM https://www.cs2ze.org'
    return resp

@app.get("/fragments/<path:name>")
def fragment(name: str):
    # 安全：只允许 fragments 目录下的 html
    if not name.endswith(".html"):
        abort(404)
    if ".." in name or name.startswith(("/", "\\")):
        abort(404)

    frag_path = Path(current_app.root_path) / "templates" / "fragments" / name
    if not frag_path.is_file():
        abort(404)

    html = frag_path.read_text(encoding="utf-8")

    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp

@app.route('/api/steam/login')
def steam_login():
    login_url = build_steam_openid_url()
    resp = set_no_store(redirect(login_url))
    resp.headers['X-CS2ZE-Auth-Bypass'] = 'steam-login'
    return resp

@app.route('/api/steam/callback')
def steam_callback():
    print("-" * 30)
    print("[SteamDebug] 进入 Callback 回调")
    
    state = request.args.get('state', '')
    expected_state = session.get('steam_login_state')
    created_at = session.get('steam_login_created_at', 0)
    
    # 打印 Session 调试信息
    print(f"[SteamDebug] URL State: {state}")
    print(f"[SteamDebug] Session State: {expected_state}")
    print(f"[SteamDebug] Session Created At: {created_at}")
    
    # 检查 Session 是否丢失
    if expected_state is None:
        print("[SteamDebug]  错误：Session 中找不到 state。可能原因：")
        print("1. Cookie 丢失 (SameSite 设置问题)")
        print("2. 域名不一致 (如 www.cs2ze.org 跳转回 cs2ze.org)")
        print("3. 服务器重启导致 Secret Key 变化")
        return render_steam_callback("error", "session_lost (cookie missing)")

    if not state or state != expected_state:
        print("[SteamDebug]  错误：State 不匹配")
        return render_steam_callback("error", "invalid_state")
        
    if created_at and int(time.time()) - int(created_at) > STEAM_AUTH_STATE_TTL_SECONDS:
        print("[SteamDebug]  错误：State 已过期")
        return render_steam_callback("error", "state_expired")
        
    # 执行验证
    steam_id = verify_steam_openid(request.args)
    
    if not steam_id:
        print("[SteamDebug]  错误：verify_steam_openid 返回空")
        return render_steam_callback("error", "invalid_auth")
        
    session['steam_id'] = steam_id
    session['steam_logged_in'] = True
    session.permanent = True
    ensure_csrf_token()
    
    # 清理 session
    session.pop('steam_login_state', None)
    session.pop('steam_login_created_at', None)
    
    print(f"[SteamDebug]  登录流程完成，已写入 Session: {steam_id}")
    print("-" * 30)
    return render_steam_callback("ok", "authenticated", steam_id=steam_id)

@app.route('/api/steam/status')
def steam_status():
    snapshot = get_config_snapshot()
    steam_id = session.get('steam_id')
    logged_in = is_logged_in()
    profile = get_cached_steam_profile(steam_id) if logged_in else None
    role = "admin" if logged_in and steam_id in snapshot['admin_steam_ids'] else "member"
    prime = bool(logged_in and steam_id in PRIME_USERS_SET)
    return set_no_store(make_json_response({
        "logged_in": logged_in,
        "steam_id": steam_id if logged_in else None,
        "role": role if logged_in else "guest",
        "prime": prime if logged_in else False,
        "profile": profile
    }))

@app.route('/api/me')
def api_me():
    steam_id = session.get('steam_id')
    logged_in = is_logged_in()
    return set_no_store(make_json_response({
        "logged_in": logged_in,
        "steam_id": steam_id if logged_in else None
    }))

@app.route('/auth/me')
def auth_me():
    snapshot = get_config_snapshot()
    steam_id = session.get('steam_id')
    logged_in = is_logged_in()
    profile = get_cached_steam_profile(steam_id) if logged_in else None
    role = "admin" if logged_in and steam_id in snapshot['admin_steam_ids'] else "member"
    prime = bool(logged_in and steam_id in PRIME_USERS_SET)
    return set_no_store(make_json_response({
        "logged_in": logged_in,
        "steam_id": steam_id if logged_in else None,
        "role": role if logged_in else "guest",
        "prime": prime if logged_in else False,
        "profile": profile
    }))

@app.route('/auth/debug/cookie')
def auth_debug_cookie():
    denied = require_admin()
    if denied:
        return denied
    probe_value = secrets.token_urlsafe(16)
    resp = make_json_response({
        "ok": True,
        "cookie_name": "cs2ze_cookie_probe",
        "cookie_value": probe_value,
        "note": "Inspect Set-Cookie presence through CDN layers."
    })
    resp.set_cookie(
        "cs2ze_cookie_probe",
        probe_value,
        max_age=300,
        httponly=True,
        secure=True,
        samesite="Lax",
        path="/"
    )
    return set_no_store(resp)

@app.route('/api/steam/logout', methods=['POST'])
def steam_logout():
    origin_denied = require_valid_origin()
    if origin_denied:
        return origin_denied
    session.clear()
    resp = set_no_store(make_json_response({"logged_in": False}))
    cookie_domain = app.config.get('SESSION_COOKIE_DOMAIN')
    if cookie_domain:
        resp.delete_cookie(app.session_cookie_name, path='/', domain=cookie_domain)
    else:
        resp.delete_cookie(app.session_cookie_name, path='/')
    return resp

@app.route('/api/config')
def get_config_meta():
    """返回社区的元数据"""
    snapshot = get_config_snapshot()
    return make_json_response(list(snapshot['community_meta']))

@app.route('/config.json')
def get_public_config():
    """公开的社区元数据（只读）"""
    snapshot = get_config_snapshot()
    return make_etag_response(list(snapshot['community_meta']), 'public, max-age=1')

@app.route('/api/servers')
def get_all_servers():
    """返回所有社区的实时服务器列表"""
    rebuild_api_servers_cache_if_needed(min_interval=1.0)
    with API_BUILD_LOCK:
        payload_bytes = API_SERVERS_BYTES
        etag_value = API_SERVERS_ETAG
    if etag_matches(request.headers.get('If-None-Match', ''), etag_value):
        resp = make_response('', 304)
        resp.headers['ETag'] = etag_value
        resp.headers['Cache-Control'] = 'private, max-age=2'
        return resp
    resp = make_response(payload_bytes, 200)
    resp.headers['Content-Type'] = 'application/json; charset=utf-8'
    resp.headers['ETag'] = etag_value
    resp.headers['Cache-Control'] = 'private, max-age=2'
    return resp

@app.route('/servers.json')
def get_public_servers():
    """公开的服务器快照（只读）"""
    rebuild_public_servers_cache_if_needed(min_interval=1.0)
    with PUBLIC_BUILD_LOCK:
        payload_bytes = PUBLIC_SERVERS_BYTES
        etag_value = PUBLIC_SERVERS_ETAG
    if etag_matches(request.headers.get('If-None-Match', ''), etag_value):
        resp = make_response('', 304)
        resp.headers['ETag'] = etag_value
        resp.headers['Cache-Control'] = 'public, max-age=15'
        return resp
    resp = make_response(payload_bytes, 200)
    resp.headers['Content-Type'] = 'application/json; charset=utf-8'
    resp.headers['ETag'] = etag_value
    resp.headers['Cache-Control'] = 'public, max-age=15'
    return resp

@app.route('/api/servers/<cid>')
def get_servers(cid):
    """返回指定社区的实时服务器列表"""
    with SERVER_CACHE_LOCK:
        current_version = SERVER_CACHE_VERSION
    with CID_CACHE_LOCK:
        cached = CID_SERVERS_CACHE.get(cid)
    # 版本不一致时重建 payload，避免并发更新导致的脏读
    if cached and cached[0] == current_version:
        payload_bytes, etag_value = cached[1], cached[2]
    else:
        with SERVER_CACHE_LOCK:
            servers = list(SERVER_CACHE.get(cid, []))
        payload_json = json.dumps(normalize_json(servers), sort_keys=True, separators=(',', ':'))
        payload_bytes = payload_json.encode('utf-8')
        etag_value = f"\"{hashlib.sha256(payload_bytes).hexdigest()}\""
        with CID_CACHE_LOCK:
            CID_SERVERS_CACHE[cid] = (current_version, payload_bytes, etag_value)
    if etag_matches(request.headers.get('If-None-Match', ''), etag_value):
        resp = make_response('', 304)
        resp.headers['ETag'] = etag_value
        resp.headers['Cache-Control'] = 'public, max-age=2'
        return resp
    resp = make_response(payload_bytes, 200)
    resp.headers['Content-Type'] = 'application/json; charset=utf-8'
    resp.headers['ETag'] = etag_value
    resp.headers['Cache-Control'] = 'public, max-age=2'
    return resp

@app.route('/api/agent/update', methods=['POST'])
def update_agent_data():
    initialize_app()
    token = os.environ.get('AGENT_SHARED_TOKEN')
    if not token:
        return make_json_response({"error": "agent token not configured"}, status=403)
    client_ip = get_client_ip(request)
    if not client_ip_allowed(client_ip):
        return make_json_response({"error": "ip not allowed"}, status=403)
    auth = request.headers.get('Authorization', '')
    if auth != f"Bearer {token}":
        return make_json_response({"error": "unauthorized"}, status=401)
    raw_body = request.get_data(cache=True, as_text=True) or ''
    signature = request.headers.get('X-Agent-Signature')
    timestamp = request.headers.get('X-Agent-Timestamp')
    payload, canonical_body = canonicalize_payload(raw_body)
    if payload is None or canonical_body is None:
        return make_json_response({"error": "invalid payload"}, status=400)
    if not verify_agent_signature(token, timestamp, signature, canonical_body):
        return make_json_response({"error": "invalid signature"}, status=401)

    communities = payload.get('communities', {})
    if not isinstance(communities, dict):
        return make_json_response({"error": "invalid payload"}, status=400)
    if not MAP_IMAGE_INDEX:
        refresh_local_caches()

    normalized_updates = {}
    updates = []
    for cid, servers in communities.items():
        if not isinstance(servers, list):
            continue
        normalized = []
        for srv in servers:
            if not isinstance(srv, dict):
                continue
            ip = srv.get('ip')
            port = srv.get('port')
            if ip and port and not srv.get('display_ip'):
                srv['display_ip'] = f"{ip}:{port}"
            if ip and not srv.get('connect_ip'):
                if is_ip_literal(ip):
                    srv['connect_ip'] = ip
                else:
                    srv['connect_ip'] = resolve_connect_ip(ip)
            image_url = get_map_image_url(srv.get('map'))
            if image_url:
                srv['image_url'] = image_url
            else:
                srv.pop('image_url', None)
            map_name = srv.get('map')
            entry = ensure_map_translation_entry(map_name)
            if entry:
                srv['map_cn'] = entry.get('zh_cn', '')
                srv['map_tw'] = entry.get('zh_tw', '')
            normalized.append(srv)
        ordered = apply_config_server_order(cid, normalized)
        normalized_updates[cid] = ordered
        updates.append((cid, ordered, compute_servers_hash(ordered)))

    if normalized_updates:
        now = int(time.time())
        with AGENT_CACHE_LOCK:
            for cid, normalized in normalized_updates.items():
                AGENT_CACHE[cid] = normalized
                AGENT_CACHE_UPDATED_AT[cid] = now
        if updates:
            apply_server_cache_updates(updates)

    maybe_flush_map_translations()
    return make_json_response({"status": "ok", "updated": list(communities.keys())})

@app.route('/api/agent/status')
def agent_status():
    token = os.environ.get('WATCHER_SHARED_TOKEN')
    if not token:
        return make_json_response({"ok": False, "error": "shared token not configured"}, status=403)
    if request.headers.get('X-Shared-Token') != token:
        return make_json_response({"ok": False, "error": "unauthorized"}, status=403)
    now = int(time.time())
    servers = []
    with AGENT_CACHE_LOCK:
        cache_snapshot = dict(AGENT_CACHE)
        updated_snapshot = dict(AGENT_CACHE_UPDATED_AT)
    for cid, srv_list in cache_snapshot.items():
        if not isinstance(srv_list, list):
            continue
        for srv in srv_list:
            if not isinstance(srv, dict):
                continue
            ip = srv.get('ip')
            port = srv.get('port')
            if not ip or not port:
                continue
            updated_at = int(srv.get('updated_at') or updated_snapshot.get(cid, 0) or 0)
            servers.append({
                "server_key": f"{ip}:{port}",
                "name": srv.get('name') or "Unknown",
                "players": int(srv.get('players') or 0),
                "max_players": int(srv.get('max_players') or 64),
                "game": srv.get('game') or "cs2",
                "community_id": srv.get('community_id') or str(cid),
                "source_type": "agent_push",
                "updated_at": updated_at
            })
    return make_json_response({"ok": True, "updated_at": now, "servers": servers})

def proxy_to_watcher(path, method):
    token = os.environ.get('WATCHER_SHARED_TOKEN')
    if not token:
        return make_json_response({"ok": False, "error": "watcher token not configured"}, status=500)

    url = f"{WATCHER_SERVICE_URL}{path}"
    headers = {"X-Shared-Token": token}
    steam_id = session.get('steam_id')

    try:
        if method == 'GET':
            params = dict(request.args or {})
            # Inject steam_id when missing (watcher requires it for queue-related calls)
            if steam_id and 'steam_id' not in params:
                params['steam_id'] = steam_id
            resp = requests.get(url, headers=headers, params=params, timeout=4)
        else:
            payload = request.get_json(silent=True) or {}
            if not isinstance(payload, dict):
                payload = {}
            # Inject steam_id when missing (watcher requires it for join/poll/leave/report)
            if steam_id and 'steam_id' not in payload:
                payload['steam_id'] = steam_id
            resp = requests.post(url, headers=headers, json=payload, timeout=4)
    except Exception as e:
        return make_json_response({"ok": False, "error": f"watcher_unreachable: {e}"}, status=502)

    try:
        data = resp.json()
    except Exception:
        return make_json_response({"ok": False, "error": "invalid watcher response"}, status=502)
    return make_json_response(data, status=resp.status_code)

@app.route('/api/map_translations')
def get_translations():
    refresh_local_caches()
    return make_json_response(MAP_TRANS_CACHE)

@app.route('/map_translations.json')
def get_public_translations():
    refresh_local_caches()
    return make_etag_response(MAP_TRANS_CACHE, 'public, max-age=1')

@app.route('/api/language')
def get_language_pack():
    return make_json_response(build_language_payload())

@app.route('/language.json')
def get_public_language_pack():
    data = build_language_payload()
    return make_etag_response(data, 'public, max-age=1')

@app.route('/api/stats')
def get_stats():
    global STATS_CACHE, STATS_CACHE_UPDATED_AT
    now = int(time.time())
    
    # 1. 实时计算当前在线数据 (Pie Chart / Total Count) - 从内存读取，无需缓存，保证秒级刷新
    snapshot = get_config_snapshot()
    colors = generate_distinct_colors(len(snapshot['community_meta']))
    meta_map = {c['id']: {'name': c.get('short_name', c['name']), 'color': colors[i]} for i, c in enumerate(snapshot['community_meta'])}
    
    current_stats = []
    total_players = 0
    
    # 直接读取当前的 SERVER_CACHE (这是由后台任务实时更新的)
    with SERVER_CACHE_LOCK:
        snapshot = dict(SERVER_CACHE)
        
    for cid, info in meta_map.items():
        count = 0
        if cid in snapshot:
            count = count_players_for_stats(cid, snapshot[cid])
        total_players += count
        current_stats.append({
            "id": cid, "name": info['name'], "count": count, "color": info['color']
        })
    current_stats.sort(key=lambda x: x['count'], reverse=True)

    # 2. 历史数据 (Line Chart) - 查询数据库，开销较大，使用缓存
    # 如果缓存存在且未过期，使用缓存中的历史数据
    if STATS_CACHE and (now - STATS_CACHE_UPDATED_AT) < STATS_CACHE_TTL_SECONDS:
        line_chart = STATS_CACHE.get('line_chart')
        total_peak_48h = STATS_CACHE.get('total_peak_48h')
    else:
        # 缓存过期，查询数据库
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT timestamp, community, count FROM player_stats WHERE timestamp > ? ORDER BY timestamp ASC", (now - 48*3600,))
        rows = c.fetchall()
        conn.close()

        line_chart = {'labels': [], 'datasets': []}
        total_peak_48h = 0
        
        if rows:
            timestamps = sorted(list(set([r[0] for r in rows])))
            line_chart['labels'] = timestamps
            
            data_map = {}
            totals_by_ts = {}
            for ts, cid, count in rows:
                if cid not in data_map:
                    data_map[cid] = {}
                data_map[cid][ts] = count
                totals_by_ts[ts] = totals_by_ts.get(ts, 0) + count
            if totals_by_ts:
                total_peak_48h = max(totals_by_ts.values())
                
            for cid, info in meta_map.items():
                if cid in data_map:
                    data = [data_map[cid].get(ts, 0) for ts in timestamps]
                    line_chart['datasets'].append({
                        "label": info['name'],
                        "borderColor": info['color'],
                        "backgroundColor": info['color'],
                        "data": data,
                        "fill": False,
                        "pointRadius": 0,
                        "tension": 0.4
                    })
        
        # 更新缓存 (只存历史部分)
        STATS_CACHE = {
            'line_chart': line_chart,
            'total_peak_48h': total_peak_48h
        }
        STATS_CACHE_UPDATED_AT = now

    # 3. 组装 Pie Chart 数据结构 (前端需要的数据格式)
    pie_chart = {'labels': [], 'datasets': [{'data': [], 'backgroundColor': []}]}
    for item in current_stats:
        if item['count'] > 0:
            pie_chart['labels'].append(item['name'])
            pie_chart['datasets'][0]['data'].append(item['count'])
            pie_chart['datasets'][0]['backgroundColor'].append(item['color'])

    # 4. 返回混合结果
    payload = {
        "current_stats": current_stats,
        "line_chart": line_chart,
        "pie_chart": pie_chart,
        "total_peak_48h": total_peak_48h
    }
    
    return make_etag_response(payload)


@app.before_request
def enforce_api_authentication():
    path = request.path or ''
    if not path.startswith('/api/'):
        return None
    if path.startswith('/api/steam/login') or path.startswith('/api/steam/callback') or path.startswith('/api/steam/status'):
        return None
    if path.startswith('/api/steam/logout'):
        return None
    if path.startswith('/api/agent/'):
        return None
    if is_logged_in():
        return None
    return make_json_response({"ok": False, "error": "login_required"}, status=401)

@app.before_request
def ensure_csrf_on_login():
    if session.get('steam_logged_in') and session.get('steam_id'):
        ensure_csrf_token()

@app.after_request
def set_cache_headers(response):
    path = request.path or ''
    if path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response
    if (
        path.startswith('/auth/')
        or path.startswith('/api/steam/')
        or path.startswith('/api/me')
        or path.startswith('/logout')
    ):
        return set_no_store(response)
    return response

@app.route('/sitemap.xml')
def sitemap_xml():
    base_url = request.url_root.rstrip('/') # 自动获取当前域名
    pages = ['', '/servers', '/map-sub', '/stats'] # 页面路径
    langs = ['en', 'zh-TW'] # 除了默认中文外的语言
    
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
    
    for p in pages:
        # 添加默认(中文)条目
        xml += '  <url>\n'
        xml += f'    <loc>{base_url}{p}</loc>\n'
        xml += '    <changefreq>daily</changefreq>\n'
        # Hreflang 交叉引用
        xml += f'    <xhtml:link rel="alternate" hreflang="x-default" href="{base_url}{p}"/>\n'
        xml += f'    <xhtml:link rel="alternate" hreflang="zh" href="{base_url}{p}"/>\n'
        for l in langs:
            xml += f'    <xhtml:link rel="alternate" hreflang="{l}" href="{base_url}{p}?lang={l}"/>\n'
        xml += '  </url>\n'
        
        # 添加其他语言条目
        for l in langs:
            xml += '  <url>\n'
            xml += f'    <loc>{base_url}{p}?lang={l}</loc>\n'
            xml += '    <changefreq>daily</changefreq>\n'
            xml += f'    <xhtml:link rel="alternate" hreflang="x-default" href="{base_url}{p}"/>\n'
            xml += f'    <xhtml:link rel="alternate" hreflang="zh" href="{base_url}{p}"/>\n'
            for l2 in langs:
                xml += f'    <xhtml:link rel="alternate" hreflang="{l2}" href="{base_url}{p}?lang={l2}"/>\n'
            xml += '  </url>\n'
            
    xml += '</urlset>'
    resp = make_response(xml)
    resp.headers["Content-Type"] = "application/xml"
    return resp

@app.route('/robots.txt')
def robots_txt():
    return f"User-agent: *\nAllow: /\nSitemap: {request.url_root}sitemap.xml"

if __name__ == '__main__':
    initialize_app()
    
    app.run(host='0.0.0.0', port=5000, debug=False)
