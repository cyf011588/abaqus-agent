# -*- coding: utf-8 -*-
"""会话组织持久化：工作空间 → 项目 → 对话 → 消息。

数据存 data/sessions.json。这一层只管「用户怎么组织对话」，
与「agent 有哪些建模能力（skills.yaml，即 cantilever 这类 skill）」是两回事。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from . import config as _cfg_mod

_PATH = _cfg_mod.ROOT / "data" / "sessions.json"


def _load() -> Dict[str, Any]:
    if _PATH.exists():
        try:
            data = json.loads(_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {"workspaces": {}}


def _save(data: Dict[str, Any]) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_PATH)


def _ws(data: Dict[str, Any], workspace: str) -> Dict[str, Any]:
    return data.setdefault("workspaces", {}).setdefault(workspace, {"projects": {}})


# ------------------------------------------------------------------ 工作空间
def list_workspaces() -> List[str]:
    return list(_load()["workspaces"])


def ensure_default() -> str:
    """首次使用时生成一个默认工作空间 + 默认项目 + 一个空对话。"""
    data = _load()
    if not data["workspaces"]:
        conv_id = f"{int(time.time() * 1000)}"
        data["workspaces"]["默认工作空间"] = {
            "projects": {
                "默认项目": {"conversations": {conv_id: {"name": "新对话", "messages": []}}}
            }
        }
        _save(data)
    return list(data["workspaces"])[0]


def add_workspace(name: str) -> str:
    data = _load()
    data["workspaces"].setdefault(name, {"projects": {}})
    _save(data)
    return name


def remove_workspace(name: str) -> None:
    data = _load()
    data["workspaces"].pop(name, None)
    _save(data)


def rename_workspace(old: str, new: str) -> None:
    data = _load()
    ws = data["workspaces"]
    if old in ws:
        ws[new] = ws.pop(old)
        _save(data)


# ------------------------------------------------------------------ 项目
def list_projects(workspace: str) -> List[str]:
    return list(_load()["workspaces"].get(workspace, {}).get("projects", {}))


def add_project(workspace: str, name: str) -> None:
    data = _load()
    ws = _ws(data, workspace)
    ws["projects"].setdefault(name, {"conversations": {}})
    _save(data)


def remove_project(workspace: str, name: str) -> None:
    data = _load()
    data["workspaces"].get(workspace, {}).get("projects", {}).pop(name, None)
    _save(data)


def rename_project(workspace: str, old: str, new: str) -> None:
    data = _load()
    projs = data["workspaces"].get(workspace, {}).get("projects", {})
    if old in projs:
        projs[new] = projs.pop(old)
        _save(data)


# ------------------------------------------------------------------ 对话
def list_conversations(workspace: str, project: str) -> List[str]:
    projs = _load()["workspaces"].get(workspace, {}).get("projects", {})
    return list(projs.get(project, {}).get("conversations", {}))


def add_conversation(workspace: str, project: str, name: str = "新对话") -> str:
    data = _load()
    proj = _ws(data, workspace)["projects"].setdefault(project, {"conversations": {}})
    conv_id = f"{int(time.time() * 1000)}"
    proj["conversations"][conv_id] = {"name": name, "messages": []}
    _save(data)
    return conv_id


def remove_conversation(workspace: str, project: str, conv_id: str) -> None:
    data = _load()
    proj = data["workspaces"].get(workspace, {}).get("projects", {}).get(project, {})
    proj.get("conversations", {}).pop(conv_id, None)
    _save(data)


def rename_conversation(workspace: str, project: str, conv_id: str, name: str) -> None:
    data = _load()
    conv = (
        data["workspaces"]
        .get(workspace, {})
        .get("projects", {})
        .get(project, {})
        .get("conversations", {})
        .get(conv_id)
    )
    if conv:
        conv["name"] = name
        _save(data)


def get_conversation(workspace: str, project: str, conv_id: str) -> Dict[str, Any]:
    proj = _load()["workspaces"].get(workspace, {}).get("projects", {}).get(project, {})
    return proj.get("conversations", {}).get(conv_id, {"name": "新对话", "messages": []})


def get_messages(workspace: str, project: str, conv_id: str) -> List[dict]:
    return list(get_conversation(workspace, project, conv_id).get("messages", []))


def save_messages(workspace: str, project: str, conv_id: str, messages: List[dict]) -> None:
    """保存一段对话消息；若还是「新对话」标题，则用首条用户消息自动命名。"""
    data = _load()
    conv = (
        _ws(data, workspace)["projects"]
        .setdefault(project, {"conversations": {}})["conversations"]
        .setdefault(conv_id, {"name": "新对话", "messages": []})
    )
    if conv.get("name") in ("", "新对话"):
        first_user = next((m["content"] for m in messages if m.get("role") == "user"), None)
        if first_user:
            conv["name"] = first_user.strip().replace("\n", " ")[:12]
    conv["messages"] = messages
    _save(data)
