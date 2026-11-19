# -*- coding: utf-8 -*-
"""LangGraph 编排层：把 tools.py 的工具注册给 LLM，组成 ReAct 智能体。

这里刻意用 StateGraph + ToolNode + tools_condition 手搭，而不是直接 create_react_agent：
一是不同 LangGraph 版本的 API 有差异，手搭更稳；二是这本身就是「harness 工程」——
正好对应该岗位的核心工作内容。
"""
from __future__ import annotations

import os
from typing import Annotated, TypedDict

from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from . import config as _cfg_mod
from . import manifest as _manifest
from . import memory as _memory
from . import modeling_knowledge as _mk
from . import tools as _tools


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


def _build_llm():
    cfg = _cfg_mod.load_config()
    llm = cfg["agent"]["llm"]
    base_url = llm.get("base_url") or os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
    api_key = os.environ.get(llm.get("api_key_env", "LLM_API_KEY"), "")
    model = llm.get("model") or os.environ.get("LLM_MODEL", "deepseek-chat")
    if not api_key:
        raise RuntimeError("未配置 LLM_API_KEY：请把 .env.example 复制为 .env 并填入 key")
    return ChatOpenAI(base_url=base_url, api_key=api_key, model=model, temperature=0)


def _tool_wrappers():
    return [
        tool(_tools.list_skills),
        tool(_tools.add_skill),
        tool(_tools.remove_skill),
        tool(_tools.rename_skill),
        tool(_tools.list_checks),
        tool(_tools.generate_model),
        tool(_tools.batch_run),
        tool(_tools.run_check),
        tool(_tools.submit_job),
        tool(_tools.job_status),
        tool(_tools.search_knowledge),
        tool(_tools.read_text),
        tool(_tools.remember),
        tool(_tools.plan_model),
        tool(_tools.modeling_guide),
        tool(_tools.web_search),
        tool(_tools.web_fetch),
        tool(_tools.write_inp),
        tool(_tools.mesh_inp),
        tool(_tools.append_inp),
        tool(_tools.repair_inp),
    ]


def _system_prompt() -> str:
    cfg = _cfg_mod.load_config()
    skills = list(cfg.get("skills", {}))
    facts = []
    for key in skills:
        for f in _memory.get_facts(key, limit=30):
            facts.append(f"- [{key}] {f}")
    fact_block = "\n".join(facts) if facts else "(暂无长期记忆)"

    manifest_blocks = []
    for key in skills:
        summ = _manifest.manifest_summary(key)
        sop = _manifest.manifest_sop(key)
        if summ:
            block = summ
            if sop:
                block += "\nSOP：\n" + sop
            manifest_blocks.append(block)
    manifest_block = "\n\n".join(manifest_blocks) if manifest_blocks else "(暂无 manifest)"

    return (
        "你是 Abaqus 参数化建模智能体，目标是把复杂的有限元建模、校验、提交工作，"
        "变成用户一句自然语言就能完成。\n\n"
        "工作纪律：\n"
        "1. manifest 已声明的参数含义/可行域/闸门契约/SOP，直接照做，禁止再 search_knowledge 检索；"
        "只有 manifest 没覆盖的细节才查一次，查到就立即动手，禁止反复检索；\n"
        "2. 单个参数组合：先 generate_model 生成，再 run_check 校验；\n"
        "3. 批量参数扫描（如 CC=50/60/.../100）：用 batch_run 一次完成，禁止逐个 generate_model+run_check 机械循环；\n"
        "4. 关键结论用 remember 记入长期记忆；\n"
        "5. 回答先给结论、再给依据，客观、简洁、不夸大；任务完成就停止，不要重复调用工具；\n"
        "6. 【硬性规则】涉及梁/柱/框架/杆系结构，generate_model 之前必须先确认单元类型：杆系用 B31 梁单元（只看整体内力），"
        "还是壳单元 S4R（能看局部屈曲/板件应力）？用户未明确指定时绝不能默认按 B31 直接生成，必须先问这一条；\n"
        "7. 【无案例兜底】用 match_case 匹配内置案例，命中 <2 个即无相似案例：不要硬套。按 docs/general_modeling_skill.md 的十步范式从零建——"
        "先 plan_model 列草案，缺失的几何/材料/边界必须问用户，不确定的关键字用 web_search 查 Abaqus 文档，绝不编造数值；命中 ≥2 时优先改造最像的案例，不要从零重写；\n"
        "8. 【运行确认】模型生成（generate_model / write_inp / append_inp）成功后，必须主动问一句"
        "「要不要现在提交 Abaqus 运行？CPU 核数用多少、要不要开 GPU（仅 Explicit 支持）」；"
        "用户明确说运行就直接 submit_job，cpus/gpus 按用户给的值，用户没给就用 config 默认并说明；"
        "提交前先 run_check 校验，有 ERROR 不要盲目提交；长作业用 wait=False 后台跑，再用 job_status 轮询。\n\n"
        "9. 【失败必须修复，不许停在报错】作业没跑成（NOT_STARTED / ABORTED / .msg 有 ERROR）时，"
        "固定按三步走，不许把报错原样丢给用户就结束：\n"
        "   (1) 先 job_status 拿到诊断（会附报错原文 + 原因 + 修法）；\n"
        "   (2) 再 repair_inp 自动改能确定的行（nlgeom 层级、*Dynamic, Implicit、steady-state、"
        "重复 *End Step、*Buckle 迭代、缺 *Conductivity、*Temperature 改 DOF 11 等）；"
        "它改不动的（缺预载步、约束不足、不收敛、截面参数）才按诊断自己去改，改前说明改哪一行；\n"
        "   (3) run_check 通过后重新 submit_job，再 job_status 确认 COMPLETED。\n"
        "   同一作业最多修 3 轮；3 轮还不成，就把「卡在哪条报错、试过什么」如实告诉用户，"
        "不要假称跑通，也不要无限重试。\n"
        "   物理性问题（精度不对、结果与理论差很多）不靠 repair_inp，要单独核对并说明口径。\n\n"
        "建模任务流程（用户要求建有限元模型时遵守）：\n"
        + _mk.MODELING_SOP + "\n\n"
        f"当前已接入技能：{', '.join(skills) if skills else '(无)'}\n\n"
        f"技能契约（manifest，已覆盖信息勿再检索）：\n{manifest_block}\n\n"
        f"长期记忆（供参考）：\n{fact_block}"
    )


