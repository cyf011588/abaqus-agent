# -*- coding: utf-8 -*-
"""测试：从零建模落盘工具 write_inp（含路径穿越防护）。"""
from pathlib import Path

from agent import config as _cfg
from agent import tools


def test_write_inp_sanitizes_job():
    out = tools.write_inp("*Heading\n** test\n", "../../evil", "pytest_tmp")
    assert "[OK] 已写入" in out
    assert "evil.inp" in out
    assert "../" not in out


def test_write_inp_writes_file():
    out = tools.write_inp("*Heading\n*Node\n1,0,0,0\n", "tmp_inp", "pytest_tmp")
    assert "[OK] 已写入" in out
    p = _cfg.ROOT / "data" / "output" / "pytest_tmp" / "tmp_inp.inp"
    assert p.exists()
    p.unlink()
    # evil.inp 也清掉，保持目录干净
    e = _cfg.ROOT / "data" / "output" / "pytest_tmp" / "evil.inp"
    if e.exists():
        e.unlink()
