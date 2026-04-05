"""Agent avatar upload and management API."""

from flask import Blueprint, jsonify, request, send_file
from pathlib import Path
import os

avatar_bp = Blueprint("avatar", __name__)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AVATARS_DIR = os.path.join(ROOT_DIR, "assets", "avatars")
PRESETS_DIR = os.path.join(AVATARS_DIR, "presets")
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB

os.makedirs(AVATARS_DIR, exist_ok=True)
os.makedirs(PRESETS_DIR, exist_ok=True)


@avatar_bp.route("/agents/<agent_id>/avatar", methods=["POST"])
def upload_avatar(agent_id):
    if "file" not in request.files:
        return jsonify({"ok": False, "msg": "no file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"ok": False, "msg": "empty filename"}), 400

    data = file.read()
    if len(data) > MAX_AVATAR_SIZE:
        return jsonify({"ok": False, "msg": "file too large (max 2MB)"}), 413

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        return jsonify({"ok": False, "msg": "unsupported file type"}), 400

    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data))
        save_path = os.path.join(AVATARS_DIR, f"{agent_id}.webp")
        img.save(save_path, "WEBP", quality=85)
    except Exception:
        save_path = os.path.join(AVATARS_DIR, f"{agent_id}{ext}")
        with open(save_path, "wb") as f:
            f.write(data)

    return jsonify({"ok": True, "path": f"/api/agents/{agent_id}/avatar"})


@avatar_bp.route("/agents/<agent_id>/avatar", methods=["GET"])
def get_avatar(agent_id):
    for ext in (".webp", ".png", ".jpg", ".jpeg", ".gif"):
        path = os.path.join(AVATARS_DIR, f"{agent_id}{ext}")
        if os.path.exists(path):
            return send_file(path)

    return jsonify({"ok": False, "msg": "avatar not found"}), 404


@avatar_bp.route("/agents/<agent_id>/avatar/preset", methods=["POST"])
def set_preset_avatar(agent_id):
    data = request.get_json(force=True)
    preset_name = (data.get("preset_name") or "").strip()
    if not preset_name:
        return jsonify({"ok": False, "msg": "preset_name is required"}), 400

    if ".." in preset_name or "/" in preset_name or "\\" in preset_name:
        return jsonify({"ok": False, "msg": "invalid preset name"}), 400

    preset_path = None
    for ext in (".webp", ".png", ".jpg"):
        candidate = os.path.join(PRESETS_DIR, f"{preset_name}{ext}")
        if os.path.exists(candidate):
            preset_path = candidate
            break

    if not preset_path:
        return jsonify({"ok": False, "msg": "preset not found"}), 404

    import shutil
    dest_ext = os.path.splitext(preset_path)[1]
    shutil.copy2(preset_path, os.path.join(AVATARS_DIR, f"{agent_id}{dest_ext}"))
    return jsonify({"ok": True})


@avatar_bp.route("/avatars/presets", methods=["GET"])
def list_presets():
    presets = []
    if os.path.isdir(PRESETS_DIR):
        for f in sorted(os.listdir(PRESETS_DIR)):
            name, ext = os.path.splitext(f)
            if ext.lower() in (".png", ".webp", ".jpg", ".jpeg", ".gif"):
                presets.append({"name": name, "file": f})
    return jsonify(presets)
