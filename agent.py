import time
import json
import requests
import os
import a2s
import base64
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
import urllib3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 配置 ---
MASTER_URL = "http://23.224.49.85:5000"  # ⚠️ 请修改为您美国主服的 IP
AGENT_TOKEN = "ZE61QNWgB7rXqNHcg84u"    # 与 app.py 保持一致
SECRETS_FILE = 'secrets.json'

# 全局 Steam API Key (将从 secrets.json 中解密加载)
STEAM_API_KEY = None

# EXG 配置
EXG_URL = "https://list.darkrp.cn:9000/serverlist/cs2maplist"

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

def fetch_exg_web_data():
    """EXG 专属爬虫"""
    cache = {}
    try:
        resp = requests.get(EXG_URL, timeout=10, verify=False)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for row in soup.find_all('tr'):
                cols = row.find_all('td')
                if len(cols) >= 3:
                    raw_name = cols[0].get_text(strip=True)
                    raw_map = cols[1].get_text(strip=True)
                    raw_players = cols[2].get_text(strip=True)
                    
                    cur, max_p = 0, 64
                    if '/' in raw_players:
                        parts = raw_players.split('/')
                        cur = int(parts[0]) if parts[0].isdigit() else 0
                        max_p = int(parts[1]) if parts[1].isdigit() else 64
                    
                    cache[raw_name] = {
                        "map": raw_map,
                        "players": cur,
                        "max_players": max_p
                    }
            # print(f"[Crawler] EXG 抓取成功: {len(cache)} 条记录")
    except Exception as e:
        print(f"[Crawler] EXG 抓取失败: {e}")
    return cache

def fetch_server_data(server_cfg, exg_cache=None):
    host, port = server_cfg['host'], server_cfg['port']
    name = server_cfg.get('name', '')
    
    res = {
        "ip": host, "port": port, "display_ip": f"{host}:{port}",
        "name": name, "map": "-", "players": 0, "max_players": 0,
        "online": False, 
        "ping": -1, 
        "game_type": "cs2"
    }

    # 1. EXG 爬虫匹配
    if exg_cache:
        for web_name, web_data in exg_cache.items():
            if (web_name in name) or (name in web_name):
                res.update({
                    "online": True,
                    "map": web_data['map'],
                    "players": web_data['players'],
                    "max_players": web_data['max_players'],
                    "ping": -1
                })
                return res

    # 2. A2S UDP 查询 (优先获取延迟)
    try:
        info = a2s.info((host, port), timeout=2.0)
        res.update({
            "online": True,
            "name": info.server_name,
            "map": info.map_name,
            "players": info.player_count,
            "max_players": info.max_players,
            "ping": int(info.ping * 1000)
        })
        return res
    except: pass

    # 3. Steam API 兜底 (前提是 Key 解密成功)
    if STEAM_API_KEY:
        try:
            u = "https://api.steampowered.com/IGameServersService/GetServerList/v1/"
            p = {"key": STEAM_API_KEY, "filter": f"\\gameaddr\\{host}:{port}", "limit": 1}
            r = requests.get(u, params=p, timeout=5)
            if r.status_code == 200:
                d = r.json().get('response', {}).get('servers', [])
                if d:
                    s = d[0]
                    res.update({
                        "online": True, "name": s.get('name'), "map": s.get('map'),
                        "players": s.get('players'), "max_players": s.get('max_players'),
                        "ping": -1
                    })
        except: pass

    return res

def run_agent():
    # 启动时加载密钥
    load_secrets()
    
    print(f"[*] Agent 启动 | 目标主服: {MASTER_URL}")
    if not STEAM_API_KEY:
        print("[Warning] 未能加载 Steam API Key，将仅使用 A2S 和 爬虫。")

    while True:
        try:
            # 1. 拉取配置
            conf_resp = requests.get(f"{MASTER_URL}/api/config", timeout=10)
            if conf_resp.status_code != 200:
                print(f"[Config] 拉取失败: {conf_resp.status_code}")
                time.sleep(10); continue
            
            # Agent 读取本地 config.json 以获取完整服务器列表
            if not os.path.exists("config.json"):
                print("[Error] 请在 Agent 同目录下放置 config.json")
                time.sleep(10); continue
                
            with open("config.json", "r", encoding="utf-8") as f:
                local_config = json.load(f)

            # 2. 预抓取 EXG 数据
            exg_cache = fetch_exg_web_data()

            # 3. 处理任务
            for comm in local_config.get('communities', []):
                if comm.get('location') != 'cn': continue 

                print(f"[Job] 更新社区: {comm['name']}")
                current_exg = exg_cache if comm['id'] == 'exg' else None
                
                with ThreadPoolExecutor(max_workers=10) as executor:
                    results = list(executor.map(lambda s: fetch_server_data(s, current_exg), comm['servers']))

                # 4. 推送
                payload = {"id": comm['id'], "servers": results}
                try:
                    requests.post(
                        f"{MASTER_URL}/api/agent/push", 
                        json=payload, 
                        headers={"Authorization": f"Bearer {AGENT_TOKEN}"}, 
                        timeout=5
                    )
                except Exception as e:
                    print(f"[Push] 推送失败: {e}")

        except Exception as e:
            print(f"[Error] 主循环异常: {e}")
        
        time.sleep(15)

if __name__ == "__main__":
    if "YOUR_" in MASTER_URL:
        print("❌ 请先修改脚本中的 MASTER_URL！")
    else:
        run_agent()