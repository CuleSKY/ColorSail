import json
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
from modules.autojoin_store import (
    fetch_autojoin_application,
    fetch_autojoin_applications,
    sanitize_autojoin_html,
    update_autojoin_application_status,
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
    app.secret_key = os.environ.get('APP_SECRET_KEY') or os.environ.get('SECRET_KEY') or 'change-me'
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
        return admin_applications()

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

    @app.route('/admin/applications')
    def admin_applications():
        applications = []
        for row in fetch_autojoin_applications():
            created_at = int(row['created_at'] or 0)
            reviewed_at = int(row['reviewed_at'] or 0) if row['reviewed_at'] else 0
            applications.append({
                "id": row['id'],
                "steam_id": row['steam_id'] or "",
                "status": row['status'] or "pending",
                "created_at": created_at,
                "created_at_human": datetime.utcfromtimestamp(created_at).strftime('%Y-%m-%d %H:%M:%S UTC') if created_at else "Unknown",
                "reviewed_at_human": datetime.utcfromtimestamp(reviewed_at).strftime('%Y-%m-%d %H:%M:%S UTC') if reviewed_at else "",
            })
        return render_template('admin_applications.html', applications=applications)

    @app.route('/admin/applications/<int:app_id>')
    def admin_application_detail(app_id):
        row = fetch_autojoin_application(app_id)
        if not row:
            abort(404)
        images = []
        try:
            images = json.loads(row['images_json'] or "[]")
        except Exception:
            images = []
        sanitized_html = sanitize_autojoin_html(row['html'] or "")
        created_at = int(row['created_at'] or 0)
        reviewed_at = int(row['reviewed_at'] or 0) if row['reviewed_at'] else 0
        application = {
            "id": row['id'],
            "steam_id": row['steam_id'] or "",
            "status": row['status'] or "pending",
            "html": sanitized_html,
            "images": images,
            "created_at_human": datetime.utcfromtimestamp(created_at).strftime('%Y-%m-%d %H:%M:%S UTC') if created_at else "Unknown",
            "reviewed_at_human": datetime.utcfromtimestamp(reviewed_at).strftime('%Y-%m-%d %H:%M:%S UTC') if reviewed_at else "",
            "reviewed_by": row['reviewed_by'] or "",
            "reject_reason": row['reject_reason'] or "",
            "admin_note": row['admin_note'] or "",
        }
        return render_template('admin_application_detail.html', application=application)

    @app.route('/admin/applications/<int:app_id>/approve', methods=['POST'])
    def admin_application_approve(app_id):
        reviewed_by = _get_cf_access_email() or "admin"
        update_autojoin_application_status(app_id, "approved", reviewed_by)
        return redirect(url_for('admin_application_detail', app_id=app_id))

    @app.route('/admin/applications/<int:app_id>/reject', methods=['POST'])
    def admin_application_reject(app_id):
        reviewed_by = _get_cf_access_email() or "admin"
        reason = request.form.get('reject_reason', '').strip()
        note = request.form.get('admin_note', '').strip()
        if not reason:
            return make_response("Reject reason required", 400)
        update_autojoin_application_status(app_id, "rejected", reviewed_by, reject_reason=reason, admin_note=note)
        return redirect(url_for('admin_application_detail', app_id=app_id))

    return app


app = create_admin_app()
application = app

__all__ = ["app", "application", "create_admin_app"]
