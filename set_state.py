#!/usr/bin/env python3
"""Update Star Office UI state (for testing or agent-driven sync).

For automatic state sync from OpenClaw: add a rule in your agent SOUL.md or AGENTS.md:
  Before starting a task: run `python3 set_state.py writing "doing XYZ"`.
  After finishing: run `python3 set_state.py idle "ready"`.
The office UI reads state from the same state.json this script writes.
"""

import json
import os
import sys
from datetime import datetime

STATE_FILE = os.environ.get(
    "STAR_OFFICE_STATE_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json"),
)

VALID_STATES = [
    "idle",
    "writing",
    "receiving",
    "replying",
    "researching",
    "executing",
    "syncing",
    "error"
]

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # If the file contains a list, find the main state or the first element
            if isinstance(data, list):
                if len(data) > 0:
                    return data[0]
                else:
                    return {
                        "state": "idle",
                        "detail": "待命中...",
                        "progress": 0,
                        "updated_at": datetime.now().isoformat()
                    }
            return data
    return {
        "state": "idle",
        "detail": "待命中...",
        "progress": 0,
        "updated_at": datetime.now().isoformat()
    }

def save_state(state):
    # If the file exists and is a list, update the first element or append
    current_data = None
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                current_data = json.load(f)
        except Exception:
            pass

    if isinstance(current_data, list):
        if len(current_data) > 0:
            current_data[0].update(state)
        else:
            current_data.append(state)
        output_data = current_data
    else:
        output_data = state

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python set_state.py <state> [detail]")
        print(f"状态选项: {', '.join(VALID_STATES)}")
        print("\n例子:")
        print("  python set_state.py idle")
        print("  python set_state.py researching \"在查 Godot MCP...\"")
        print("  python set_state.py writing \"在写热点日报模板...\"")
        sys.exit(1)
    
    state_name = sys.argv[1]
    detail = sys.argv[2] if len(sys.argv) > 2 else ""
    
    if state_name not in VALID_STATES:
        print(f"无效状态: {state_name}")
        print(f"有效选项: {', '.join(VALID_STATES)}")
        sys.exit(1)
    
    state = load_state()
    state["state"] = state_name
    state["detail"] = detail
    state["updated_at"] = datetime.now().isoformat()
    
    save_state(state)
    print(f"状态已更新: {state_name} - {detail}")
