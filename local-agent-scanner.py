#!/usr/bin/env python3
"""
Star Office — 本地 Agent 活動掃描器
自動偵測 ~/.openclaw/agents/ 下所有 agent 的活動狀態，
並透過 Star Office API 註冊為訪客。

用法：
  python3 local-agent-scanner.py          # 前台執行
  python3 local-agent-scanner.py --daemon # 背景掃描模式
"""

import json
import os
import sys
import time
import glob
from datetime import datetime

# === 設定 ===
OPENCLAW_DIR = os.path.expanduser("~/.openclaw")
AGENTS_DIR = os.path.join(OPENCLAW_DIR, "agents")
OFFICE_URL = os.environ.get("STAR_OFFICE_URL", "http://127.0.0.1:19000")
JOIN_KEY = os.environ.get("STAR_OFFICE_JOIN_KEY", "ocj_example_team_01")
SCAN_INTERVAL = int(os.environ.get("STAR_OFFICE_SCAN_INTERVAL", "20"))

# Agent 活動判定：session 檔案在 N 秒內有更新 → 視為活躍
ACTIVE_THRESHOLD_SECONDS = 120  # 2 分鐘內有寫入 = 活躍
IDLE_THRESHOLD_SECONDS = 300    # 5 分鐘無更新 = idle

# 排除的 agent（不需要在 Office 裡顯示）
EXCLUDED_AGENTS = {"main", "claude"}

# Agent 顯示名稱對照表（可自訂）
AGENT_DISPLAY_NAMES = {
    "lobster-support": "🦞 龍蝦工程師",
    "hamster-editor": "🐹 倉鼠編輯",
    "hamster-writer": "🐹 倉鼠寫手",
    "hamster-collector": "🐹 倉鼠採集",
    "lily-pm": "🌸 Lily PM",
    "chief-designer": "🎨 首席設計",
    "data-janitor": "🧹 資料清潔工",
    "family-group": "👨‍👩‍👧 家庭群組",
    "finance-cfo": "💰 財務長",
    "skill-optimizer": "⚡ 技能優化",
    "workflow-optimizer": "🔧 工作流優化",
}

# 已註冊的 agent 快取
_registered_agents = {}  # agent_name -> {"agentId": ..., "last_state": ...}
_STATE_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "local-scanner-state.json"
)


def _load_cache():
    global _registered_agents
    if os.path.exists(_STATE_CACHE_FILE):
        try:
            with open(_STATE_CACHE_FILE, "r") as f:
                _registered_agents = json.load(f)
        except Exception:
            _registered_agents = {}


