# -*- coding: utf-8 -*-
"""评估集运行器：批量执行 evals/tasks.yaml，判定并输出 evals/report.md。

用法（在项目根目录）：
  .venv/Scripts/python -m evals.run_eval                # 真实 LLM 全量
  .venv/Scripts/python -m evals.run_eval --limit 5      # 只跑前 5 条
  .venv/Scripts/python -m evals.run_eval --categories qa,anomaly
  .venv/Scripts/python -m evals.run_eval --dry-run      # 模拟决策，无 key 演示评估流程
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml

from agent import runlog

REJECT_KW = ("无法", "不能", "不存在", "非法", "错误", "失败", "无效", "超出", "不支持", "不可")


def load_tasks(path: Path) -> list:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    tasks = data.get("tasks", []) if isinstance(data, dict) else data
    return list(tasks or [])


def _answer_of(messages) -> str:
    last = messages[-1] if messages else None
    return str(getattr(last, "content", last) or "")


def run_task_real(agent, task: dict) -> dict:
    t0 = time.time()
    try:
        result = agent.invoke({"messages": [("user", task["prompt"])]})
        messages = result.get("messages", [])
        ok, error = True, ""
    except Exception as e:  # noqa: BLE001
        messages, ok, error = [], False, str(e)
    elapsed = time.time() - t0
    tool_calls = runlog.extract_tool_calls(messages)
    answer = _answer_of(messages)
    try:
        runlog.save_run(
            task["prompt"], ok, elapsed, error,
            tool_calls=tool_calls, token_usage=runlog.extract_token_usage(messages),
        )
    except Exception:  # noqa: BLE001
        pass
    return {"tool_calls": tool_calls, "answer": answer, "ok": ok, "error": error}


def run_task_dry(task: dict) -> dict:
    """模拟一个「正确」的 agent：按任务期望构造工具序列与答案，用于无 key 演示评估流程。"""
    tc = list(task.get("must_call", []))
    if task.get("gate_required") and "run_check" not in tc and "batch_run" not in tc:
        tc.append("run_check")
    parts = []
    if task.get("expect_keywords"):
        parts.append("；".join(task["expect_keywords"]))
    if task.get("expect_reject"):
        parts.append("不可行 / 不存在")
    if not parts:
        parts.append("已完成")
    return {"tool_calls": tc, "answer": "（dry-run 模拟）" + " ".join(parts), "ok": True, "error": ""}


def judge(task: dict, run: dict) -> list:
    fails = []
    tc = run["tool_calls"]
    ans = (run.get("answer") or "").lower()
    for t in task.get("must_call", []):
        if t not in tc:
            fails.append(f"缺工具 {t}")
    for t in task.get("must_not_call", []):
        if t in tc:
            fails.append(f"不应调 {t}")
    if task.get("gate_required") and "generate_model" in tc and "run_check" not in tc:
        fails.append("生成后未跑 run_check")
    if task.get("expect_reject") and not any(k in ans for k in REJECT_KW):
        fails.append("未明确拒绝/报错")
    for k in task.get("expect_keywords", []):
        if k.lower() not in ans:
            fails.append(f"缺关键词 {k}")
    return fails


def _write_report(path: Path, mode: str, rows: list, metrics: dict) -> None:
    lines = [
        "# Abaqus Agent 评估报告",
        "",
        f"- 模式：{mode}",
        f"- 任务总数：{metrics['total']}",
        f"- 通过：{metrics['passed']}",
        f"- **端到端成功率：{metrics['success_rate']:.1%}**",
        f"- **闸门调用正确率：{metrics['gate_rate']:.1%}**（{metrics['gate_ok']}/{metrics['gate_total']}）",
        f"- **平均工具调用轮数：{metrics['avg_tools']:.2f}**",
        "",
        "## 逐任务结果",
        "",
        "| id | 类别 | 工具调用 | 通过 | 失败原因 |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        tc = ", ".join(r["run"]["tool_calls"]) or "（无）"
        verdict = "✅" if r["passed"] else "❌"
        why = "；".join(r["fails"]) or "—"
        lines.append(f"| {r['task']['id']} | {r['task'].get('category','')} | {tc} | {verdict} | {why} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--categories", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tasks", default=str(ROOT / "evals" / "tasks.yaml"))
    a = ap.parse_args()

    tasks = load_tasks(Path(a.tasks))
    cats = {c for c in a.categories.split(",") if c}
    if cats:
        tasks = [t for t in tasks if t.get("category") in cats]
    if a.limit:
        tasks = tasks[: a.limit]

    mode = "dry-run（模拟决策，非真实 LLM）" if a.dry_run else "real（真实 LLM）"
    if a.dry_run:
        results = [(t, run_task_dry(t)) for t in tasks]
    else:
        from agent.graph import build_agent

        agent = build_agent()
        results = []
        for t in tasks:
            print(f"[eval] {t['id']} ...", flush=True)
            results.append((t, run_task_real(agent, t)))

    rows = []
    for t, run in results:
        fails = judge(t, run)
        rows.append({"task": t, "run": run, "fails": fails, "passed": not fails})

    total = len(rows)
    passed = sum(1 for r in rows if r["passed"])
    gate_rows = [r for r in rows if r["task"].get("gate_required")]
    gate_ok = sum(1 for r in gate_rows if "生成后未跑 run_check" not in r["fails"])
    tool_counts = [len(r["run"]["tool_calls"]) for r in rows]
    avg_tools = (sum(tool_counts) / len(tool_counts)) if tool_counts else 0.0

    metrics = {
        "total": total,
        "passed": passed,
        "success_rate": (passed / total) if total else 0.0,
        "gate_ok": gate_ok,
        "gate_total": len(gate_rows),
        "gate_rate": (gate_ok / len(gate_rows)) if gate_rows else 1.0,
        "avg_tools": avg_tools,
    }

    out = ROOT / "evals" / "report.md"
    _write_report(out, mode, rows, metrics)

    print("\n==== 评估汇总 ====")
    print(f"模式：{mode}")
    print(f"成功率：{metrics['success_rate']:.1%}（{passed}/{total}）")
    print(f"闸门调用正确率：{metrics['gate_rate']:.1%}（{gate_ok}/{metrics['gate_total']}）")
    print(f"平均工具调用轮数：{avg_tools:.2f}")
    print(f"报告已写入：{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
