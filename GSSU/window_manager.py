"""
Window Manager - 窗口校准系统
4象限铁律：最多4个窗口，位置固定，坐标可预测
"""
import win32gui
import win32con
import time

SCREEN_W = 1920
SCREEN_H = 1080

# 四象限坐标表
LAYOUTS = {
    1: [
        (0, 0, SCREEN_W, SCREEN_H),
    ],
    2: [
        (0, 0, SCREEN_W // 2, SCREEN_H),
        (SCREEN_W // 2, 0, SCREEN_W // 2, SCREEN_H),
    ],
    3: [
        (0, 0, SCREEN_W // 2, SCREEN_H),
        (SCREEN_W // 2, 0, SCREEN_W // 2, SCREEN_H // 2),
        (SCREEN_W // 2, SCREEN_H // 2, SCREEN_W // 2, SCREEN_H // 2),
    ],
    4: [
        (0, 0, SCREEN_W // 2, SCREEN_H // 2),
        (SCREEN_W // 2, 0, SCREEN_W // 2, SCREEN_H // 2),
        (0, SCREEN_H // 2, SCREEN_W // 2, SCREEN_H // 2),
        (SCREEN_W // 2, SCREEN_H // 2, SCREEN_W // 2, SCREEN_H // 2),
    ],
}

# 不管的窗口
IGNORE_TITLES = {"", "Program Manager", "Windows Input Experience"}
IGNORE_CLASSES = {"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW"}


def get_managed_windows():
    """获取所有应该管理的可见窗口"""
    windows = []
    
    def enum_cb(hwnd, results):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if title in IGNORE_TITLES:
            return
        try:
            cls = win32gui.GetClassName(hwnd)
            if cls in IGNORE_CLASSES:
                return
        except:
            pass
        if win32gui.IsIconic(hwnd):
            return
        results.append((hwnd, title))
    
    win32gui.EnumWindows(enum_cb, windows)
    return windows


def arrange_windows():
    """
    核心函数：获取所有窗口，按数量选择布局，摆放到位。
    超过4个的最小化。
    """
    windows = get_managed_windows()
    
    if not windows:
        return []
    
    if len(windows) > 4:
        for hwnd, title in windows[4:]:
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        windows = windows[:4]
    
    count = len(windows)
    layout = LAYOUTS[count]
    
    result = []
    for i, (hwnd, title) in enumerate(windows):
        x, y, w, h = layout[i]
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.MoveWindow(hwnd, x, y, w, h, True)
        
        quadrant = f"Q{i+1}" if count > 1 else "FULL"
        result.append({
            "hwnd": hwnd,
            "title": title,
            "quadrant": quadrant,
            "rect": (x, y, w, h),
        })
    
    return result


def snap_to_quadrant(hwnd, quadrant):
    """把指定窗口摆到指定象限"""
    positions = {
        "FULL": (0, 0, SCREEN_W, SCREEN_H),
        "Q1": (0, 0, SCREEN_W // 2, SCREEN_H // 2),
        "Q2": (SCREEN_W // 2, 0, SCREEN_W // 2, SCREEN_H // 2),
        "Q3": (0, SCREEN_H // 2, SCREEN_W // 2, SCREEN_H // 2),
        "Q4": (SCREEN_W // 2, SCREEN_H // 2, SCREEN_W // 2, SCREEN_H // 2),
        "LEFT": (0, 0, SCREEN_W // 2, SCREEN_H),
        "RIGHT": (SCREEN_W // 2, 0, SCREEN_W // 2, SCREEN_H),
    }
    
    if quadrant not in positions:
        return
    
    x, y, w, h = positions[quadrant]
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.MoveWindow(hwnd, x, y, w, h, True)


def get_layout_info():
    """返回当前布局的文字描述，注入 OBS"""
    windows = get_managed_windows()
    
    if not windows:
        return "布局=桌面(无窗口)"
    
    count = min(len(windows), 4)
    layout = LAYOUTS[count]
    
    parts = []
    for i, (hwnd, title) in enumerate(windows[:4]):
        if count == 1:
            q = "全屏"
        else:
            q = f"Q{i+1}"
        short_title = title[:20] if len(title) > 20 else title
        parts.append(f"{q}={short_title}")
    
    return f"布局={count}窗口 " + " | ".join(parts)


def snap_foreground_to_q1():
    """只把当前前台窗口放到 Q1，不动其他窗口"""
    time.sleep(0.3)
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return "no_hwnd"

    try:
        snap_to_quadrant(hwnd, "Q1")
        title = win32gui.GetWindowText(hwnd)
        return f"snapped_q1:{title}"
    except Exception as e:
        return f"error:{e}"


def focus_window(keyword):
    """根据标题关键词聚焦窗口"""
    keyword = (keyword or "").strip().lower()
    if not keyword:
        return "no_keyword"

    matches = []

    def enum_cb(hwnd, results):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        if keyword in title.lower():
            results.append((hwnd, title))

    win32gui.EnumWindows(enum_cb, matches)

    if not matches:
        return f"not_found:{keyword}"

    hwnd, title = matches[0]

    try:
        # 先恢复窗口
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        # 再尝试置顶 + 前台
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)

        # 再读一次标题确认
        new_hwnd = win32gui.GetForegroundWindow()
        new_title = win32gui.GetWindowText(new_hwnd)

        if keyword in new_title.lower():
            return f"focused:{new_title}"
        return f"focus_failed:{new_title}"

    except Exception as e:
        return f"focus_error:{e}"