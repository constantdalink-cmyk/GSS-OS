"""
Library Manager - 键函=库=记忆 统一体
"""
import os
import stat
import yaml
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(BASE_DIR, "skills")
SKILLS_PATH = os.path.join(SKILLS_DIR, "skills.yaml")


def _load():
    if not os.path.exists(SKILLS_PATH):
        return {}
    with open(SKILLS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save(data):
    if not os.path.exists(SKILLS_DIR):
        os.makedirs(SKILLS_DIR, exist_ok=True)
    if os.path.exists(SKILLS_PATH):
        os.chmod(SKILLS_PATH, stat.S_IWRITE)
    with open(SKILLS_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


def get_skill(app, skill):
    skills = _load()
    entry = skills.get(app, {}).get(skill, {})
    if isinstance(entry, dict) and entry.get("status") == "active":
        return entry.get("keys", "")
    return ""


def execute_ld(ref):
    parts = ref.split(".", 1)
    if len(parts) != 2:
        return "error: format app.skill"
    app, skill = parts
    keys = get_skill(app, skill)
    if not keys:
        return f"error: {app}.{skill} not found or undone"
    return keys


def record_success(app, skill, keys):
    skills = _load()
    app_data = skills.setdefault(app, {})
    entry = app_data.get(skill)

    if entry is None:
        app_data[skill] = {
            "keys": keys,
            "success": 1,
            "fail": 0,
            "status": "active",
        }
    elif entry.get("status") == "undone":
        entry["success"] = entry.get("success", 0) + 1
        entry["keys"] = keys
        entry["status"] = "active"
    else:
        entry["success"] = entry.get("success", 0) + 1
        if keys != entry.get("keys"):
            old_keys = entry.get("keys", "")
            versions = entry.setdefault("old_versions", [])
            versions.append({"keys": old_keys, "status": "undone"})
            entry["keys"] = keys

    _save(skills)


def record_fail(app, skill):
    skills = _load()
    entry = skills.get(app, {}).get(skill)
    if not entry:
        return

    entry["fail"] = entry.get("fail", 0) + 1

    if entry["fail"] > entry.get("success", 0):
        entry["status"] = "undone"
        old_versions = entry.get("old_versions", [])
        for v in reversed(old_versions):
            if v.get("status") != "deleted":
                v["status"] = "active"
                entry["keys"] = v["keys"]
                entry["status"] = "active"
                entry["fail"] = 0
                break

    _save(skills)


def get_libs_hint(current_app=""):
    skills = _load()
    parts = []

    if current_app and current_app in skills:
        names = [
            k for k, v in skills[current_app].items()
            if isinstance(v, dict) and v.get("status") == "active" and not k.startswith("_")
        ]
        if names:
            parts.append(f"{current_app}({','.join(names[:6])})")

    for app, app_data in skills.items():
        if app == current_app:
            continue
        names = [
            k for k, v in app_data.items()
            if isinstance(v, dict) and v.get("status") == "active" and not k.startswith("_")
        ]
        total = sum(
            app_data[k].get("success", 0) for k in names
            if isinstance(app_data.get(k), dict)
        )
        if total >= 3 and names:
            parts.append(f"{app}({','.join(names[:4])})")

    return " | ".join(parts[:6])


def _make_skill_name(goal):
    goal = goal.lower().strip()
    goal = re.sub(r"[^\w\u4e00-\u9fff]+", "_", goal)
    return goal[:30].strip("_") or "task"


def learn_from_history(goal, history, current_app):
    successful = []
    for h in history:
        if h.get("status") == "undone":
            continue
        head = h["act"].split()[0] if h["act"].split() else ""
        if head not in {"o", "t", "hk", "c", "w", "ld"}:
            continue
        res = h["res"]
        if res.startswith("ok:") or res == "silent_ok":
            successful.append(h["act"])

    if not successful:
        return

    keys_seq = " | ".join(successful)
    skill_name = _make_skill_name(goal)

    last_change = ""
    for h in reversed(history):
        if h["res"].startswith("ok:"):
            last_change = h["res"]
            break

    skills = _load()
    # desktop 是降级兜底，技能应归入实际 app
    # 从 keys_seq 里推断真实 app
    effective_app = current_app
    if current_app == "desktop":
        if "notepad" in keys_seq.lower() or "o notepad" in keys_seq:
            effective_app = "notepad"
    app_data = skills.setdefault(effective_app, {})

    existing = app_data.get(skill_name)
    if existing and isinstance(existing, dict):
        existing["success"] = existing.get("success", 0) + 1
        if keys_seq != existing.get("keys"):
            old = existing.get("keys", "")
            versions = existing.setdefault("old_versions", [])
            versions.append({"keys": old, "status": "undone"})
            existing["keys"] = keys_seq
        if last_change:
            existing["verify"] = last_change
    else:
        app_data[skill_name] = {
            "keys": keys_seq,
            "verify": last_change,
            "success": 1,
            "fail": 0,
            "status": "active",
        }

    _save(skills)