"""
GSS-OS 主入口 - 阀门路由版 (Valve Mechanism)
核心机制：
1. 阀门机制 (Valve)：大模型反问自己，判断任务意图 (CHAT/OS/MIX)
2. 快路径分离：聊天走 CHAT 管线，干活走 OS 管线，混合走 MIX 管线
3. 动态加载：规划时不带 libs，单步执行时按需带 libs
"""

import sys
import time
import lib_manager

from intent_router import classify_task
from prompt import (
    build_chat_package,
    build_plan_package,
    build_step_package,
    estimate_tokens_rough,
    total_chars,
    total_tokens_rough
)
from parser import parse_todo, parse_step
from executor import run as execute
from ai_client import ask


def print_pkg_report(title: str, pkg: dict):
    print(f"\n[{title}]")
    for name in ["base", "keys", "libs", "state", "task"]:
        text = pkg.get(name, "")
        chars = len(text)
        toks = estimate_tokens_rough(text)
        print(f"  {name:<5}: {chars:>4} chars | ~{toks:>4} tokens")
    print(f"  total: {total_chars(pkg)} chars | ~{total_tokens_rough(pkg)} tokens")


def print_usage(usage):
    if not usage:
        print("  API usage: unavailable")
        return
    print("  API usage:")
    print(f"    prompt_tokens    : {usage.get('prompt_tokens')}")
    print(f"    completion_tokens: {usage.get('completion_tokens')}")
    print(f"    total_tokens     : {usage.get('total_tokens')}")


def run_chat_task(task: str):
    """专门处理纯聊天任务的极简管线"""
    pkg = build_chat_package(task)
    print_pkg_report("CHAT PROMPT", pkg)

    print("\n[CHAT THINKING...]")
    result = ask(pkg)
    text = result["text"]
    usage = result["usage"]

    print_usage(usage)
    print(f"\n[RAW CHAT]\n{text}")

    actions = parse_step(text)

    if not actions:
        # 如果模型直接回了自然语言，作为兜底直接打印
        print(f"\n🗣️  \033[92m[AI 说]: {text}\033[0m")
        return

    for i, act in enumerate(actions, 1):
        if act["type"] == "think":
            print(f"\n  [{i}/{len(actions)}] 💡 [反思]: {act['content']}")
            time.sleep(0.1)
        elif act["type"] == "cmd":
            cmd = act["content"]
            if cmd.startswith("say "):
                msg = cmd[4:].strip()
                print(f"\n  [{i}/{len(actions)}] 🗣️  \033[92m[AI 说]: {msg}\033[0m")
            else:
                print(f"\n  [{i}/{len(actions)}] ⚠️  [忽略越权命令]: {cmd}")


def run_os_task(task: str):
    """处理操作系统动作的 TODO + 单步管线"""
    # =============================
    # Stage 1: TODO Planning
    # =============================
    plan_pkg = build_plan_package(task)
    print_pkg_report("PLAN PROMPT", plan_pkg)

    print("\n[PLAN THINKING...]")
    plan_result = ask(plan_pkg)
    plan_text = plan_result["text"]
    plan_usage = plan_result["usage"]

    print_usage(plan_usage)
    print(f"\n[RAW PLAN]\n{plan_text}")

    todos = parse_todo(plan_text)
    if not todos:
        print("\n[TODO] 无法解析出有效的任务清单。")
        return

    print(f"\n[TODO LIST] ({len(todos)} steps)")
    for i, todo in enumerate(todos, 1):
        print(f"  {i}. {todo}")

    # =============================
    # Stage 2: Single-step driving
    # =============================
    for idx, todo in enumerate(todos, 1):
        step_pkg = build_step_package(task, todo, idx, len(todos))
        print_pkg_report(f"STEP {idx} PROMPT", step_pkg)

        print(f"\n[STEP {idx} THINKING...]")
        step_result = ask(step_pkg)
        step_text = step_result["text"]
        step_usage = step_result["usage"]

        print_usage(step_usage)
        print(f"\n[RAW STEP {idx}]\n{step_text}")

        actions = parse_step(step_text)
        if not actions:
            print(f"\n  [STEP {idx}] 未解析到合法动作，跳过")
            continue

        for act in actions:
            if act["type"] == "think":
                print(f"\n  [STEP {idx}] 💡 [反思]: {act['content']}")
                time.sleep(0.15)
            elif act["type"] == "cmd":
                cmd = act["content"]
                if cmd.startswith("say "):
                    msg = cmd[4:].strip()
                    print(f"\n  [STEP {idx}] 🗣️  \033[92m[AI 说]: {msg}\033[0m")
                    time.sleep(0.15)
                    continue

                print(f"\n  [STEP {idx}] ⚡ [执行]: {cmd}")
                execute(cmd)
                # 防黑屏节流阀
                time.sleep(0.5)


def run_task(task: str):
    """总任务入口：通过阀门派发管线"""
    print(f"\n{'='*56}")
    print(f"[TASK] {task}")
    print(f"{'='*56}")

    # 1. 过阀门 (Valve Routing)
    print("\n[VALVE] AI 正在反思并分类任务意图...")
    mode = classify_task(task)
    print(f"[VALVE RESULT] 意图路由判定为: {mode.upper()}")

    # 2. 根据阀门结果派发管线
    if mode == "chat":
        print("\n>> 走 CHAT 纯聊天快路径 (不挂载系统环境)")
        run_chat_task(task)
        
    elif mode == "os":
        print("\n>> 走 OS 操作系统管线 (挂载程序库与网格)")
        run_os_task(task)
        
    elif mode == "mix":
        print("\n>> 走 MIX 混合管线 (先回应，再干活)")
        print("\n--- Phase 1: 聊天回应 ---")
        run_chat_task(task)
        print("\n--- Phase 2: 系统操作 ---")
        run_os_task(task)

    print(f"\n{'='*56}")
    print("[DONE] Task completed.")
    print(f"{'='*56}")


def main():
    lib_manager.init()

    print("""
╔════════════════════════════════════════════════╗
║         GSS-OS Valve & Single-Step版          ║
║                                                ║
║  1. AI 意图阀门 (CHAT / OS / MIX)              ║
║  2. 单步规划与执行 (TODO -> Step)              ║
║  3. 防黑屏物理节流 (0.5s pause)                ║
║                                                ║
║  Type task or 'q' to quit                      ║
╚════════════════════════════════════════════════╝
    """)

    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        run_task(task)
        return

    while True:
        try:
            task = input("\n[GSS-OS] > ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not task:
            continue
        if task.lower() in ("q", "quit", "exit"):
            break
        if task.lower() == "grid":
            from grid import grid
            import threading
            threading.Thread(target=grid.show, daemon=True).start()
            continue

        run_task(task)

    print("\nBye.")


if __name__ == "__main__":
    main()