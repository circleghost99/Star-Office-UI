#!/usr/bin/env python3
"""
Star Office — Agent 自動偵測模組
從 ~/.openclaw/ 讀取所有 agent 資訊，包括配置、狀態、skills。
"""

import json
import os
import glob
import time
import re
from datetime import datetime


OPENCLAW_DIR = os.environ.get("OPENCLAW_DIR") or os.path.join(os.path.expanduser("~"), ".openclaw")
AGENTS_DIR = os.path.join(OPENCLAW_DIR, "agents")
CONFIG_FILE = os.path.join(OPENCLAW_DIR, "openclaw.json")

# 不在辦公室顯示的 agent
EXCLUDED_AGENTS = {"claude"}

# session 活動判定閾值
ACTIVE_THRESHOLD_SECONDS = 120   # 2 分鐘內有寫入 = 活躍
IDLE_THRESHOLD_SECONDS = 300     # 5 分鐘無更新 = idle


def _load_openclaw_config():
    """載入 openclaw.json，回傳 agent 配置列表"""
    if not os.path.isfile(CONFIG_FILE):
        return []
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        agents_section = data.get("agents", {})
        if isinstance(agents_section, dict):
            return agents_section.get("list", [])
        if isinstance(agents_section, list):
            return agents_section
    except Exception:
        pass
    return []


def _parse_bootstrap(agent_dir):
    """從 BOOTSTRAP.md 提取角色描述"""
    bootstrap = os.path.join(agent_dir, "BOOTSTRAP.md")
    if not os.path.isfile(bootstrap):
        return None
    try:
        with open(bootstrap, "r", encoding="utf-8") as f:
            content = f.read(2000)  # 只讀前 2KB
        # 嘗試提取第一段描述
        lines = [l.strip() for l in content.split("\n") if l.strip() and not l.startswith("#")]
        return lines[0] if lines else None
    except Exception:
        return None


def _detect_activity(agent_dir):
    """偵測 agent 的活動狀態

    Returns: (state, detail, last_active_iso)
    """
    sessions_dir = os.path.join(agent_dir, "sessions")
    if not os.path.isdir(sessions_dir):
        return "idle", "無活躍 session", None

    session_files = glob.glob(os.path.join(sessions_dir, "*.jsonl"))
    if not session_files:
        return "idle", "無活躍 session", None

    now = time.time()
    latest_mtime = 0
    latest_file = None

    for sf in session_files:
        try:
            mtime = os.path.getmtime(sf)
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_file = sf
        except Exception:
            continue

    if latest_file is None:
        return "idle", "無活躍 session", None

    last_active = datetime.fromtimestamp(latest_mtime).isoformat()
    age = now - latest_mtime

    if age < ACTIVE_THRESHOLD_SECONDS:
        detail = _extract_session_detail(latest_file) or "工作中"
        return "writing", detail, last_active
    elif age < IDLE_THRESHOLD_SECONDS:
        mins = int(age / 60)
        return "idle", f"最近活動 {mins} 分鐘前", last_active
    else:
        return "idle", "待命中", last_active


def _extract_session_detail(session_file):
    """從 session jsonl 最後幾行嘗試提取工作描述"""
    try:
        with open(session_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in reversed(lines[-5:]):
            try:
                entry = json.loads(line.strip())
                role = entry.get("role", "")
                content = entry.get("content", "")
                if role == "assistant" and isinstance(content, str) and len(content) > 5:
                    return content.strip().replace("\n", " ")[:30]
            except Exception:
                continue
    except Exception:
        pass
    return None


def _has_memory(agent_id):
    """檢查 agent 是否有 memory 目錄"""
    memory_dir = os.path.join(AGENTS_DIR, agent_id, "memory")
    if not os.path.isdir(memory_dir):
        return False
    return any(f.endswith(".md") for f in os.listdir(memory_dir))


def discover_all_agents():
    """發現所有 agent，回傳完整資訊列表

    合併三個資料來源：
    1. ~/.openclaw/agents/ 目錄（實際存在的 agent）
    2. openclaw.json 配置（名稱、model、skills）
    3. BOOTSTRAP.md（角色描述）
    """
    # 從 openclaw.json 建立 id → config 的映射
    config_list = _load_openclaw_config()
    config_map = {}
    for cfg in config_list:
        if isinstance(cfg, dict):
            agent_id = cfg.get("id", "")
            if agent_id:
                config_map[agent_id] = cfg

    # 掃描 agents 目錄
    agents = []
    if not os.path.isdir(AGENTS_DIR):
        return agents

    for dirname in sorted(os.listdir(AGENTS_DIR)):
        agent_dir = os.path.join(AGENTS_DIR, dirname)
        if not os.path.isdir(agent_dir) or dirname.startswith(".") or dirname in EXCLUDED_AGENTS:
            continue

        # 合併配置
        cfg = config_map.get(dirname, {})
        config_name = cfg.get("name", "")
        config_skills = cfg.get("skills", [])

        # 取得 model
        model_cfg = cfg.get("model", {})
        primary_model = ""
        if isinstance(model_cfg, dict):
            primary_model = model_cfg.get("primary", "")
        elif isinstance(model_cfg, str):
            primary_model = model_cfg

        # 偵測活動
        state, detail, last_active = _detect_activity(agent_dir)

        # 讀取 BOOTSTRAP.md
        bootstrap_desc = _parse_bootstrap(agent_dir)

        agent_info = {
            "id": dirname,
            "displayName": config_name or dirname,
            "role": bootstrap_desc or "",
            "model": primary_model,
            "state": state,
            "detail": detail,
            "skills": config_skills,
            "hasMemory": _has_memory(dirname),
            "lastActive": last_active,
            "isMain": dirname == "main",
        }
        agents.append(agent_info)

    return agents


def get_agent_status(agent_id):
    """取得單一 agent 的即時狀態"""
    agent_dir = os.path.join(AGENTS_DIR, agent_id)
    if not os.path.isdir(agent_dir):
        return None

    state, detail, last_active = _detect_activity(agent_dir)
    return {
        "id": agent_id,
        "state": state,
        "detail": detail,
        "lastActive": last_active,
    }
