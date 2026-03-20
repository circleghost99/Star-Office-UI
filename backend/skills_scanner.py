#!/usr/bin/env python3
"""
Star Office — Skills 掃描模組
掃描 ~/.openclaw/skills/ 目錄，解析每個 skill 的 SKILL.md 提取資訊。
同時從 openclaw.json 建立 skill ↔ agent 關聯。
"""

import os
import re

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from agent_discovery import _load_openclaw_config

OPENCLAW_DIR = os.environ.get("OPENCLAW_DIR") or os.path.join(os.path.expanduser("~"), ".openclaw")
SKILLS_DIR = os.path.join(OPENCLAW_DIR, "skills")

# npm 全域安裝的 OpenClaw 內建 skills 路徑
_NPM_GLOBAL_PATHS = [
    os.path.join(os.path.expanduser("~"), ".npm-global", "lib", "node_modules", "openclaw", "skills"),
    "/usr/local/lib/node_modules/openclaw/skills",
    "/usr/lib/node_modules/openclaw/skills",
]
NPM_SKILLS_DIR = next((p for p in _NPM_GLOBAL_PATHS if os.path.isdir(p)), None)

def _all_skills_dirs():
    """回傳所有要掃描的 skills 目錄（本地優先）"""
    dirs = []
    if os.path.isdir(SKILLS_DIR):
        dirs.append(("local", SKILLS_DIR))
    # hooks 目錄也可能包含 skill（例如 self-improvement）
    hooks_dir = os.path.join(OPENCLAW_DIR, "hooks")
    if os.path.isdir(hooks_dir):
        dirs.append(("hooks", hooks_dir))
    if NPM_SKILLS_DIR:
        dirs.append(("builtin", NPM_SKILLS_DIR))
    return dirs


def _parse_skill_md(skill_dir):
    """從 SKILL.md 提取 name 和 description

    SKILL.md 格式：
    ---
    name: skill-name
    description: short description
    ---
    ... detailed instructions ...
    """
    skill_md = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(skill_md):
        return None, None

    try:
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read(3000)

        # 嘗試解析 YAML frontmatter
        fm_match = re.match(r"^---\s*\n(.*?\n)---\s*\n", content, re.DOTALL)
        if fm_match:
            if HAS_YAML:
                try:
                    fm = yaml.safe_load(fm_match.group(1))
                    if isinstance(fm, dict):
                        return fm.get("name", ""), fm.get("description", "")
                except Exception:
                    pass
            else:
                # Regex fallback for YAML frontmatter
                fm_text = fm_match.group(1)
                name_m = re.search(r"^name:\s*(.+)$", fm_text, re.MULTILINE)
                desc_m = re.search(r"^description:\s*(.+)$", fm_text, re.MULTILINE)
                return (
                    name_m.group(1).strip() if name_m else "",
                    desc_m.group(1).strip() if desc_m else "",
                )

        # Fallback: 從第一行非空行提取
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        name = lines[0].lstrip("#").strip() if lines else ""
        desc = lines[1] if len(lines) > 1 else ""
        return name, desc

    except Exception:
        return None, None


def _build_skill_agent_map():
    """從 openclaw.json 建立 skill_name → [agent_ids] 映射"""
    config_list = _load_openclaw_config()
    mapping = {}
    for cfg in config_list:
        if not isinstance(cfg, dict):
            continue
        agent_id = cfg.get("id", "")
        agent_name = cfg.get("name", agent_id)
        skills = cfg.get("skills", [])
        for skill_name in skills:
            if skill_name not in mapping:
                mapping[skill_name] = []
            mapping[skill_name].append({
                "id": agent_id,
                "name": agent_name,
            })
    return mapping


def scan_all_skills():
    """掌描所有 skills，回傳完整資訊列表（本地 + npm 全域）"""
    skill_agent_map = _build_skill_agent_map()
    skills = {}

    for source, base_dir in _all_skills_dirs():
        if not os.path.isdir(base_dir):
            continue
        for dirname in sorted(os.listdir(base_dir)):
            if dirname in skills:  # 本地優先，不覆蓋
                continue
            skill_dir = os.path.join(base_dir, dirname)
            if not os.path.isdir(skill_dir) or dirname.startswith("."):
                continue

            name, description = _parse_skill_md(skill_dir)

            has_scripts = os.path.isdir(os.path.join(skill_dir, "scripts"))
            has_examples = os.path.isdir(os.path.join(skill_dir, "examples"))

            skill_info = {
                "name": dirname,
                "displayName": name or dirname,
                "description": description or "",
                "usedBy": skill_agent_map.get(dirname, []),
                "hasScripts": has_scripts,
                "hasExamples": has_examples,
                "path": skill_dir,
                "source": source,
            }
            skills[dirname] = skill_info

    return sorted(skills.values(), key=lambda x: x["name"])


def get_skill_detail(skill_name):
    """取得單一 skill 的詳細資訊（含完整 SKILL.md 內容）"""
    # 在所有目錄中搜尋
    skill_dir = None
    for source, base_dir in _all_skills_dirs():
        candidate = os.path.join(base_dir, skill_name)
        if os.path.isdir(candidate):
            skill_dir = candidate
            break

    if skill_dir is None:
        return None

    name, description = _parse_skill_md(skill_dir)
    skill_agent_map = _build_skill_agent_map()

    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    full_content = ""
    if os.path.isfile(skill_md_path):
        try:
            with open(skill_md_path, "r", encoding="utf-8") as f:
                full_content = f.read()
        except Exception:
            pass

    return {
        "name": skill_name,
        "displayName": name or skill_name,
        "description": description or "",
        "usedBy": skill_agent_map.get(skill_name, []),
        "content": full_content,
        "path": skill_dir,
    }
