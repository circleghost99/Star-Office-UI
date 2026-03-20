#!/usr/bin/env python3
"""
Star Office — Agent 像素精靈圖產生器
用 nano-banana-pro (Gemini Image) 為每個 OpenClaw agent 產生專屬精靈圖。

Usage:
    python3 scripts/generate-sprites.py                       # 產生所有 agent
    python3 scripts/generate-sprites.py --agent lobster-support  # 只產生指定 agent
    python3 scripts/generate-sprites.py --dry-run             # 預覽 prompt 不實際產生
    python3 scripts/generate-sprites.py --style "cyberpunk"   # 自訂風格
    python3 scripts/generate-sprites.py --list                # 列出所有 agent
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── 路徑 ──
OPENCLAW_DIR = Path.home() / ".openclaw"
OPENCLAW_JSON = OPENCLAW_DIR / "openclaw.json"
SKILL_SCRIPT = OPENCLAW_DIR / "skills" / "nano-banana-pro" / "scripts" / "generate_image.py"
PROJECT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"
OUTPUT_DIR = PROJECT_DIR / "generated-sprites"
BACKUP_DIR = OUTPUT_DIR / "backups"

# ── 精靈表規格 ──
FRAME_SIZE = 32          # 每幀 32×32 px
GRID_COLS = 4            # 4 列
GRID_ROWS = 2            # 2 行
SHEET_W = FRAME_SIZE * GRID_COLS   # 128 px
SHEET_H = FRAME_SIZE * GRID_ROWS   # 64 px

# ── Agent 角色設定（可自訂） ──
AGENT_PERSONAS = {
    "lobster-support":   {"animal": "lobster",  "color": "red",       "accessory": "captain hat"},
    "hamster-collector": {"animal": "hamster",  "color": "orange",    "accessory": "explorer backpack"},
    "hamster-editor":    {"animal": "hamster",  "color": "brown",     "accessory": "reading glasses and book"},
    "hamster-writer":    {"animal": "hamster",  "color": "golden",    "accessory": "quill pen"},
    "chief-designer":    {"animal": "cat",      "color": "white",     "accessory": "beret and paintbrush"},
    "data-janitor":      {"animal": "raccoon",  "color": "gray",      "accessory": "broom and bucket"},
    "family-group":      {"animal": "puppy",    "color": "cream",     "accessory": "bow tie"},
    "finance-cfo":       {"animal": "owl",      "color": "teal",      "accessory": "monocle and calculator"},
    "lily-pm":           {"animal": "bunny",    "color": "pink",      "accessory": "clipboard"},
    "main":              {"animal": "cat",      "color": "orange tabby", "accessory": "headphones"},
    "skill-optimizer":   {"animal": "fox",      "color": "amber",     "accessory": "wrench and gears"},
    "workflow-optimizer": {"animal": "beaver",  "color": "brown",     "accessory": "hard hat"},
}

DEFAULT_PERSONA = {"animal": "robot", "color": "blue", "accessory": "antenna"}


def load_agents():
    """從 agent_discovery 模組讀取所有 agent"""
    sys.path.insert(0, str(PROJECT_DIR / "backend"))
    try:
        from agent_discovery import discover_all_agents
        agents = discover_all_agents()
        return [{"id": a["id"], "name": a["displayName"]} for a in agents]
    except Exception as e:
        print(f"❌ 載入 agent 失敗: {e}")
        sys.exit(1)


def build_prompt(agent_id, display_name, style=""):
    """為 agent 產生圖像 prompt"""
    persona = AGENT_PERSONAS.get(agent_id, DEFAULT_PERSONA)
    animal = persona["animal"]
    color = persona["color"]
    accessory = persona["accessory"]

    style_str = style if style else "cute cozy warm-toned"

    return (
        f"pixel art character, 32x32 sprite, {color} {animal} character, "
        f"{accessory}, {style_str} style, "
        f"single character centered on transparent background, "
        f"front-facing idle pose, cute chibi proportions, "
        f"clean crisp pixel outlines, limited retro color palette, "
        f"game sprite asset, no text, no watermark"
    )


def generate_single_image(prompt, output_path):
    """呼叫 nano-banana-pro 產生單一圖像"""
    if not SKILL_SCRIPT.exists():
        print(f"❌ 找不到 nano-banana-pro: {SKILL_SCRIPT}")
        sys.exit(1)

    cmd = [
        "uv", "run", str(SKILL_SCRIPT),
        "--prompt", prompt,
        "--filename", str(output_path),
        "--resolution", "1K",
        "--aspect-ratio", "1:1",
    ]

    print(f"   🍌 呼叫 nano-banana-pro...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        print(f"   ❌ 產生失敗: {result.stderr[:200]}")
        return False

    if output_path.exists():
        print(f"   ✅ 產生成功: {output_path}")
        return True
    else:
        # nano-banana-pro 可能用不同的副檔名
        for ext in [".png", ".webp", ".jpg"]:
            alt = output_path.with_suffix(ext)
            if alt.exists():
                print(f"   ✅ 產生成功: {alt}")
                return True
        print(f"   ❌ 找不到輸出檔案")
        return False


def find_output(base_path):
    """找到 nano-banana-pro 實際輸出的檔案"""
    if base_path.exists():
        return base_path
    for ext in [".png", ".webp", ".jpg"]:
        alt = base_path.with_suffix(ext)
        if alt.exists():
            return alt
    return None


def make_spritesheet(source_image_path, output_path, format="WEBP"):
    """將單一角色圖裁切/縮放成 128×64 精靈表（32×32 × 8 幀）"""
    try:
        from PIL import Image
    except ImportError:
        print("❌ 需要 Pillow: pip install Pillow")
        sys.exit(1)

    img = Image.open(source_image_path).convert("RGBA")

    # 縮放到 32×32
    frame = img.resize((FRAME_SIZE, FRAME_SIZE), Image.NEAREST)

    # 建立 128×64 的精靈表（8 幀，全部相同但可以做微調）
    sheet = Image.new("RGBA", (SHEET_W, SHEET_H), (0, 0, 0, 0))

    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            # 對每幀做微小偏移模擬走動動畫
            offset_y = -1 if (col + row) % 2 == 1 else 0
            x = col * FRAME_SIZE
            y = row * FRAME_SIZE + offset_y
            sheet.paste(frame, (x, max(0, y)))

    # 儲存
    if format == "WEBP":
        sheet.save(output_path, "WEBP", quality=95)
    else:
        sheet.save(output_path, "PNG")

    print(f"   📋 精靈表: {output_path} ({SHEET_W}×{SHEET_H})")
    return True


def backup_existing(filepath):
    """備份現有的精靈圖"""
    if filepath.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = BACKUP_DIR / f"{filepath.stem}-{ts}{filepath.suffix}"
        shutil.copy2(filepath, backup)
        print(f"   💾 備份: {backup.name}")


def process_agent(agent, slot_index, style="", dry_run=False):
    """處理單一 agent"""
    agent_id = agent["id"]
    display_name = agent["name"]
    slot = slot_index + 1  # 1-indexed

    print(f"\n{'='*50}")
    print(f"🎨 {display_name} ({agent_id}) → slot {slot}")
    print(f"{'='*50}")

    prompt = build_prompt(agent_id, display_name, style)
    print(f"   📝 Prompt: {prompt[:100]}...")

    if dry_run:
        print(f"   ⏭️  --dry-run, 跳過產生")
        return True

    # 1. 產生原始圖
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = OUTPUT_DIR / f"{agent_id}-raw.png"
    if not generate_single_image(prompt, raw_path):
        return False

    actual_raw = find_output(raw_path)
    if not actual_raw:
        print(f"   ❌ 找不到原始圖")
        return False

    # 2. 製作精靈表
    anim_path = FRONTEND_DIR / f"guest_anim_{slot}.webp"
    role_path = FRONTEND_DIR / f"guest_role_{slot}.png"

    backup_existing(anim_path)
    backup_existing(role_path)

    make_spritesheet(actual_raw, anim_path, "WEBP")
    make_spritesheet(actual_raw, role_path, "PNG")

    return True


def main():
    parser = argparse.ArgumentParser(description="Star Office Agent 像素精靈圖產生器")
    parser.add_argument("--agent", help="只產生指定 agent（by ID）")
    parser.add_argument("--style", default="", help="自訂風格（例如: cyberpunk, cute, sci-fi）")
    parser.add_argument("--dry-run", action="store_true", help="預覽 prompt 不實際產生")
    parser.add_argument("--list", action="store_true", help="列出所有 agent")
    parser.add_argument("--slots", type=int, default=6, help="可用的精靈 slot 數量（預設 6）")
    args = parser.parse_args()

    all_agents = load_agents()
    # 排除 main（主角有自己的精靈）
    guest_agents = [a for a in all_agents if a["id"] != "main"]

    if args.list:
        print(f"\n📋 共 {len(guest_agents)} 個 agent（排除 main）：\n")
        for i, a in enumerate(guest_agents):
            persona = AGENT_PERSONAS.get(a["id"], DEFAULT_PERSONA)
            marker = "✅" if a["id"] in AGENT_PERSONAS else "🤖"
            print(f"  {i+1}. {marker} {a['name']} ({a['id']}) → {persona['animal']}")
        print(f"\n  ✅ = 已設定角色  🤖 = 使用預設")
        return

    # 篩選
    if args.agent:
        targets = [a for a in guest_agents if a["id"] == args.agent]
        if not targets:
            print(f"❌ 找不到 agent: {args.agent}")
            print(f"   可用: {', '.join(a['id'] for a in guest_agents)}")
            sys.exit(1)
    else:
        targets = guest_agents[:args.slots]  # 最多 N 個 slot

    print(f"\n🎮 Star Office 像素精靈圖產生器")
    print(f"   目標: {len(targets)} 個 agent")
    print(f"   風格: {args.style or '(預設: cute cozy warm-toned)'}")
    print(f"   模式: {'預覽' if args.dry_run else '產生'}")

    success = 0
    for i, agent in enumerate(targets):
        if args.agent:
            # 找到這個 agent 在 guest list 中的 slot
            slot = next((j for j, a in enumerate(guest_agents) if a["id"] == agent["id"]), i)
        else:
            slot = i

        if process_agent(agent, slot, args.style, args.dry_run):
            success += 1

    print(f"\n{'='*50}")
    print(f"✅ 完成: {success}/{len(targets)} 個 agent")
    if not args.dry_run:
        print(f"   精靈圖位於: {FRONTEND_DIR}/guest_anim_*.webp")
        print(f"   原始圖位於: {OUTPUT_DIR}/")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
