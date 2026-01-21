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
from urllib.parse import urlencode
from datetime import datetime
from datetime import timedelta
from flask import Flask, render_template, jsonify, request, redirect, session, url_for, make_response
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
app.secret_key = os.environ.get('APP_SECRET_KEY') or os.environ.get('SECRET_KEY') or 'change-me'

# --- 基础配置 ---
CONFIG_FILE = 'config.json'
TRANS_FILE = 'map_translations.json'
LANGUAGE_FILE = 'language.json'
DB_FILE = "stats.db"
STATIC_MAP_DIR = os.path.join(STATIC_DIR, 'maps')

# EXG API 地址
EXG_API_URL = "https://list.darkrp.cn:9000/ServerList/CurrentStatus"
EXG_SESSION = requests.Session()
EXG_CACHE = []
EXG_CACHE_UPDATED_AT = 0

os.makedirs(STATIC_MAP_DIR, exist_ok=True)

# --- 全局状态 ---
SERVER_CACHE = {}
AGENT_CACHE = {}
AGENT_CACHE_UPDATED_AT = {}
COMMUNITY_META = []
ADMIN_STEAM_IDS = set()
FYS_COMMUNITY_IDS = set()
MAP_IMAGE_INDEX = {}
MAP_IMAGE_MTIME = 0
MAP_TRANS_CACHE = {}
MAP_TRANS_NORMALIZED = {}
MAP_TRANS_LOCK = threading.Lock()
SERVER_CACHE_LOCK = threading.Lock()
AGENT_CACHE_LOCK = threading.Lock()
MAP_TRANS_DIRTY = False
MAP_TRANS_LAST_WRITE = 0
MAP_CACHE_UPDATED_AT = 0
CACHE_REFRESH_INTERVAL_SECONDS = 300
OPENCC_S2T = OpenCC('s2t') if OpenCC else None
OPENCC_S2HK = OpenCC('s2hk') if OpenCC else None
OPENCC_S2TWP = OpenCC('s2twp') if OpenCC else None

EXG_FETCH_INTERVAL_SECONDS = 15
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

AGENT_ALLOWED_CIDRS = [cidr.strip() for cidr in os.environ.get('AGENT_ALLOWED_CIDRS', '').split(',') if cidr.strip()]
AGENT_TRUSTED_PROXIES = [cidr.strip() for cidr in os.environ.get('AGENT_TRUSTED_PROXIES', '').split(',') if cidr.strip()]
AGENT_SIGNATURE_TTL_SECONDS = int(os.environ.get('AGENT_SIGNATURE_TTL_SECONDS', '300'))

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
    global MAP_IMAGE_INDEX, MAP_IMAGE_MTIME, MAP_TRANS_CACHE, MAP_TRANS_NORMALIZED, MAP_CACHE_UPDATED_AT
    now = int(time.time())
    if not force and (now - MAP_CACHE_UPDATED_AT) < CACHE_REFRESH_INTERVAL_SECONDS:
        return
    try:
        if os.path.exists(STATIC_MAP_DIR):
            dir_mtime = int(os.path.getmtime(STATIC_MAP_DIR))
            if force or dir_mtime != MAP_IMAGE_MTIME:
                files = {}
                for f in os.listdir(STATIC_MAP_DIR):
                    if f.lower().endswith(('.jpg', '.png', '.webp', '.jpeg')):
                        map_name = f.rsplit('.', 1)[0].lower()
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
                with open(TRANS_FILE, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
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
            print(f"[Cache] 已加载 {len(MAP_TRANS_CACHE)} 个地图翻译")
    except Exception as e:
        print(f"[Cache] 翻译加载失败: {e}")
        MAP_TRANS_CACHE = {}
        MAP_TRANS_NORMALIZED = {}
    MAP_CACHE_UPDATED_AT = now

def convert_to_traditional(text):
    if not text:
        return ''
    try:
        if not OPENCC_S2T:
            return text
        return OPENCC_S2T.convert(text)
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
    try:
        resp = requests.post(STEAM_OPENID_ENDPOINT, data=payload, timeout=10)
    except Exception as e:
        print(f"[Steam] 验证失败: {e}")
        return None
    if resp.status_code != 200 or "is_valid:true" not in resp.text:
        print(f"[Steam] OpenID 校验失败: {resp.status_code}")
        return None
    claimed_id = args.get("openid.claimed_id", "")
    match = re.search(r"https?://steamcommunity\\.com/openid/id/(\\d+)", claimed_id)
    if not match:
        return None
    return match.group(1)

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
            if (window.opener && !window.opener.closed) {{
                window.opener.postMessage(payload, "*");
            }}
            window.close();
        }})();
    </script>
