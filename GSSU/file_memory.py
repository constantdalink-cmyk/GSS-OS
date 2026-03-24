# file_memory.py

import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEM_PATH = os.path.join(BASE_DIR, "file_memory.json")


def _load():
    if not os.path.exists(MEM_PATH):
        return {"by_goal": {}, "by_alias": {}}
    try:
        with open(MEM_PATH, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        data.setdefault("by_goal", {})
        data.setdefault("by_alias", {})
        return data
    except:
        return {"by_goal": {}, "by_alias": {}}


def _save(data):
    with open(MEM_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def record(goal, saved_path, aliases=None):
    if not saved_path or not os.path.isabs(saved_path):
        return
    data = _load()
    data["by_goal"][goal] = saved_path
    for a in (aliases or []):
        if a:
            data["by_alias"][a] = saved_path
    _save(data)


def get_latest():
    """获取最近一次保存的文件路径"""
    data = _load()
    if data["by_goal"]:
        return list(data["by_goal"].values())[-1]
    return ""


def resolve(goal):
    data = _load()

    # 1. 先精确匹配 goal
    if goal in data["by_goal"]:
        p = data["by_goal"][goal]
        return p if p and os.path.isabs(p) else ""

    g = goal.lower()

    # 2. 再匹配 alias
    for alias, path in data["by_alias"].items():
        if alias and alias.lower() in g:
            return path if path and os.path.isabs(path) else ""

    # 3. 最后做弱匹配：关键词交集 + 包含关系匹配
    for old_goal, path in data["by_goal"].items():
        og = old_goal.lower()
        import re as _re
        # 提取2字以上中文词
        g_words = set(_re.findall(r'[\u4e00-\u9fff]{2,}', g))
        og_words = set(_re.findall(r'[\u4e00-\u9fff]{2,}', og))
        common = g_words & og_words
        # 排除过于泛化的词
        noise = {"函数", "代码", "文件", "保存", "记事本", "支持", "使用", "进行"}
        meaningful = common - noise
        if meaningful:
            return path if path and os.path.isabs(path) else ""
        # 补充：包含关系匹配（"计算" in "计算器"）
        for gw in g_words:
            for ow in og_words:
                if gw in ow or ow in gw:
                    if gw not in noise and ow not in noise:
                        return path if path and os.path.isabs(path) else ""

    return ""

def cleanup_missing():
    data = _load()
    changed = False

    # 清理 by_goal
    bad_goals = []
    for goal, path in data.get("by_goal", {}).items():
        if not path or not os.path.isabs(path) or not os.path.isfile(path):
            bad_goals.append(goal)
    for g in bad_goals:
        del data["by_goal"][g]
        changed = True

    # 清理 by_alias
    bad_alias = []
    for alias, path in data.get("by_alias", {}).items():
        if not path or not os.path.isabs(path) or not os.path.isfile(path):
            bad_alias.append(alias)
    for a in bad_alias:
        del data["by_alias"][a]
        changed = True

    if changed:
        _save(data)

    return {
        "removed_goals": len(bad_goals),
        "removed_alias": len(bad_alias),
    }