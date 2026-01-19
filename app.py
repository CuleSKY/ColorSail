import json
import time
import sqlite3
import requests
import sys
import os
import base64
import threading
import colorsys
import socket
import urllib3
from datetime import datetime
from datetime import timedelta
from flask import Flask, render_template, jsonify, request
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

# --- 基础配置 ---
CONFIG_FILE = 'config.json'
TRANS_FILE = 'map_translations.json'
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
MAP_IMAGE_INDEX = {}
MAP_TRANS_CACHE = {}
MAP_TRANS_NORMALIZED = {}
MAP_TRANS_LOCK = threading.Lock()
MAP_TRANS_DIRTY = False
MAP_TRANS_LAST_WRITE = 0
MAP_CACHE_UPDATED_AT = 0
CACHE_REFRESH_INTERVAL_SECONDS = 300
MAP_TRANS_MTIME = 0
MAP_IMAGE_MTIME = 0
OPENCC = OpenCC('s2t') if OpenCC else None

EXG_SERVER_STALE_SECONDS = 15
EXG_FETCH_INTERVAL_SECONDS = 15
HTTP_SESSION = requests.Session()
EXG_VERIFY_SSL = os.environ.get('EXG_VERIFY_SSL', 'true').lower() in ('1', 'true', 'yes')

EXG_STATS_EXCLUDE_KEYWORDS = ("pve", "大厅", "躲猫猫", "mg")
STATS_CACHE_TTL_SECONDS = 30 * 60
STATS_CACHE = None
STATS_CACHE_UPDATED_AT = 0
STATS_EXPORT_RETENTION_DAYS = 30

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000

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

def beijing_timestamp():
    return int(time.time()) + 8 * 3600

def beijing_date():
    return datetime.utcnow() + timedelta(hours=8)

