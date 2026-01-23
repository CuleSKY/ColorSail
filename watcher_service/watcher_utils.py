import json
import os
import time

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'watcher_config.json')


def now_ts():
    return int(time.time())


def load_config(path=None):
    cfg_path = path or CONFIG_PATH
    with open(cfg_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def make_fast_join_url(game, ip, port):
    appid = 730 if str(game).lower() == 'cs2' else 240
    return f"steam://rungameid/{appid}//+connect%20{ip}:{port}"
