"""AI Client - 返回 text + usage"""

import config


def ask(prompt_package: dict, is_creator: bool = False) -> dict:
    """
    返回：
    {
      "text": "...",
      "usage": {
         "prompt_tokens": ...,
         "completion_tokens": ...,
         "total_tokens": ...
      }
    }
    """
    if config.AI_MODE == "openai":
        return _openai(prompt_package, is_creator=is_creator)
    else:
        raise ValueError(f"Unknown AI_MODE: {config.AI_MODE}")


def _openai(prompt_package: dict, is_creator: bool = False) -> dict:
    try:
        from openai import OpenAI
    except ImportError:
        return {
            "text": "[API Error] 未安装 openai 包。请运行 pip install openai",
            "usage": None
        }

    try:
        client = OpenAI(
            api_key=config.OPENAI_KEY,
            base_url=config.OPENAI_BASE_URL
        )

        if is_creator:
            creator_prompt = f"""Write a minimal Python script.
Purpose: {prompt_package}
Rules:
- Single file
- Include if __name__ == "__main__"
- No markdown
- Output code only
"""
            messages = [{"role": "user", "content": creator_prompt}]
        else:
            messages = []

            if prompt_package.get("base"):
                messages.append({
                    "role": "user",
                    "content": "[BASE]\n" + prompt_package["base"]
                })

            if prompt_package.get("keys"):
                messages.append({
                    "role": "user",
                    "content": "[KEYS]\n" + prompt_package["keys"]
                })

            if prompt_package.get("libs"):
                messages.append({
                    "role": "user",
                    "content": "[LIBS]\n" + prompt_package["libs"]
                })

            if prompt_package.get("state"):
                messages.append({
                    "role": "user",
                    "content": "[STATE]\n" + prompt_package["state"]
                })

            if prompt_package.get("task"):
                messages.append({
                    "role": "user",
                    "content": "[TASK]\n" + prompt_package["task"]
                })

        resp = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=messages,
            max_tokens=220,
            temperature=0.0
        )

        usage = None
        if hasattr(resp, "usage") and resp.usage:
            usage = {
                "prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
                "completion_tokens": getattr(resp.usage, "completion_tokens", None),
                "total_tokens": getattr(resp.usage, "total_tokens", None)
            }

        return {
            "text": resp.choices[0].message.content.strip(),
            "usage": usage
        }

    except Exception as e:
        return {
            "text": f"[API Error] 请求失败: {str(e)}",
            "usage": None
        }