</body>
</html>"""
    resp = make_response(html)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
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
    name_match = re.search(r"<steamID><!\\[CDATA\\[(.*?)\\]\\]></steamID>", text)
    avatar_match = re.search(r"<avatarMedium><!\\[CDATA\\[(.*?)\\]\\]></avatarMedium>", text)
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

def get_map_translation_entry(map_name):
    if not map_name:
        return None
    if map_name in MAP_TRANS_CACHE:
        return MAP_TRANS_CACHE[map_name]
    map_clean = normalize_map_name(map_name)
    if map_clean and map_clean in MAP_TRANS_CACHE:
        return MAP_TRANS_CACHE[map_clean]
    if map_clean and map_clean in MAP_TRANS_NORMALIZED:
        return MAP_TRANS_NORMALIZED[map_clean]
    return None

def update_map_translation_entry(map_name, map_display):
    global MAP_TRANS_DIRTY
    if not map_name or not map_display:
        return False
    map_clean = normalize_map_name(map_name)
    map_key = map_name if map_name in MAP_TRANS_CACHE else (map_clean or map_name)
    zh_cn = str(map_display).strip()
    if not zh_cn:
        return False
    zh_tw = convert_to_traditional(zh_cn)
    updated = False
    with MAP_TRANS_LOCK:
        entry = MAP_TRANS_CACHE.get(map_key)
        if entry:
            if not entry.get('zh_cn'):
                entry['zh_cn'] = zh_cn
                updated = True
            if not entry.get('zh_tw'):
                entry['zh_tw'] = zh_tw
                updated = True
            MAP_TRANS_CACHE[map_key] = entry
        else:
            MAP_TRANS_CACHE[map_key] = {"zh_cn": zh_cn, "zh_tw": zh_tw}
            updated = True
        if updated:
            rebuild_translated_index()
            MAP_TRANS_DIRTY = True
    return updated

def flush_map_translations(force=False):
    global MAP_TRANS_DIRTY, MAP_TRANS_LAST_WRITE
    if not MAP_TRANS_DIRTY and not force:
        return
    with MAP_TRANS_LOCK:
        try:
            with open(TRANS_FILE, 'w', encoding='utf-8') as f:
                json.dump(MAP_TRANS_CACHE, f, ensure_ascii=False, indent=4)
            MAP_TRANS_DIRTY = False
            MAP_TRANS_LAST_WRITE = int(time.time())
        except Exception as e:
            print(f"[Cache] 翻译写入失败: {e}")

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

def load_config():
    """加载 config.json 中的社区列表结构"""
    global COMMUNITY_META, STATS_EXPORT_RETENTION_DAYS, FYS_COMMUNITY_IDS, ADMIN_STEAM_IDS
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                COMMUNITY_META = data.get('communities', [])
                ADMIN_STEAM_IDS = {str(sid).strip() for sid in data.get('admin_steam_ids', []) if str(sid).strip()}
                fys_ids = set()
                for comm in COMMUNITY_META:
                    cid = str(comm.get('id', '')).strip()
                    name = str(comm.get('name', '')).strip()
                    short_name = str(comm.get('short_name', '')).strip()
                    if cid.casefold() == "fys" or name.casefold() == "fys" or short_name.casefold() == "fys":
                        if cid:
                            fys_ids.add(cid)
                FYS_COMMUNITY_IDS = fys_ids
                retention_days = data.get('stats_export_retention_days')
                if isinstance(retention_days, int) and retention_days > 0:
                    STATS_EXPORT_RETENTION_DAYS = retention_days
                print(f"[Config] 已加载 {len(COMMUNITY_META)} 个社区配置")
        else:
            print("[Config] 配置文件不存在")
            COMMUNITY_META = []
            FYS_COMMUNITY_IDS = set()
            ADMIN_STEAM_IDS = set()
    except Exception as e:
        print(f"[Config] 加载失败: {e}")
        FYS_COMMUNITY_IDS = set()
        ADMIN_STEAM_IDS = set()

def build_community_meta():
    def is_svg_asset(value):
        if not value:
            return False
        value = str(value)
        return value.lower().split('?', 1)[0].endswith('.svg')

    meta = []
    for c in COMMUNITY_META:
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
                    
                    # 中文翻译（优先使用 API 提供的）
                    if map_display:
                        update_map_translation_entry(map_name, map_display)
                        server_obj['map_cn'] = map_display
                        server_obj['map_tw'] = convert_to_traditional(map_display)
                    else:
                        entry = get_map_translation_entry(map_name)
                        if entry:
                            server_obj['map_cn'] = entry.get('zh_cn', '')
                            server_obj['map_tw'] = entry.get('zh_tw', '')
                    
                    servers.append(server_obj)
                    
                except Exception as e:
                    continue
            
            EXG_CACHE = servers
            EXG_CACHE_UPDATED_AT = now
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
    resolved_ip = None
    try:
        resolved_ip = socket.gethostbyname(host)
    except Exception:
        resolved_ip = None
    
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
        entry = get_map_translation_entry(info.map_name)
        if entry:
            res['map_cn'] = entry.get('zh_cn', '')
            res['map_tw'] = entry.get('zh_tw', '')
            
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
    return cid.casefold() == "fys" or cid in FYS_COMMUNITY_IDS

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

def update_single_comm(comm):
    """更新单个社区数据并写入缓存"""
    global SERVER_CACHE
    cid = comm['id']
    result = []
    now = int(time.time())

    def agent_fallback(reason):
        print(f"[Update] {comm['name']}: {reason}")
        with SERVER_CACHE_LOCK:
            return SERVER_CACHE.get(cid, [])

    if comm.get('location') != 'cn':
        with AGENT_CACHE_LOCK:
            agent_servers = AGENT_CACHE.get(cid)
            agent_updated_at = AGENT_CACHE_UPDATED_AT.get(cid, 0)
        if agent_servers is None:
            result = agent_fallback("等待 agent 数据 (non-cn)")
        elif now - agent_updated_at > AGENT_STALE_SECONDS:
            result = agent_fallback("agent 数据过期 (non-cn)")
        else:
            result = agent_servers
            online_count = sum(1 for s in agent_servers if s.get('online'))
            total_players = sum(s['players'] for s in agent_servers if s.get('online'))
            print(f"[Update] {comm['name']}: {online_count}/{len(agent_servers)} 在线, {total_players} 玩家 (agent)")
    else:
        use_agent = comm.get('source') == 'agent' or comm.get('agent') is True
        with AGENT_CACHE_LOCK:
            agent_servers = AGENT_CACHE.get(cid, [])
            agent_updated_at = AGENT_CACHE_UPDATED_AT.get(cid, 0)
            has_agent_data = cid in AGENT_CACHE
        if use_agent or has_agent_data:
            if agent_updated_at and now - agent_updated_at > AGENT_STALE_SECONDS:
                result = agent_fallback("agent 数据过期")
            else:
                result = agent_servers
                online_count = sum(1 for s in agent_servers if s.get('online'))
                total_players = sum(s['players'] for s in agent_servers if s.get('online'))
                print(f"[Update] {comm['name']}: {online_count}/{len(agent_servers)} 在线, {total_players} 玩家 (agent)")
        elif cid == 'exg':
            exg_data = fetch_exg_data_from_api()
            if exg_data:
                result = exg_data
            else:
                with SERVER_CACHE_LOCK:
                    result = SERVER_CACHE.get(cid, [])
            online_count = sum(1 for s in result if s.get('online'))
            total_players = sum(s['players'] for s in result if s.get('online'))
            print(f"[Update] {comm['name']}: {online_count}/{len(result)} 在线, {total_players} 玩家")
        else:
            server_list = comm.get('servers', [])
            if server_list:
                game = comm.get('game', 'cs2')
                max_workers = min(20, max(1, len(server_list)))
                with ThreadPoolExecutor(max_workers=max_workers) as exe:
                    result = list(exe.map(lambda s: fetch_a2s_data(s, game), server_list))
                online_count = sum(1 for s in result if s.get('online'))
                total_players = sum(s['players'] for s in result if s.get('online'))
                print(f"[Update] {comm['name']}: {online_count}/{len(result)} 在线, {total_players} 玩家")
            else:
                result = []

    with SERVER_CACHE_LOCK:
        SERVER_CACHE[cid] = result
    return result


def update_all_data():
    """立即刷新所有社区数据（仅用于启动或手动调用）"""
    load_config()
    refresh_local_caches()
    for comm in COMMUNITY_META:
        update_single_comm(comm)
    save_stats()
    flush_map_translations()

# --- 5. 数据库逻辑 ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS player_stats (timestamp INTEGER, community TEXT, count INTEGER)''')
    conn.commit()
    conn.close()

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
    cutoff = time.time() - STATS_EXPORT_RETENTION_DAYS * 24 * 3600
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
SCHEDULE_INTERVAL_SECONDS = 15
SCHEDULE_CONFIG_SYNC_SECONDS = 300
SCHEDULE_STATS_SAVE_SECONDS = 60
AGENT_STALE_SECONDS = 60

scheduler = BackgroundScheduler()
scheduler.add_job(export_stats_to_excel, 'interval', hours=48, id='stats_export')
scheduler.add_job(cleanup_stat_exports, 'interval', days=1, id='stats_cleanup')

def schedule_community_jobs():
    """为每个社区建立错位轮询任务"""
    load_config()
    refresh_local_caches()
    if not COMMUNITY_META:
        return
    job_ids = {f"comm_update_{c['id']}" for c in COMMUNITY_META}
    for job in scheduler.get_jobs():
        if job.id.startswith("comm_update_") and job.id not in job_ids:
            scheduler.remove_job(job.id)
    spread = SCHEDULE_INTERVAL_SECONDS / max(1, len(COMMUNITY_META))
    now = datetime.now()
    for index, comm in enumerate(COMMUNITY_META):
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
    flush_map_translations()

scheduler.add_job(schedule_community_jobs, 'interval', seconds=SCHEDULE_CONFIG_SYNC_SECONDS, id='config_sync')
scheduler.add_job(save_stats_snapshot, 'interval', seconds=SCHEDULE_STATS_SAVE_SECONDS, id='stats_snapshot')

def start_scheduler():
    if not scheduler.running:
        schedule_community_jobs()
        scheduler.start()

# --- 7. Flask 路由 ---
@app.route('/')
@app.route('/servers')
@app.route('/map-sub')
@app.route('/stats')
@app.route('/feedback')
def index():
    view_map = {
        '/': 'servers',
        '/servers': 'servers',
        '/map-sub': 'map_sub',
        '/stats': 'stats',
        '/feedback': 'feedback'
    }
    initial_view = view_map.get(request.path, 'servers')
    load_config()
    initial_config = build_community_meta()
    return render_template('index.html', initial_view=initial_view, initial_config=initial_config)

@app.route('/api/steam/login')
def steam_login():
    login_url = build_steam_openid_url()
    return redirect(login_url)

@app.route('/api/steam/callback')
def steam_callback():
    state = request.args.get('state', '')
    expected_state = session.get('steam_login_state')
    created_at = session.get('steam_login_created_at', 0)
    if not state or state != expected_state:
        return render_steam_callback("error", "invalid_state")
    if created_at and int(time.time()) - int(created_at) > STEAM_AUTH_STATE_TTL_SECONDS:
        return render_steam_callback("error", "state_expired")
    steam_id = verify_steam_openid(request.args)
    if not steam_id:
        return render_steam_callback("error", "invalid_auth")
    session['steam_id'] = steam_id
    session['steam_logged_in'] = True
    session.pop('steam_login_state', None)
    session.pop('steam_login_created_at', None)
    return render_steam_callback("ok", "authenticated", steam_id=steam_id)

@app.route('/api/steam/status')
def steam_status():
    load_config()
    steam_id = session.get('steam_id')
    logged_in = bool(session.get('steam_logged_in')) and bool(steam_id)
    profile = get_cached_steam_profile(steam_id) if logged_in else None
    role = "admin" if logged_in and steam_id in ADMIN_STEAM_IDS else "member"
    return jsonify({
        "logged_in": logged_in,
        "steam_id": steam_id if logged_in else None,
        "role": role if logged_in else "guest",
        "profile": profile
    })

@app.route('/api/steam/logout', methods=['POST'])
def steam_logout():
    session.pop('steam_id', None)
    session.pop('steam_logged_in', None)
    session.pop('steam_login_state', None)
    session.pop('steam_login_created_at', None)
    session.pop('steam_profile', None)
    session.pop('steam_profile_updated_at', None)
    return jsonify({"logged_in": False})

@app.route('/api/config')
def get_config_meta():
    """返回社区的元数据"""
    load_config()
    return jsonify(build_community_meta())

@app.route('/api/servers/<cid>')
def get_servers(cid):
    """返回指定社区的实时服务器列表"""
    with SERVER_CACHE_LOCK:
        data = SERVER_CACHE.get(cid, [])
    return jsonify(data)

@app.route('/api/agent/update', methods=['POST'])
def update_agent_data():
    token = os.environ.get('AGENT_SHARED_TOKEN')
    if not token:
        return jsonify({"error": "agent token not configured"}), 403
    client_ip = get_client_ip(request)
    if not client_ip_allowed(client_ip):
        return jsonify({"error": "ip not allowed"}), 403
    auth = request.headers.get('Authorization', '')
    if auth != f"Bearer {token}":
        return jsonify({"error": "unauthorized"}), 401
    raw_body = request.get_data(cache=True, as_text=True) or ''
    signature = request.headers.get('X-Agent-Signature')
    timestamp = request.headers.get('X-Agent-Timestamp')
    payload, canonical_body = canonicalize_payload(raw_body)
    if payload is None or canonical_body is None:
        return jsonify({"error": "invalid payload"}), 400
    if not verify_agent_signature(token, timestamp, signature, canonical_body):
        return jsonify({"error": "invalid signature"}), 401

    communities = payload.get('communities', {})
    if not isinstance(communities, dict):
        return jsonify({"error": "invalid payload"}), 400
    if not MAP_IMAGE_INDEX:
        refresh_local_caches()

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
                try:
                    srv['connect_ip'] = socket.gethostbyname(ip)
                except Exception:
                    srv['connect_ip'] = ip
            image_url = get_map_image_url(srv.get('map'))
            if image_url:
                srv['image_url'] = image_url
            else:
                srv.pop('image_url', None)
            map_name = srv.get('map')
            entry = get_map_translation_entry(map_name)
            if entry:
                srv['map_cn'] = entry.get('zh_cn', '')
                srv['map_tw'] = entry.get('zh_tw', '')
            normalized.append(srv)
        with AGENT_CACHE_LOCK:
            AGENT_CACHE[cid] = normalized
            AGENT_CACHE_UPDATED_AT[cid] = int(time.time())

    return jsonify({"status": "ok", "updated": list(communities.keys())})

@app.route('/api/map_translations')
def get_translations():
    refresh_local_caches()
    return jsonify(MAP_TRANS_CACHE)

@app.route('/api/language')
def get_language_pack():
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
                return jsonify(data)
    except Exception as e:
        print(f"[Language] 加载失败: {e}")
    return jsonify({})

@app.route('/api/stats')
def get_stats():
    global STATS_CACHE, STATS_CACHE_UPDATED_AT
    now = int(time.time())
    if STATS_CACHE and (now - STATS_CACHE_UPDATED_AT) < STATS_CACHE_TTL_SECONDS:
        response = jsonify(STATS_CACHE)
        response.headers['Cache-Control'] = f"public, max-age={STATS_CACHE_TTL_SECONDS}, s-maxage={STATS_CACHE_TTL_SECONDS}"
        return response

    colors = generate_distinct_colors(len(COMMUNITY_META))
    meta_map = {c['id']: {'name': c.get('short_name', c['name']), 'color': colors[i]} for i, c in enumerate(COMMUNITY_META)}
    
    current_stats = []
    total_players = 0
    for cid, info in meta_map.items():
        count = 0
        if cid in SERVER_CACHE:
            count = count_players_for_stats(cid, SERVER_CACHE[cid])
        total_players += count
        current_stats.append({
            "id": cid, "name": info['name'], "count": count, "color": info['color']
        })
    current_stats.sort(key=lambda x: x['count'], reverse=True)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT timestamp, community, count FROM player_stats WHERE timestamp > ? ORDER BY timestamp ASC", (int(time.time()) - 48*3600,))
    rows = c.fetchall()
    conn.close()

    line_chart = {'labels': [], 'datasets': []}
    pie_chart = {'labels': [], 'datasets': [{'data': [], 'backgroundColor': []}]}
    total_peak_48h = 0
    
    for item in current_stats:
        if item['count'] > 0:
            pie_chart['labels'].append(item['name'])
            pie_chart['datasets'][0]['data'].append(item['count'])
            pie_chart['datasets'][0]['backgroundColor'].append(item['color'])

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

    payload = {
        "current_stats": current_stats,
        "line_chart": line_chart,
        "pie_chart": pie_chart,
        "total_peak_48h": total_peak_48h
    }
    STATS_CACHE = payload
    STATS_CACHE_UPDATED_AT = now
    response = jsonify(payload)
    response.headers['Cache-Control'] = f"public, max-age={STATS_CACHE_TTL_SECONDS}, s-maxage={STATS_CACHE_TTL_SECONDS}"
    return response


@app.after_request
def set_cache_headers(response):
    path = request.path or ''
    if path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print(" " * 20 + "CS2ZE Browser 服务器")
    print("=" * 70 + "\n")
    
    init_db()
    load_config()
    refresh_local_caches()
    
    print("\n[Startup] 执行初始数据更新...")
    print("-" * 70)
    update_all_data()
    flush_map_translations(force=True)
    print("-" * 70)
    print("\n✓ 初始化完成，服务器启动中...\n")

    start_scheduler()
    
    app.run(host='0.0.0.0', port=5000, debug=False)
