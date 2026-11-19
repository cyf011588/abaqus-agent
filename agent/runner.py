# -*- coding: utf-8 -*-
"""命令行入口。

用法：
  python -m agent "端部 2 列、混凝土 80、M27，生成并校验"
  python -m agent                              # 交互式 REPL
"""
from __future__ import annotations

import sys
import time


def _build():
    try:
        from .graph import build_agent
    except ImportError as e:
        sys.stderr.write(
            "缺少 LangGraph 依赖，请先执行：pip install -r requirements.txt\n"
            f"原始错误：{e}\n"
        )
        sys.exit(1)
    return build_agent()


def _invoke(agent, task: str, history=None) -> tuple[str, str]:
    """执行一次并落盘结构化运行日志，返回 (answer, error)。"""
    from . import runlog

    t0 = time.time()
    ok, error, messages = True, "", []
    try:
        result = agent.invoke({"messages": list(history or [("user", task)])})
        messages = result.get("messages", [])
    except Exception as e:  # noqa: BLE001
        ok, error = False, str(e)
    elapsed = time.time() - t0
    last = messages[-1] if messages else None
    answer = str(getattr(last, "content", last) or "")
    try:
        runlog.save_run(
            task,
            ok,
            elapsed,
            error,
            tool_calls=runlog.extract_tool_calls(messages),
            token_usage=runlog.extract_token_usage(messages),
        )
    except Exception:  # noqa: BLE001
        pass
    return answer, error


def run(agent, task: str) -> str:
    answer, error = _invoke(agent, task)
    return answer if not error else f"[出错] {error}"


def repl(agent) -> None:
    print("Abaqus Agent 已启动，输入任务或 quit 退出。")
    history: list = []  # 跨轮会话历史，让 agent 有短时记忆
    while True:
        try:
            line = input("\n>> ")
        except (EOFError, KeyboardInterrupt):
            break
        line = line.strip()
        if line.lower() in ("quit", "exit", "q"):
            break
        if not line:
            continue
        history.append(("user", line))
        answer, error = _invoke(agent, line, history)
        if error:
            print(f"\n[出错] {error}")
        else:
            print("\n" + answer)
        history.append(("assistant", answer))


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    # dry-run 演示模式：不依赖 langgraph / API key，录屏用
    if "--dry-run" in argv:
        argv = [a for a in argv if a != "--dry-run"]
        from . import demo
        demo.run_demo(" ".join(argv))
        return
    agent = _build()
    if argv:
        print(run(agent, " ".join(argv)))
    else:
        repl(agent)


if __name__ == "__main__":
    main()
