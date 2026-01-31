import json
import sqlite3
import time
import re

DB_FILE = "stats.db"


def sanitize_autojoin_html(raw_html):
    if not raw_html:
        return ""
    cleaned = re.sub(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", raw_html, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"\son\w+\s*=\s*(['\"]).*?\1", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"javascript:", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def create_autojoin_application(steam_id, html, images):
    created_at = int(time.time())
    payload = json.dumps(images or [], ensure_ascii=False)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        '''
        INSERT INTO autojoin_applications
        (steam_id, html, images_json, status, created_at, reviewed_at, reviewed_by, reject_reason, admin_note)
        VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
        ''',
        (steam_id, html, payload, "pending", created_at),
    )
    conn.commit()
    app_id = c.lastrowid
    conn.close()
    return app_id


def update_autojoin_application_status(app_id, status, reviewed_by, reject_reason=None, admin_note=None):
    reviewed_at = int(time.time())
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        '''
        UPDATE autojoin_applications
        SET status = ?, reviewed_at = ?, reviewed_by = ?, reject_reason = ?, admin_note = ?
        WHERE id = ?
        ''',
        (status, reviewed_at, reviewed_by, reject_reason, admin_note, app_id),
    )
    conn.commit()
    conn.close()


def fetch_autojoin_applications():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        '''
        SELECT id, steam_id, html, images_json, status, created_at, reviewed_at, reviewed_by, reject_reason, admin_note
        FROM autojoin_applications
        ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END, created_at DESC
        '''
    )
    rows = c.fetchall()
    conn.close()
    return rows


def fetch_autojoin_application(app_id):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        '''
        SELECT id, steam_id, html, images_json, status, created_at, reviewed_at, reviewed_by, reject_reason, admin_note
        FROM autojoin_applications
        WHERE id = ?
        ''',
        (app_id,),
    )
    row = c.fetchone()
    conn.close()
    return row


def get_autojoin_enabled(steam_id):
    if not steam_id:
        return False
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM autojoin_applications WHERE steam_id = ? AND status = 'approved' LIMIT 1",
        (steam_id,),
    )
    row = c.fetchone()
    conn.close()
    return bool(row)