def _save_cache():
    try:
        with open(_STATE_CACHE_FILE, "w") as f:
            json.dump(_registered_agents, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def discover_agents():
    """掃描 ~/.openclaw/agents/ 目錄，回傳 agent 名稱列表"""
    if not os.path.isdir(AGENTS_DIR):
        return []
    agents = []
    for d in sorted(os.listdir(AGENTS_DIR)):
        full = os.path.join(AGENTS_DIR, d)
        if os.path.isdir(full) and d not in EXCLUDED_AGENTS and not d.startswith("."):
            agents.append(d)
    return agents


def detect_agent_activity(agent_name):
    """偵測 agent 的活動狀態
    
    回傳: (state, detail)
    - "writing" + detail  → 有活躍 session
    - "idle" + detail     → 無活躍 session
    """
    agent_dir = os.path.join(AGENTS_DIR, agent_name)
    sessions_dir = os.path.join(agent_dir, "sessions")
    
    # 找所有 session 檔案
    session_files = []
    if os.path.isdir(sessions_dir):
        session_files = glob.glob(os.path.join(sessions_dir, "*.jsonl"))
    
    if not session_files:
        return "idle", "無活躍 session"
    
    # 找最近修改的 session
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
        return "idle", "無活躍 session"
    
    age = now - latest_mtime
    
    if age < ACTIVE_THRESHOLD_SECONDS:
        # 嘗試讀取最後一行取得更具體的狀態
        detail = _extract_session_detail(latest_file)
        return "writing", detail or "工作中"
    elif age < IDLE_THRESHOLD_SECONDS:
        mins = int(age / 60)
        return "idle", f"最近活動 {mins} 分鐘前"
    else:
        return "idle", "待命中"


def _extract_session_detail(session_file):
    """從 session jsonl 最後幾行嘗試提取工作描述"""
    try:
        with open(session_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # 讀最後 3 行，找 assistant 的回應
        for line in reversed(lines[-5:]):
            try:
                entry = json.loads(line.strip())
                role = entry.get("role", "")
                content = entry.get("content", "")
                if role == "assistant" and isinstance(content, str) and len(content) > 5:
                    # 截取前 30 字作為 detail
                    clean = content.strip().replace("\n", " ")[:30]
                    return clean
            except Exception:
                continue
    except Exception:
        pass
    return None


def join_agent(agent_name, state="idle", detail=""):
    """註冊 agent 為 Star Office 訪客"""
    import urllib.request
    import urllib.error
    
    display_name = AGENT_DISPLAY_NAMES.get(agent_name, agent_name)
    payload = json.dumps({
        "name": display_name,
        "joinKey": JOIN_KEY,
        "state": state,
        "detail": detail
    }).encode("utf-8")
    
    req = urllib.request.Request(
        f"{OFFICE_URL}/join-agent",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("utf-8"))
        if data.get("ok"):
            agent_id = data.get("agentId")
            _registered_agents[agent_name] = {
                "agentId": agent_id,
                "last_state": state,
                "display_name": display_name
            }
            _save_cache()
            print(f"  ✅ {display_name} 已加入辦公室 (id={agent_id})")
            return True
        else:
            print(f"  ⚠️  {display_name} 加入失敗: {data.get('msg', '?')}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        # 429 = 超出並發限制，不是嚴重錯誤
        if e.code == 429:
            print(f"  ⏳ {display_name} 併發限制，稍後重試")
        else:
            print(f"  ❌ {display_name} 加入失敗 (HTTP {e.code}): {body[:100]}")
    except Exception as e:
        print(f"  ❌ {display_name} 加入異常: {e}")
    return False


def push_state(agent_name, state, detail):
    """推送 agent 狀態到 Star Office"""
    import urllib.request
    import urllib.error
    
    cached = _registered_agents.get(agent_name, {})
    agent_id = cached.get("agentId")
    display_name = cached.get("display_name", agent_name)
    
    if not agent_id:
        # 需要先 join
        return join_agent(agent_name, state, detail)
    
    payload = json.dumps({
        "agentId": agent_id,
        "joinKey": JOIN_KEY,
        "state": state,
        "detail": detail,
        "name": display_name
    }).encode("utf-8")
    
    req = urllib.request.Request(
        f"{OFFICE_URL}/agent-push",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("utf-8"))
        if data.get("ok"):
            area = data.get("area", "breakroom")
            _registered_agents[agent_name]["last_state"] = state
            _save_cache()
            return True
        else:
            print(f"  ⚠️  {display_name} 推送失敗: {data.get('msg', '?')}")
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):
            # 已被移出或 key 過期，重新 join
            print(f"  🔄 {display_name} 需要重新加入")
            del _registered_agents[agent_name]
            _save_cache()
            return join_agent(agent_name, state, detail)
        print(f"  ❌ {display_name} 推送失敗 (HTTP {e.code})")
    except Exception as e:
        print(f"  ❌ {display_name} 推送異常: {e}")
    return False


def scan_and_push():
    """執行一輪掃描 + 推送
    
    只讓正在工作的 agent 出現在辦公室。
    - 活躍 agent → 推送工作狀態（出現在場景中）
    - 剛變 idle 的 agent → 推送 idle（讓角色走回休息區，隨後會被 offline 機制移除）
    - 一直 idle 的 agent → 不推送（不出現在場景中）
    """
    agents = discover_agents()
    if not agents:
        return

    active_count = 0
    for agent_name in agents:
        state, detail = detect_agent_activity(agent_name)
        cached = _registered_agents.get(agent_name, {})
        was_active = cached.get("last_state") not in (None, "idle")

        if state != "idle":
            # 正在工作 → 推送（會自動 join 如果還沒註冊）
            push_state(agent_name, state, detail)
            active_count += 1
        elif was_active:
            # 剛從工作變 idle → 推送一次 idle，讓角色離場
            push_state(agent_name, "idle", "工作完成，離開辦公室")
        # else: 一直 idle → 不推送，不佔場景空間

    return active_count


def main():
    daemon_mode = "--daemon" in sys.argv
    force_mode = "--force" in sys.argv

    print("🏢 Star Office — 本地 Agent 掃描器")
    print(f"   掃描目錄: {AGENTS_DIR}")
    print(f"   Office URL: {OFFICE_URL}")
    print(f"   Join Key: {JOIN_KEY}")
    print(f"   掃描間隔: {SCAN_INTERVAL}秒")
    print(f"   排除: {', '.join(EXCLUDED_AGENTS)}")
    print()

    _load_cache()

    # --force: 清除舊快取，強制所有 agent 重新 join
    if force_mode:
        global _registered_agents
        _registered_agents = {}
        _save_cache()
        print("🔄 已清除快取，所有 agent 將重新加入")

    agents = discover_agents()
    print(f"🔎 發現 {len(agents)} 個 agent: {', '.join(agents)}")
    print()

    if not daemon_mode:
        # 單次掃描
        print("--- 執行一次掃描 ---")
        active = scan_and_push()
        print(f"\n✅ 掃描完成，{active or 0} 個 agent 活躍中")
        return

    # Daemon 模式
    print("🚀 啟動持續掃描模式（Ctrl+C 停止）")
    try:
        while True:
            try:
                ts = datetime.now().strftime("%H:%M:%S")
                active = scan_and_push()
                if active:
                    print(f"[{ts}] 掃描完成，{active} 個 agent 活躍")
            except Exception as e:
                print(f"⚠️  掃描異常: {e}")
            time.sleep(SCAN_INTERVAL)
    except KeyboardInterrupt:
        print("\n👋 掃描器已停止")


if __name__ == "__main__":
    main()

