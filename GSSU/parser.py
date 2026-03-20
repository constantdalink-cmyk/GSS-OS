"""Parser - 支持 TODO 规划与单步执行"""

import re

VALID = {
    "c", "dc", "rc", "dr", "sc",
    "t", "hk",
    "o", "k",
    "w", "gd",
    "hc",
    "mk_lib", "ld", "mv",
    "say"
}

SCHEMA_MARKERS = [
    ":clk", ":dbl", ":rclk", ":type", ":hotkey",
    ":open", ":kill", ":wait", ":grid",
    ":mktool", ":newlib", ":load", ":move",
    ":reply"
]


def parse_todo(response: str) -> list:
    """
    解析规划阶段返回的 TODO 列表。
    允许格式：
      1 open
      2 wait
    """
    todos = []

    for raw in response.strip().split("\n"):
        line = raw.strip()
        if not line:
            continue

        # 防止把说明书抄回来
        if any(m in line for m in SCHEMA_MARKERS):
            continue
        if "|" in line:
            continue
        if "<" in line and ">" in line:
            continue

        # 匹配 "1 xxx" / "1. xxx" / "1) xxx"
        m = re.match(r"^\s*\d+[\.\)]?\s*(.+)$", line)
        if m:
            todo = m.group(1).strip()
            if todo:
                todos.append(todo)

    return todos


def parse_step(response: str) -> list:
    """
    解析单步阶段输出。
    返回：
    [
      {"type":"think","content":"open"},
      {"type":"cmd","content":"o notepad"}
    ]
    """
    actions = []

    for raw in response.strip().split("\n"):
        line = raw.strip()
        if not line:
            continue

        # 防回显说明书
        if any(m in line for m in SCHEMA_MARKERS):
            continue
        if "|" in line:
            continue
        if "<" in line and ">" in line:
            continue

        if line.startswith("[T]"):
            content = line[3:].strip()
            if content:
                actions.append({"type": "think", "content": content})
            continue

        cmd = line.split(" ", 1)[0]
        if cmd in VALID:
            actions.append({"type": "cmd", "content": line})

    return actions