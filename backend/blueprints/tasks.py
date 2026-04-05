"""Task management and task flow API."""

from flask import Blueprint, jsonify, request
from database import get_db, dict_from_row
from datetime import datetime

tasks_bp = Blueprint("tasks", __name__)


def _get_sse_emit():
    """Lazy import to avoid circular dependency with app.py.
    Returns None if sse_emit is not available (e.g. in test mode).
    """
    try:
        from app import sse_emit
        return sse_emit
    except Exception:
        return None


@tasks_bp.route("/tasks", methods=["GET"])
def list_tasks():
    db = get_db()
    status = request.args.get("status")
    agent_id = request.args.get("agent_id")

    query = "SELECT * FROM tasks"
    params = []
    conditions = []

    if status:
        conditions.append("status = ?")
        params.append(status)
    if agent_id:
        conditions.append("assigned_agent_id = ?")
        params.append(agent_id)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY updated_at DESC"

    rows = db.execute(query, params).fetchall()
    tasks = [dict_from_row(r) for r in rows]

    if request.args.get("flows") == "true":
        for task in tasks:
            flow_rows = db.execute(
                "SELECT * FROM task_flows WHERE task_id = ? ORDER BY created_at",
                (task["id"],),
            ).fetchall()
            task["flows"] = [dict_from_row(f) for f in flow_rows]

    return jsonify(tasks)


@tasks_bp.route("/tasks", methods=["POST"])
def create_task():
    data = request.get_json(force=True)
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"ok": False, "msg": "title is required"}), 400

    db = get_db()
    now = datetime.now().isoformat()
    cur = db.execute(
        "INSERT INTO tasks (title, description, status, assigned_agent_id, department_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            title,
            data.get("description", ""),
            data.get("status", "pending"),
            data.get("assigned_agent_id"),
            data.get("department_id"),
            now,
            now,
        ),
    )
    db.commit()
    task_id = cur.lastrowid
    task = dict_from_row(db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())

    emit = _get_sse_emit()
    if emit:
        try:
            emit("task_created", task)
        except Exception:
            pass

    return jsonify({"ok": True, "task": task}), 201


@tasks_bp.route("/tasks/<int:task_id>", methods=["PATCH"])
def update_task(task_id):
    data = request.get_json(force=True)
    db = get_db()

    existing = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not existing:
        return jsonify({"ok": False, "msg": "task not found"}), 404

    allowed_fields = {"title", "description", "status", "assigned_agent_id", "department_id"}
    updates = []
    params = []
    for field in allowed_fields:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])

    if not updates:
        return jsonify({"ok": False, "msg": "no valid fields to update"}), 400

    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(task_id)

    db.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
    db.commit()

    task = dict_from_row(db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())

    emit = _get_sse_emit()
    if emit:
        try:
            emit("task_updated", task)
        except Exception:
            pass

    return jsonify({"ok": True, "task": task})


@tasks_bp.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return jsonify({"ok": True})


@tasks_bp.route("/tasks/<int:task_id>/flows", methods=["GET"])
def list_task_flows(task_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM task_flows WHERE task_id = ? ORDER BY created_at", (task_id,)
    ).fetchall()
    return jsonify([dict_from_row(r) for r in rows])


@tasks_bp.route("/tasks/<int:task_id>/flows", methods=["POST"])
def create_task_flow(task_id):
    data = request.get_json(force=True)
    from_agent = (data.get("from_agent_id") or "").strip()
    to_agent = (data.get("to_agent_id") or "").strip()
    if not from_agent or not to_agent:
        return jsonify({"ok": False, "msg": "from_agent_id and to_agent_id are required"}), 400

    db = get_db()
    existing = db.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not existing:
        return jsonify({"ok": False, "msg": "task not found"}), 404

    cur = db.execute(
        "INSERT INTO task_flows (task_id, from_agent_id, to_agent_id, action, note) VALUES (?, ?, ?, ?, ?)",
        (task_id, from_agent, to_agent, data.get("action", ""), data.get("note", "")),
    )
    db.commit()

    flow = dict_from_row(
        db.execute("SELECT * FROM task_flows WHERE id = ?", (cur.lastrowid,)).fetchone()
    )

    emit = _get_sse_emit()
    if emit:
        try:
            emit("task_flow", flow)
        except Exception:
            pass

    return jsonify({"ok": True, "flow": flow}), 201
