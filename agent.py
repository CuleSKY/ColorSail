import time
import json
import requests
import os
import a2s
import base64
import random
import hashlib
import hmac
from concurrent.futures import ThreadPoolExecutor
import socket
import urllib3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 配置 ---
MASTER_URL = os.environ.get("MASTER_URL", "")
AGENT_TOKEN = os.environ.get("AGENT_SHARED_TOKEN", "")    # 与 app.py 保持一致
SECRETS_FILE = 'secrets.json'

# 全局 Steam API Key (将从 secrets.json 中解密加载)
STEAM_API_KEY = None

# EXG API
EXG_API_URL = "https://list.darkrp.cn:9000/ServerList/CurrentStatus"
EXG_SESSION = requests.Session()
EXG_CACHE = []
EXG_CACHE_UPDATED_AT = 0
EXG_FETCH_INTERVAL_SECONDS = 15
EXG_VERIFY_SSL = os.environ.get('EXG_VERIFY_SSL', 'true').lower() in ('1', 'true', 'yes')

def load_secrets():
    """加载并解密 secrets.json 中的 Steam API Key"""
    global STEAM_API_KEY
    print("[Secrets] 正在加载密钥...")
    
    key_b64 = os.environ.get("APP_SECRET_KEY")
    if not key_b64:
        print("[Secrets] ❌ 环境变量 APP_SECRET_KEY 未设置！无法解密 API Key。")
        return

    try:
        if not os.path.exists(SECRETS_FILE):
            print(f"[Secrets] ❌ 未找到 {SECRETS_FILE}")
            return

        with open(SECRETS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            token_b64 = data.get('steam_api_token')
            
            if token_b64:
                # 解密逻辑
                key = base64.urlsafe_b64decode(key_b64)
                aesgcm = AESGCM(key)
                raw_data = base64.urlsafe_b64decode(token_b64)
                nonce = raw_data[:12]
                ciphertext = raw_data[12:]
                STEAM_API_KEY = aesgcm.decrypt(nonce, ciphertext, None).decode()
                print("[Secrets] ✅ Steam API Key 解密成功。")
            else:
                print("[Secrets] ❌ secrets.json 中缺少 steam_api_token 字段。")
                
    except Exception as e:
        print(f"[Secrets] ❌ 解密失败: {e}")

def fetch_server_data(server_cfg):
    host, port = server_cfg['host'], server_cfg['port']
    name = server_cfg.get('name', '')

    resolved_ip = None
    try:
        resolved_ip = socket.gethostbyname(host)
    except Exception:
        resolved_ip = None

    res = {
        "ip": host, "connect_ip": resolved_ip or host, "port": port, "display_ip": f"{host}:{port}",
        "name": name, "map": "-", "players": 0, "max_players": 0,
        "online": False,
        "ping": -1,
        "game_type": "cs2",
        "query_source": "offline"
    }

    # 1. A2S UDP 查询 (优先获取延迟)
    try:
        info = a2s.info((host, port), timeout=2.0)
        res.update({
            "online": True,
            "name": info.server_name,
            "map": info.map_name,
            "players": info.player_count,
            "max_players": info.max_players,
            "ping": int(info.ping * 1000),
            "query_source": "a2s"
        })
        return res
    except Exception:
        pass

    # 2. Steam API 兜底 (前提是 Key 解密成功)
    if STEAM_API_KEY:
        try:
            u = "https://api.steampowered.com/IGameServersService/GetServerList/v1/"
            query_addr = f"{resolved_ip or host}:{port}"
            p = {"key": STEAM_API_KEY, "filter": f"\\gameaddr\\{query_addr}", "limit": 1}
            r = requests.get(u, params=p, timeout=5)
            if r.status_code == 200:
                d = r.json().get('response', {}).get('servers', [])
                if d:
                    s = d[0]
                    res.update({
                        "online": True, "name": s.get('name'), "map": s.get('map'),
                        "players": s.get('players'), "max_players": s.get('max_players'),
                        "ping": -1,
                        "query_source": "steam_api"
                    })
        except Exception:
            pass

    return res

def fetch_exg_data_from_api():
    """从 EXG API 获取实时服务器数据"""
    global EXG_CACHE, EXG_CACHE_UPDATED_AT
    now = int(time.time())
    if EXG_CACHE and (now - EXG_CACHE_UPDATED_AT) < EXG_FETCH_INTERVAL_SECONDS:
        return EXG_CACHE

    servers = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        resp = EXG_SESSION.get(EXG_API_URL, timeout=10, verify=EXG_VERIFY_SSL, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            if not isinstance(data, list):
                data = [data]

            for item in data:
                try:
                    server_info = item.get('Server', {})
                    status_info = item.get('Status', {})

                    ip = server_info.get('Ip')
                    port = server_info.get('Port')
                    if not ip or not port:
                        continue

                    name = (status_info.get('FullTitle') or
                            server_info.get('DisplayNameCN') or
                            server_info.get('DisplayName') or
                            f"EXG {port}")

                    map_name = status_info.get('Map', '-')
                    map_display = status_info.get('MapDisplayName', '')
                    current_players = status_info.get('CurrentPlayers', 0)
                    max_players = status_info.get('MaxPlayers', 64)

                    server_obj = {
                        "name": name.strip(),
                        "ip": str(ip).strip(),
                        "connect_ip": str(ip).strip(),
                        "port": int(port),
                        "display_ip": f"{ip}:{port}",
                        "map": map_name,
                        "players": int(current_players),
                        "max_players": int(max_players),
                        "online": True,
                        "ping": -1,
                        "game_type": "cs2",
                        "query_source": "exg_api"
                    }

                    if map_display:
                        server_obj['map_cn'] = map_display
                        server_obj['map_tw'] = map_display

                    servers.append(server_obj)
                except Exception:
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

def run_agent():
    # 启动时加载密钥
    load_secrets()
    
    print(f"[*] Agent 启动 | 目标主服: {MASTER_URL}")
    if not AGENT_TOKEN:
        print("[Error] 未配置 AGENT_SHARED_TOKEN，无法推送数据。")
        return
    if not STEAM_API_KEY:
        print("[Warning] 未能加载 Steam API Key，将仅使用 A2S 查询。")

    base_interval = 15
    comm_index = 0
    comm_count = 1

    while True:
        try:
            # Agent 读取本地 config.json 以获取完整服务器列表
            if not os.path.exists("config.json"):
                print("[Error] 请在 Agent 同目录下放置 config.json")
                time.sleep(10)
                continue
                
            with open("config.json", "r", encoding="utf-8") as f:
                local_config = json.load(f)

            cn_comms = [
                comm for comm in local_config.get('communities', [])
                if comm.get('location') == 'cn'
            ]

            if not cn_comms:
                time.sleep(10)
                continue
            comm_count = len(cn_comms)

            comm = cn_comms[comm_index % len(cn_comms)]
            comm_index += 1
            server_list = comm.get('servers', [])

            print(f"[Job] 更新社区: {comm['name']}")
            if comm.get('id') == 'exg':
                results = fetch_exg_data_from_api()
            else:
                if server_list:
                    max_workers = min(10, max(1, len(server_list)))
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        results = list(executor.map(fetch_server_data, server_list))
                else:
                    results = []

            online_count = sum(1 for r in results if r.get("online"))
            a2s_count = sum(1 for r in results if r.get("query_source") == "a2s")
            steam_count = sum(1 for r in results if r.get("query_source") == "steam_api")
            print(f"[Job] {comm['name']}: {online_count}/{len(results)} 在线 (A2S {a2s_count}, Steam {steam_count})")

            payload = {"communities": {comm['id']: results}}
            payload_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)
            timestamp = str(int(time.time()))
            signature = hmac.new(
                AGENT_TOKEN.encode('utf-8'),
                f"{timestamp}.{payload_json}".encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            try:
                resp = requests.post(
                    f"{MASTER_URL}/api/agent/update",
                    data=payload_json,
                    headers={
                        "Authorization": f"Bearer {AGENT_TOKEN}",
                        "X-Agent-Timestamp": timestamp,
                        "X-Agent-Signature": signature,
                        "Content-Type": "application/json"
                    },
                    timeout=5
                )
                if resp.ok:
                    print(f"[Push] ✅ 更新成功: {comm['id']}")
                else:
                    print(f"[Push] ❌ 更新失败: HTTP {resp.status_code}")
            except Exception as e:
                print(f"[Push] 推送失败: {e}")

        except Exception as e:
            print(f"[Error] 主循环异常: {e}")

        per_comm_delay = max(1.0, base_interval / max(1, comm_count))
        jitter = random.uniform(0.2, 1.2)
        time.sleep(per_comm_delay + jitter)

if __name__ == "__main__":
    if not MASTER_URL:
        print("❌ 请先设置环境变量 MASTER_URL！")
    else:
        run_agent()
