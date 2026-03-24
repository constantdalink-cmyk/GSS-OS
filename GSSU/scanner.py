"""
Scanner - 系统扫描器
启动时扫一次，缓存结果，极低token注入STATE
"""
import os
import glob
import time

_cache = None

def _scan_start_menu():
    """扫开始菜单，提取已安装应用名"""
    apps = set()
    paths = [
        os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs"),
    ]
    for base in paths:
        for lnk in glob.glob(os.path.join(base, "**", "*.lnk"), recursive=True):
            name = os.path.splitext(os.path.basename(lnk))[0]
            # 过滤掉卸载、帮助等无用项
            skip = [
                "uninstall", "卸载", "help", "帮助", "readme", "license",
                "administrative", "管理", "component", "verifier",
                "command prompt", "powershell", "developer",
                "database compare", "character map",
            ]
            if any(s in name.lower() for s in skip):
                continue
            apps.add(name)
    return sorted(apps)


def _scan_user_files():
    """扫桌面和文档，提取用户文件"""
    files = []
    IGNORE_EXT = {".lnk", ".ini", ".tmp", ".log"}
    dirs = [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Documents"),
    ]
    for d in dirs:
        if not os.path.exists(d):
            continue
        for f in os.listdir(d)[:30]:
            fp = os.path.join(d, f)
            ext = os.path.splitext(f)[1].lower()
            if ext in IGNORE_EXT:
                continue
            if os.path.isfile(fp):
                files.append(f)
    return sorted(files)


def scan():
    """执行扫描，缓存结果"""
    global _cache
    t0 = time.time()

    apps = _scan_start_menu()
    files = _scan_user_files()

    _cache = {
        "apps": apps,
        "files": files,
        "time": time.time(),
    }
    print(f"🔎 [SCAN] {len(apps)} 应用, {len(files)} 文件, 耗时 {time.time()-t0:.2f}s")
    return _cache


def get_apps_hint(max_items=8):
    """返回压缩后的应用列表字符串"""
    if not _cache:
        scan()
    apps = _cache["apps"][:max_items]
    return ",".join(apps) if apps else ""


def get_files_hint(max_items=10):
    """返回压缩后的文件列表字符串"""
    if not _cache:
        scan()
    files = _cache["files"][:max_items]
    return ",".join(files) if files else ""


def get_scan_hint():
    """一行式注入STATE"""
    apps = get_apps_hint()
    files = get_files_hint()
    parts = []
    if apps:
        parts.append(f"APPS: {apps}")
    if files:
        parts.append(f"FILES: {files}")
    return " | ".join(parts)