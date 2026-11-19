# -*- coding: utf-8 -*-
"""技能 manifest：声明每个参数化建模技能的参数契约、CLI 契约、闸门契约与 SOP。

manifest 放在项目根 manifests/<skill>.yaml，是「接一个新技能」时唯一要写的数据文件。
工具层据此做参数预检与通用执行，不必再为每个技能硬编码。

本模块只依赖标准库 + pyyaml（项目已有依赖），不引入 langchain/langgraph。
"""
from __future__ import annotations

import json
import math
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

from . import config as _cfg_mod

MANIFEST_DIR = _cfg_mod.ROOT / "manifests"


def load_manifest(skill: str) -> dict:
    """加载 manifests/<skill>.yaml；缺失或损坏时返回空 dict（向后兼容）。"""
    p = MANIFEST_DIR / f"{skill}.yaml"
    if not p.exists():
        return {}
    try:
        import yaml

        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return data if isinstance(data, dict) else {}


# --------------------------------------------------------------------------- 参数校验
def _to_float(v: Any) -> float:
    if isinstance(v, bool):
        raise ValueError
    return float(v)


def _param_issues(name: str, spec: dict, value: Any, params: dict) -> List[dict]:
    """对单个参数做类型 / 枚举 / 范围 / 规则 / 正则校验，返回 issue 列表。"""
    issues: List[dict] = []
    t = spec.get("type")
    norm = value
    if t == "float":
        try:
            norm = _to_float(value)
        except (TypeError, ValueError):
            issues.append(dict(level="error", field=name,
                               msg=f"非法参数 {name}：必须是数字，收到 {value!r}"))
            return issues
    elif t == "int":
        try:
            norm = int(value)
        except (TypeError, ValueError):
            issues.append(dict(level="error", field=name,
                               msg=f"非法参数 {name}：必须是整数，收到 {value!r}"))
            return issues
    elif t == "str":
        norm = str(value)
    elif t == "bool":
        norm = bool(value)
    elif t == "list":
        if not isinstance(value, (list, tuple)):
            issues.append(dict(level="error", field=name,
                               msg=f"非法参数 {name}：必须是列表，收到 {value!r}"))
            return issues
        norm = list(value)

    if "enum" in spec and norm not in spec["enum"]:
        issues.append(dict(level="error", field=name,
                           msg=f"非法参数 {name}：只支持 {'/'.join(map(str, spec['enum']))}，收到 {value!r}"))
    if t in ("float", "int"):
        if "min" in spec and norm < spec["min"]:
            issues.append(dict(level="error", field=name,
                               msg=f"参数 {name}={value} 超出下限 {spec['min']}（不可行）"))
        if "max" in spec and norm > spec["max"]:
            issues.append(dict(level="error", field=name,
                               msg=f"参数 {name}={value} 超出上限 {spec['max']}（不可行）"))
    if "pattern" in spec and t == "str" and not re.match(spec["pattern"], norm):
        issues.append(dict(level="error", field=name,
                           msg=f"非法参数 {name}：{value!r} 不符合命名规则"))
    return issues


def validate_params(skill: str, params: Dict[str, Any]) -> List[dict]:
    """校验一组参数；只校验 manifest 里已声明的参数，未声明的透传（由 build 脚本自行校验）。"""
    m = load_manifest(skill)
    spec = m.get("params", {})
    issues: List[dict] = []
    for name, value in (params or {}).items():
        if value is None:
            continue
        if name in spec:
            issues.extend(_param_issues(name, spec[name], value, params))
    return issues


def blocked(issues: List[dict]) -> bool:
    return any(i["level"] == "error" for i in issues)


def format_issues(issues: List[dict]) -> str:
    return "\n".join(f"- [{i['level']}] {i['msg']}" for i in issues)


# --------------------------------------------------------------------------- 摘要 / SOP
def manifest_summary(skill: str) -> str:
    """把 manifest 压缩成人话摘要，注入 system prompt（已覆盖的信息禁止再检索）。"""
    m = load_manifest(skill)
    if not m:
        return ""
    lines = [f"### 技能 {skill}（{m.get('name', skill)}）"]
    params = m.get("params", {})
    if params:
        lines.append("参数契约：")
        for name, spec in params.items():
            bits = []
            if "type" in spec:
                bits.append(spec["type"])
            if "enum" in spec:
                bits.append("枚举 " + "/".join(map(str, spec["enum"])))
            if "min" in spec or "max" in spec:
                bits.append(f"范围 {spec.get('min', '-∞')}~{spec.get('max', '∞')}")
            desc = spec.get("desc", "")
            lines.append(f"  - {name}: {'；'.join(bits)}" + (f" — {desc}" if desc else ""))
    validators = m.get("validators", [])
    if validators:
        lines.append("闸门契约：")
        for v in validators:
            cli = v.get("cli") or (v.get("script", "") + " <inp>")
            lines.append(f"  - {v['script']}: {v.get('desc', '')}；调用 {cli}")
    return "\n".join(lines)


def manifest_sop(skill: str) -> str:
    return load_manifest(skill).get("sop", "")


def cli_mode(skill: str) -> str:
    """参数 -> 命令行的映射方式：flags（逐个 --flag 值，默认）/ params_file（写 JSON 传 --params-file）。"""
    return load_manifest(skill).get("cli", {}).get("mode", "flags")


def build_params_file(params: Dict[str, Any]) -> str:
    """把参数写到临时 JSON 文件，返回路径（供 mode=params_file 的 build 脚本使用）。"""
    fd, path = tempfile.mkstemp(prefix="params_", suffix=".json")
    with open(fd, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False)
    return path
