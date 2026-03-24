# core.py

# ──────────────────────────────────────────────────────────────
# 启动权限检查
# ──────────────────────────────────────────────────────────────
import os
import sys
import ctypes
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    print("╔═════════════════════════════════════════╗")
    print("║  ⚠️  GSS-OS 需要管理员权限              ║")
    print("║                                         ║")
    print("║  需要权限用于：                          ║")
    print("║  · 写入技能库                            ║")
    print("║  · 移动窗口位置                          ║")
    print("║  · 读取系统进程信息                      ║")
    print("╚═════════════════════════════════════════╝")
    print()
    choice = input("是否申请管理员权限？[Y/N]: ").strip().upper()
    if choice == "Y":
        script = os.path.abspath(sys.argv[0])
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}"', None, 1
        )
        print("已申请权限，本窗口将关闭。")
    else:
        print("已退出。")
    sys.exit()

os.makedirs("skills", exist_ok=True)
import config
os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
# ──────────────────────────────────────────────────────────────

"""
GSS-OS Agent Core v2.8
显式 phase 推进，build_signal 只保留环境事实检测
"""
import time
import pyautogui
import win32gui
import scanner

from observer import get_observation, take_snapshot, run_and_diff, diff_snapshots
from executor import run_cmd
from lib_manager import get_libs_hint, execute_ld, record_success, record_fail, learn_from_history
from ai_client import ask
from config import MAX_STEPS, MAX_HISTORY
import window_manager

# 有序列表：parse_response 按优先级匹配，t/write 优先于 hk/c
VALID_HEADS = ["t", "write", "read", "say", "o", "f", "hk", "c", "w", "ld", "ASK", "VISION", "DONE"]
ACTION_HEADS = {"o", "f", "t", "hk", "c", "w", "ld", "read", "write"}
SILENT_CMDS = {
    "f",
    "c",
    "hk @1+a",
    "hk @1+c",
    "hk @1+x",
    "hk @1+z",
    "hk @1+y",
    "hk @1+s",
    "hk tab",
    "hk enter",
}


def handle_saveas_reflex(source_title=""):
    """
    系统反射：处理另存为对话框（不经过模型）。
    直接将文件保存到受控工作区。
    """
    import re
    import pyperclip
    import config

    hwnd = win32gui.GetForegroundWindow()
    title = win32gui.GetWindowText(hwnd)
    print(f"🔧 [REFLEX] 前台窗口: '{title}'")

    if '另存为' not in title and 'save as' not in title.lower():
        print("🔧 [REFLEX] 前台不是另存为，尝试聚焦...")
        window_manager.focus_window("另存为")
        time.sleep(0.3)

    raw_name = source_title or "untitled"
    raw_name = raw_name.replace("*", "").strip()
    raw_name = raw_name.replace(" - Notepad", "").replace(" - 记事本", "").strip()
    raw_name = re.sub(r'[<>:"/\\\\|?*]+', "_", raw_name)

    # 🔧 FIX: 对话框标题不能当文件名
    if "另存为" in raw_name or "save as" in raw_name.lower() or not raw_name.strip():
        from datetime import datetime
        raw_name = f"gssu_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"🔧 [REFLEX] 检测到对话框标题污染，使用时间戳文件名: {raw_name}")

    if "." not in raw_name:
        raw_name += ".txt"

    full_path = os.path.join(config.WORKSPACE_DIR, raw_name)
    print(f"🔧 [REFLEX] 保存到工作区: {full_path}")

    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyperclip.copy(full_path)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(2.0)

    hwnd2 = win32gui.GetForegroundWindow()
    title2 = win32gui.GetWindowText(hwnd2)
    if "确认" in title2 or "replace" in title2.lower() or "替换" in title2 or "confirm" in title2.lower():
        print("🔧 [REFLEX] 检测到覆盖确认，按Alt+Y确认")
        pyautogui.hotkey('alt', 'y')
        time.sleep(2.0)

    hwnd3 = win32gui.GetForegroundWindow()
    title3 = win32gui.GetWindowText(hwnd3)
    if "另存为" not in title3 and "save as" not in title3.lower():
        return f"ok:saved:{full_path}"
    else:
        return f"reflex_fail:dialog_still_open:{full_path}"


def goal_flags(goal):
    g = goal.lower()
    return {
        "open_like": any(k in g for k in ["打开", "open"]),
        "type_like": any(k in g for k in ["输入", "键入", "打字", "type", "写", "记录", "填写"]),
        "save_like": any(k in g for k in ["保存", "save"]),
        "is_notepad": any(k in g for k in ["记事本", "notepad", "笔记本"]),
        "read_like": any(k in g for k in ["看", "读", "read", "查看", "读取"]),
        "write_like": any(k in g for k in ["write", "写入"]),
        "edit_like": any(k in g for k in ["改", "修改", "编辑", "替换", "更新", "edit", "modify", "change"]),
        "merge_like": any(k in g for k in ["合并", "merge", "拼接", "combined", "整合"]),
        "compare_like": any(k in g for k in ["对比", "比较", "compare", "diff"]),
        "copy_func_like": any(k in g for k in ["复制到", "拷贝到", "copy to", "移到"]),
    }


def build_signal(obs):
    o = obs.lower()
    if "对话框=另存为" in o or "窗口=另存为" in o or "save as" in o:
        return "SIGNAL: dialog_saveas"
    return ""


def build_stage_summary(phase):
    summaries = {
        "need_open":      "→打开",
        "opened":         "✓打开 | 任务完成",
        "need_focus":     "✓打开 | →聚焦",
        "need_type":      "✓打开 ✓聚焦 | →输入",
        "need_save":      "✓打开 ✓聚焦 ✓输入 | →保存(Ctrl+S)",
        "need_action":    "→执行文件/工具动作",
        "dialog_saveas":  "✓打开 ✓聚焦 ✓输入 ✓Ctrl+S | [系统接管另存为]",
        "saved":          "✓打开 ✓聚焦 ✓输入 ✓保存 | 任务完成",
        "typed":          "✓打开 ✓聚焦 ✓输入 | 任务完成",
    }
    return summaries.get(phase, "")


def resolve_goal_file(goal):
    try:
        import file_memory
        p = file_memory.resolve(goal)
        if p and os.path.isabs(p):
            if os.path.isfile(p):
                print(f"✅ [FILE RESOLVE] {goal[:30]}… → {p}")
                return p
            else:
                print(f"⚠️ [FILE RESOLVE] 记录路径已失效: {p}")

        # 兜底：用最近一次保存的文件，但必须存在
        latest = file_memory.get_latest()
        if latest and os.path.isabs(latest):
            if os.path.isfile(latest):
                print(f"⚠️ [FILE RESOLVE] 弱匹配失败，使用最近文件: {latest}")
                return latest
            else:
                print(f"⚠️ [FILE RESOLVE] 最近文件已失效: {latest}")

        print(f"⚠️ [FILE RESOLVE] 未找到任何可用文件记录")
    except Exception as e:
        print(f"❌ [FILE RESOLVE] file_memory 不可用: {e}")
    return ""


def build_state(goal, history, obs, step, libs, phase, action_subphase=""):
    active = [h for h in history[-MAX_HISTORY:] if h.get("status") != "undone"]
    hist_lines = [f"  {i+1}. {h['act']} → {h['res']}" for i, h in enumerate(active)]
    hist_str = "\n".join(hist_lines) if hist_lines else "  (无)"

    parts = [f"GOAL: {goal}", f"OBS: {obs}"]

    if phase != "need_open":
        parts.append(f"SIGNAL: {phase}")

    summary = build_stage_summary(phase)
    if summary:
        parts.append(f"STAGE: {summary}")

    if phase == "need_action" and action_subphase:
        parts.append(f"ACTION_PHASE: {action_subphase}")

    if phase == "need_action":
        parts.append("HINT: 本任务为纯数据/文件操作，请直接使用 read 或 write 指令，不要打开任何 GUI 窗口。结束后输出 DONE。")

    if phase == "need_type":
        import re
        m = re.search(r"输入(.+?)(?:，|,|然后|并|$)", goal)
        if not m:
            parts.append(f"HINT: 请用 t 指令输入符合目标的内容")

    if phase == "need_open":
        if libs:
            parts.append(f"LIBS: {libs}")
        scan_hint = scanner.get_scan_hint()
        if scan_hint:
            parts.append(scan_hint)

    import worktree
    wt_hint = worktree.get_hint()
    if wt_hint:
        parts.append(wt_hint)

    if phase == "need_action":
        resolved_file = resolve_goal_file(goal)
        if resolved_file and os.path.isabs(resolved_file):
            parts.append(f"FILE_HINT: {resolved_file}")
        else:
            parts.append("FILE_HINT: <none>")

    parts.append(f"HISTORY:\n{hist_str}")
    parts.append(f"STEP: {step}")
    return "\n".join(parts)


