from __future__ import annotations

from flask import Flask, jsonify, request


def _require_token(shared_token: str):
    token = request.headers.get("X-Shared-Token")
    if not token or token != shared_token:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    return None


def create_app(manager, shared_token: str) -> Flask:
    app = Flask(__name__)

    @app.route("/v1/autojoin/start", methods=["POST"])
    def autojoin_start():
        denied = _require_token(shared_token)
        if denied:
            return denied
        payload = request.get_json(silent=True) or {}
        steam_id = payload.get("steam_id")
        server_key = payload.get("server_key")
        priority = payload.get("priority") or "none"
        queue_type = payload.get("queue_type") or "normal"
        if not steam_id or not server_key:
            return jsonify({"ok": False, "error": "invalid_request"}), 400
        result = manager.enqueue(steam_id, server_key, priority, queue_type)
        return jsonify(result)

    @app.route("/v1/autojoin/joined", methods=["POST"])
    def autojoin_joined():
        denied = _require_token(shared_token)
        if denied:
            return denied
        payload = request.get_json(silent=True) or {}
        steam_id = payload.get("steam_id")
        queue_id = payload.get("queue_id")
        server_key = payload.get("server_key")
        if not steam_id or not queue_id or not server_key:
            return jsonify({"ok": False, "error": "invalid_request"}), 400
        result = manager.mark_joined(queue_id, steam_id, server_key)
        return jsonify(result)

    @app.route("/v1/autojoin/stop", methods=["POST"])
    def autojoin_stop():
        denied = _require_token(shared_token)
        if denied:
            return denied
        payload = request.get_json(silent=True) or {}
        steam_id = payload.get("steam_id")
        queue_id = payload.get("queue_id")
        server_key = payload.get("server_key")
        if not steam_id or not queue_id or not server_key:
            return jsonify({"ok": False, "error": "invalid_request"}), 400
        result = manager.stop_queue(queue_id, steam_id, server_key)
        return jsonify(result)

    @app.route("/v1/autojoin/status")
    def autojoin_status():
        denied = _require_token(shared_token)
        if denied:
            return denied
        server_key = request.args.get("server_key")
        if not server_key:
            return jsonify({"ok": False, "error": "invalid_request"}), 400
        status = manager.get_status(server_key)
        return jsonify({"ok": True, "status": status})

    return app
