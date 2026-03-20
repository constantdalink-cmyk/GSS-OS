"""
Intent Router - 阀门机制 (Valve)
不偷懒写正则，让大模型自己反思并分类任务意图。
极低 Token 消耗的零样本分类。
"""
from ai_client import ask

VALVE_PROMPT = """Classify this user input.
Options:
- OS (needs to operate computer, open app, type, click)
- CHAT (just greeting, question, no computer operation)
- MIX (both OS and CHAT)

Output ONLY the option name (OS, CHAT, or MIX).
Input: {task}"""

def classify_task(task: str) -> str:
    """
    通过 AI 阀门判断意图
    返回: "os", "chat", 或 "mix"
    """
    if not task:
        return "chat"
        
    prompt = VALVE_PROMPT.format(task=task.strip())
    
    # 构建兼容 ai_client.ask 格式的伪包
    pkg = {
        "base": prompt,
        "keys": "",
        "libs": "",
        "state": "",
        "task": ""
    }
    
    # 呼叫 AI 判定，这步消耗极小 (约 50 tokens)
    result = ask(pkg)
    response = result["text"].strip().upper()
    
    # 解析并收编结果
    if "OS" in response and "MIX" not in response:
        return "os"
    elif "CHAT" in response:
        return "chat"
    elif "MIX" in response:
        return "mix"
    else:
        # 如果模型发疯，默认走相对安全的 os 链路
        return "os"