def parse_response(text, state_hint="", action_subphase=""):
    import re

    raw_text = text

    # 先裁掉大块规则/示例污染，但保留前面的有效内容
    for marker in ["【状态信号】", "【规则】", "【示例】", "【指令】"]:
        if marker in text:
            text = text.split(marker)[0]

    reason_match = re.search(r"R\s+(.*?)(?:\n|$)", text)
    reason = reason_match.group(1).strip() if reason_match else ""

    # 已完成阶段直接收束
    if state_hint in ("opened", "typed", "saved"):
        return {"reason": reason or "阶段已完成，系统自动收束", "cmd": "DONE"}

    # ─────────────────────────────────────────────
    # 第1层：显式标签提取
    # 支持：
    #   一条指令：f notepad
    #   指令：hk @1+s
    # ─────────────────────────────────────────────
    label_cmd = re.search(r"(?:一条指令|指令)\s*[：:]\s*([^\n]+)", raw_text)
    if label_cmd:
        candidate = label_cmd.group(1).strip()
        if candidate:
            text = text + "\n" + candidate

    # ─────────────────────────────────────────────
    # 第2层：指令：t / write + 内容：...
    # 但只取最后一个内容块，避免误吃示例内容
    # ─────────────────────────────────────────────
    label_heads = re.findall(r"(?:一条指令|指令)\s*[：:]\s*([a-zA-Z]+)\s*$", raw_text, re.MULTILINE)
    if label_heads:
        h = label_heads[-1].strip()

        if h in ("t", "write"):
            # 只取最后一个“内容/文本”块
            content_matches = re.findall(r"(?:内容|文本)\s*[：:]\s*(.+?)(?=\n(?:当前状态|当前判断|一条指令|指令|R\s|【|DONE|$))", raw_text, re.DOTALL)
            if content_matches:
                payload = content_matches[-1].strip()

                for bad_marker in [
                    "\nR ", "\n当前状态", "\n当前判断", "\n【",
                    "\n一条指令", "\n指令", "\n快捷键", "\nDONE"
                ]:
                    if bad_marker in payload:
                        payload = payload.split(bad_marker)[0]

                payload = payload.strip()
                if payload:
                    return {"reason": reason, "cmd": f"{h} {payload}"}

    cmd = ""

    # ─────────────────────────────────────────────
    # 第3层：标准 / 宽松指令匹配
    # ─────────────────────────────────────────────
    for head in VALID_HEADS:
        if head in ("t", "write"):
            # 优先匹配标准顶格格式
            match = re.search(rf"^{head}[\s](.*)", text, re.MULTILINE | re.DOTALL)
            if not match:
                # 宽松匹配：允许前面有“指令：”“一条指令：”等噪音
                match = re.search(rf"(?:^|\n)\s*{head}[\s](.*)", text, re.MULTILINE | re.DOTALL)

            if match:
                payload = match.group(1)

                for bad_marker in [
                    "\nR ", "\n【", "\n当前判断", "\n当前状态", "\n下一步操作",
                    "\n指令：", "\n一条指令：", "\n快捷键：", "\nDONE"
                ]:
                    if bad_marker in payload:
                        payload = payload.split(bad_marker)[0]

                payload = payload.strip()

                if payload.startswith("```"):
                    payload = payload.split("\n", 1)[-1]
                if payload.endswith("```"):
                    payload = payload.rsplit("\n", 1)[0]

                payload = payload.strip()
                if payload:
                    cmd = f"{head} {payload}"
                    break

        else:
            # 标准顶格匹配
            match = re.search(rf"^{head}(?:[\s].*?)?$", text, re.MULTILINE)
            if not match:
                # 宽松匹配：允许行首有少量噪音空白
                match = re.search(rf"(?:^|\n)\s*{head}(?:[\s].*?)?$", text, re.MULTILINE)

            if match:
                cmd = match.group(0).strip()
                # 去掉可能残留的“指令：”
                cmd = re.sub(r"^(?:一条指令|指令)\s*[：:]\s*", "", cmd).strip()
                break

    if not cmd:
        return {"reason": reason, "cmd": ""}

    # ─────────────────────────────────────────────
    # 阶段约束
    # ─────────────────────────────────────────────
    if state_hint == "need_open":
        if cmd.startswith("o "):
            return {"reason": reason, "cmd": cmd}

    elif state_hint == "need_focus":
        if cmd.startswith("f "):
            return {"reason": reason, "cmd": cmd}
        if cmd.startswith("o "):
            fixed = "f " + cmd[2:].strip()
            print(f"🔄 [AUTO FIX] need_focus阶段: o → f")
            return {"reason": reason, "cmd": fixed}

    elif state_hint == "need_type":
        if cmd.startswith("t "):
            return {"reason": reason, "cmd": cmd}

    elif state_hint == "need_save":
        if cmd.startswith("hk "):
            return {"reason": reason, "cmd": cmd}

    elif state_hint == "need_action":
        if action_subphase == "need_read":
            if cmd.startswith("read ") or cmd.startswith("ASK "):
                return {"reason": reason, "cmd": cmd}
            return {"reason": reason, "cmd": ""}

        if action_subphase == "need_answer":
            if cmd.startswith("say ") or cmd == "DONE":
                return {"reason": reason, "cmd": cmd}
            return {"reason": reason, "cmd": ""}

        if action_subphase == "done":
            if cmd == "DONE":
                return {"reason": reason, "cmd": "DONE"}
            return {"reason": reason, "cmd": ""}

    elif state_hint == "dialog_saveas":
        return {"reason": "系统反射接管", "cmd": ""}

    # 通用兜底：尊重阶段
    head = cmd.split()[0]
    if head in VALID_HEADS:
        if state_hint == "need_open" and head != "o":
            return {"reason": reason, "cmd": ""}
        if state_hint == "need_focus" and head not in ("f", "o"):
            return {"reason": reason, "cmd": ""}
        if state_hint == "need_type" and head != "t":
            return {"reason": reason, "cmd": ""}
        if state_hint == "need_save" and head != "hk":
            return {"reason": reason, "cmd": ""}
        return {"reason": reason, "cmd": cmd}

    return {"reason": reason, "cmd": ""}


def is_silent(cmd):
    return any(cmd.startswith(s) for s in SILENT_CMDS)


def judge_change(goal, changes, cmd, result="", old_title="", new_title=""):
    if str(result).startswith("error:"):
        return "error"

    if cmd.strip().startswith("f "):
        if not changes:
            return "silent_ok"
        return "good"

    if "@1+s" in cmd.lower():
        old_dirty = old_title.startswith("*") or old_title.startswith("●")
        new_clean = not (new_title.startswith("*") or new_title.startswith("●"))
        if old_dirty and new_clean:
            return "good"

    if not changes:
        return "silent_ok" if is_silent(cmd) else "no_change"

    SYS_PROCS = {
        "mousocoreworker.exe", "searchprotocolhost.exe", "searchfilterhost.exe",
        "audiodg.exe", "sppsvc.exe", "wuauclt.exe", "taskhostw.exe",
        "runtimebroker.exe", "smartscreen.exe", "backgroundtaskhost.exe",
        "systemsettingsbroker.exe",
        "sdxhelper.exe",
        "dataexchangehost.exe",
        "phoneexperiencehost.exe",
    }
    for c in changes:
        if c.startswith("-进程:"):
            proc_name = c.split(":")[1].strip().lower()
            if proc_name in SYS_PROCS:
                continue
            if not any(k in goal.lower() for k in ["关闭", "删除", "退出", "close", "kill"]):
                return "bad"
        if c.startswith("-文件:"):
            if not any(k in goal.lower() for k in ["关闭", "删除", "退出", "close", "kill"]):
                return "bad"

    return "good"


