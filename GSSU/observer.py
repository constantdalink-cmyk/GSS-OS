"""
Observer - 系统之眼
快照 + diff = 事实
v2.6 - 修复：title 本身是"另存为"时也能检测到对话框
"""
import win32gui
import psutil
import pyperclip
import os
import time

_last_snapshot = None
WATCH_DIRS = [
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Documents"),
]


def take_snapshot():
    global _last_snapshot
    hwnd = win32gui.GetForegroundWindow()
    title = win32gui.GetWindowText(hwnd)

    windows = []
    def enum_cb(h, results):
        if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h):
            results.append(win32gui.GetWindowText(h))
    win32gui.EnumWindows(enum_cb, windows)

    procs = set()
    for p in psutil.process_iter(['name']):
        try:
            procs.add(p.info['name'].lower())
        except:
            pass

    try:
        clip = pyperclip.paste()[:100]
    except:
        clip = ""

    files = {}
    for d in WATCH_DIRS:
        if os.path.exists(d):
            for f in os.listdir(d)[:20]:
                fp = os.path.join(d, f)
                try:
                    files[fp] = os.path.getmtime(fp)
                except:
                    pass

    snap = {
        "title": title,
        "windows": sorted(windows),
        "procs": procs,
        "clipboard": clip,
        "files": files,
        "time": time.time(),
    }
    _last_snapshot = snap
    return snap


def diff_snapshots(before, after):
    changes = []
    if before["title"] != after["title"]:
        changes.append(f"窗口:{before['title']}→{after['title']}")
    for w in set(after["windows"]) - set(before["windows"]):
        changes.append(f"+窗口:{w}")
    for w in set(before["windows"]) - set(after["windows"]):
        changes.append(f"-窗口:{w}")
    for p in after["procs"] - before["procs"]:
        changes.append(f"+进程:{p}")
    for p in before["procs"] - after["procs"]:
        changes.append(f"-进程:{p}")
    if before["clipboard"] != after["clipboard"]:
        changes.append(f"剪贴板→{after['clipboard'][:50]}")
    for fp, mt in after["files"].items():
        old = before["files"].get(fp)
        if old is None:
            changes.append(f"+文件:{os.path.basename(fp)}")
        elif mt > old:
            changes.append(f"改文件:{os.path.basename(fp)}")
    for fp in before["files"]:
        if fp not in after["files"]:
            changes.append(f"-文件:{os.path.basename(fp)}")
    return changes


def get_observation():
    """
    增强版 OBS：
    - 返回当前窗口标题
    - 检测未保存标记 (* 或 ●)
    - 检测另存为对话框：title 本身 或 windows 列表里
    """
    snap = take_snapshot()
    title = snap.get('title', '')
    parts = [f"窗口={title}"]

    # 检测未保存标记
    if title.startswith("*") or title.startswith("●"):
        parts.append("未保存")

    # 修复：title 本身是"另存为"时也能检测到
    saveas_detected = (
        '另存为' in title or 'save as' in title.lower()
        or any('另存为' in w or 'save as' in w.lower()
               for w in snap.get('windows', []))
    )
    if saveas_detected:
        parts.append("对话框=另存为")
    elif any('保存' in w and '确认' in w for w in snap.get('windows', [])):
        parts.append("对话框=保存确认")

    return " | ".join(parts)


def run_and_diff(cmd_str):
    from executor import run_cmd as _exec

    global _last_snapshot
    before = _last_snapshot or take_snapshot()

    steps = [s.strip() for s in cmd_str.split("|")]
    for s in steps:
        if s:
            _exec(s)
            time.sleep(0.3)

    time.sleep(0.5)
    after = take_snapshot()
    changes = diff_snapshots(before, after)

    if changes:
        return "ok: " + " | ".join(changes)
    else:
        return "no_change"