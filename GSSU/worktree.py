# worktree.py

"""
WorkTree - 任务操作变更树
记录每次任务做了什么，供下一个AI读取
"""
import os
import json
import time
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TREE_PATH = os.path.join(BASE_DIR, "worktree.json")
MAX_ENTRIES = 10


def _load():
    if not os.path.exists(TREE_PATH):
        return []
    try:
        with open(TREE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f) or []
        # 去重：同 goal 只保留最新一条，合并 count
        seen = {}
        for entry in data:
            g = entry.get("goal", "")
            if entry.get("saved_file"):
                sf = entry["saved_file"]
                # 强制修正 final_obs，避免旧 final_obs 污染 MEM 显示
                entry["final_obs"] = f"窗口={sf} - Notepad"
            if g in seen:
                seen[g]["count"] = seen[g].get("count", 1) + entry.get("count", 1)
                seen[g]["time"] = entry.get("time", seen[g]["time"])
                seen[g]["steps"] = entry.get("steps", seen[g]["steps"])
                seen[g]["final_obs"] = entry.get("final_obs", seen[g]["final_obs"])
                seen[g]["result"] = entry.get("result", seen[g]["result"])
                if entry.get("saved_file"):
                    seen[g]["saved_file"] = entry.get("saved_file")
                if entry.get("saved_path"):
                    seen[g]["saved_path"] = entry.get("saved_path")
                all_files = seen[g].get("all_files", [])
                for fname in entry.get("all_files", []):
                    if fname and fname not in all_files:
                        all_files.append(fname)
                if entry.get("saved_file") and entry.get("saved_file") not in all_files:
                    all_files.append(entry.get("saved_file"))
                seen[g]["all_files"] = all_files[-5:]
                old_targets = set(seen[g].get("targets", []))
                old_targets.update(entry.get("targets", []))
                seen[g]["targets"] = list(old_targets)
            else:
                seen[g] = dict(entry)
        return list(seen.values())
    except:
        return []


def _save(data):
    with open(TREE_PATH, "w", encoding="utf-8") as f:
        json.dump(data[-MAX_ENTRIES:], f, ensure_ascii=False, indent=2)


def record(goal, steps, result, final_obs="", saved_file="", saved_path="", targets=None):
    tree = _load()
    existing = None
    for entry in tree:
        if entry.get("goal") == goal:
            existing = entry
            break

    safe_targets = targets or []

    if existing:
        existing["count"] = existing.get("count", 1) + 1
        existing["steps"] = steps
        existing["result"] = result
        existing["final_obs"] = final_obs
        existing["time"] = time.strftime("%H:%M:%S")
        
        old_targets = set(existing.get("targets", []))
        old_targets.update(safe_targets)
        existing["targets"] = list(old_targets)

        if saved_file:
            existing["saved_file"] = saved_file
            all_files = existing.get("all_files", [])
            if saved_file not in all_files:
                all_files.append(saved_file)
            existing["all_files"] = all_files[-5:]
        if saved_path:
            existing["saved_path"] = saved_path
    else:
        entry = {
            "goal": goal,
            "steps": steps,
            "result": result,
            "final_obs": final_obs,
            "time": time.strftime("%H:%M:%S"),
            "count": 1,
            "targets": safe_targets
        }
        if saved_file:
            entry["saved_file"] = saved_file
            entry["all_files"] = [saved_file]
        if saved_path:
            entry["saved_path"] = saved_path
        tree.append(entry)
    _save(tree)