def auto_recover(judgement):
    if judgement == "bad":
        pyautogui.hotkey('ctrl', 'z')
        time.sleep(0.3)
        return True
    return False


def verify_done(history, initial_snap, current_snap):
    has_real_action = any(
        h.get("status") != "undone"
        and h["act"].split()[0] in ACTION_HEADS
        and str(h["res"]).startswith("ok:")
        for h in history
    )
    has_reflex_ok = any(
        h["act"] == "REFLEX:saveas"
        and str(h["res"]).startswith("ok:")
        and h.get("status") != "undone"
        for h in history
    )
    if not has_real_action and not has_reflex_ok:
        return False, "没有成功执行任何有效动作"

    changes = diff_snapshots(initial_snap, current_snap)
    if changes:
        return True, " | ".join(changes)

    has_ok_change = any(
        str(h["res"]).startswith("ok:") and h.get("status") != "undone"
        for h in history
    )
    if has_ok_change:
        return True, "历史记录确认有成功操作"

    return False, "系统状态与开始时完全相同"


# 已知合法 app 名白名单
_KNOWN_APPS = {
    "notepad", "chrome", "edge", "explorer", "firefox",
    "word", "excel", "powershell", "cmd", "desktop",
    "blender", "code", "pycharm", "everything"
}

def detect_app(obs):
    if "窗口=" in obs:
        after = obs.split("窗口=")[1]
        # 取第一段（空格或"-"前）
        raw = after.split("(")[0].strip()
        # 去掉 Notepad 后缀
        for suffix in [" - Notepad", " - 记事本", " - Google Chrome", " - Microsoft Edge"]:
            if suffix in raw:
                raw = raw.split(suffix)[0].strip()
        # 去掉脏前缀（* 号、路径）
        raw = raw.lstrip("*").strip()
        # 只取第一个词
        first = raw.split()[0] if raw.split() else ""
        first_lower = first.lower()
        # 白名单检查
        if first_lower in _KNOWN_APPS:
            return first_lower
        # 路径形式（含 \ 或 /）→ 降级到 desktop
        if "\\" in first or "/" in first or ":" in first:
            return "desktop"
        # 含中文、含点、含括号 → 不是 app 名 → desktop
        import re
        if re.search(r'[\u4e00-\u9fff.()（）]', first):
            return "desktop"
        # 其他未知英文 → 原样返回（保守）
        if first_lower:
            return first_lower
    return "desktop"


def is_open_goal_done(goal, obs, cmd):
    g = goal.lower()
    o = obs.lower()
    c = cmd.lower().strip()

    open_like = any(k in g for k in ["打开", "open"])
    if not open_like:
        return False
    if not c.startswith("o "):
        return False

    app = c[2:].strip()
    if app and app in o:
        return True
    if ("记事本" in g or "笔记本" in g) and "notepad" in o:
        return True
    if "浏览器" in g and ("chrome" in o or "edge" in o or "browser" in o):
        return True

    return False


def is_type_goal_done(goal, obs, cmd, history):
    if "另存为" in obs or "save as" in obs.lower() or "对话框=另存为" in obs:
        return False

    g = goal.lower()
    c = cmd.lower().strip()

    type_like = any(k in g for k in ["输入", "键入", "打字", "type", "写", "记录", "填写"])
    if not type_like:
        return False
    if not c.startswith("t "):
        return False

    typed_same = any(
        h.get("status") != "undone"
        and h["act"].strip().lower() == c
        and str(h["res"]).startswith("ok:")
        for h in history
    )
    return typed_same


def is_focus_stage_done(goal, obs, cmd, history):
    g = goal.lower()
    c = cmd.lower().strip()

    type_like = any(k in g for k in ["输入", "键入", "打字", "type", "写", "记录", "填写"])
    if not type_like:
        return False
    if not c.startswith("f "):
        return False

    focused_same = any(
        h.get("status") != "undone"
        and h["act"].strip().lower() == c
        and (
            h["res"] == "silent_ok"
            or str(h["res"]).startswith("ok:")
        )
        for h in history
    )
    return focused_same


def advance_phase(goal, phase, cmd, obs_after=""):
    flags = goal_flags(goal)
    c = cmd.lower().strip()
    o = (obs_after or "").lower()

    if phase == "need_action":
        return "need_action"

    if c.startswith("o "):
        if flags["type_like"]:
            return "need_focus"
        return "opened"

    if c.startswith("f "):
        if flags["type_like"]:
            return "need_type"
        return "opened"

    if c.startswith("t "):
        if flags["save_like"]:
            return "need_save"
        return "typed"

    if c.startswith("hk ") and "@1+s" in c:
        if "对话框=另存为" in o or "窗口=另存为" in o or "save as" in o:
            return "dialog_saveas"
        return "saved"

    if cmd == "REFLEX:saveas":
        return "saved"

    return phase


