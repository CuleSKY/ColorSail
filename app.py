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
from flask import Flask, render_template, jsonify, request
import a2s
from apscheduler.schedulers.background import BackgroundScheduler
from concurrent.futures import ThreadPoolExecutor

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# --- 基础配置 ---
CONFIG_FILE = 'config.json'
TRANS_FILE = 'map_translations.json'
DB_FILE = "stats.db"
STATIC_MAP_DIR = os.path.join('static', 'maps')

# EXG API 地址
EXG_API_URL = "https://list.darkrp.cn:9000/ServerList/CurrentStatus"

os.makedirs(STATIC_MAP_DIR, exist_ok=True)

# --- 全局状态 ---
SERVER_CACHE = {}
AGENT_CACHE = {}
AGENT_CACHE_UPDATED_AT = {}
EXG_CACHE = {}
EXG_CACHE_UPDATED_AT = 0.0
COMMUNITY_META = []
MAP_IMAGE_INDEX = set()
MAP_TRANS_CACHE = {}

EXG_SERVER_STALE_SECONDS = 15
EXG_FETCH_INTERVAL_SECONDS = 15
HTTP_SESSION = requests.Session()

EXG_STATS_EXCLUDE_KEYWORDS = ("pve", "大厅", "躲猫猫", "mg")

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

