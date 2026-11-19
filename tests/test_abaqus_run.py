# -*- coding: utf-8 -*-
"""abaqus_run：运行命令行构造、run 脚本生成、.sta 状态判定。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import abaqus_run as r


def test_build_argv_cpu_and_gpu():
    argv = r.build_argv("abq2020", "J1", cpus=8, gpus=2, double=True)
    assert argv[0] == "abq2020"
    assert "job=J1" in argv
    assert "cpus=8" in argv
    assert "gpus=2" in argv
    assert "double=both" in argv
    # int / ask=off 一定在，但后面可能追加 scratch=（中文路径环境下）
    assert "int" in argv and "ask=off" in argv


def test_scratch_arg_always_ascii():
    """TEMP/USERNAME 含中文时，命令行必须补英文 scratch，否则特征值分析会静默退出。"""
    sc = r.scratch_arg()
    if sc is not None:
        assert sc.startswith("scratch=")
        assert all(ord(ch) < 128 for ch in sc), sc
    env = r.abq_env()
    if env is not None:
        assert all(ord(ch) < 128 for ch in env["USERNAME"])


def test_scratch_dir_exists_when_needed():
    sc = r.scratch_arg()
    if sc is not None:
        assert Path(sc.split("=", 1)[1]).is_dir()


def test_build_argv_no_gpu_when_zero():
    argv = r.build_argv("abq2020", "J1", cpus=4, gpus=0, double=False)
    assert not any(a.startswith("gpus=") for a in argv)
    assert not any(a.startswith("double=") for a in argv)


def test_run_script_writes_defaults_and_usage():
    text = r.run_script_text("MYJOB", cpus=16, gpus=1, abq="D:/SIM/abq2020")
    assert "$Cpus = 16" in text
    assert "$Gpus = 1" in text
    assert '$job = "MYJOB"' in text
    assert "D:/SIM/abq2020" in text
    assert "-Cpus" in text and "-Gpus" in text and "-Status" in text


def test_write_run_script_creates_file(tmp_path):
    p = r.write_run_script(tmp_path / "sub", "T1", cpus=4, gpus=0)
    assert p.exists()
    assert p.name == "run_T1.ps1"
    raw = p.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM，PowerShell 5.1 识别中文
    assert "T1" in p.read_text(encoding="utf-8-sig")


def test_sta_state(tmp_path):
    assert r.sta_state(tmp_path, "X") == "NOT_STARTED"
    (tmp_path / "X.sta").write_text("some progress", encoding="utf-8")
    assert r.sta_state(tmp_path, "X") == "RUNNING"
    (tmp_path / "X.sta").write_text("THE ANALYSIS HAS COMPLETED SUCCESSFULLY", encoding="utf-8")
    assert r.sta_state(tmp_path, "X") == "COMPLETED"


def test_describe_mentions_gpu():
    assert "2 GPU" in r.describe("J", 8, 2, True)
    assert "无 GPU" in r.describe("J", 8, 0, False)


def test_resolve_argv_wraps_bat_in_cmd(monkeypatch):
    """abq2020 实际是 .bat，Windows 不能直接 CreateProcess（曾报 WinError 2）。"""
    monkeypatch.setattr(r.shutil, "which", lambda x: "D:\\SIMULIA\\Commands\\abq2020.BAT")
    argv = r.resolve_argv(["abq2020", "job=J", "cpus=10"])
    assert argv[1] == "/c"
    assert argv[2].lower().endswith(".bat")
    assert "job=J" in argv and "cpus=10" in argv


def test_resolve_argv_exe_passthrough(monkeypatch):
    monkeypatch.setattr(r.shutil, "which", lambda x: "C:\\x\\abq.exe")
    argv = r.resolve_argv(["abq", "job=J"])
    assert argv[0] == "C:\\x\\abq.exe"
    assert "/c" not in argv


def test_abq_path_found_and_missing(monkeypatch):
    monkeypatch.setattr(r.shutil, "which", lambda x: "D:\\SIMULIA\\Commands\\abq2020.BAT")
    assert r.abq_path("abq2020").lower().endswith(".bat")
    monkeypatch.setattr(r.shutil, "which", lambda x: None)
    assert r.abq_path("no_such_abq") is None
