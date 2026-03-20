#!/usr/bin/env python3
"""
Star Office — Memory 瀏覽模組
讀取 agent 的 memory 目錄，提供檔案列表和內容。
"""

import os
from datetime import datetime

OPENCLAW_DIR = os.environ.get("OPENCLAW_DIR") or os.path.join(os.path.expanduser("~"), ".openclaw")
AGENTS_DIR = os.path.join(OPENCLAW_DIR, "agents")


def _get_memory_dir(agent_id):
    """取得 agent 的 memory 目錄路徑（若存在）"""
    memory_dir = os.path.join(AGENTS_DIR, agent_id, "memory")
    if os.path.isdir(memory_dir):
        return memory_dir
    return None


def list_memory_files(agent_id):
    """列出 agent 的 memory 檔案

    Returns: list of {name, size, modified, modified_iso}
    """
    memory_dir = _get_memory_dir(agent_id)
    if not memory_dir:
        return []

    files = []
    for fname in sorted(os.listdir(memory_dir), reverse=True):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(memory_dir, fname)
        try:
            stat = os.stat(fpath)
            files.append({
                "name": fname,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "modifiedIso": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        except Exception:
            continue

    return files


def read_memory_file(agent_id, filename):
    """讀取 memory 檔案內容

    Returns: {content, filename} or None
    """
    # 安全檢查：防止目錄穿越
    if ".." in filename or "/" in filename or "\\" in filename:
        return None

    memory_dir = _get_memory_dir(agent_id)
    if not memory_dir:
        return None

    fpath = os.path.join(memory_dir, filename)
    if not os.path.isfile(fpath):
        return None

    try:
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        return {
            "content": content,
            "filename": filename,
        }
    except Exception:
        return None


def get_latest_memo(agent_id):
    """取得 agent 最新的 memory 檔案（通常是昨天/今天的日記）

    Returns: {date, content, filename} or None
    """
    files = list_memory_files(agent_id)
    if not files:
        return None

    # 最新的檔案（已按名稱倒序排列，日期格式 YYYY-MM-DD.md 正好）
    latest = files[0]
    result = read_memory_file(agent_id, latest["name"])
    if result:
        # 從檔名嘗試提取日期
        date_str = latest["name"].replace(".md", "")
        result["date"] = date_str
    return result
