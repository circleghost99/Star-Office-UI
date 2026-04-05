"""Cost & Engagement Dashboard API."""

from flask import Blueprint, jsonify, request
from database import get_db, dict_from_row
from datetime import datetime

cost_dashboard_bp = Blueprint("cost_dashboard", __name__)


@cost_dashboard_bp.route("/cost-dashboard", methods=["GET"])
def cost_dashboard():
    db = get_db()
    month = request.args.get("month")
    if month:
        like_pattern = f"{month}%"
    else:
        like_pattern = datetime.now().strftime("%Y-%m") + "%"

    rows = db.execute(
        """SELECT agent_id,
                  SUM(input_tokens) as total_input,
                  SUM(output_tokens) as total_output,
                  SUM(cache_read_tokens) as total_cache,
                  SUM(total_tokens) as total_tokens,
                  ROUND(SUM(cost_usd), 4) as total_cost
           FROM token_usage_log
           WHERE logged_at LIKE ?
           GROUP BY agent_id
           ORDER BY total_cost DESC""",
        (like_pattern,),
    ).fetchall()

    agents = [dict_from_row(r) for r in rows]
    grand_total = sum(a["total_cost"] or 0 for a in agents)

    return jsonify({
        "month": like_pattern.rstrip("%"),
        "agents": agents,
        "grand_total_cost": round(grand_total, 4),
        "grand_total_tokens": sum(a["total_tokens"] or 0 for a in agents),
    })


@cost_dashboard_bp.route("/engagement-dashboard", methods=["GET"])
def engagement_dashboard():
    db = get_db()
    rows = db.execute(
        """SELECT agent_id, date, conversations, word_count, token_usage,
                  errors, praises, task_completions
           FROM agent_daily_stats
           WHERE date >= date('now', '-7 days')
           ORDER BY date DESC, agent_id"""
    ).fetchall()
    return jsonify([dict_from_row(r) for r in rows])


@cost_dashboard_bp.route("/token-usage", methods=["POST"])
def log_token_usage():
    data = request.get_json(force=True)
    agent_id = (data.get("agent_id") or "").strip()
    if not agent_id:
        return jsonify({"ok": False, "msg": "agent_id is required"}), 400

    db = get_db()
    db.execute(
        """INSERT INTO token_usage_log
           (agent_id, input_tokens, output_tokens, cache_read_tokens, total_tokens, cost_usd, model)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            agent_id,
            data.get("input_tokens", 0),
            data.get("output_tokens", 0),
            data.get("cache_read_tokens", 0),
            data.get("total_tokens", 0),
            data.get("cost_usd", 0.0),
            data.get("model", ""),
        ),
    )
    db.commit()
    return jsonify({"ok": True}), 201


@cost_dashboard_bp.route("/engagement-increment", methods=["POST"])
def engagement_increment():
    data = request.get_json(force=True)
    agent_id = (data.get("agent_id") or "").strip()
    if not agent_id:
        return jsonify({"ok": False, "msg": "agent_id is required"}), 400

    today = datetime.now().strftime("%Y-%m-%d")
    db = get_db()

    db.execute(
        """INSERT INTO agent_daily_stats (agent_id, date) VALUES (?, ?)
           ON CONFLICT(agent_id, date) DO NOTHING""",
        (agent_id, today),
    )

    valid_fields = {"conversations", "word_count", "token_usage", "errors", "praises", "task_completions"}
    for field in valid_fields:
        amount = data.get(field)
        if amount and isinstance(amount, (int, float)) and amount > 0:
            db.execute(
                f"UPDATE agent_daily_stats SET {field} = {field} + ? WHERE agent_id = ? AND date = ?",
                (int(amount), agent_id, today),
            )

    db.commit()
    return jsonify({"ok": True})
