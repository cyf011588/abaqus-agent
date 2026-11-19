# -*- coding: utf-8 -*-
"""测试：从零建模分步落盘工具 mesh_inp / append_inp / write_inp。"""
from agent import config as _cfg
from agent import tools


def _clean(job, out="pytest_mesh"):
    p = _cfg.ROOT / "data" / "output" / out / f"{job}.inp"
    if p.exists():
        p.unlink()


def test_mesh_inp_rect_shell():
    _clean("tmp")
    out = tools.mesh_inp("rect_shell", '{"L":1000,"W":500,"nx":10,"ny":5}', "tmp", "pytest_mesh")
    assert "[OK] 已写网格骨架" in out
    p = _cfg.ROOT / "data" / "output" / "pytest_mesh" / "tmp.inp"
    assert p.exists()
    txt = p.read_text(encoding="utf-8")
    assert "*Node" in txt and "*Element, type=S4R" in txt and "*Nset, nset=X0" in txt
    _clean("tmp")


def test_mesh_inp_frame():
    _clean("fr")
    out = tools.mesh_inp("frame", '{"n_story":3,"n_bay":2,"h":3000,"L":6000}', "fr", "pytest_mesh")
    assert "[OK]" in out and "B31" in out
    _clean("fr")


def test_append_inp():
    _clean("ap")
    tools.mesh_inp("beam", '{"L":1000,"nx":10}', "ap", "pytest_mesh")
    out = tools.append_inp("*Material, name=STEEL\n*Elastic\n210000, 0.3", "ap", "pytest_mesh")
    assert "[OK] 已追加" in out
    p = _cfg.ROOT / "data" / "output" / "pytest_mesh" / "ap.inp"
    assert "*Elastic" in p.read_text(encoding="utf-8")
    _clean("ap")


def test_append_inp_missing():
    out = tools.append_inp("x", "no_such", "pytest_mesh")
    assert "[FAIL]" in out


def test_mesh_inp_missing_param():
    out = tools.mesh_inp("rect_shell", '{"L":1000}', "t2", "pytest_mesh")
    assert "[FAIL]" in out


def test_mesh_inp_bad_json():
    out = tools.mesh_inp("rect_shell", "not json", "t3", "pytest_mesh")
    assert "[FAIL]" in out


def test_mesh_inp_unknown_kind():
    out = tools.mesh_inp("foo", "{}", "t4", "pytest_mesh")
    assert "[FAIL]" in out
