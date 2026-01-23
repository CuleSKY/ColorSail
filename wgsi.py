# wsgi.py
from app import app, init_db, load_config, load_prime_users, refresh_local_caches, update_all_data, flush_map_translations, start_scheduler

_BOOTSTRAPPED = False

def bootstrap():
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    _BOOTSTRAPPED = True

    init_db()
    load_config()
    load_prime_users()
    refresh_local_caches()
    update_all_data()
    flush_map_translations(force=True)
    start_scheduler()

bootstrap()

# 给 gunicorn 用
application = app
