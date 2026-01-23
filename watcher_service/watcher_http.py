from flask import Flask, jsonify, request
from watcher_targets import list_targets


def create_app(manager, shared_token):
    app = Flask(__name__)

    @app.before_request
    def check_token():
        if request.headers.get('X-Shared-Token') != shared_token:
            return jsonify({"ok": False, "error": "unauthorized"}), 403

    @app.route('/v1/autojoin/join', methods=['POST'])
    def autojoin_join():
        payload = request.get_json(silent=True) or {}
        return jsonify(manager.join(payload.get('steam_id'), payload.get('server_key'), payload.get('queue_type')))

    @app.route('/v1/autojoin/poll')
    def autojoin_poll():
        steam_id = request.args.get('steam_id')
        server_key = request.args.get('server_key')
        return jsonify(manager.poll(steam_id, server_key))

    @app.route('/v1/autojoin/report', methods=['POST'])
    def autojoin_report():
        payload = request.get_json(silent=True) or {}
        return jsonify(manager.report(payload.get('steam_id'), payload.get('ticket_id'), payload.get('result')))

    @app.route('/v1/autojoin/leave', methods=['POST'])
    def autojoin_leave():
        payload = request.get_json(silent=True) or {}
        return jsonify(manager.leave(payload.get('steam_id'), payload.get('server_key')))

    @app.route('/v1/targets')
    def get_targets():
        return jsonify({"ok": True, "targets": list_targets()})

    return app
