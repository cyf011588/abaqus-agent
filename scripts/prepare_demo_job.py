# -*- coding: utf-8 -*-
"""录屏前准备：造一个"真实失败"的作业，供 Web 案例库里演示 诊断 → 自动修 → 重跑。

用法：
    .\\.venv\\Scripts\\python.exe scripts\\prepare_demo_job.py

产物：data/output/broken_demo/DEMO_RD.inp（故意写错的 *Dload）+ 真实失败的 .msg/.dat。
跑完后在 http://localhost:8502 的「案例库」里能看到这一行 ❌ 失败，选中它做诊断/自动修/重跑。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import abaqus_run as ar

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "output" / "broken_demo"
SRC = ROOT / "data" / "output" / "axisym" / "AXISYM.inp"
JOB = "DEMO_RD"
ABQ = r"D:\SIMULIA\Commands\abq2020.bat"


def main() -> int:
    if not SRC.exists():
        print(f"[!] 缺少 {SRC}")
        return 1
    DEMO.mkdir(parents=True, exist_ok=True)
    for old in DEMO.glob(f"{JOB}.*"):
        old.unlink()
    bad = SRC.read_text(encoding="utf-8").replace("*Dsload", "*Dload")
    (DEMO / f"{JOB}.inp").write_text(bad, encoding="utf-8")

    argv = ar.resolve_argv(ar.build_argv(ABQ, JOB, 2, 0, False,
                                        extra=["interactive", "ask_delete=OFF"]))
    proc = subprocess.run(argv, cwd=str(DEMO), capture_output=True, text=True,
                          env=ar.abq_env(), timeout=600)
    tail = (proc.stdout or "").strip().splitlines()
    print("求解末尾：", tail[-1] if tail else "(无输出)")
    dat = DEMO / f"{JOB}.dat"
    n = dat.read_text(encoding="utf-8", errors="replace").count("***ERROR") if dat.exists() else 0
    print(f"已生成 {DEMO}，.dat 里 {n} 条 ***ERROR —— 案例库里会显示为 ❌ 失败")
    return 0


if __name__ == "__main__":
    sys.exit(main())