def refresh_local_caches(force=False):
    """刷新地图图片索引和翻译文件"""
    global MAP_IMAGE_INDEX, MAP_TRANS_CACHE, MAP_TRANS_NORMALIZED, MAP_CACHE_UPDATED_AT, MAP_TRANS_MTIME, MAP_IMAGE_MTIME
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
                file_mtime = int(os.path.getmtime(TRANS_FILE))
                if not force and file_mtime == MAP_TRANS_MTIME:
                    MAP_CACHE_UPDATED_AT = now
                    return
                with open(TRANS_FILE, 'r', encoding='utf-8') as f:
                    raw_trans = json.load(f)
            else:
                raw_trans = {}
                with open(TRANS_FILE, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
                file_mtime = int(os.path.getmtime(TRANS_FILE))
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
            MAP_TRANS_MTIME = file_mtime
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
        if not OPENCC:
            return text
        return OPENCC.convert(text)
    except Exception:
        return text

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
    global MAP_TRANS_DIRTY, MAP_TRANS_LAST_WRITE, MAP_TRANS_MTIME
    if not MAP_TRANS_DIRTY and not force:
        return
    with MAP_TRANS_LOCK:
        try:
            with open(TRANS_FILE, 'w', encoding='utf-8') as f:
                json.dump(MAP_TRANS_CACHE, f, ensure_ascii=False, indent=4)
            if os.path.exists(TRANS_FILE):
                try:
                    MAP_TRANS_MTIME = int(os.path.getmtime(TRANS_FILE))
                except Exception:
                    pass
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
    global COMMUNITY_META, STATS_EXPORT_RETENTION_DAYS
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                COMMUNITY_META = data.get('communities', [])
                retention_days = data.get('stats_export_retention_days')
                if isinstance(retention_days, int) and retention_days > 0:
                    STATS_EXPORT_RETENTION_DAYS = retention_days
                print(f"[Config] 已加载 {len(COMMUNITY_META)} 个社区配置")
        else:
            print("[Config] 配置文件不存在")
            COMMUNITY_META = []
    except Exception as e:
        print(f"[Config] 加载失败: {e}")

# --- 2. 核心：EXG API 直接抓取（实时数据）---
def fetch_exg_data_from_api():
    """
    直接从 EXG API 获取实时服务器数据
    返回格式与 A2S 查询结果一致
    """
    global EXG_CACHE, EXG_CACHE_UPDATED_AT
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
            EXG_CACHE_UPDATED_AT = int(time.time())
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

# --- 4. 主更新循环 ---
def update_all_data():
    """定时任务：更新所有社区数据"""
    global SERVER_CACHE, EXG_CACHE_UPDATED_AT
    load_config()
    refresh_local_caches()
    
    new_cache = {}
    
    for comm in COMMUNITY_META:
        cid = comm['id']
        if comm.get('location') != 'cn':
            agent_servers = AGENT_CACHE.get(cid)
            if agent_servers is None:
                new_cache[cid] = []
                print(f"[Update] {comm['name']}: 等待 agent 数据 (non-cn)")
                continue
            new_cache[cid] = agent_servers
            online_count = sum(1 for s in agent_servers if s.get('online'))
            total_players = sum(s['players'] for s in agent_servers if s.get('online'))
            print(f"[Update] {comm['name']}: {online_count}/{len(agent_servers)} 在线, {total_players} 玩家 (agent)")
            continue
        use_agent = comm.get('source') == 'agent' or comm.get('agent') is True
        if use_agent:
            agent_servers = AGENT_CACHE.get(cid, [])
            new_cache[cid] = agent_servers
            online_count = sum(1 for s in agent_servers if s.get('online'))
            total_players = sum(s['players'] for s in agent_servers if s.get('online'))
            print(f"[Update] {comm['name']}: {online_count}/{len(agent_servers)} 在线, {total_players} 玩家 (agent)")
            continue
        if cid in AGENT_CACHE:
            agent_servers = AGENT_CACHE.get(cid, [])
            new_cache[cid] = agent_servers
            online_count = sum(1 for s in agent_servers if s.get('online'))
            total_players = sum(s['players'] for s in agent_servers if s.get('online'))
            print(f"[Update] {comm['name']}: {online_count}/{len(agent_servers)} 在线, {total_players} 玩家 (agent)")
            continue
        
        # === EXG 特殊处理：直接从 API 获取 ===
        if cid == 'exg':
            exg_data = fetch_exg_data_from_api()
            if exg_data:
                new_cache[cid] = exg_data
            else:
                new_cache[cid] = SERVER_CACHE.get(cid, [])
            online_count = sum(1 for s in new_cache[cid] if s.get('online'))
            total_players = sum(s['players'] for s in new_cache[cid] if s.get('online'))
            print(f"[Update] {comm['name']}: {online_count}/{len(new_cache[cid])} 在线, {total_players} 玩家")
        
        # === 其他社区：使用 A2S ===
        else:
            server_list = comm.get('servers', [])
            if not server_list:
                new_cache[cid] = []
                continue
            
            game = comm.get('game', 'cs2')
            
            with ThreadPoolExecutor(max_workers=20) as exe:
                results = list(exe.map(lambda s: fetch_a2s_data(s, game), server_list))
            
            online_count = sum(1 for s in results if s.get('online'))
            total_players = sum(s['players'] for s in results if s.get('online'))
            
            new_cache[cid] = results
            print(f"[Update] {comm['name']}: {online_count}/{len(results)} 在线, {total_players} 玩家")

    SERVER_CACHE = new_cache
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
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM player_stats WHERE timestamp < ?", (timestamp - 48 * 3600,))
    
    for cid, servers in SERVER_CACHE.items():
        if cid == "exg":
            count = sum(s['players'] for s in servers if s.get('online') and is_exg_stats_eligible(s))
        else:
            count = sum(s['players'] for s in servers if s.get('online'))
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
scheduler = BackgroundScheduler()
scheduler.add_job(update_all_data, 'interval', seconds=15, id='updater')
scheduler.add_job(export_stats_to_excel, 'interval', hours=48, id='stats_export')
scheduler.add_job(cleanup_stat_exports, 'interval', days=1, id='stats_cleanup')

def start_scheduler():
    if not scheduler.running:
        scheduler.start()

# --- 7. Flask 路由 ---
@app.route('/')
@app.route('/servers')
@app.route('/map-sub')
@app.route('/stats')
def index():
    view_map = {
        '/': 'servers',
        '/servers': 'servers',
        '/map-sub': 'map_sub',
        '/stats': 'stats'
    }
    initial_view = view_map.get(request.path, 'servers')
    return render_template('index.html', initial_view=initial_view)

@app.route('/api/config')
def get_config_meta():
    """返回社区的元数据"""
    load_config()
    meta = []
    for c in COMMUNITY_META:
        meta.append({
            "id": c['id'],
            "name": c['name'],
            "logo": c.get('logo', ''),
            "game": c.get('game', 'cs2'),
            "features": c.get('features', []),
            "map_url": c.get('map_cd_url', '') if "map_cd" in c.get('features', []) else "",
            "short_name": c.get('short_name', c['name'])
        })
    return jsonify(meta)

@app.route('/api/servers/<cid>')
def get_servers(cid):
    """返回指定社区的实时服务器列表"""
    return jsonify(SERVER_CACHE.get(cid, []))

@app.route('/api/agent/update', methods=['POST'])
def update_agent_data():
    token = os.environ.get('AGENT_SHARED_TOKEN')
    if not token:
        return jsonify({"error": "agent token not configured"}), 403
    auth = request.headers.get('Authorization', '')
    if auth != f"Bearer {token}":
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
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
        AGENT_CACHE[cid] = normalized
        AGENT_CACHE_UPDATED_AT[cid] = int(time.time())

    return jsonify({"status": "ok", "updated": list(communities.keys())})

@app.route('/api/map_translations')
def get_translations():
    return jsonify(MAP_TRANS_CACHE)

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
            if cid == "exg":
                count = sum(s['players'] for s in SERVER_CACHE[cid] if s.get('online') and is_exg_stats_eligible(s))
            else:
                count = sum(s['players'] for s in SERVER_CACHE[cid] if s.get('online'))
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
    
    for item in current_stats:
        if item['count'] > 0:
            pie_chart['labels'].append(item['name'])
            pie_chart['datasets'][0]['data'].append(item['count'])
            pie_chart['datasets'][0]['backgroundColor'].append(item['color'])

    if rows:
        timestamps = sorted(list(set([r[0] for r in rows])))
        line_chart['labels'] = timestamps
        
        data_map = {}
        for ts, cid, count in rows:
            if cid not in data_map: data_map[cid] = {}
            data_map[cid][ts] = count
            
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
        "pie_chart": pie_chart
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
