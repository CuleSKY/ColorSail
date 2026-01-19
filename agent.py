import time
import json
import requests
import os
import a2s
import base64
from concurrent.futures import ThreadPoolExecutor
import socket
import urllib3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 配置 ---
MASTER_URL = "http://23.224.49.85:5000"  # ⚠️ 请修改为您中国主服的 IP
AGENT_TOKEN = "ZE61QNWgB7rXqNHcg84u"    # 与 app.py 保持一致
SECRETS_FILE = 'secrets.json'

# 全局 Steam API Key (将从 secrets.json 中解密加载)
STEAM_API_KEY = None

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
    except: pass

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
        except: pass

    return res

def run_agent():
    # 启动时加载密钥
    load_secrets()
    
    print(f"[*] Agent 启动 | 目标主服: {MASTER_URL}")
    if not STEAM_API_KEY:
        print("[Warning] 未能加载 Steam API Key，将仅使用 A2S 查询。")

    while True:
        try:
            # Agent 读取本地 config.json 以获取完整服务器列表
            if not os.path.exists("config.json"):
                print("[Error] 请在 Agent 同目录下放置 config.json")
                time.sleep(10); continue
                
            with open("config.json", "r", encoding="utf-8") as f:
                local_config = json.load(f)

            non_cn_comms = [
                comm for comm in local_config.get('communities', [])
                if comm.get('location') != 'cn'
            ]

            # 处理任务
            payload = {"communities": {}}
            for comm in non_cn_comms:

                print(f"[Job] 更新社区: {comm['name']}")

                with ThreadPoolExecutor(max_workers=10) as executor:
                    results = list(executor.map(fetch_server_data, comm.get('servers', [])))

                online_count = sum(1 for r in results if r.get("online"))
                a2s_count = sum(1 for r in results if r.get("query_source") == "a2s")
                steam_count = sum(1 for r in results if r.get("query_source") == "steam_api")
                print(f"[Job] {comm['name']}: {online_count}/{len(results)} 在线 (A2S {a2s_count}, Steam {steam_count})")

                payload["communities"][comm['id']] = results

            if payload["communities"]:
                try:
                    resp = requests.post(
                        f"{MASTER_URL}/api/agent/update",
                        json=payload,
                        headers={"Authorization": f"Bearer {AGENT_TOKEN}"},
                        timeout=5
                    )
                    if resp.ok:
                        print(f"[Push] ✅ 更新成功: {', '.join(payload['communities'].keys())}")
                    else:
                        print(f"[Push] ❌ 更新失败: HTTP {resp.status_code}")
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
