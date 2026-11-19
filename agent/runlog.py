# -*- coding: utf-8 -*-
"""运行日志：把每次任务的结构化信息落盘到 data/runs/<timestamp>.json。

供 G3 评估统计与简历量化使用：任务文本、工具调用序列、耗时、token 用量、成败。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config as _cfg_mod


def _runs_dir() -> Path:
    d = _cfg_mod.ROOT / "data" / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def extract_tool_calls(messages: List[Any]) -> List[str]:
    """从 LangChain 消息列表里抽出工具调用名序列（AIMessage.tool_calls 的 name）。"""
    seq: List[str] = []
    for m in messages:
        for tc in getattr(m, "tool_calls", []) or []:
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
            if name:
                seq.append(name)
    return seq


def extract_token_usage(messages: List[Any]) -> Dict[str, int]:
    """累加 AIMessage 的 token 用量（DeepSeek 走 response_metadata / usage_metadata）。"""
    total: Dict[str, int] = {}
    for m in messages:
        u = getattr(m, "response_metadata", {}).get("token_usage")
        if not isinstance(u, dict):
            u = getattr(m, "usage_metadata", None)
        if isinstance(u, dict):
            for k, v in u.items():
                if isinstance(v, int):
                    total[k] = total.get(k, 0) + v
    return total


def save_run(
    task: str,
    ok: bool,
    elapsed_sec: float,
    error: str = "",
    tool_calls: Optional[List[str]] = None,
    token_usage: Optional[Dict[str, int]] = None,
) -> Path:
    """落盘一次运行记录，返回 JSON 文件路径。"""
    ts = int(time.time() * 1000)
    record = {
        "ts": ts,
        "task": task,
        "ok": ok,
        "error": error,
        "elapsed_sec": round(elapsed_sec, 3),
        "tool_calls": tool_calls or [],
        "token_usage": token_usage or {},
    }
    path = _runs_dir() / f"{ts}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