def agent_loop(goal):
    history = []
    step = 1
    edit_mode = None
    initial_snap = take_snapshot()
    prev_title = initial_snap.get('title', '')
    flags = goal_flags(goal)
    action_subphase = "need_read" if flags["read_like"] else ""
    
    if flags["read_like"] or flags["write_like"] or flags["edit_like"] or flags.get("merge_like") or flags.get("compare_like") or flags.get("copy_func_like"):
        phase = "need_action"
        if flags["edit_like"] or flags.get("copy_func_like"):
            action_subphase = "need_read"
        elif flags.get("merge_like") or flags.get("compare_like"):
            action_subphase = "need_read"
    else:
        phase = "need_open"

    print(f"\n{'='*50}")
    print(f"🚀 [GSS-OS] 启动任务: {goal}")
    print(f"{'='*50}")

    pre_obs = get_observation()
    pre_snap = initial_snap
    env_facts = []

    if flags["is_notepad"]:
        np_windows = [w for w in pre_snap["windows"] if "notepad" in w.lower()]
        if np_windows:
            env_facts.append(f"已有记事本窗口:{np_windows[0]}")
        else:
            env_facts.append("无记事本窗口")

    IGNORE_EXT = {".lnk", ".ini", ".tmp"}
    for fp, mt in pre_snap["files"].items():
        ext = os.path.splitext(fp)[1].lower()
        if ext not in IGNORE_EXT and os.path.isfile(fp):
            env_facts.append(f"磁盘已有:{os.path.basename(fp)}")

    if env_facts:
        print(f"🔎 [PRE-CHECK] {' | '.join(env_facts)}")

    import worktree
    wt_data = worktree._load()
    mem_resolved = False
    for entry in wt_data:
        if entry.get("result") != "done":
            continue
        old_goal = entry.get("goal", "").lower()
        new_goal = goal.lower()
        is_similar = (old_goal == new_goal) or (new_goal in old_goal) or (old_goal in new_goal)
        if is_similar and entry.get("count", 1) >= 1:
            final_obs = entry.get("final_obs", "")
            import re
            old_fname = entry.get("saved_file", "")
            all_files = entry.get("all_files", [])
            if not old_fname:
                m = re.search(r"窗口=([^\|]+)", final_obs)
                if m:
                    old_title = m.group(1).strip()
                    old_fname = old_title.split(" - ")[0].strip() if " - " in old_title else ""

            candidate_files = []
            if old_fname:
                candidate_files.append(old_fname)
            for f in all_files:
                if f and f not in candidate_files:
                    candidate_files.append(f)

            found_name = ""
            for cand in candidate_files:
                if any(cand in w for w in initial_snap.get("windows", [])):
                    found_name = cand
                    break

            if found_name:
                print(f"🔎 [MEM CHECK] 发现相关旧产物: {found_name}")
                choice = input(f"❓ 上次已完成'{entry.get('goal','')}' (文件:{found_name})，要新建还是继续编辑？[N新建/E编辑]: ").strip().upper()
                if choice == "E":
                    phase = "need_focus"
                    edit_mode = "append"
                    print(f"📌 [MEM] 用户选择编辑旧文件，追加模式")
                mem_resolved = True
                break

            for fp in initial_snap.get("files", {}):
                basename = os.path.basename(fp)
                matched = ""
                for cand in candidate_files:
                    if cand and cand in basename:
                        matched = basename
                        break
                if matched:
                    print(f"🔎 [MEM CHECK] 磁盘发现旧文件: {matched}")
                    choice = input(f"❓ 上次已完成'{entry.get('goal','')}' (文件:{matched})，要新建还是继续编辑？[N新建/E编辑]: ").strip().upper()
                    if choice == "E":
                        phase = "need_focus"
                        edit_mode = "append"
                        print(f"📌 [MEM] 用户选择编辑旧文件，追加模式")
                    mem_resolved = True
                    break

            if mem_resolved:
                break

    # fallback：对任意"记事本 + 写/输入 + 保存"任务，如果最近有保存文件，就询问【新建 / 编辑】
    if (not mem_resolved) and flags["is_notepad"] and flags["type_like"] and flags["save_like"]:
        recent_entry = None
        for entry in reversed(wt_data):
            if entry.get("result") != "done":
                continue
            sf = entry.get("saved_file", "")
            sp = entry.get("saved_path", "")
            if sf and sp and os.path.isfile(sp):
                recent_entry = entry
                break
            elif sf and sp and not os.path.isfile(sp):
                print(f"⚠️ [MEM CHECK] 跳过失效文件: {sf} | {sp}")

        if recent_entry:
            sf = recent_entry.get("saved_file", "")
            sp = recent_entry.get("saved_path", "")
            old_goal_text = recent_entry.get("goal", "")
            print(f"🔎 [MEM CHECK] 发现最近文件: {sf}")
            choice = input(
                f"❓ 检测到最近文件 '{sf}'（来自任务: {old_goal_text[:20]}），要新建还是继续编辑？[N新建/E编辑]: "
            ).strip().upper()

            if choice == "E":
                if not sp or not os.path.isfile(sp):
                    print(f"⚠️ [MEM] 目标文件已不存在，自动改为新建: {sp}")
                    phase = "need_open"
                    action_subphase = ""
                    flags["edit_like"] = False
                    print("📌 [MEM] 已切换为新建模式")
                else:
                    try:
                        import file_memory
                        file_memory.record(goal, sp, aliases=["最近文件", "刚才的文件"])
                    except Exception as e:
                        print(f"⚠️ [MEM CHECK] 临时绑定失败: {e}")

                    phase = "need_action"
                    action_subphase = "need_read"
                    flags["edit_like"] = True
                    print(f"📌 [MEM] 用户选择编辑旧文件，将进入 read→edit→write 流")
            else:
                print("📌 [MEM] 用户选择新建文件")

        mem_resolved = True

    while step <= MAX_STEPS:
        # 连续失败检测（INVALID 或 no_change 都算）
        consec_fail = 0
        for h in reversed(history):
            act = h["act"]
            res = str(h.get("res", ""))
            if act == "INVALID" or res == "no_change" or res.startswith("error:"):
                consec_fail += 1
            else:
                break
        if consec_fail >= 5:
            print(f"🛑 [GIVE UP] 连续 {consec_fail} 次失败，系统放弃")
            print(f"🗣️ [SAY] 抱歉，我无法完成「{goal[:20]}」，请换一种方式描述。")
            break

        obs = get_observation()
        env_signal = build_signal(obs)

        # 补丁 A：need_focus 快捷放行
        if phase == "need_focus":
            obs_low = obs.lower()
            if flags["is_notepad"] and "notepad" in obs_low:
                print("✅ [AUTO SKIP] 当前已在记事本前台，跳过 focus")
                history.append({"act": "f notepad", "res": "auto_skip:focus_already_ok", "status": "undone"})
                phase = "need_type"
                step += 1
                continue

        if env_signal == "SIGNAL: dialog_saveas":
            phase = "dialog_saveas"

        if phase == "dialog_saveas":
            print(f"\n📦 [STATE {step}] OBS: {obs}")
            print("🔧 [REFLEX] 另存为对话框 → 系统接管")
            reflex_result = handle_saveas_reflex(prev_title)
            print(f"DEBUG reflex_result={reflex_result}")
            if reflex_result.startswith("ok:"):
                history.append({"act": "REFLEX:saveas", "res": reflex_result, "status": "active"})
                phase = "saved"
            else:
                history.append({"act": "REFLEX:saveas", "res": reflex_result, "status": "undone"})
            print(f"🔧 [REFLEX RESULT] {reflex_result}")
            new_snap = take_snapshot()
            prev_title = new_snap.get('title', '')
            step += 1
            continue

        # 🔧 FIX: need_answer 阶段，系统直接从 read 结果生成答案或执行编辑
        if phase == "need_action" and action_subphase == "need_answer":
            read_content = ""
            for h in history:
                if h.get("status") == "active" and h["act"].startswith("read ") and str(h["res"]).startswith("ok:"):
                    read_content = str(h["res"])
                    break

            if read_content:
                try:
                    from openai import OpenAI
                    import config
                    _client = OpenAI(api_key=config.OPENAI_KEY, base_url=config.OPENAI_BASE_URL)

                    # merge / compare 共用多文件读取路径
                    if flags.get("merge_like", False) or flags.get("compare_like", False):
                        import re as _re
                        
                        # 从 file_memory 里找所有相关文件
                        import file_memory as _fm
                        all_goals = _fm._load().get("by_goal", {})
                        
                        # 提取 goal 里的关键词，匹配多个文件
                        contents = []
                        matched_files = []
                        keywords = ["计算器", "排序", "诗"]
                        for kw in keywords:
                            if kw in goal:
                                for g_key, path in all_goals.items():
                                    if kw in g_key and path not in matched_files:
                                        try:
                                            with open(path, "r", encoding="utf-8") as _f:
                                                c = _f.read()
                                            contents.append(f"# === {kw}代码 ===\n{c}")
                                            matched_files.append(path)
                                            print(f"📂 [MERGE] 读取: {path}")
                                        except Exception as e:
                                            print(f"⚠️ [MERGE] 读取失败: {path} → {e}")
                                        break
                        
                        if contents:
                            if flags.get("compare_like", False):
                                # 对比模式：提取大纲并回答
                                from extractor import extract_outline
                                report_parts = []
                                for i, (path, content_text) in enumerate(zip(matched_files, contents)):
                                    _basename = path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
                                    outline = extract_outline(content_text.split("===\n", 1)[-1] if "===" in content_text else content_text)
                                    report_parts.append(f"{_basename}: {outline if outline else '无函数'}")
                                report = "\n".join(report_parts)
                                print(f"🗣️ [COMPARE] {report}")
                                history.append({"act": f"say {report}", "res": "delivered", "status": "active"})
                                action_subphase = "done"
                                print("✅ [COMPARE DONE] 对比完成")
                                try:
                                    import worktree
                                    final_obs = get_observation()
                                    worktree.record(goal, "compare→say", "done", final_obs)
                                except Exception:
                                    pass
                                break
                            else:
                                # 合并模式：原来的 merge 逻辑
                                merged = "\n\n".join(contents)
                                # 确定输出路径
                                import re as _re2
                                fname_match = _re2.search(r'(\w+\.py|\w+\.txt)', goal)
                                if fname_match:
                                    out_name = fname_match.group(1)
                                else:
                                    out_name = "combined.py"
                                out_path = f"C:\\Users\\rwxh5\\Documents\\GSSU_WORK\\{out_name}"
                                
                                from executor import run_cmd as _exec
                                write_result = _exec(f"write {out_path}|{merged}")
                                print(f"📝 [MERGE] 已合并写入: {write_result}")
                                _basename = out_path.rsplit("\\", 1)[-1]
                                history.append({"act": f"write {_basename}", "res": write_result, "status": "active"})
                                action_subphase = "done"
                                
                                # 记录到 file_memory
                                try:
                                    _fm.record(goal, out_path, aliases=[out_name, "合并文件"])
                                except Exception:
                                    pass
                                
                                print(f"✅ [MERGE DONE] 合并完成: {matched_files} → {out_path}")
                                try:
                                    import worktree
                                    final_obs = get_observation()
                                    worktree.record(goal, "merge→write", "done", final_obs,
                                                   saved_file=_basename, saved_path=out_path)
                                except Exception:
                                    pass
                                break
                        else:
                            print("⚠️ [MERGE] 未找到可合并的文件，降级为普通 edit")

                    if flags.get("copy_func_like", False):
                        import re as _re
                        import file_memory as _fm
                        from extractor import read_function
                        
                        # 提取函数名
                        func_match = _re.search(r'(\w+)\s*函数', goal)
                        target_func = func_match.group(1) if func_match else ""
                        
                        # 从 goal 里找源文件和目标文件
                        all_goals = _fm._load().get("by_goal", {})
                        source_path = ""
                        dest_path = ""
                        for kw in ["计算器", "排序", "诗"]:
                            if kw in goal:
                                for g_key, path in all_goals.items():
                                    if kw in g_key:
                                        if not source_path:
                                            source_path = path
                                        break
                        # "到排序/到计算器" → 目标文件
                        dest_match = _re.search(r'到([\u4e00-\u9fff]+?)(?:代码|文件|里)', goal)
                        if dest_match:
                            dest_kw = dest_match.group(1)
                            for g_key, path in all_goals.items():
                                if dest_kw in g_key and path != source_path:
                                    dest_path = path
                                    break
                        
                        if source_path and dest_path and target_func:
                            # 读源文件
                            src_code = open(source_path, "r", encoding="utf-8").read()
                            func_code = read_function(src_code, target_func)
                            if func_code:
                                # 读目标文件并追加
                                dst_code = open(dest_path, "r", encoding="utf-8").read()
                                new_dst = dst_code.rstrip() + "\n\n" + func_code + "\n"
                                from executor import run_cmd as _exec
                                write_result = _exec(f"write {dest_path}|{new_dst}")
                                _basename = dest_path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
                                print(f"📝 [COPY FUNC] {target_func} → {_basename}: {write_result}")
                                history.append({"act": f"write {_basename}", "res": write_result, "status": "active"})
                                action_subphase = "done"
                                print(f"✅ [COPY FUNC DONE] {target_func} 已复制到 {_basename}")
                                try:
                                    import worktree
                                    final_obs = get_observation()
                                    worktree.record(goal, "copy_func→write", "done", final_obs)
                                except Exception:
                                    pass
                                break
                        print(f"⚠️ [COPY FUNC] 无法定位源/目标: src={source_path} dst={dest_path} func={target_func}")

                    if flags.get("edit_like", False):
                        # 尝试从 goal 里提取目标函数名
                        import re as _re
                        # 方法1：找"XXX函数"前面的英文词
                        func_match = _re.search(r'(\w+)\s*函数', goal)
                        if not func_match:
                            # 方法2：找"修改/改 XXX"的英文词
                            func_match = _re.search(r'(?:修改|改|更新|edit|modify)\s+(\w+)', goal)
                        target_func = func_match.group(1) if func_match else ""
                        # 过滤掉非函数名的词
                        if target_func in ("函数", "代码", "文件", "里", "的"):
                            target_func = ""

                        # 提取原始代码（去掉 ok:lines 1-N 前缀）
                        raw_code = read_content
                        if raw_code.startswith("ok:"):
                            raw_code = "\n".join(raw_code.splitlines()[1:])

                        # 如果找到目标函数，只读取那个函数
                        from extractor import read_function, replace_function
                        if target_func:
                            func_text = read_function(raw_code, target_func)
                            context_for_model = func_text if func_text else raw_code
                            print(f"🎯 [P5] 定位到函数 {target_func}:\n{context_for_model}")
                        else:
                            context_for_model = raw_code
                            print(f"⚠️ [P5] 未提取到函数名，使用全文")

                        # 调模型生成新函数
                        _resp = _client.chat.completions.create(
                            model=config.OPENAI_MODEL,
                            messages=[
                                {"role": "system", "content": "你是代码修改器。根据用户要求修改函数。只输出修改后的完整函数代码，不要解释，不要加```标记，不要输出其他函数。"},
                                {"role": "user", "content": f"原始函数:\n{context_for_model}\n\n修改要求: {goal}"}
                            ],
                            max_tokens=300,
                            temperature=0.0
                        )
                        new_func = _resp.choices[0].message.content.strip()
                        if new_func.startswith("```"):
                            new_func = new_func.split("\n", 1)[-1]
                        if new_func.endswith("```"):
                            new_func = new_func.rsplit("\n", 1)[0]
                        new_func = new_func.strip()

                        if new_func:
                            real_file = resolve_goal_file(goal)
                            if real_file:
                                from executor import run_cmd as _exec
                                # 精准替换：如果有目标函数，只替换那个函数
                                if target_func and read_function(raw_code, target_func):
                                    final_code = replace_function(raw_code, target_func, new_func)
                                    print(f"🎯 [P5] 精准替换函数 {target_func}")
                                else:
                                    final_code = new_func
                                    print(f"⚠️ [P5] 全文替换")
                                write_result = _exec(f"write {real_file}|{final_code}")
                                print(f"📝 [AUTO EDIT] 已写入: {write_result}")
                                _basename = real_file.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
                                history.append({"act": f"write {_basename}", "res": write_result, "status": "active"})
                                action_subphase = "done"
                                print(f"✅ [AUTO DONE] 编辑任务完成 (read→edit→write)")
                                print(f"📄 新代码:\n{final_code}")
                                try:
                                    import worktree
                                    final_obs = get_observation()
                                    worktree.record(goal, "read→write", "done", final_obs,
                                                    saved_file=real_file.rsplit("\\", 1)[-1].rsplit("/", 1)[-1],
                                                    saved_path=real_file)
                                except Exception:
                                    pass
                                break
                            else:
                                print("⚠️ [AUTO EDIT] 无法确定写入路径，降级为 say")
                    
                    # 回答任务（非编辑）
                    _resp = _client.chat.completions.create(
                        model=config.OPENAI_MODEL,
                        messages=[
                            {"role": "system", "content": "你是代码分析助手。根据代码内容直接回答问题。只输出答案，不要解释过程。"},
                            {"role": "user", "content": f"代码内容:\n{read_content}\n\n问题: {goal}"}
                        ],
                        max_tokens=100,
                        temperature=0.0
                    )
                    answer = _resp.choices[0].message.content.strip()
                    if answer:
                        print(f"🗣️ [AUTO ANSWER] {answer}")
                        history.append({"act": f"say {answer}", "res": "delivered", "status": "active"})
                        action_subphase = "done"
                        print("✅ [AUTO DONE] 文件任务已完成 (read→auto_answer→done)")
                        try:
                            import worktree
                            final_obs = get_observation()
                            worktree.record(goal, "read→say", "done", final_obs)
                        except Exception:
                            pass
                        break
                except Exception as e:
                    print(f"⚠️ [AUTO ANSWER/EDIT FAIL] {e}, 降级让模型尝试")

        current_app = detect_app(obs)
        libs = get_libs_hint(current_app)
        state = build_state(goal, history, obs, step, libs, phase, action_subphase)

        print(f"\n📦 [STATE {step}]\n{state}")

        response = ask(state)
        print(f"🔍 [RAW] {repr(response)}")

        if response["text"].startswith("[API Error]"):
            print(f"❌ [API ERROR] {response['text']}")
            break

        parsed = parse_response(response["text"], state_hint=phase, action_subphase=action_subphase)
        reason, cmd = parsed["reason"], parsed["cmd"]

        if reason:
            print(f"💡 [R] {reason}")

        if phase == "need_action" and action_subphase == "need_read":
            real_file = resolve_goal_file(goal)
            if real_file and (real_file[1:3] == ":\\" or real_file.startswith("/")):
                cmd = f"read {real_file}|1-40"
                reason = "系统使用真实文件路径"
                print(f"🔄 [FILE MEMORY] 强制读取真实路径: {cmd}")

        if not cmd:
            if phase == "need_type":
                if "hello world" in goal.lower() or "helloworld" in goal.lower():
                    cmd = 't print("Hello, World!")'
                    print(f"🔄 [AUTO GEN] Hello World 快速生成: {cmd}")
                else:
                    import re
                    m = re.search(r"输入(.+?)(?:，|,|然后|并|$)", goal)
                    if m:
                        auto_text = m.group(1).strip()
                        cmd = f"t {auto_text}"
                        print(f"🔄 [AUTO GEN] 模型无法输出t，系统自动生成: {cmd}")
                    else:
                        consec = 0
                        for h in reversed(history):
                            act = h["act"]
                            res = str(h.get("res", ""))
                            if act == "INVALID" or "auto_skip" in res:
                                consec += 1
                            else:
                                break

                        if consec >= 2:
                            print("🔄 [CONTENT GEN] 模型无法输出t，系统单独请求生成内容")
                            from openai import OpenAI
                            import config
                            _client = OpenAI(api_key=config.OPENAI_KEY, base_url=config.OPENAI_BASE_URL)

                            import re as _re
                            content_desc = _re.sub(r"(帮我|请|用记事本|打开记事本|并保存|然后保存|保存)", "", goal).strip()
                            if not content_desc:
                                content_desc = goal
                            _gen_resp = _client.chat.completions.create(
                                model=config.OPENAI_MODEL,
                                messages=[
                                    {"role": "system", "content": "你是文本生成器。用户说什么你就直接输出对应内容。不要解释，不要加前缀，不要说'好的'，直接输出文本本身。"},
                                    {"role": "user", "content": content_desc}
                                ],
                                max_tokens=60,
                                temperature=0.7
                            )
                            gen_text = _gen_resp.choices[0].message.content.strip()
                            if gen_text and not gen_text.startswith("["):
                                if gen_text.startswith("```"):
                                    gen_text = gen_text.split("\n", 1)[-1]
                                if gen_text.endswith("```"):
                                    gen_text = gen_text.rsplit("\n", 1)[0]
                                gen_text = gen_text.strip('"\'')
                                cmd = f"t {gen_text}"
                                print(f"🔄 [CONTENT GEN] 生成内容: {gen_text[:50]}...")
                            else:
                                print("⚠️ [CONTENT GEN] 生成失败，等待重试")
                                history.append({"act": "INVALID", "res": f"content_gen_failed", "status": "undone"})
                                step += 1
                                continue
                        else:
                            print("⚠️ [NEED TYPE] 无法提取输入内容，等待模型生成")
                            history.append({"act": "INVALID", "res": f"need model to generate content for:{goal}", "status": "undone"})
                            step += 1
                            continue
            elif phase == "need_save":
                cmd = "hk @1+s"
                print(f"🔄 [AUTO GEN] 模型无法输出保存指令，系统自动生成: {cmd}")
            elif phase == "need_focus":
                consec = 0
                for h in reversed(history):
                    if h["act"] == "INVALID":
                        consec += 1
                    else:
                        break
                if consec >= 2:
                    app_kw = "notepad" if flags["is_notepad"] else ""
                    if not app_kw:
                        import re as _re
                        m = _re.search(r"打开(.*?)(?:，|,|然后|并|$)", goal)
                        if m:
                            app_kw = m.group(1).strip()
                    if app_kw:
                        cmd = f"f {app_kw}"
                        print(f"🔄 [AUTO GEN] 模型无法输出聚焦指令，系统强制生成: {cmd}")
                    else:
                        print("⚠️ [INVALID] 无法提取聚焦目标")
                        history.append({"act": "INVALID", "res": f"no target for stage:{phase}", "status": "undone"})
                        step += 1
                        continue
                else:
                    print("⚠️ [INVALID] 无合法指令（可能阶段约束拒绝）")
                    history.append({"act": "INVALID", "res": f"no valid cmd for stage:{phase}", "status": "undone"})
                    step += 1
                    continue
            elif phase == "need_open":
                consec = 0
                for h in reversed(history):
                    if h["act"] == "INVALID":
                        consec += 1
                    else:
                        break
                if consec >= 3:
                    # 从 goal 里提取可能的应用名（英文词优先）
                    import re as _re
                    eng_words = _re.findall(r'[a-zA-Z]\w+', goal)
                    if eng_words:
                        app_name = eng_words[0]
                        cmd = f"o {app_name}"
                        print(f"🔄 [AUTO GEN] 系统强制尝试打开: {cmd}")
                    else:
                        print(f"🛑 [GIVE UP] 无法从目标中提取应用名")
                        break
                else:
                    print("⚠️ [INVALID] 无合法指令（可能阶段约束拒绝）")
                    history.append({"act": "INVALID", "res": f"no valid cmd for stage:{phase}", "status": "undone"})
                    step += 1
                    continue
            elif phase == "need_action":
                real_file = resolve_goal_file(goal)
                if action_subphase == "need_read":
                    if real_file and (real_file[1:3] == ":\\" or real_file.startswith("/")):
                        cmd = f"read {real_file}|1-40"
                        print(f"🔄 [AUTO GEN] 使用真实文件路径读取: {cmd}")
                    else:
                        cmd = "ASK 我没有找到刚才保存文件的真实路径，请输入完整路径"
                        print("❓ [ASK ROUTE] 缺少真实文件路径，改为询问用户")
                else:
                    print("⚠️ [INVALID] 无合法指令（可能阶段约束拒绝）")
                    history.append({"act": "INVALID", "res": f"no valid cmd for stage:{phase}", "status": "undone"})
                    step += 1
                    continue
            else:
                print("⚠️ [INVALID] 无合法指令（可能阶段约束拒绝）")
                history.append({"act": "INVALID", "res": f"no valid cmd for stage:{phase}", "status": "undone"})
                step += 1
                continue

        print(f"⚡ [CMD] {cmd}")

        if is_open_goal_done(goal, obs, cmd):
            print("✅ [AUTO SKIP] 打开阶段已达成，跳过重复 open")
            history.append({"act": cmd, "res": "auto_skip:open_done", "status": "undone"})
            phase = advance_phase(goal, phase, cmd, obs)
            step += 1
            continue

        if is_focus_stage_done(goal, obs, cmd, history):
            print("✅ [AUTO SKIP] 聚焦阶段已达成，跳过重复 focus")
            history.append({"act": cmd, "res": "auto_skip:focus_done", "status": "undone"})
            phase = advance_phase(goal, phase, cmd, obs)
            step += 1
            continue

        if is_type_goal_done(goal, obs, cmd, history):
            print("✅ [AUTO SKIP] 输入阶段已达成，跳过重复输入")
            history.append({"act": cmd, "res": "auto_skip:type_done", "status": "undone"})
            phase = advance_phase(goal, phase, cmd, obs)
            step += 1
            continue

        head = cmd.strip().split()[0]

        if head == "DONE":
            consec_done_rejected = sum(
                1 for h in history
                if h["act"] == "DONE(rejected)" and h.get("status") == "undone"
            )
            if consec_done_rejected >= 3:
                print(f"🛑 [GIVE UP] DONE 连续被拒 {consec_done_rejected} 次")
                print(f"🗣️ [SAY] 任务遇到问题，我已停止：{goal[:20]}")
                break

            if phase in ("need_open", "need_focus", "need_type", "need_save", "dialog_saveas"):
                print(f"⛔ [DONE 被拒] 当前阶段未完成: {phase}")
                history.append({"act": "DONE(rejected)", "res": phase, "status": "undone"})
                step += 1
                continue

            current_snap = take_snapshot()
            passed, detail = verify_done(history, initial_snap, current_snap)
            if passed:
                print(f"✅ [DONE] 系统验证通过")
                print(f"📸 [总变化] {detail}")
                try:
                    learn_from_history(goal, history, current_app)
                except Exception as e:
                    print(f"⚠️ [MEMORY SAVE ERROR] {e}")
                    
                try:
                    import worktree
                    from extractor import extract_outline
                    
                    abstracted_steps = []
                    targets = set()
                    file_outlines = {}
                    
                    if current_app and current_app != "desktop":
                        targets.add(current_app)

                    for h in history:
                        if h.get("status") != "active":
                            continue
                        act = h["act"]
                        if act.startswith("t "):
                            payload = act[2:]
                            abstracted_steps.append(f"t <{len(payload)}字>")
                            outline = extract_outline(payload)
                            if outline:
                                file_outlines["current_edit"] = outline
                        elif act.startswith("write "):
                            parts = act[6:].split("|", 1)
                            path = parts[0].strip()
                            payload = parts[1].strip() if len(parts) > 1 else ""
                            targets.add(os.path.basename(path))
                            abstracted_steps.append(f"write {os.path.basename(path)}")
                            outline = extract_outline(payload)
                            if outline:
                                file_outlines[os.path.basename(path)] = outline
                        elif act.startswith("read "):
                            path = act[5:].split("|")[0].strip()
                            targets.add(os.path.basename(path))
                            abstracted_steps.append(f"read {os.path.basename(path)}")
                        else:
                            abstracted_steps.append(act)

                    steps_str = " → ".join(abstracted_steps)
                    final_obs = get_observation()

                    import re as _re
                    _fm = _re.search(r"窗口=([^\|]+)", final_obs)
                    saved_file = ""
                    saved_path = ""

                    for h in reversed(history):
                        if h["act"] == "REFLEX:saveas" and str(h["res"]).startswith("ok:saved:"):
                            saved_path = str(h["res"]).split("ok:saved:", 1)[1].strip()
                            saved_file = os.path.basename(saved_path)
                            break

                    if not saved_file and _fm:
                        _title = _fm.group(1).strip()
                        if " - Notepad" in _title:
                            saved_file = _title.split(" - Notepad")[0].strip()

                    print(f"DEBUG saved_file={saved_file} | saved_path={saved_path}")

                    if saved_file:
                        targets.add(saved_file)
                        if "current_edit" in file_outlines:
                            file_outlines[saved_file] = file_outlines.pop("current_edit")

                    outline_hint = ""
                    if file_outlines:
                        outline_hint = " " + " ".join([v for v in file_outlines.values()])

                    worktree.record(
                        goal,
                        steps_str + outline_hint,
                        "done",
                        final_obs,
                        saved_file=saved_file,
                        saved_path=saved_path,
                        targets=list(targets)
                    )

                    try:
                        import file_memory
                        aliases = []
                        g = goal.lower()
                        if "计算器" in g and "代码" in g:
                            aliases += ["计算器代码", "刚才保存的计算器代码", "上次保存的计算器代码"]
                        if "诗" in g:
                            aliases += ["诗", "刚才保存的诗", "上次保存的诗"]

                        print(f"DEBUG file_memory about to record: goal={goal} | path={saved_path}")

                        if saved_path:
                            file_memory.record(goal, saved_path, aliases=aliases)
                        else:
                            print("DEBUG file_memory skipped: saved_path empty")
                    except Exception as e:
                        print(f"⚠️ [FILE MEMORY ERROR] {e}")

                except Exception as e:
                    print(f"⚠️ [WORKTREE ERROR] {e}")

                break
            else:
                # 补充：如果 phase 已经是 opened/saved/typed，允许放行
                if phase in ("opened", "saved", "typed"):
                    import re as _re
                    eng_words = _re.findall(r'[a-zA-Z]\w+', goal)
                    app_name = eng_words[0].lower() if eng_words else ""
                    current_title = get_observation()
                    if app_name and app_name in current_title.lower():
                        # 检查是不是 cmd 伪装的
                        import win32gui as _wg
                        fg_hwnd = _wg.GetForegroundWindow()
                        fg_class = _wg.GetClassName(fg_hwnd)
                        if "console" in fg_class.lower() or "cmd" in fg_class.lower():
                            pyautogui.hotkey("alt", "f4")
                            time.sleep(0.5)
                            print(f"🔧 [CLEANUP] 已关闭意外打开的 CMD 窗口: {app_name}")
                    print(f"✅ [DONE] 阶段已完成 ({phase})，允许放行")
                    break
                has_say = any(h["act"].startswith("say ") and h.get("status") != "undone" for h in history)
                if has_say:
                    print(f"✅ [DONE] 聊天任务完成")
                    break
                print(f"⛔ [DONE 被拒] {detail}")
                history.append({"act": "DONE(rejected)", "res": detail, "status": "undone"})
                step += 1
                continue

        elif head == "ASK":
            question = cmd[4:].strip()
            answer = input(f"❓ [ASK] {question}\n> ")
            history.append({"act": cmd, "res": f"user: {answer}", "status": "active"})

        elif head == "VISION":
            vis = get_observation()
            print(f"👁️ [VISION] {vis}")
            history.append({"act": cmd, "res": vis, "status": "active"})

        elif head == "say":
            msg = cmd[4:].strip()
            print(f"🗣️ [SAY] {msg}")
            history.append({"act": cmd, "res": "delivered", "status": "active"})
            if phase == "need_action" and action_subphase == "need_answer":
                action_subphase = "done"

            # 🔧 FIX: need_action 任务中 say 完成后，系统自动收束
            if phase == "need_action" and action_subphase == "done":
                print("✅ [AUTO DONE] 文件任务已完成 (read→say→done)，系统自动收束")
                try:
                    import worktree
                    final_obs = get_observation()
                    worktree.record(goal, "read→say", "done", final_obs)
                except Exception:
                    pass
                break

        elif head == "ld":
            ref = cmd[3:].strip()
            keys_seq = execute_ld(ref)
            if not keys_seq or keys_seq.startswith("error"):
                print(f"❌ [LD FAIL] {keys_seq}")
                history.append({"act": cmd, "res": keys_seq or "not found", "status": "undone"})
                parts = ref.split(".", 1)
                if len(parts) == 2:
                    record_fail(parts[0], parts[1])
            else:
                result = run_and_diff(keys_seq)
                changes = result.replace("ok: ", "").split(" | ") if result.startswith("ok:") else []
                new_snap = take_snapshot()
                new_title = new_snap.get('title', '')
                judgement = judge_change(goal, changes, keys_seq, result, prev_title, new_title)
                prev_title = new_title

                if auto_recover(judgement):
                    print(f"🔄 [AUTO UNDO] 库调用结果异常，已撤销")
                    history.append({"act": cmd, "res": "auto_undo", "status": "undone"})
                    parts = ref.split(".", 1)
                    if len(parts) == 2:
                        record_fail(parts[0], parts[1])
                else:
                    print(f"✅ [LD → {keys_seq}] {result}")
                    history.append({"act": cmd, "res": result, "status": "active"})
                    parts = ref.split(".", 1)
                    if len(parts) == 2:
                        record_success(parts[0], parts[1], keys_seq)

        elif head in ACTION_HEADS:
            exec_cmd = cmd.strip()

            if exec_cmd.startswith("t ") and edit_mode == "append":
                new_text = exec_cmd[2:]
                import pyautogui as _pag
                import pyperclip as _pc
                _pag.hotkey("ctrl", "a")
                time.sleep(0.1)
                _pag.hotkey("ctrl", "c")
                time.sleep(0.1)
                old_text = _pc.paste()
                combined = old_text + "\n" + new_text
                exec_cmd = f"t {combined}"
                edit_mode = None
                print(f"📌 [APPEND] 旧内容({len(old_text)}字) + 新内容 → 合并写入")

            if exec_cmd.startswith("hk ") and "@1+s" in exec_cmd.lower():
                import win32gui as _wg
                fg_title = _wg.GetWindowText(_wg.GetForegroundWindow()).lower()
                goal_is_notepad = any(k in goal.lower() for k in ["记事本", "notepad"])
                if goal_is_notepad and "notepad" not in fg_title:
                    print(f"⚠️ [FOCUS GUARD] 保存前焦点不在记事本，自动聚焦")
                    run_cmd("f notepad")
                    time.sleep(0.3)

            if head in ("read", "write"):
                from executor import run_cmd as _exec_direct
                result = _exec_direct(exec_cmd)
                print(f"📝 [DATA] {result[:200]}...")
                short_res = result
                if head == "read" and str(result).startswith("ok:"):
                    # 保留完整内容（限 2000 字符防爆 token）
                    if len(result) > 2000:
                        short_res = result[:2000] + "\n…(已截断)"
                    else:
                        short_res = result
                        
                status = "active" if str(result).startswith("ok:") else "undone"
                history.append({"act": cmd, "res": short_res, "status": status})

                if head == "read" and str(result).startswith("error: file not found"):
                    print("⚠️ [EDIT TARGET LOST] 目标文件不存在，自动切回新建流程")
                    phase = "need_open"
                    action_subphase = ""
                    flags["edit_like"] = False
                    step += 1
                    continue

                if head == "read" and str(result).startswith("ok:"):
                    action_subphase = "need_answer"
                step += 1
                continue

            if exec_cmd.startswith("t "):
                from executor import run_cmd as _exec_direct
                before_snap = take_snapshot()
                result = _exec_direct(exec_cmd)
                time.sleep(0.5)
                after_snap = take_snapshot()
                changes = diff_snapshots(before_snap, after_snap)
                if result == "ok" and changes:
                    result = "ok: " + " | ".join(changes)
                elif result == "ok" and not changes:
                    result = "no_change"
            else:
                result = run_and_diff(exec_cmd)

            if exec_cmd.startswith("o "):
                app_kw = exec_cmd[2:].strip().lower()
                snap_verify = take_snapshot()
                actually_open = any(app_kw in w.lower() for w in snap_verify["windows"])
                if not actually_open:
                    print(f"⚠️ [POST-CHECK] '{app_kw}' 执行后窗口未出现，标记失败")
                    result = f"error: {app_kw} window not found after open"

                if app_kw in ("notepad",) and actually_open:
                    fg_title = snap_verify.get("title", "")
                    is_clean = (
                        fg_title in ("无标题 - Notepad", "Untitled - Notepad")
                        or (fg_title.startswith("*无标题 - ") or fg_title.startswith("*Untitled - "))
                    )
                    if not is_clean:
                        print(f"⚠️ [STALE FILE] 打开了旧文件'{fg_title}'，关闭后重新打开")
                        import subprocess as _sp
                        import shutil
                        _sp.run("taskkill /f /im notepad.exe", shell=True, capture_output=True)
                        time.sleep(0.5)
                        session_path = os.path.expandvars(
                            r"%LocalAppData%\Packages\Microsoft.WindowsNotepad_8wekyb3d8bbwe\LocalState\TabState"
                        )
                        if os.path.exists(session_path):
                            shutil.rmtree(session_path, ignore_errors=True)
                            print("🔧 [STALE FILE] 已清除会话恢复数据")
                        _sp.Popen("start notepad", shell=True)
                        time.sleep(1.5)
                        try:
                            window_manager.snap_foreground_to_q1()
                        except:
                            pass
                        verify_snap = take_snapshot()
                        verify_title = verify_snap.get("title", "")
                        is_clean = "无标题" in verify_title or "untitled" in verify_title.lower()
                        if is_clean:
                            history.append({
                                "act": f"SYSTEM:stale_file_cleared:{fg_title}",
                                "res": "ok:reopened_clean_notepad",
                                "status": "active"
                            })
                        else:
                            history.append({
                                "act": f"SYSTEM:stale_file_cleared:{fg_title}",
                                "res": f"warn:still_showing:{verify_title}",
                                "status": "active"
                            })
                            print(f"⚠️ [STALE FILE] 重开后仍显示'{verify_title}'")

            changes = result.replace("ok: ", "").split(" | ") if result.startswith("ok:") else []
            new_snap = take_snapshot()
            new_title = new_snap.get('title', '')
            judgement = judge_change(goal, changes, exec_cmd, result, prev_title, new_title)
            prev_title = new_title

            if auto_recover(judgement):
                print(f"🔄 [AUTO UNDO] 异常变化，已自动 Ctrl+Z")
                history.append({"act": cmd, "res": "auto_undo: " + result, "status": "undone"})

            elif judgement == "error":
                print(f"❌ [ERROR] {result}")
                history.append({"act": cmd, "res": result, "status": "undone"})
                # 对"打开不存在程序"这种场景，直接告诉用户并结束
                if exec_cmd.startswith("o "):
                    print(f"🗣️ [SAY] 程序无法打开：{exec_cmd[2:].strip()}")
                    break

            elif judgement == "no_change":
                print(f"⚠️ [NO CHANGE] 执行了但系统无变化")
                history.append({"act": cmd, "res": "no_change", "status": "undone"})

            elif judgement == "silent_ok":
                print(f"🔇 [SILENT OK] 命令已执行（无可检测变化）")
                if "@1+s" in cmd.lower():
                    time.sleep(1.5)
                    obs_recheck = get_observation()
                    if "另存为" in obs_recheck or "save as" in obs_recheck.lower():
                        print("🔧 [DELAYED DETECT] 另存为对话框延迟弹出")
                        history.append({"act": cmd, "res": "ok:dialog_saveas_delayed", "status": "active"})
                        phase = "dialog_saveas"
                        step += 1
                        continue
                history.append({"act": cmd, "res": "silent_ok", "status": "active"})
                obs_after = get_observation()
                phase = advance_phase(goal, phase, cmd, obs_after)
            else:
                print(f"✅ [OK] {result}")
                history.append({"act": cmd, "res": result, "status": "active"})
                obs_after = get_observation()
                phase = advance_phase(goal, phase, cmd, obs_after)

        else:
            print(f"⚠️ [UNKNOWN] {cmd}")
            history.append({"act": cmd, "res": "unknown", "status": "undone"})

        step += 1

    if step > MAX_STEPS:
        print(f"🛑 [TIMEOUT] {MAX_STEPS} 步未完成，强制退出")
        print(f"🗣️ [SAY] 我用了 {MAX_STEPS} 步仍未完成「{goal[:20]}」，请重新描述或分解任务。")

    print(f"\n{'='*50}")
    print(f"📋 [完整历史]")
    for i, h in enumerate(history, 1):
        mark = "✅" if h.get("status") == "active" else "↩️"
        print(f"  {mark} {i}. {h['act']} → {h['res']}")
    print(f"{'='*50}")


