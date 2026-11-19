# -*- coding: utf-8 -*-
"""inp_doctor 规则库测试：把真机踩过的每类报错固化一条断言。

这些报错原文都来自 2026-11-15 真跑 13 个案例时的 .dat / .msg。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import inp_doctor as d  # noqa: E402

SAMPLES = [
    ("***ERROR: in keyword *DYNAMIC, file \"x.inp\", line 105: Unknown parameter: implicit.",
     "*Dynamic"),
    ("***ERROR: in keyword *STATIC, file \"x.inp\", line 101: Unknown parameter: nlgeom.",
     "nlgeom=YES"),
    ("***ERROR: in keyword *COUPLEDTEMPERATURE-DISPLACEMENT: Unknown parameter: steady-state.",
     "steady state"),
    ("***ERROR: ELEMENT 1 IS AN ELEMENT WITH TEMPERATURE DEGREES OF FREEDOM. "
     "IT REQUIRES A THERMAL CONDUCTIVITY PROPERTY DEFINITION", "Conductivity"),
    ("***ERROR: *TEMPERATURE MAY NOT BE USED WITH ELEMENTS THAT POSSESS TEMPERATURE "
     "DEGREES OF FREEDOM.", "DOF 11"),
    ("***ERROR: TEMPERATURE BOUNDARY CONDITION VIA DOF 11 IS SPECIFIED FOR NODE 21 "
     "IN A *STATIC PROCEDURE.", "op=NEW"),
    ("***ERROR: ONLY DEGREES OF FREEDOM 11 AND ABOVE CAN BE ACTIVE IN THE MODEL "
     "FOR THIS PROCEDURE.", "Coupled Temperature-Displacement"),
    ("***ERROR: THE EIGENVALUES CANNOT BE FOUND. THIS COULD BE CAUSED DUE TO "
     "INSTABILITIES IN THE BASE STATE", "*Buckle"),
    ("***ERROR: INCREASE THE NUMBER OF ITERATIONS TO GET THE REQUESTED NUMBER OF "
     "EIGENVALUES", "40"),
    ("***ERROR: STEP DEFINITION CARDS BETWEEN *END STEP AND *STEP ARE IGNORED.",
     "*End Step"),
    ("***ERROR: in keyword *KINEMATIC, file \"x.inp\", line 54: The keyword is misplaced.",
     "assembly"),
    ("***ERROR: The web thickness (t3) must be greater than zero.",
     "l, h, b1, b2, t1, t2, t3"),
    ("***ERROR: NUMERICAL SINGULARITY WHEN PROCESSING NODE 3.", "刚体位移"),
]

# 真实 Abaqus 里 KINEMATIC 报错的原文次序不同，这里单独验证"层级"这条
EXTRA = [
    ("***ERROR: in keyword *KINEMATIC, file \"x.inp\", line 54: The keyword \n"
     "is misplaced. It can be suboption for the following keyword(s)/level(s): "
     "assembly, instance, coupling, part", "assembly"),
]


def test_every_sample_hits_a_rule():
    missing = []
    for text, expect in SAMPLES + EXTRA:
        rule = d.match_rule(text)
        if rule is None:
            missing.append(text[:60])
            continue
        assert expect in rule["fix"], f"{text[:50]} -> 修法里应含 {expect}"
    assert not missing, "未命中规则的报错: " + "; ".join(missing)


def test_diagnose_reads_dat_and_reports(tmp_path):
    dat = tmp_path / "BADJob.dat"
    dat.write_text(
        "***ERROR: in keyword *STATIC, file \"BADJob.inp\", line 101: "
        "Unknown parameter: nlgeom. The parameter may be misspelled.\n"
        "\n"
        "***ERROR: THE EIGENVALUES CANNOT BE FOUND. THIS COULD BE CAUSED DUE TO \n"
        "          INSTABILITIES IN THE BASE STATE\n",
        encoding="utf-8",
    )
    text = d.diagnose(tmp_path, "BADJob")
    assert "共 2 条 ERROR" in text
    assert "nlgeom" in text and "nlgeom=YES" in text
    assert "Preload" in text or "预载" in text


def test_diagnose_without_error_returns_clean_message(tmp_path):
    (tmp_path / "OK.dat").write_text("THE ANALYSIS HAS COMPLETED SUCCESSFULLY\n", encoding="utf-8")
    assert "没有找到 ***ERROR" in d.diagnose(tmp_path, "OK")


def test_unknown_error_is_flagged(tmp_path):
    (tmp_path / "X.dat").write_text("***ERROR: SOMETHING NOBODY HAS SEEN BEFORE\n", encoding="utf-8")
    text = d.diagnose(tmp_path, "X")
    assert "未收录" in text


def test_auto_patch_nlgeom_and_dup_endstep(tmp_path):
    inp = tmp_path / "P.inp"
    inp.write_text(
        "*Heading\n"
        "*Step, name=LargeDeflection\n"
        "*Static, nlgeom=YES\n"
        "1., 1., 1e-5, 1.\n"
        "*End Step\n"
        "*End Step\n",
        encoding="utf-8",
    )
    (tmp_path / "P.dat").write_text(
        "***ERROR: in keyword *STATIC, file \"P.inp\", line 3: Unknown parameter: nlgeom.\n"
        "***ERROR: STEP DEFINITION CARDS BETWEEN *END STEP AND *STEP ARE IGNORED.\n",
        encoding="utf-8",
    )
    report = d.auto_patch(tmp_path, "P")
    text = inp.read_text(encoding="utf-8")
    assert "自动改 2 处" in report
    assert "*Step, name=LargeDeflection, nlgeom=YES" in text
    assert "*Static, nlgeom" not in text
    assert text.count("*End Step") == 1
    assert (tmp_path / "P.inp.bak").exists()


def test_auto_patch_leaves_manual_only_alone(tmp_path):
    inp = tmp_path / "B.inp"
    orig = "*Heading\n*Step, name=Buckle\n*Buckle\n4, , 30\n*End Step\n"
    inp.write_text(orig, encoding="utf-8")
    (tmp_path / "B.dat").write_text(
        "***ERROR: THE EIGENVALUES CANNOT BE FOUND.\n", encoding="utf-8"
    )
    report = d.auto_patch(tmp_path, "B")
    assert "没有可自动应用的改动" in report
    assert "需人工处理" in report
    assert inp.read_text(encoding="utf-8") == orig  # 一个字都不能动


def test_auto_patch_buckle_iterations(tmp_path):
    inp = tmp_path / "K.inp"
    inp.write_text("*Step, name=B\n*Buckle\n4, , 30\n*End Step\n", encoding="utf-8")
    (tmp_path / "K.dat").write_text(
        "***ERROR: INCREASE THE NUMBER OF ITERATIONS TO GET THE REQUESTED NUMBER "
        "OF EIGENVALUES\n", encoding="utf-8",
    )
    d.auto_patch(tmp_path, "K")
    assert "4, , 40" in inp.read_text(encoding="utf-8")


def test_auto_patch_dload_surface_to_dsload(tmp_path):
    """*Dload 的数据行写的是 *Surface 名 → 自动改成 *Dsload。"""
    inp = tmp_path / "S.inp"
    inp.write_text(
        "*Heading\n*Surface, type=ELEMENT, name=TOP\n1, S3\n"
        "*Step, name=Pressure\n*Static\n*Dload\nTOP, P, 10.0\n*End Step\n",
        encoding="utf-8",
    )
    (tmp_path / "S.dat").write_text(
        '***ERROR: in keyword *DLOAD, file "S.inp", line 7: Unknown assembly\n'
        "***ERROR: ELEMENT SET TOP HAS NOT BEEN DEFINED\n", encoding="utf-8",
    )
    report = d.auto_patch(tmp_path, "S")
    text = inp.read_text(encoding="utf-8")
    assert "*Dsload" in text
    assert "*Dload\n" not in text
    assert "Dsload" in report
    assert (tmp_path / "S.inp.bak").exists()


def test_auto_patch_keeps_dload_when_name_is_elset(tmp_path):
    """名字是 elset 时不能乱改成 *Dsload。"""
    inp = tmp_path / "E.inp"
    orig = "*Heading\n*Elset, elset=ALL\n1, 2\n*Step, name=P\n*Static\n*Dload\nALL, P, 0.1\n*End Step\n"
    inp.write_text(orig, encoding="utf-8")
    (tmp_path / "E.dat").write_text(
        "***ERROR: ELEMENT SET XXX HAS NOT BEEN DEFINED\n", encoding="utf-8"
    )
    d.auto_patch(tmp_path, "E")
    assert inp.read_text(encoding="utf-8") == orig


def test_new_rules_cover_real_errors():
    from agent import inp_doctor as dd
    cases = {
        "***ERROR: ELEMENT SET TOP HAS NOT BEEN DEFINED": "*Dsload",
        "***ERROR: 80 elements have missing property definitions.": "*Solid Section",
        "***ERROR: SURFACE TOP_BOT IS NOT CONTINUOUS OR IS COMPOSED OF TWO OR MORE": "连续",
        "Unable to open C:\\Temp\\abqscratch\\u_J_1\\J.stf.": "scratch",
    }
    for msg, hint in cases.items():
        rule = dd.match_rule(msg)
        assert rule is not None, msg
        assert hint in rule["fix"], (msg, rule["fix"])