BUDGET_EXHAUSTED_NOTE = (
    "【预算耗尽】本次任务的工具调用轮数已用完，现在禁止再调用任何工具。"
    "直接用已获得的信息给出最终回答：说清做到哪一步、哪些还没做完、下一步需要用户提供什么。"
)


def budget_state(used: int, max_steps: int) -> dict:
    """按已用轮数决定本轮还能不能调用工具。

    normal：正常绑定工具；hint：只提醒剩余轮数；final：不再给工具，强制收敛。
    """
    left = max_steps - used
    if left <= 0:
        return {"mode": "final", "left": left, "note": BUDGET_EXHAUSTED_NOTE}
    if left <= 2:
        return {"mode": "hint", "left": left,
                "note": f"【只剩 {left} 轮工具调用】不要再开启新的校验或探索流程，"
                        "优先收敛：能交付就直接给结论，做不到就说明卡在哪。"}
    return {"mode": "normal", "left": left, "note": None}


def build_agent():
    llm = _build_llm()
    tools = _tool_wrappers()
    llm_with_tools = llm.bind_tools(tools)
    system = _system_prompt()
    # 工具调用预算：一轮 = 一次 LLM 决策（可能带多个并行工具调用）
    max_steps = int(_cfg_mod.load_config()["agent"].get("max_steps", 12))

    def chatbot(state: AgentState):
        msgs = list(state["messages"])
        if not msgs or getattr(msgs[0], "type", None) != "system":
            msgs = [SystemMessage(content=system)] + msgs
        used = sum(1 for m in msgs if getattr(m, "type", None) == "ai")
        bs = budget_state(used, max_steps)
        # 预算耗尽时不再给工具：用纯 LLM 收敛，避免撞 LangGraph 的 recursion_limit 硬崩
        if bs["mode"] == "final":
            return {"messages": [llm.invoke(msgs + [SystemMessage(content=bs["note"])])]}
        if bs["note"]:
            msgs = msgs + [SystemMessage(content=bs["note"])]
        return {"messages": [llm_with_tools.invoke(msgs)]}

    builder = StateGraph(AgentState)
    builder.add_node("chatbot", chatbot)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "chatbot")
    builder.add_conditional_edges("chatbot", tools_condition)
    builder.add_edge("tools", "chatbot")
    graph = builder.compile()
    # 递归上限：每轮最多 chatbot + tools 两步，再留余量给收尾回答
    return graph.with_config({"recursion_limit": max_steps * 2 + 8})
