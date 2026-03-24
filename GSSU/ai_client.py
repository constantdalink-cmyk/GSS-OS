# ai_client.py

"""AI Client - 统一接口（极简prompt）"""

import config

CORE_SYSTEM = """你是GSS-OS Agent。

每次只回两行：
R 当前判断
一条指令

【指令】
o|f|t|hk|c|w|say|ASK|VISION|DONE|ld|read|write

【状态信号】
- SIGNAL: opened 表示打开完成
- SIGNAL: need_focus 表示下一步应聚焦
- SIGNAL: need_type 表示下一步应输入
- SIGNAL: typed 表示输入完成
- SIGNAL: need_save 表示下一步应保存
- SIGNAL: saved 表示保存完成

【规则】
- 一次只回一组R+指令
- 只做下一步，不要一次输出多步计划
- HISTORY里成功的动作不要重做
- OBS已显示目标达成就DONE
- 输入前先聚焦目标窗口
- t 是打字输入
- 保存优先使用 hk @1+s
- hk 里 @1=ctrl @2=win @3=alt @4=shift
- read 路径 读取文件(可指定行如 read main.py|10-20)
- write 路径|内容 写入文件
- say 内容 用来输出答案或回答用户的问题

【示例】
R 记事本未打开
o notepad

R 需要聚焦
f notepad

R 需要输入多行代码
t def add(x, y):
    return x + y

def sub(x, y):
    return x - y

R 需要保存
hk @1+s

R 保存完成
DONE
"""

def ask(prompt_input) -> dict:
    if config.AI_MODE == "openai":
        return _openai(prompt_input)
    raise ValueError(f"Unknown AI_MODE: {config.AI_MODE}")


def _build_messages(prompt_input):
    if isinstance(prompt_input, str):
        return [
            {"role": "system", "content": CORE_SYSTEM},
            {"role": "user", "content": prompt_input}
        ]

    if isinstance(prompt_input, dict):
        base = prompt_input.get("base", "").strip()
        system_text = base if base else CORE_SYSTEM

        user_parts = []
        for name in ["keys", "libs", "state", "task"]:
            text = prompt_input.get(name, "")
            if text:
                user_parts.append(f"[{name.upper()}]\n{text}")

        user_text = "\n\n".join(user_parts).strip() or "(empty)"

        return [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text}
        ]

    raise TypeError(f"ask() 只支持 str 或 dict，收到: {type(prompt_input).__name__}")


def _extract_text_content(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                text = getattr(item, "text", "")
                if text:
                    parts.append(str(text))
        return "".join(parts).strip()
    return str(content).strip()


def _openai(prompt_input) -> dict:
    try:
        from openai import OpenAI
    except ImportError:
        return {"text": "[API Error] 未安装 openai 包", "usage": None}

    try:
        client = OpenAI(
            api_key=config.OPENAI_KEY,
            base_url=config.OPENAI_BASE_URL
        )

        messages = _build_messages(prompt_input)

        resp = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=messages,
            max_tokens=800,
            temperature=0.0
        )

        usage = None
        if getattr(resp, "usage", None):
            usage = {
                "prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
                "completion_tokens": getattr(resp.usage, "completion_tokens", None),
                "total_tokens": getattr(resp.usage, "total_tokens", None)
            }

        content = resp.choices[0].message.content
        text = _extract_text_content(content)

        return {"text": text, "usage": usage}

    except Exception as e:
        return {"text": f"[API Error] 请求失败: {str(e)}", "usage": None}