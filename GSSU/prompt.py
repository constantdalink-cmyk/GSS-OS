"""Prompt Builder - 优化版：聊天快路径 + 阀门单步驱动"""

import lib_manager
from grid import grid


# =============================
# Token 粗估：chars / 4 * 语言系数
# =============================
def language_coef(text: str) -> float:
    if not text:
        return 1.0

    total = len(text)
    non_ascii = sum(1 for ch in text if ord(ch) > 127)
    ratio = non_ascii / total

    if ratio < 0.05:
        return 1.0
    elif ratio < 0.30:
        return 1.2
    elif ratio < 0.70:
        return 1.5
    else:
        return 1.8

def estimate_tokens_rough(text: str) -> int:
    """
    token ≈ chars / 4 * language_coef
    注意：只是粗估，论文/实验请优先使用 API usage。
    """
    if not text:
        return 0
    chars = len(text)
    coef = language_coef(text)
    return max(1, int((chars / 4.0) * coef))


# =============================
# 1. Chat 快路径 (极简上下文)
# =============================
CHAT_BASE = """Reply only.
Out:
say <msg>
No tools. No prose.
"""

# =============================
# 2. OS 规划阶段 (生成 TODO)
# =============================
PLAN_BASE = """Make TODO only.
<=6 lines.
Format:
1 short
2 short
No prose.
"""

# =============================
# 3. OS 单步阶段 (执行单个 TODO)
# =============================
STEP_BASE = """One TODO only.
Out:
[T] short
cmd arg
T short. One cmd only.
If no OS action, use say.
No prose.
"""

# =============================
# 键函层（可删减）
# =============================
KEYS_PROMPT = """Cmd:
say <msg>
o <app>
k <app>
t <text>
hk <keys>
w <ms>
gd <1-8>
c <XY>
dc <XY>
rc <XY>
dr <XY1> <XY2>
sc <dir> <n>
hc <name>
mk_lib <name>
ld <name>
mv <tool> <lib>
"""


def _all_libs_text() -> str:
    apps = lib_manager.get_lib_prompt("lib_sys")
    tools = lib_manager.get_lib_prompt("lib_how")

    parts = []
    if apps:
        parts.append("[Apps]")
        parts.append(apps)
    if tools:
        parts.append("[Tools]")
        parts.append(tools)

    return "\n".join(parts).strip()


def _filter_libs(task_text: str, todo_text: str = "") -> str:
    """
    简单做相关库筛选：
    - 如果匹配到 app/tool 名称或描述，则只返回相关项
    - 如果没匹配到，返回全部
    """
    full = _all_libs_text()
    if not full:
        return ""

    target = f"{task_text}\n{todo_text}".lower()
    lines = full.splitlines()

    result = []
    current_header = None
    buffer_under_header = []

    def flush_section():
        nonlocal result, current_header, buffer_under_header
        if not current_header:
            return
        if buffer_under_header:
            result.append(current_header)
            result.extend(buffer_under_header)
        current_header = None
        buffer_under_header = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("[") and line.endswith("]"):
            flush_section()
            current_header = line
            continue

        left = line.split(":", 1)[0].strip().lower()
        right = line.split(":", 1)[1].strip().lower() if ":" in line else line.lower()

        # 简单匹配
        if left in target or right in target:
            buffer_under_header.append(line)

    flush_section()

    # 如果完全没命中，回退返回完整库
    if not result:
        return full

    return "\n".join(result)


def _state_prompt() -> str:
    rows, cols = grid.get_size()
    return f"Grid:{cols}x{rows}"

# ==============================================================
# 以下是三个不同管线的 Package 构建函数，供 main.py 导入使用
# ==============================================================

def build_chat_package(task: str) -> dict:
    """供纯聊天任务使用：不需要键函，不需要库，不需要网格状态"""
    return {
        "base": CHAT_BASE.strip(),
        "keys": "",
        "libs": "",
        "state": "",
        "task": task.strip()
    }


def build_plan_package(task: str) -> dict:
    """供 OS 规划阶段使用：不需要键函"""
    return {
        "base": PLAN_BASE.strip(),
        "keys": "",
        "libs": "",
        "state": "",
        "task": task.strip()
    }


def build_step_package(task: str, todo: str, step_index: int, total_steps: int) -> dict:
    """供 OS 单步执行使用：全量加载所需上下文"""
    task_block = f"Task:{task}\nNow:{todo}\nStep:{step_index}/{total_steps}"

    return {
        "base": STEP_BASE.strip(),
        "keys": KEYS_PROMPT.strip(),
        "libs": _filter_libs(task, todo),
        "state": _state_prompt(),
        "task": task_block
    }


def total_chars(pkg: dict) -> int:
    return sum(len(v) for v in pkg.values() if v)

def total_tokens_rough(pkg: dict) -> int:
    return sum(estimate_tokens_rough(v) for v in pkg.values() if v)