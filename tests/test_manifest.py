# -*- coding: utf-8 -*-
"""manifest 参数预检的单元测试（纯逻辑，不依赖 Abaqus / LLM）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import manifest as m
from agent import tools as t


def _check(skill, params):
    return t._precheck(skill, params)


def test_non_numeric_blocked():
    """float 参数收到非数字 -> 预检拦下。"""
    for bad in ("abc", "一百", "10mm"):
        assert "参数预检未通过" in (_check("cantilever", {"L": bad}) or "")


def test_int_non_numeric_blocked():
    """int 参数收到非整数 -> 预检拦下。"""
    assert "参数预检未通过" in (_check("cantilever", {"nx": "十"}) or "")


def test_below_min_blocked():
    """低于 min 的几何值不可行。"""
    msg = _check("cantilever", {"L": 0.5}) or ""
    assert "超出下限" in msg


def test_bad_job_name_blocked():
    """作业名必须匹配命名规则。"""
    msg = _check("cantilever", {"job": "bad name!"}) or ""
    assert "命名规则" in msg


def test_valid_params_pass():
    assert _check("cantilever", {"L": 100, "W": 10, "H": 10, "P": 1000,
                                 "nx": 20, "ny": 2, "nz": 2, "job": "JOB1"}) is None


def test_cli_mode_default_flags():
    assert m.cli_mode("cantilever") == "flags"
    assert m.cli_mode("nonexistent") == "flags"
