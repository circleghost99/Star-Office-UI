"""Workspace ZIP export API."""

from flask import Blueprint, jsonify, send_file
import os
import zipfile
import tempfile

workspace_export_bp = Blueprint("workspace_export", __name__)

OPENCLAW_DIR = os.environ.get("OPENCLAW_DIR") or os.path.join(os.path.expanduser("~"), ".openclaw")

EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".cache"}
EXCLUDE_EXTS = {".pyc", ".pyo"}


@workspace_export_bp.route("/agents/<agent_id>/workspace/download", methods=["POST"])
def download_workspace(agent_id):
    if ".." in agent_id or "/" in agent_id or "\\" in agent_id:
        return jsonify({"ok": False, "msg": "invalid agent_id"}), 400

    workspace_path = os.path.join(OPENCLAW_DIR, "agents", agent_id)
    if not os.path.isdir(workspace_path):
        return jsonify({"ok": False, "msg": "agent workspace not found"}), 404

    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    try:
        with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(workspace_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for f in files:
                    _, ext = os.path.splitext(f)
                    if ext.lower() in EXCLUDE_EXTS:
                        continue
                    full_path = os.path.join(root, f)
                    arc_name = os.path.relpath(full_path, workspace_path)
                    try:
                        zf.write(full_path, arc_name)
                    except (PermissionError, OSError):
                        continue

        return send_file(
            tmp.name,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"{agent_id}-workspace.zip",
        )
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