def route(goal):
    from openai import OpenAI
    import config

    hard_action_keywords = ["打开", "用记事本", "保存", "输入", "打字", "read", "write", "读", "写文件", "点击", "运行", "对比", "合并", "修改", "编辑", "改", "复制"]
    goal_lower = goal.lower()
    if any(k in goal_lower for k in hard_action_keywords):
        print(f"🔀 [ROUTE] 硬规则匹配命中，强制进入 Agent 流")
        agent_loop(goal)
        return

    client = OpenAI(api_key=config.OPENAI_KEY, base_url=config.OPENAI_BASE_URL)
    resp = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[{"role": "user", "content": f"决定下面这句话是需要操控电脑的系统指令（回复A），还是聊天/问答（回复B）。只回复一个字母。\n'{goal}'"}],
        max_tokens=3,
        temperature=0.0
    )
    c = resp.choices[0].message.content.strip()
    print(f"🔀 [ROUTE] 模型判断: {c}")

    if c.startswith("A"):
        agent_loop(goal)
    else:
        resp2 = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[{"role": "user", "content": goal}],
            max_tokens=200,
            temperature=0.7
        )
        print(f"🗣️ {resp2.choices[0].message.content.strip()}")


def main():
    # 启动时自动清洗失效记忆
    try:
        import file_memory
        fm_stat = file_memory.cleanup_missing()
        print(f"🧹 [CLEAN] file_memory: removed_goals={fm_stat['removed_goals']} removed_alias={fm_stat['removed_alias']}")
    except Exception as e:
        print(f"⚠️ [CLEAN] file_memory cleanup failed: {e}")

    try:
        import worktree
        wt_stat = worktree.cleanup_missing()
        print(f"🧹 [CLEAN] worktree: changed={wt_stat['changed']} entries={wt_stat['entries']}")
    except Exception as e:
        print(f"⚠️ [CLEAN] worktree cleanup failed: {e}")

    print("""
╔═════════════════════════════════════════╗
║  GSS-OS Agent Core v2.8                ║
║  显式 phase 推进 · diff 自检            ║
║  反射处理另存为 · DONE 系统验证         ║
║  Type task or 'q' to quit              ║
╚═════════════════════════════════════════╝
    """)
    scanner.scan()
    if len(sys.argv) > 1:
        route(" ".join(sys.argv[1:]))
        input("\n按回车关闭...")
        return
    while True:
        try:
            task = input("\n[GSS-OS] > ").strip()
            if not task:
                continue
            if task.lower() in ("q", "quit", "exit"):
                break
            route(task)
        except Exception as e:
            print(f"\n💥 [FATAL ERROR] {e}")
        except (KeyboardInterrupt, EOFError):
            break
    print("\nBye.")
    input("按回车关闭...")


if __name__ == "__main__":
    main()