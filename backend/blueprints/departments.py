"""Department management API."""

from flask import Blueprint, jsonify, request
from database import get_db, dict_from_row

departments_bp = Blueprint("departments", __name__)


@departments_bp.route("/departments", methods=["GET"])
def list_departments():
    db = get_db()
    rows = db.execute("SELECT * FROM departments ORDER BY id").fetchall()
    return jsonify([dict_from_row(r) for r in rows])


@departments_bp.route("/departments", methods=["POST"])
def create_department():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    label = (data.get("label") or "").strip()
    if not name or not label:
        return jsonify({"ok": False, "msg": "name and label are required"}), 400
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO departments (name, label) VALUES (?, ?)", (name, label)
        )
        db.commit()
    except Exception:
        return jsonify({"ok": False, "msg": "department name already exists"}), 409
    return jsonify({"ok": True, "id": cur.lastrowid}), 201


@departments_bp.route("/departments/<int:dept_id>", methods=["DELETE"])
def delete_department(dept_id):
    db = get_db()
    db.execute("DELETE FROM departments WHERE id = ?", (dept_id,))
    db.commit()
    return jsonify({"ok": True})
