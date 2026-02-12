import os
import time
from datetime import datetime
from flask import Flask, abort, make_response, redirect, render_template, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from app import (
    STATIC_DIR,
    ADMIN_HOSTNAME,
    _get_cf_access_email,
    check_prime_rate_limit,
    fetch_persona_name,
    get_cached_steam_profile,
    init_db,
    load_prime_users,
    log_prime_audit,
    normalize_host,
    refresh_config_snapshot,
    validate_steam64,
    PRIME_USERS_LOCK,
    PRIME_USERS_META,
    PRIME_USERS_SET,
    _write_prime_users_locked,
)
_ADMIN_INITIALIZED = False


def _ensure_admin_initialized():
    global _ADMIN_INITIALIZED
    if _ADMIN_INITIALIZED:
        return
    init_db()
    refresh_config_snapshot(force=True)
    load_prime_users()
    _ADMIN_INITIALIZED = True


def _get_request_host():
    forwarded_host = request.headers.get('X-Forwarded-Host', '')
    host = forwarded_host or request.headers.get('Host', '')
    if not host:
        return ""
    return host.split(',')[0].strip()


def _admin_host_allowed():
    host = normalize_host(_get_request_host())
    if not host:
        return True
    if host == ADMIN_HOSTNAME:
        return True
    return host in {"localhost", "127.0.0.1"}


def create_admin_app():
    app = Flask(__name__, static_folder=STATIC_DIR)
    secret_key = os.environ.get('APP_SECRET_KEY') or os.environ.get('SECRET_KEY')
    if not secret_key or secret_key == 'change-me':
        raise RuntimeError('APP_SECRET_KEY/SECRET_KEY must be set to a fixed non-default value.')
    app.secret_key = secret_key
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000
    app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_REQUEST_BYTES', 2 * 1024 * 1024))
    app.config['SESSION_COOKIE_SAMESITE'] = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', '').lower() in ('1', 'true', 'yes')

    @app.before_request
    def enforce_admin_host():
        _ensure_admin_initialized()
        if not _admin_host_allowed():
            abort(404)

    @app.route('/')
    def admin_root():
        return redirect(url_for('admin_prime'))

    @app.route('/admin/prime')
    def admin_prime():
        users = []
        with PRIME_USERS_LOCK:
            for entry in PRIME_USERS_META.values():
                added_at = int(entry.get('added_at') or 0)
                users.append({
                    "steam_id": entry.get('steam_id', ''),
                    "persona_name": entry.get('persona_name') or "Unknown",
                    "added_by": entry.get('added_by') or "",
                    "added_at": added_at,
                    "added_at_human": datetime.utcfromtimestamp(added_at).strftime('%Y-%m-%d %H:%M:%S UTC') if added_at else "Unknown"
                })
        users.sort(key=lambda x: x.get('added_at', 0), reverse=True)
        return render_template('admin_prime.html', users=users, csrf_token=session.get('csrf_token', ''))

    @app.route('/admin/prime/add', methods=['POST'])
    def admin_prime_add():
        admin_id = _get_cf_access_email() or "admin"
        if not check_prime_rate_limit(admin_id):
            log_prime_audit("ADD", admin_id, request.form.get('steam_id', ''), "FAIL", "rate_limited")
            return make_response("Too Many Requests", 429)
        target_raw = request.form.get('steam_id', '')
        target_id = validate_steam64(target_raw)
        if not target_id:
            print(f"[Prime] invalid steam64: {target_raw}")
            log_prime_audit("ADD", admin_id, target_raw, "FAIL", "invalid_steam64")
            return make_response("Invalid steam64", 400)

        persona_name = None
        profile = get_cached_steam_profile(target_id)
        if profile:
            persona_name = profile.get('name')
        if not persona_name:
            persona_name = fetch_persona_name(target_id)
        if not persona_name:
            persona_name = "Unknown"

        now = int(time.time())
        with PRIME_USERS_LOCK:
            PRIME_USERS_SET.add(target_id)
            PRIME_USERS_META[target_id] = {
                "steam_id": target_id,
                "persona_name": persona_name,
                "added_by": admin_id,
                "added_at": now
            }
            try:
                _write_prime_users_locked()
            except Exception as e:
                print(f"[Prime] write failed: {e}")
                log_prime_audit("ADD", admin_id, target_id, "FAIL", "write_failed")
                return make_response("Write failed", 500)

        log_prime_audit("ADD", admin_id, target_id, "OK", "added_or_exists")
        return redirect(url_for('admin_prime'))

    @app.route('/admin/prime/remove', methods=['POST'])
    def admin_prime_remove():
        admin_id = _get_cf_access_email() or "admin"
        if not check_prime_rate_limit(admin_id):
            log_prime_audit("REMOVE", admin_id, request.form.get('steam_id', ''), "FAIL", "rate_limited")
            return make_response("Too Many Requests", 429)
        target_raw = request.form.get('steam_id', '')
        target_id = validate_steam64(target_raw)
        if not target_id:
            print(f"[Prime] invalid steam64: {target_raw}")
            log_prime_audit("REMOVE", admin_id, target_raw, "FAIL", "invalid_steam64")
            return make_response("Invalid steam64", 400)
        removed = False
        with PRIME_USERS_LOCK:
            if target_id in PRIME_USERS_SET:
                PRIME_USERS_SET.discard(target_id)
                PRIME_USERS_META.pop(target_id, None)
                removed = True
            try:
                _write_prime_users_locked()
            except Exception as e:
                print(f"[Prime] write failed: {e}")
                log_prime_audit("REMOVE", admin_id, target_id, "FAIL", "write_failed")
                return make_response("Write failed", 500)
        reason = "removed" if removed else "not_found"
        log_prime_audit("REMOVE", admin_id, target_id, "OK", reason)
        return redirect(url_for('admin_prime'))

    return app


app = create_admin_app()
application = app

__all__ = ["app", "application", "create_admin_app"]