def refresh_local_caches():
    """刷新地图图片索引和翻译文件"""
    global MAP_IMAGE_INDEX, MAP_TRANS_CACHE
    try:
        if os.path.exists(STATIC_MAP_DIR):
            files = set()
            for f in os.listdir(STATIC_MAP_DIR):
                if f.lower().endswith(('.jpg', '.png', '.webp', '.jpeg')):
                    map_name = f.rsplit('.', 1)[0].lower()
                    files.add(map_name)
            MAP_IMAGE_INDEX = files
            print(f"[Cache] 已加载 {len(MAP_IMAGE_INDEX)} 个地图图片")
    except Exception as e:
        print(f"[Cache] 图片索引加载失败: {e}")
        MAP_IMAGE_INDEX = set()

    try:
        if os.path.exists(TRANS_FILE):
            with open(TRANS_FILE, 'r', encoding='utf-8') as f:
                MAP_TRANS_CACHE = json.load(f)
            print(f"[Cache] 已加载 {len(MAP_TRANS_CACHE)} 个地图翻译")
        else:
            with open(TRANS_FILE, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            MAP_TRANS_CACHE = {}
    except Exception as e:
        print(f"[Cache] 翻译加载失败: {e}")
        MAP_TRANS_CACHE = {}

def load_config():
    """加载 config.json 中的社区列表结构"""
    global COMMUNITY_META
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                COMMUNITY_META = data.get('communities', [])
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
    servers = []
    success = False
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        
        resp = HTTP_SESSION.get(EXG_API_URL, timeout=10, verify=False, headers=headers)
        
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
                    map_clean = map_name.lower().strip()
                    if map_clean.endswith('.bsp'):
                        map_clean = map_clean[:-4]
                    
                    if map_clean in MAP_IMAGE_INDEX:
                        server_obj['image_url'] = f"/static/maps/{map_clean}.jpg"
                    else:
                        server_obj['image_url'] = None
                    
                    # 中文翻译（优先使用 API 提供的）
                    if map_display:
                        server_obj['map_cn'] = map_display
                    elif map_name in MAP_TRANS_CACHE:
                        server_obj['map_cn'] = MAP_TRANS_CACHE[map_name]
                    elif map_clean in MAP_TRANS_CACHE:
                        server_obj['map_cn'] = MAP_TRANS_CACHE[map_clean]
                    
                    servers.append(server_obj)
                    
                except Exception as e:
                    continue
            
            print(f"[EXG API] 成功获取 {len(servers)} 个服务器")
                    
        else:
            print(f"[EXG API] HTTP 错误: {resp.status_code}")
            
    except Exception as e:
        print(f"[EXG API] 请求失败: {e}")

    return servers if success else None

def merge_exg_cache(fetched_servers):
    global EXG_CACHE
    now = time.time()
    for srv in fetched_servers:
        key = srv.get('display_ip') or f"{srv.get('ip')}:{srv.get('port')}"
        if not key:
            continue
        EXG_CACHE[key] = {**srv, "_last_seen": now}

    stale_keys = [k for k, v in EXG_CACHE.items() if now - v.get("_last_seen", 0) > EXG_SERVER_STALE_SECONDS]
    for k in stale_keys:
        del EXG_CACHE[k]

    return [{k: v for k, v in item.items() if k != "_last_seen"} for item in EXG_CACHE.values()]

# --- 3. 核心：A2S 抓取逻辑（其他社区）---
def fetch_a2s_data(server_cfg, game_type='cs2'):
    """使用 A2S 查询服务器"""
    host = server_cfg['host']
    port = server_cfg['port']
    name = server_cfg.get('name', f"{host}:{port}")
    
    res = {
        "name": name,
        "ip": host, 
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
        map_clean = info.map_name.lower().strip()
        if map_clean.endswith('.bsp'):
            map_clean = map_clean[:-4]
        
        if map_clean in MAP_IMAGE_INDEX:
            res['image_url'] = f"/static/maps/{map_clean}.jpg"
        
        # 翻译匹配
        if info.map_name in MAP_TRANS_CACHE:
            res['map_cn'] = MAP_TRANS_CACHE[info.map_name]
        elif map_clean in MAP_TRANS_CACHE:
            res['map_cn'] = MAP_TRANS_CACHE[map_clean]
            
    except Exception as e:
        pass
    
    return res

def is_exg_stats_eligible(server):
    name = (server.get("name") or "").strip()
    if not name:
        return True
    lower_name = name.lower()
    return not any(keyword in lower_name if keyword.isascii() else keyword in name for keyword in EXG_STATS_EXCLUDE_KEYWORDS)

# --- 4. 主更新循环 ---
def update_all_data():
    """定时任务：更新所有社区数据"""
    global SERVER_CACHE, EXG_CACHE_UPDATED_AT
    load_config()
    refresh_local_caches()
    
    new_cache = {}
    
    for comm in COMMUNITY_META:
        cid = comm['id']
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
            now = time.time()
            fetched = None
            if now - EXG_CACHE_UPDATED_AT >= EXG_FETCH_INTERVAL_SECONDS:
                fetched = fetch_exg_data_from_api()
            if fetched is not None:
                new_cache[cid] = merge_exg_cache(fetched)
                EXG_CACHE_UPDATED_AT = now
            else:
                new_cache[cid] = merge_exg_cache([])
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

# --- 6. 任务调度 ---
scheduler = BackgroundScheduler()
scheduler.add_job(update_all_data, 'interval', seconds=15, id='updater')
scheduler.start()

# --- 7. Flask 路由 ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config')
def get_config_meta():
    """返回社区的元数据"""
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
    if token:
        auth = request.headers.get('Authorization', '')
        if auth != f"Bearer {token}":
            return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    communities = payload.get('communities', {})
    if not isinstance(communities, dict):
        return jsonify({"error": "invalid payload"}), 400

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
            normalized.append(srv)
        AGENT_CACHE[cid] = normalized
        AGENT_CACHE_UPDATED_AT[cid] = int(time.time())

    return jsonify({"status": "ok", "updated": list(communities.keys())})

@app.route('/api/map_translations')
def get_translations():
    return jsonify(MAP_TRANS_CACHE)

@app.route('/api/stats')
def get_stats():
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
        line_chart['labels'] = [datetime.fromtimestamp(ts).strftime('%H:%M') for ts in timestamps]
        
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

    return jsonify({
        "current_stats": current_stats,
        "line_chart": line_chart,
        "pie_chart": pie_chart
    })

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
    print("-" * 70)
    print("\n✓ 初始化完成，服务器启动中...\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
