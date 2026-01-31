import os
import json

# 配置路径
MAPS_DIR = os.path.join('static', 'maps')
TRANS_FILE = 'map_translations.json'

def import_maps():
    print("--- 地图文件名导入工具 ---")
    
    # 1. 获取所有 jpg 文件名（不含后缀）
    if not os.path.exists(MAPS_DIR):
        print(f"[Error] 目录不存在: {MAPS_DIR}")
        return

    map_files = set()
    for f in os.listdir(MAPS_DIR):
        if f.lower().endswith('.jpg'):
            map_name = os.path.splitext(f)[0]
            map_files.add(map_name)
    
    print(f"扫描到 {len(map_files)} 个地图图片。")

    # 2. 读取现有翻译
    current_data = {}
    if os.path.exists(TRANS_FILE):
        try:
            with open(TRANS_FILE, 'r', encoding='utf-8') as f:
                current_data = json.load(f)
        except Exception as e:
            print(f"[Error] 读取 JSON 失败: {e}")
            return

    # 3. 合并
    added_count = 0
    for map_name in map_files:
        if map_name not in current_data:
            current_data[map_name] = "" # 默认留空，等待人工翻译
            added_count += 1
            print(f"[+] 添加新地图: {map_name}")

    # 4. 保存
    if added_count > 0:
        with open(TRANS_FILE, 'w', encoding='utf-8') as f:
            json.dump(current_data, f, indent=4, ensure_ascii=False)
        print(f"\n成功导入 {added_count} 个新地图到 {TRANS_FILE}。")
    else:
        print("\n没有发现新地图，无需更新。")

if __name__ == "__main__":
    import_maps()