"""Port scanning security API."""

from flask import Blueprint, jsonify, request
from database import get_db, dict_from_row
from datetime import datetime

security_bp = Blueprint("security", __name__)


@security_bp.route("/security/settings", methods=["GET"])
def get_security_settings():
    db = get_db()
    row = db.execute("SELECT * FROM security_settings WHERE id = 1").fetchone()
    if not row:
        return jsonify({})
    result = dict_from_row(row)
    result.pop("prompt_guard_api_key", None)
    return jsonify(result)


@security_bp.route("/security/settings", methods=["PATCH"])
def update_security_settings():
    data = request.get_json(force=True)
    db = get_db()

    allowed = {"port_scan_enabled", "port_scan_interval_hours", "prompt_guard_enabled", "prompt_guard_api_key"}
    updates = []
    params = []
    for field in allowed:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])

    if not updates:
        return jsonify({"ok": False, "msg": "no valid fields"}), 400

    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())

    db.execute(f"UPDATE security_settings SET {', '.join(updates)} WHERE id = 1", params)
    db.commit()

    from services.port_scanner import reschedule_scanner
    try:
        reschedule_scanner()
    except Exception:
        pass

    return jsonify({"ok": True})


@security_bp.route("/security/port-scan/latest", methods=["GET"])
def port_scan_latest():
    db = get_db()
    latest_ts = db.execute(
        "SELECT MAX(scanned_at) as ts FROM port_scan_results"
    ).fetchone()
    if not latest_ts or not latest_ts["ts"]:
        return jsonify([])

    rows = db.execute(
        "SELECT * FROM port_scan_results WHERE scanned_at = ? ORDER BY port",
        (latest_ts["ts"],),
    ).fetchall()
    return jsonify([dict_from_row(r) for r in rows])


@security_bp.route("/security/port-scan/history", methods=["GET"])
def port_scan_history():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM port_scan_results WHERE scanned_at >= datetime('now', '-7 days') ORDER BY scanned_at DESC, port"
    ).fetchall()
    return jsonify([dict_from_row(r) for r in rows])


@security_bp.route("/security/port-scan/trigger", methods=["POST"])
def trigger_port_scan():
    from services.port_scanner import run_scan
    import threading
    t = threading.Thread(target=run_scan, daemon=True)
    t.start()
    return jsonify({"ok": True, "msg": "scan started"})
