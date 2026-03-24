# executor.py

"""物理执行器 - 键函→物理动作"""
import subprocess
import time
import pyautogui
import pyperclip
import os
import win32gui
import win32con
from config import DANGEROUS_KEYS

pyautogui.FAILSAFE = True

MODS = {
    "@1": "ctrl",
    "@2": "win",
    "@3": "alt",
    "@4": "shift",
}

KEYS = {
    "a","b","c","d","e","f","g","h","i","j","k","l","m",
    "n","o","p","q","r","s","t","u","v","w","x","y","z",
    "0","1","2","3","4","5","6","7","8","9",
    "enter","esc","tab","space",
    "up","down","left","right",
    "delete","backspace",
    "f1","f2","f3","f4","f5","f6",
    "f7","f8","f9","f10","f11","f12",
}


def compile_hk(expr: str):
    expr = expr.strip().lower().replace(" ", "")
    if not expr:
        return None
    parts = expr.split("+")
    if any(not p for p in parts):
        return None
    if len(parts) == 1:
        if parts[0] in KEYS:
            return [parts[0]]
        return None
    mods = parts[:-1]
    last = parts[-1]
    if last not in KEYS:
        return None
    compiled = []
    seen = set()
    for m in mods:
        if m not in MODS:
            return None
        real = MODS[m]
        if real not in seen:
            compiled.append(real)
            seen.add(real)
    compiled.append(last)
    return compiled


def run_cmd(command):
    parts = command.strip().split(" ", 1)
    cmd = parts[0]
    arg = parts[1].strip() if len(parts) > 1 else ""

    try:
        if cmd == "o":
            subprocess.Popen(f"start {arg}", shell=True)
            time.sleep(1.2)

            # 检测是否弹出了"找不到程序"的错误对话框 (#32770)
            import win32gui as _wg
            import win32con as _wc
            found_error_dialog = False

            def _check_dialog(hwnd, _):
                nonlocal found_error_dialog
                cls = _wg.GetClassName(hwnd)
                title = _wg.GetWindowText(hwnd)
                if cls == "#32770" and arg.lower() in title.lower():
                    found_error_dialog = True
                    # 发送关闭消息
                    _wg.PostMessage(hwnd, _wc.WM_CLOSE, 0, 0)
                    print(f"🔧 [CLEANUP] 已关闭错误对话框: {title}")

            _wg.EnumWindows(_check_dialog, None)

            if found_error_dialog:
                return f"error: program '{arg}' not found"

            try:
                import window_manager
                snap_result = window_manager.snap_foreground_to_q1()
                return f"ok:{snap_result}"
            except Exception:
                return "ok"

        elif cmd == "f":
            try:
                import window_manager
                result = window_manager.focus_window(arg)
                return f"ok:{result}"
            except Exception as e:
                return f"error: {e}"

        elif cmd == "t":
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.1)
            pyperclip.copy(arg)
            pyautogui.hotkey("ctrl", "v")
            return "ok"

        elif cmd == "hk":
            keys = compile_hk(arg)
            if not keys:
                return f"error: invalid hk expr {arg}"
            real_combo = "+".join(keys)
            for dk in DANGEROUS_KEYS:
                if real_combo == dk.lower().replace(" ", ""):
                    return f"blocked: {arg} is dangerous"
            pyautogui.hotkey(*keys)
            return "ok"

        elif cmd == "c":
            coords = arg.replace("{", "").replace("}", "").split(",")
            if len(coords) == 2:
                x, y = int(coords[0].strip()), int(coords[1].strip())
                pyautogui.click(x, y)
                return "ok"
            return "error: bad coords"

        elif cmd == "read":
            parts = arg.split("|", 1)
            path = parts[0].strip()

            actual_path = path
            if not os.path.isfile(actual_path):
                try:
                    import observer
                    snap = observer.take_snapshot()
                    found_files = []
                    for fp in snap.get("files", {}).keys():
                        if os.path.basename(fp).lower() == path.lower():
                            found_files.append(fp)
                    if found_files:
                        actual_path = found_files[0]
                except Exception:
                    pass

            if not os.path.isfile(actual_path):
                found = False
                desktop_paths = [
                    os.path.expanduser("~/Desktop"),
                    os.path.expanduser("~/OneDrive/Desktop"),
                    os.path.expanduser("~/OneDrive/桌面"),
                    os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
                    os.path.join(os.environ.get("USERPROFILE", ""), "桌面")
                ]
                doc_paths = [
                    os.path.expanduser("~/Documents"),
                    os.path.expanduser("~/OneDrive/Documents"),
                    os.path.expanduser("~/OneDrive/文档"),
                    os.path.join(os.environ.get("USERPROFILE", ""), "Documents"),
                    os.path.join(os.environ.get("USERPROFILE", ""), "文档")
                ]
                for d in desktop_paths + doc_paths:
                    if os.path.isdir(d):
                        p = os.path.join(d, path)
                        if os.path.isfile(p):
                            actual_path = p
                            found = True
                            break
                if not found:
                    return f"error: file not found: {path}"

            try:
                with open(actual_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()

                if len(parts) > 1:
                    range_str = parts[1].strip()
                    if "-" in range_str:
                        start_str, end_str = range_str.split("-")
                        start = max(0, int(start_str) - 1)
                        end = min(len(lines), int(end_str))
                        content = "".join(lines[start:end])
                        return f"ok:lines {start+1}-{end}\n{content}"

                content = "".join(lines[:30])
                if len(lines) > 30:
                    content += f"\n... (还有 {len(lines)-30} 行, 用 read path|start-end 查看)"
                return f"ok:\n{content}"
            except Exception as e:
                return f"error: {e}"

        elif cmd == "write":
            if "|" not in arg:
                return "error: format is write path|content"
            path, content = arg.split("|", 1)
            path = path.strip()
            content = content.strip()
            try:
                dirn = os.path.dirname(path)
                if dirn:
                    os.makedirs(dirn, exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"ok:written {os.path.basename(path)}"
            except Exception as e:
                return f"error: {e}"

        elif cmd == "w":
            time.sleep(int(arg) / 1000.0)
            return "ok"

        elif cmd == "say":
            return "ok"

        else:
            return f"error: unknown cmd {cmd}"

    except Exception as e:
        return f"error: {e}"