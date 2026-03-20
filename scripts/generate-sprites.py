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
    "lobster-support":   {"animal": "hamster",  "color": "red-brown",  "accessory": "captain hat and anchor badge"},
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
    """將單一角色圖裁切/縮放成 128×64 精靈表（32×32 × 8 幀）
    用 Pillow 做 4 個走動姿勢：idle, lean-left, idle, lean-right（模擬走動）
    """
    try:
        from PIL import Image, ImageChops
    except ImportError:
        print("❌ 需要 Pillow: pip install Pillow")
        sys.exit(1)

    img = Image.open(source_image_path).convert("RGBA")

    # 縮放到 32×32
    base_frame = img.resize((FRAME_SIZE, FRAME_SIZE), Image.LANCZOS)

    # === 產生 4 個走動姿勢 ===
    # Frame 0: idle (原始)
    f0 = base_frame.copy()

    # Frame 1: lean left + bob up (左傾 + 上移)
    f1 = Image.new("RGBA", (FRAME_SIZE, FRAME_SIZE), (0, 0, 0, 0))
    f1.paste(base_frame, (-1, -1))  # 左移 1px, 上移 1px

    # Frame 2: idle (微調)
    f2 = base_frame.copy()

    # Frame 3: lean right + bob up (右傾 + 上移)
    f3 = Image.new("RGBA", (FRAME_SIZE, FRAME_SIZE), (0, 0, 0, 0))
    f3.paste(base_frame, (1, -1))  # 右移 1px, 上移 1px

    # 8 幀循環：idle, left, idle, right, idle, left, idle, right
    frames = [f0, f1, f2, f3, f0, f1, f2, f3]

    # 建立 128×64 的精靈表
    sheet = Image.new("RGBA", (SHEET_W, SHEET_H), (0, 0, 0, 0))
    for idx, frame in enumerate(frames):
        col = idx % GRID_COLS
        row = idx // GRID_COLS
        x = col * FRAME_SIZE
        y = row * FRAME_SIZE
        sheet.paste(frame, (x, y))

    # 儲存
    if format == "WEBP":
        sheet.save(output_path, "WEBP", quality=95)
    else:
        sheet.save(output_path, "PNG")

    print(f"   📋 精靈表: {output_path} ({SHEET_W}×{SHEET_H}, 4 poses × 2 rows)")
    return True


def generate_walk_poses(base_image_path, agent_id, style=""):
    """用 nano-banana-pro 的 edit 模式產生走動姿勢變化"""
    try:
        from PIL import Image
    except ImportError:
        return None

    poses = {}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Pose 1: 左腳踏出
    pose_prompts = [
        ("left_step", "edit this pixel art character to show it leaning slightly left with left arm forward, walking pose, keep same style and colors"),
        ("right_step", "edit this pixel art character to show it leaning slightly right with right arm forward, walking pose, keep same style and colors"),
        ("bounce", "edit this pixel art character to show it slightly squished/bouncing down, cute bounce animation frame, keep same style and colors"),
    ]

    for pose_name, prompt in pose_prompts:
        out_path = OUTPUT_DIR / f"{agent_id}-{pose_name}.png"
        cmd = [
            "uv", "run", str(SKILL_SCRIPT),
            "--prompt", prompt,
            "--filename", str(out_path),
            "-i", str(base_image_path),
            "--resolution", "1K",
            "--aspect-ratio", "1:1",
        ]
        print(f"   🎨 產生 {pose_name} 姿勢...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        actual = find_output(out_path)
        if actual:
            poses[pose_name] = actual
            print(f"   ✅ {pose_name}: {actual.name}")
        else:
            print(f"   ⚠️  {pose_name} 失敗，使用 Pillow 偏移替代")

    return poses


def make_animated_spritesheet(base_image_path, poses, output_path, format="WEBP"):
    """用產生的多姿勢圖片組裝精靈表"""
    try:
        from PIL import Image
    except ImportError:
        print("❌ 需要 Pillow")
        sys.exit(1)

    base = Image.open(base_image_path).convert("RGBA")
    base_frame = base.resize((FRAME_SIZE, FRAME_SIZE), Image.LANCZOS)

    # 載入各姿勢，失敗則用偏移替代
    def load_pose(name, dx, dy):
        if name in poses and poses[name].exists():
            img = Image.open(poses[name]).convert("RGBA")
            return img.resize((FRAME_SIZE, FRAME_SIZE), Image.LANCZOS)
        else:
            f = Image.new("RGBA", (FRAME_SIZE, FRAME_SIZE), (0, 0, 0, 0))
            f.paste(base_frame, (dx, dy))
            return f

    f_idle = base_frame.copy()
    f_left = load_pose("left_step", -1, -1)
    f_right = load_pose("right_step", 1, -1)
    f_bounce = load_pose("bounce", 0, 1)

    # 走動循環：idle → left → bounce → right → idle → left → bounce → right
    frames = [f_idle, f_left, f_bounce, f_right, f_idle, f_left, f_bounce, f_right]

    # 組裝
    sheet = Image.new("RGBA", (SHEET_W, SHEET_H), (0, 0, 0, 0))
    for idx, frame in enumerate(frames):
        col = idx % GRID_COLS
        row = idx // GRID_COLS
        sheet.paste(frame, (col * FRAME_SIZE, row * FRAME_SIZE))

    if format == "WEBP":
        sheet.save(output_path, "WEBP", quality=95)
    else:
        sheet.save(output_path, "PNG")

    print(f"   📋 動畫精靈表: {output_path} ({SHEET_W}×{SHEET_H}, 4 poses)")
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

    # 1. 產生原始圖（idle pose）
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = OUTPUT_DIR / f"{agent_id}-raw.png"
    if not generate_single_image(prompt, raw_path):
        return False

    actual_raw = find_output(raw_path)
    if not actual_raw:
        print(f"   ❌ 找不到原始圖")
        return False

    # 2. 產生走動姿勢（用 edit 模式）
    print(f"\n   🚶 產生走動動畫姿勢...")
    poses = generate_walk_poses(actual_raw, agent_id, style)
    if poses is None:
        poses = {}

    # 3. 備份舊精靈圖
    anim_path = FRONTEND_DIR / f"guest_anim_{slot}.webp"
    role_path = FRONTEND_DIR / f"guest_role_{slot}.png"

    backup_existing(anim_path)
    backup_existing(role_path)

    # 4. 組裝動畫精靈表
    make_animated_spritesheet(actual_raw, poses, anim_path, "WEBP")
    make_animated_spritesheet(actual_raw, poses, role_path, "PNG")

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
