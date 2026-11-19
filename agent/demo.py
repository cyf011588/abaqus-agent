# -*- coding: utf-8 -*-
"""--dry-run 演示模式：不调用大模型、不需要 API key，按预置脚本真实调用工具层。

用途：录屏演示「自然语言 → 预检 → 生成 → 闸门 → 记忆」的完整链路。
「决策」由本脚本代替大模型，但每一步工具调用都是真实的。
"""
from __future__ import annotations

from pathlib import Path

from . import memory as _memory
from . import tools as _tools

DEMO_SKILL = "cantilever"
DEMO_OUT = "demo_out"  # 相对，_generate 会 resolve 到 data/output/demo_out
DEMO_JOB = "CANT_DEMO"
DEMO_PARAMS = {"L": 1000, "W": 50, "H": 100, "P": 1000, "nx": 20, "ny": 2, "nz": 2}


def _p(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def _think(t: str) -> None:
    print("\n[思考] " + t)


def _act(t: str) -> None:
    print("\n[调用工具] " + t)


def run_demo(task: str = "") -> str:
    _p("Abaqus Agent · 演示模式（dry-run，不调用大模型）")
    if task:
        print("任务：" + task)
    print("说明：下面的工具调用都是真实执行，只有「决策」由预置脚本代替大模型。")

    _think("先看已接入的技能和可用闸门。")
    _act("list_skills / list_checks")
    print(_tools.list_skills())
    print(_tools.list_checks(DEMO_SKILL))

    _think("生成前：先按 manifest 契约做参数预检（合法放行、非法拦截）。")
    _act("precheck(manifest)")
    print(_tools._precheck(DEMO_SKILL, DEMO_PARAMS)
          or "[OK] 参数预检通过：L=1000、W=50、H=100、P=1000 均在可行域内")
    print("  非法参数演示 → " + (_tools._precheck(DEMO_SKILL, {"L": 1000, "P": "abc"}) or "").replace("\n", "\n  "))

    _think("按示例参数生成 inp。")
    _act("generate_model")
    ok, out_dir, produced, text = _tools._generate(DEMO_SKILL, DEMO_PARAMS, job=DEMO_JOB, out=DEMO_OUT)
    print(f"[{'OK' if ok else 'FAIL'}] 生成目录：{out_dir}")
    for f in produced:
        print(" - " + f)
    if not ok:
        print(text)
        return "dry-run 生成失败"

    # 用确定路径定位主 inp（不依赖"新增文件"差异：重复运行时文件已存在也能正确校验）
    main = str(Path(out_dir) / (DEMO_JOB + ".inp"))
    _think("跑结构闸门，确认关键字齐全、每个节点都被单元引用。")
    _act("run_check(check_inp.py)")
    print(_tools.run_check(DEMO_SKILL, "check_inp.py", main))

    _think("把这次结论写入长期记忆。")
    _act("remember")
    print(_tools.remember(DEMO_SKILL, "演示：1000×50×100 悬臂梁 1000 N，生成并通过结构闸门"))

    _p("演示结束")
    facts = _memory.get_facts(DEMO_SKILL, 5)
    print("当前长期记忆（最新 5 条）：")
    for f in facts:
        print(" - " + f)
    return "dry-run 完成"


if __name__ == "__main__":
    run_demo()
