# -*- coding: utf-8 -*-
"""工具层核心函数测试（全 mock，不依赖 Abaqus 与外部技能项目）。"""
from __future__ import annotations

from pathlib import Path

from agent import tools


# --------------------------------------------------------------------------- submit_job / job_status：作业名拼接
def test_submit_job_name_no_buck(monkeypatch, tmp_path):
    """buck=False 时作业名必须等于 job，不能变成 job+job（回归）。"""
    monkeypatch.setattr(tools, "_cfg", lambda: {"abaqus": {"command": "abq", "cpus": 4}})
    (tmp_path / "M27.inp").write_text("*Heading\n", encoding="utf-8")
    captured = {}

    def fake_run(cmd, cwd, timeout=86400):
        captured["cmd"] = cmd
        return 0, "ok"

    monkeypatch.setattr(tools, "_run", fake_run)
    tools.submit_job(str(tmp_path), "M27", buck=False)
    # resolve_argv 可能把 abq 包成 cmd /c <abq2020.bat> ...，所以按"参数里含 job="断言
    assert any("job=M27" in c for c in captured["cmd"])


def test_submit_job_name_buck(monkeypatch, tmp_path):
    monkeypatch.setattr(tools, "_cfg", lambda: {"abaqus": {"command": "abq", "cpus": 4}})
    (tmp_path / "M27-BUCK.inp").write_text("*Heading\n", encoding="utf-8")
    captured = {}

    def fake_run(cmd, cwd, timeout=86400):
        captured["cmd"] = cmd
        return 0, "ok"

    monkeypatch.setattr(tools, "_run", fake_run)
    tools.submit_job(str(tmp_path), "M27", buck=True)
    assert any("job=M27-BUCK" in c for c in captured["cmd"])


def test_job_status_name_no_buck(tmp_path):
    """buck=False 时读取 job.sta（回归：旧 bug 会去找 jobjob.sta）。"""
    (tmp_path / "M27.sta").write_text(
        "THE ANALYSIS HAS COMPLETED SUCCESSFULLY\n", encoding="utf-8"
    )
    r = tools.job_status(str(tmp_path), "M27", buck=False)
    assert "COMPLETED" in r


def test_job_status_name_buck(tmp_path):
    (tmp_path / "M27-BUCK.sta").write_text(
        "THE ANALYSIS HAS COMPLETED SUCCESSFULLY\n", encoding="utf-8"
    )
    r = tools.job_status(str(tmp_path), "M27", buck=True)
    assert "COMPLETED" in r


# --------------------------------------------------------------------------- generate_model：参数转 CLI flags
def test_generate_flags(monkeypatch, tmp_path):
    """参数 → CLI flag：bool 转开关、None 跳过、下划线转连字符。"""
    monkeypatch.setattr(
        tools, "_skill", lambda s: {"root": str(tmp_path), "build_script": "build.py"}
    )
    monkeypatch.setattr(tools, "_root", lambda s: tmp_path)
    captured = {}

    def fake_run(cmd, cwd, timeout=86400):
        captured["argv"] = cmd
        return 0, ""

    monkeypatch.setattr(tools, "_run", fake_run)
    tools._generate(
        "cantilever",
        {"sp": 10, "cc": 80, "fin_classic": True, "skip": None},
        job="J1",
        out="cantilever",
    )
    argv = captured["argv"]
    assert argv.count("--sp") == 1 and "10" in argv
    assert argv.count("--cc") == 1 and "80" in argv
    assert argv.count("--fin-classic") == 1
    assert "--skip" not in argv
    assert "--job" in argv and "J1" in argv
    assert "--out" in argv


# --------------------------------------------------------------------------- run_check：闸门名匹配（带/不带 .py）
def test_run_check_py_suffix_tolerance(monkeypatch, tmp_path):
    monkeypatch.setattr(
        tools,
        "_skill",
        lambda s: {"root": str(tmp_path), "validators": [{"script": "check_geom.py", "desc": "geom"}]},
    )
    monkeypatch.setattr(tools, "_root", lambda s: tmp_path)
    captured = {}

    def fake_run(cmd, cwd, timeout=7200):
        captured["cmd"] = cmd
        return 0, "ok"

    monkeypatch.setattr(tools, "_run", fake_run)
    r = tools.run_check("cantilever", "check_geom", str(tmp_path / "x.inp"), extra_args=["--B", "300"])
    assert r.startswith("[PASS]")
    assert captured["cmd"][1] == "check_geom.py"
    assert captured["cmd"][-2:] == ["--B", "300"]


def test_run_check_unknown_gate(monkeypatch, tmp_path):
    monkeypatch.setattr(
        tools,
        "_skill",
        lambda s: {"root": str(tmp_path), "validators": [{"script": "check_geom.py", "desc": "geom"}]},
    )
    monkeypatch.setattr(tools, "_root", lambda s: tmp_path)
    r = tools.run_check("cantilever", "nope", str(tmp_path / "x.inp"))
    assert r.startswith("[FAIL]")


# --------------------------------------------------------------------------- batch_run：扫描参数追加
def test_batch_run_appends_sweep_value(monkeypatch):
    def fake_generate(skill, params, job=None, out=None):
        return True, Path("out"), [f"out/{params['cc']}.inp"], ""

    monkeypatch.setattr(tools, "_generate", fake_generate)
    calls = []

    def fake_run_check(skill, check, inp, extra_args=None):
        calls.append((inp, list(extra_args or [])))
        return "[PASS] x\n== 1/1 PASS"

    monkeypatch.setattr(tools, "run_check", fake_run_check)
    r = tools.batch_run(
        "cantilever",
        {"B": 300, "end_cols": 2},
        "cc",
        [50, 60],
        check="check_geom.py",
        check_extra_args=["--B", "300", "--end-cols", "2"],
    )
    assert calls[0][1] == ["--B", "300", "--end-cols", "2", "--cc", "50"]
    assert calls[1][1] == ["--B", "300", "--end-cols", "2", "--cc", "60"]
    assert "cc=50" in r and "cc=60" in r


# --------------------------------------------------------------------------- 输出目录逃逸防护
def test_out_escape_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(
        tools, "_skill", lambda s: {"root": str(tmp_path), "build_script": "build.py"}
    )
    monkeypatch.setattr(tools, "_root", lambda s: tmp_path)
    captured = {}

    def fake_run(cmd, cwd, timeout=86400):
        captured["argv"] = cmd
        return 0, ""

    monkeypatch.setattr(tools, "_run", fake_run)
    ok, out_dir, produced, text = tools._generate("cantilever", {"cc": 80}, out="../../evil")
    # 逃逸被拦回：输出目录必须落在 data/output/cantilever
    assert out_dir.name == "cantilever"
    assert "data" in out_dir.parts and "output" in out_dir.parts
    assert str(out_dir) in captured["argv"]


# --------------------------------------------------------------------------- generate_model 包装层
def test_generate_model_ok_and_remembers(monkeypatch, tmp_path):
    monkeypatch.setattr(
        tools, "_generate", lambda skill, params, job=None, out=None: (True, tmp_path, ["a.inp"], "")
    )
    called = {}

    def fake_remember(skill, job, params, status, summary):
        called["skill"] = skill

    monkeypatch.setattr(tools._memory, "remember_case", fake_remember)
    r = tools.generate_model("cantilever", {"cc": 80}, job="J1")
    assert r.startswith("[OK]")
    assert called.get("skill") == "cantilever"
