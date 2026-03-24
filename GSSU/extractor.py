# extractor.py

"""
Extractor - 文本/代码结构提取器
将长代码压缩成极低Token的大纲，供AI"缩起来"看
"""

def extract_outline(text: str) -> str:
    lines = text.split("\n")
    outline = []
    
    for i, line in enumerate(lines):
        clean_line = line.strip()
        if clean_line.startswith("class ") or clean_line.startswith("def "):
            # 提取签名
            signature = clean_line.split(":")[0] + ":"
            outline.append(f"L{i+1}: {signature}")
            
    if not outline:
        return ""
        
    return "大纲:[" + " | ".join(outline) + "]"


def locate_function(text: str, func_name: str):
    """
    在代码文本里定位某个函数的行范围。
    返回 (start_line, end_line) 从1开始，或 (0, 0) 表示未找到。
    """
    lines = text.split("\n")
    start = 0
    
    # 找到目标函数的起始行
    for i, line in enumerate(lines):
        clean = line.strip()
        if clean.startswith("def ") and func_name in clean:
            start = i + 1  # 行号从1开始
            break
    
    if not start:
        return 0, 0
    
    # 找到下一个同级 def/class 的起始行作为结束
    end = len(lines)
    for i in range(start, len(lines)):  # start 是1-based，直接用作0-based的下一行
        clean = lines[i].strip()
        if clean.startswith("def ") or clean.startswith("class "):
            end = i  # 0-based index 即为前一行的1-based行号
            break
    
    return start, end


def read_function(text: str, func_name: str) -> str:
    """
    直接返回某函数的代码文本。
    """
    start, end = locate_function(text, func_name)
    if not start:
        return ""
    lines = text.split("\n")
    return "\n".join(lines[start-1:end])


def replace_function(text: str, func_name: str, new_func: str) -> str:
    """
    用 new_func 替换原文件中 func_name 对应的函数。
    返回替换后的完整文本。
    """
    start, end = locate_function(text, func_name)
    if not start:
        return text  # 找不到就原样返回
    lines = text.split("\n")
    new_func_lines = new_func.splitlines()
    # 确保函数后有空行
    if new_func_lines and new_func_lines[-1].strip():
        new_func_lines.append("")
    new_lines = lines[:start-1] + new_func_lines + lines[end:]
    return "\n".join(new_lines)