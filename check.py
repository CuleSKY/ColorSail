import json
import socket
import os
import a2s
import time

# --- 颜色配置 (让输出更直观) ---
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def load_config():
    if not os.path.exists("config.json"):
        print(f"{Colors.FAIL}[错误] 找不到 config.json 文件！请将此脚本放在配置文件同级目录下。{Colors.ENDC}")
        return None
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"{Colors.FAIL}[错误] config.json 格式错误: {e}{Colors.ENDC}")
        return None

def check_server(server, timeout=3.0):
    host = server.get('host')
    port = server.get('port')
    # 关键：检查是否有 query_port，没有则使用 port
    query_port = server.get('query_port', port)
    name_hint = server.get('name', '未命名服务器')

    target_str = f"{host}:{query_port}"
    if query_port != port:
        target_str += f" (连接端口: {port})"

    print(f"正在连接: {target_str:<35} ... ", end='', flush=True)

    try:
        # 1. DNS 解析测试
        try:
            ip = socket.gethostbyname(host)
        except socket.gaierror:
            print(f"{Colors.FAIL}[DNS 解析失败]{Colors.ENDC}")
            return

        # 2. A2S 查询测试
        start_time = time.time()
        info = a2s.info((host, query_port), timeout=timeout)
        ping = int((time.time() - start_time) * 1000)

        # 成功输出
        print(f"{Colors.OKGREEN}[成功]{Colors.ENDC}")
        print(f"    ├─ 状态: {Colors.BOLD}在线{Colors.ENDC}")
        print(f"    ├─ 名称: {info.server_name}")
        print(f"    ├─ 地图: {info.map_name}")
        print(f"    ├─ 玩家: {info.player_count}/{info.max_players}")
        print(f"    └─ 延迟: {ping}ms")

    except socket.timeout:
        print(f"{Colors.FAIL}[超时]{Colors.ENDC}")
        print(f"    └─ 原因: 服务器无响应。可能是防火墙阻挡了 UDP 端口 {query_port}，或者查询端口设置错误。")
    except ConnectionRefusedError:
        print(f"{Colors.FAIL}[连接被拒绝]{Colors.ENDC}")
        print(f"    └─ 原因: 端口 {query_port} 上没有运行 A2S 服务。")
    except Exception as e:
        print(f"{Colors.FAIL}[未知错误]{Colors.ENDC}")
        print(f"    └─ 详情: {e}")

def main():
    print(f"{Colors.HEADER}=== A2S 连通性诊断工具 ==={Colors.ENDC}\n")
    
    config = load_config()
    if not config:
        return

    communities = config.get('communities', [])
    if not communities:
        print("config.json 中没有找到 communities 配置。")
        return

    total_servers = 0
    
    for comm in communities:
        print(f"\n{Colors.OKCYAN}>>> 正在扫描社区: {comm.get('name', 'Unknown')} (ID: {comm.get('id')}) <<<{Colors.ENDC}")
        servers = comm.get('servers', [])
        
        if not servers:
            print("  (该社区下无服务器)")
            continue

        for srv in servers:
            check_server(srv)
            total_servers += 1
            time.sleep(0.1) # 稍微停顿一下，防止并发太快看不清

    print(f"\n{Colors.HEADER}=== 诊断结束 (共检测 {total_servers} 个服务器) ==={Colors.ENDC}")

if __name__ == "__main__":
    main()