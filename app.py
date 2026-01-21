from flask import session, jsonify


def steam_callback():
    # Your existing logic here
    session.modified = True  # Marking the session as modified


def steam_status():
    response = jsonify(status="active")  # Your existing status logic
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response