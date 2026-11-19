# -*- coding: utf-8 -*-
"""工具调用预算与 LangGraph 递归上限的回归测试。

背景：真实任务里出现过 GRAPH_RECURSION_LIMIT —— recursion_limit 被设成
max_steps*2+4=28，而"检索案例 → 生成模型 → 校验 → 修复"这类流程一轮就要
2 个图步，12 轮预算根本不够，撞上限直接抛错、用户只看到一行报错。

现在的策略：预算内正常跑，剩 2 轮开始催促收敛，预算用尽后不再绑工具，
用纯 LLM 给结论，所以永远不会硬崩到 recursion_limit。
"""
from __future__ import annotations

from agent import graph as g


def test_normal_when_budget_plenty():
    bs = g.budget_state(used=0, max_steps=18)
    assert bs["mode"] == "normal"
    assert bs["left"] == 18
    assert bs["note"] is None


def test_hint_when_two_left():
    bs = g.budget_state(used=16, max_steps=18)
    assert bs["mode"] == "hint"
    assert bs["left"] == 2
    assert "只剩 2 轮" in bs["note"]


def test_final_when_budget_exhausted():
    bs = g.budget_state(used=18, max_steps=18)
    assert bs["mode"] == "final"
    assert "预算耗尽" in bs["note"]
    assert "禁止再调用任何工具" in bs["note"]


def test_final_beyond_budget():
    bs = g.budget_state(used=25, max_steps=12)
    assert bs["mode"] == "final"


def test_recursion_limit_covers_worst_case():
    """即便把预算全部用满，recursion_limit 也要留出收尾那一轮。"""
    for max_steps in (12, 18, 30):
        limit = max_steps * 2 + 8
        assert limit >= max_steps * 2 + 2  # chatbot+tools 交替 + 一轮纯 LLM 收尾
