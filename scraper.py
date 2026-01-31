import os
import time
import random
import requests
import re
from bs4 import BeautifulSoup

# --- 配置 ---
# 图片保存目录
SAVE_DIR = os.path.join('static', 'maps')
# 搜索关键词
SEARCH_TERM = "ze_"
# 爬取最大页数 (设为 None 则爬完为止，建议先设个 50 页试试)
MAX_PAGES = 50 
# Steam 创意工坊 CS2 (AppID 730) 搜索 URL
BASE_URL = "https://steamcommunity.com/workshop/browse/"

# 伪装浏览器头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://steamcommunity.com/app/730/workshop/'
}

def sanitize_filename(name):
    """去除文件名中的非法字符"""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def download_image(url, filename):
    path = os.path.join(SAVE_DIR, filename)
    if os.path.exists(path):
        print(f"[Skip] 已存在: {filename}")
        return

    try:
        # 图片下载稍微快一点没关系，但也要注意
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            with open(path, 'wb') as f:
                f.write(resp.content)
            print(f"[Download] 成功: {filename}")
        else:
            print(f"[Error] 图片下载失败 {resp.status_code}: {url}")
    except Exception as e:
        print(f"[Error] 下载异常: {e}")

def scrape():
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)
        print(f"创建目录: {SAVE_DIR}")

    page = 1
    while True:
        if MAX_PAGES and page > MAX_PAGES:
            print("达到最大页数限制，停止。")
            break

        print(f"\n--- 正在爬取第 {page} 页 ---")
        
        # 构造参数: textmatch 保证标题匹配度
        params = {
            "appid": "730",
            "searchtext": SEARCH_TERM,
            "childpublishedfileid": "0",
            "browsesort": "textmatch", 
            "section": "readytouseitems",
            "p": page
        }

        try:
            resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"页面请求失败: {resp.status_code}")
                break

            soup = BeautifulSoup(resp.text, 'html.parser')
            items = soup.find_all('div', class_='workshopItem')

            if not items:
                print("本页没有找到物品，可能已到达末尾。")
                break

            for item in items:
                # 1. 获取标题 (作为文件名)
                title_div = item.find('div', class_='workshopItemTitle')
                if not title_div: continue
                title = title_div.get_text(strip=True)
                
                # 2. 简单的过滤：只下载包含 ze_ 的 (防止搜出来 unrelated)
                if "ze_" not in title.lower():
                    continue

                # 3. 获取图片链接
                img_tag = item.find('img', class_='workshopItemPreviewImage')
                if img_tag:
                    img_url = img_tag.get('src')
                    # 有些图片 URL 没有协议头
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url
                    
                    filename = sanitize_filename(title) + ".jpg"
                    download_image(img_url, filename)

            # --- 温和等待 ---
            # 随机休眠 2-5 秒，防止封 IP
            sleep_time = random.uniform(2, 5)
            print(f"第 {page} 页完成，休息 {sleep_time:.2f} 秒...")
            time.sleep(sleep_time)

            page += 1

        except Exception as e:
            print(f"爬取中断: {e}")
            break

if __name__ == "__main__":
    print("开始 Steam 创意工坊爬虫 (Target: ze_ maps)...")
    print("按 Ctrl+C 随时停止")
    try:
        scrape()
    except KeyboardInterrupt:
        print("\n用户手动停止。")