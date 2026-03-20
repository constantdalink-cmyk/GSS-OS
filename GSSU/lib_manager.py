"""库管理器：负责技能的基因化存储与按需挂载"""
import os
import yaml

LIBS_DIR, TOOLS_DIR = "libs", "tools"

def init():
    os.makedirs(LIBS_DIR, exist_ok=True)
    os.makedirs(TOOLS_DIR, exist_ok=True)
    sys_path = os.path.join(LIBS_DIR, "lib_sys.yaml")
    if not os.path.exists(sys_path):
        _save(sys_path, {
            "notepad": "记事本", "explorer": "资源管理器",
            "cmd": "命令行", "calc": "计算器",
            "edge": "Edge浏览器"
        })
    how_path = os.path.join(LIBS_DIR, "lib_how.yaml")
    if not os.path.exists(how_path): _save(how_path, {})

def load_lib(name: str):
    path = os.path.join(LIBS_DIR, f"{name}.yaml")
    if not os.path.exists(path): return {}
    with open(path, "r", encoding="utf-8") as f: return yaml.safe_load(f) or {}

def make_lib(name: str):
    path = os.path.join(LIBS_DIR, f"{name}.yaml")
    if not os.path.exists(path): _save(path, {})

def register_tool(name: str, code: str):
    path = os.path.join(TOOLS_DIR, f"{name}.py")
    with open(path, "w", encoding="utf-8") as f: f.write(code)
    how = load_lib("lib_how")
    how[name] = f"HOW-code tool: {path}"
    _save(os.path.join(LIBS_DIR, "lib_how.yaml"), how)

def move_tool(tool_name: str, lib_name: str):
    lib_path = os.path.join(LIBS_DIR, f"{lib_name}.yaml")
    if not os.path.exists(lib_path): return
    lib = load_lib(lib_name)
    lib[tool_name] = f"HOW-code tool"
    _save(lib_path, lib)

def get_lib_prompt(lib_name: str) -> str:
    lib = load_lib(lib_name)
    return "\n".join([f"{k}: {v}" for k, v in lib.items()]) if lib else ""

def _save(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True)