def get_hint(max_entries=3, disk_files=None):
    tree = _load()
    if not tree:
        return ""

    sorted_tree = sorted(tree, key=lambda x: x.get("count", 1), reverse=True)
    recent = sorted_tree[:max_entries]
    lines = []

    APP_TARGETS = {"notepad", "chrome", "edge", "explorer", "desktop"}

    for e in recent:
        goal_short = e.get("goal", "")[:20]
        count = e.get("count", 1)
        result = e.get("result", "")
        final_obs = e.get("final_obs", "")
        fname = e.get("saved_file", "")
        saved_path = e.get("saved_path", "")

        # 如果 saved_path 已失效，彻底视为无文件
        if saved_path and (not os.path.isabs(saved_path) or not os.path.isfile(saved_path)):
            saved_path = ""
            fname = ""

        if not fname:
            m = re.search(r"窗口=([^\|]+)", final_obs)
            if m:
                title = m.group(1).strip()
                if "." in title:
                    candidate = title.split(" - ")[0].strip()
                    # 只有真实存在才接受
                    for d in [
                        os.path.expanduser("~/Desktop"),
                        os.path.expanduser("~/Documents"),
                        os.path.expanduser("~/Documents/GSSU_WORK")
                    ]:
                        full = os.path.join(d, candidate)
                        if os.path.isfile(full):
                            fname = candidate
                            break

        parts = [f"{goal_short}:{result}"]
        if count > 1:
            parts.append(f"x{count}")

        # 只保留“真的还活着”的 targets
        raw_targets = e.get("targets", [])
        live_targets = []

        for t in raw_targets:
            if t in APP_TARGETS:
                live_targets.append(t)
                continue

            still_exists = False
            for d in [
                os.path.expanduser("~/Desktop"),
                os.path.expanduser("~/Documents"),
                os.path.expanduser("~/Documents/GSSU_WORK")
            ]:
                full = os.path.join(d, t)
                if os.path.isfile(full):
                    still_exists = True
                    break

            if still_exists:
                live_targets.append(t)

        # 如果没有 live target，但 saved_path 还有效，则用 fname
        if not live_targets and fname and saved_path:
            live_targets = [fname]

        # 只有真的有活 target，才显示 涉及:[...]
        if live_targets:
            shown_targets = []
            for t in live_targets:
                if t in APP_TARGETS:
                    shown_targets.append(t)
                else:
                    shown_targets.append(f"{t}(存)")
            parts.append(f"涉及:[{','.join(shown_targets)}]")

        steps = e.get("steps", "")
        if steps:
            parts.append(f"[{steps}]")

        # 过滤掉“既没有活 target，也没有 saved_path，也不是纯 read→say 聊天型记录”的脏 entry
        has_live_file = bool(saved_path or live_targets)
        is_chat_like = steps in ("read→say", "compare→say")
        if has_live_file or is_chat_like:
            lines.append(" ".join(parts))

    return "MEM:" + " | ".join(lines) if lines else ""


def cleanup_missing():
    tree = _load()
    changed = False
    new_tree = []

    APP_TARGETS = {"notepad", "chrome", "edge", "explorer", "desktop"}

    for entry in tree:
        sp = entry.get("saved_path", "")
        sf = entry.get("saved_file", "")

        # 1. saved_path 不存在就清掉 saved_path / saved_file
        if sp and (not os.path.isabs(sp) or not os.path.isfile(sp)):
            entry["saved_path"] = ""
            entry["saved_file"] = ""
            changed = True

        # 2. all_files 只保留仍存在的 basename
        new_all_files = []
        for fname in entry.get("all_files", []):
            if not fname:
                continue
            still_exists = False
            for d in [
                os.path.expanduser("~/Desktop"),
                os.path.expanduser("~/Documents"),
                os.path.expanduser("~/Documents/GSSU_WORK")
            ]:
                full = os.path.join(d, fname)
                if os.path.isfile(full):
                    still_exists = True
                    break
            if still_exists:
                new_all_files.append(fname)

        if new_all_files != entry.get("all_files", []):
            entry["all_files"] = new_all_files
            changed = True

        # 3. targets 只保留 app 名或真实还存在的文件名
        new_targets = []
        for t in entry.get("targets", []):
            if t in APP_TARGETS:
                new_targets.append(t)
                continue

            still_exists = False
            for d in [
                os.path.expanduser("~/Desktop"),
                os.path.expanduser("~/Documents"),
                os.path.expanduser("~/Documents/GSSU_WORK")
            ]:
                full = os.path.join(d, t)
                if os.path.isfile(full):
                    still_exists = True
                    break
            if still_exists:
                new_targets.append(t)

        if new_targets != entry.get("targets", []):
            entry["targets"] = new_targets
            changed = True

        # 4. 没有活文件、没有活 target、也不是纯 say 类记录 → 丢弃
        has_saved = bool(entry.get("saved_path"))
        has_targets = bool(entry.get("targets"))
        steps = entry.get("steps", "")
        is_chat_like = steps in ("read→say", "compare→say")

        if has_saved or has_targets or is_chat_like:
            new_tree.append(entry)
        else:
            changed = True

    if changed:
        _save(new_tree)

    return {
        "entries": len(new_tree),
        "changed": changed,
    }