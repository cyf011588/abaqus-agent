# -*- coding: utf-8 -*-
"""加载 config.yaml 与 .env，暴露运行时配置。

依赖：pyyaml（requirements.txt 已列出）；python-dotenv 可选。
技能注册表独立放在 skills.yaml，方便增删改（数据与配置分离）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CONFIG_PATH = ROOT / "config.yaml"
ENV_PATH = ROOT / ".env"
SKILLS_PATH = ROOT / "skills.yaml"
# 本地私有技能（真实项目、路径只在本机有效）：不进 git，加载时覆盖/追加到公共注册表
SKILLS_LOCAL_PATH = ROOT / "skills.local.yaml"


def _load_env() -> None:
    """把 .env 注入环境变量。优先用 python-dotenv，缺失时手动解析 KEY=VALUE 行。"""
    if not ENV_PATH.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_PATH)
        return
    except ImportError:
        pass
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _read_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        sys.stderr.write("缺少 pyyaml，请先执行：pip install -r requirements.txt\n")
        raise exc
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _load_skills() -> dict:
    """从 skills.yaml 读技能注册表；兼容旧的 projects.yaml 与 config.yaml 的 projects 段。

    skills.local.yaml 若存在，会覆盖同名条目并追加新条目——用来放真实项目
    （路径只在本机有效），这样公共 skills.yaml 可以干净发布。
    """
    skills: dict = {}
    if SKILLS_PATH.exists():
        data = _read_yaml(SKILLS_PATH)
        base = data.get("skills", data)
        if isinstance(base, dict):
            skills = dict(base)
    if SKILLS_LOCAL_PATH.exists() and os.environ.get("ABAQUS_AGENT_NO_LOCAL") != "1":
        data = _read_yaml(SKILLS_LOCAL_PATH)
        local = data.get("skills", data)
        if isinstance(local, dict):
            skills.update(local)
    # 界面里导入的技能写在这里：不受 NO_LOCAL 影响，导入后立刻生效
    imported = ROOT / "skills.imported.yaml"
    if imported.exists():
        data = _read_yaml(imported)
        extra = data.get("skills", data)
        if isinstance(extra, dict):
            skills.update(extra)
    if skills:
        return skills
    legacy_path = ROOT / "projects.yaml"
    if legacy_path.exists():
        data = _read_yaml(legacy_path)
        skills = data.get("projects", data)
        if isinstance(skills, dict):
            return skills
    if CONFIG_PATH.exists():
        legacy = _read_yaml(CONFIG_PATH).get("projects", {})
        if isinstance(legacy, dict):
            return legacy
    return {}


def load_config() -> dict:
    """加载并返回完整配置（config.yaml + skills.yaml 合并）。"""
    _load_env()
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"缺少配置文件：{CONFIG_PATH}")
    cfg = _read_yaml(CONFIG_PATH)
    cfg["skills"] = _load_skills()
    return cfg


def save_skills(skills: dict) -> None:
    """把技能注册表写回 skills.yaml（增删改技能时调用）。"""
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        sys.stderr.write("缺少 pyyaml，请先执行：pip install -r requirements.txt\n")
        raise exc
    with open(SKILLS_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {"skills": skills},
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )
