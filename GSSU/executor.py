"""物理执行映射"""
import subprocess, time, pyautogui, pyperclip
import config, howcode, lib_manager
from grid import grid
from gate import gate

pyautogui.FAILSAFE = True

def run(command: str):
    parts = command.split(" ", 1)
    cmd, arg = parts[0], parts[1].strip() if len(parts) > 1 else ""
    
    if cmd == "c": _c(arg)
    elif cmd == "dc": _dc(arg)
    elif cmd == "t": _t(arg)
    elif cmd == "hk": _hk(arg)
    elif cmd == "o": _o(arg)
    elif cmd == "w": time.sleep(int(arg)/1000.0)
    elif cmd == "gd": grid.set_level(int(arg))
    elif cmd == "hc": howcode.handle(arg)
    elif cmd == "mk_lib": _mk_lib(arg)
    elif cmd == "ld": lib_manager.load_lib(arg)
    elif cmd == "say": pass # GUI handled

def _c(cell):
    x, y = grid.cell_to_pixel(cell)
    if x: pyautogui.click(x, y)

def _dc(cell):
    x, y = grid.cell_to_pixel(cell)
    if x: pyautogui.doubleClick(x, y)

def _t(text):
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")

def _hk(combo):
    for dk in config.DANGEROUS_KEYS:
        if combo.lower().replace(" ", "") == dk.lower().replace(" ", ""):
            if not gate.review("Dangerous Hotkey", f"AI attempt: {combo}"): return
    pyautogui.hotkey(*[k.strip().lower() for k in combo.split("+")])

def _o(app):
    subprocess.Popen(f"start {app}", shell=True)

def _mk_lib(name):
    if gate.review("Library Creation", f"Create {name}?"): lib_manager.make_lib(name)