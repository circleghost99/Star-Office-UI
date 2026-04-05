"""Office layout save/load API."""

from flask import Blueprint, jsonify, request
from database import get_db
from datetime import datetime
import json

office_layout_bp = Blueprint("office_layout", __name__)


@office_layout_bp.route("/office/layout", methods=["GET"])
def get_layout():
    db = get_db()
    row = db.execute("SELECT layout_data FROM office_layout WHERE id = 1").fetchone()
    if not row:
        return jsonify({})
    try:
        return jsonify(json.loads(row["layout_data"]))
    except (json.JSONDecodeError, TypeError):
        return jsonify({})


@office_layout_bp.route("/office/layout", methods=["POST"])
def save_layout():
    data = request.get_json(force=True)
    layout_json = json.dumps(data, ensure_ascii=False)
    db = get_db()
    db.execute(
        """INSERT INTO office_layout (id, layout_data, updated_at) VALUES (1, ?, ?)
           ON CONFLICT(id) DO UPDATE SET layout_data = excluded.layout_data, updated_at = excluded.updated_at""",
        (layout_json, datetime.now().isoformat()),
    )
    db.commit()
    return jsonify({"ok": True})
