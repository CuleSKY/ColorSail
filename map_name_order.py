import json
import os

# 配置路径
TRANS_FILE = 'map_translations.json'

def sort_translations():
    print(f"--- 正在排序 {TRANS_FILE} ---")

    if not os.path.exists(TRANS_FILE):
        print(f"[Error] 未找到文件: {TRANS_FILE}")
        return

    try:
        # 1. 读取现有文件
        with open(TRANS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        count = len(data)
        print(f"读取到 {count} 条翻译数据。")

        # 2. 排序并写入
        # sort_keys=True 会自动按键名(地图名)的字母顺序排列
        with open(TRANS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False, sort_keys=True)
            
        print(f"✅ 排序完成！已保存回 {TRANS_FILE}")

    except json.JSONDecodeError:
        print("[Error] JSON 格式错误，请检查文件内容是否合法。")
    except Exception as e:
        print(f"[Error] 发生错误: {e}")

if __name__ == "__main__":
    sort_translations()