# -*- coding: utf-8 -*-
"""录屏镜头 6 用：故意造一个违例 inp，演示「失败 → 自动诊断 → 自动修 → 重跑成功」。

用法（在项目根目录）：
    .\\.venv\\Scripts\\python.exe scripts\\demo_self_repair.py

做的事：
1. 取内置案例 axisym 的 inp，把面载荷关键字 *Dsload 改回 *Dload（数据行填的是面名，*Dload 只认元素集）；
2. 真提交 Abaqus → 预期输入处理失败；
3. tools.job_status() 读出报错并自动附诊断；
4. tools.repair_inp() 自动把它改回去（备份 .inp.bak，逐条报告改了什么）；
5. 再提交一次 → COMPLETED；
6. 清理临时目录（不影响 data/output/axisym 本身）。

每一步都打印 [n] 标记，方便录屏时和旁白对齐。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import abaqus_run as ar
from agent import tools

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "data" / "output" / "_repair_demo"
JOB = "RD"
SRC = ROOT / "data" / "output" / "axisym" / "AXISYM.inp"
ABQ = r"D:\SIMULIA\Commands\abq2020.bat"


def _run(argv, cwd, timeout=300):
    p = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True,
                       env=ar.abq_env(), timeout=timeout)
    lines = (p.stdout or "").strip().splitlines()
    return lines[-1] if lines else "(无输出)"


def main() -> int:
    if not SRC.exists():
        print(f"[!] 缺少 {SRC}，先运行：python -m agent --dry-run  或生成 axisym 案例")
        return 1

    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    bad = SRC.read_text(encoding="utf-8").replace("*Dsload", "*Dload")
    (DEMO_DIR / f"{JOB}.inp").write_text(bad, encoding="utf-8")
    print("[1] 造坏点：把 *Dsload 改回 *Dload —— 数据行填的是面名 TOP，*Dload 只认元素集")

    argv = ar.resolve_argv(ar.build_argv(ABQ, JOB, 2, 0, False,
                                        extra=["interactive", "ask_delete=OFF"]))
    print("[2] 提交求解 …（预期输入处理失败）")
    print("    末尾：", _run(argv, DEMO_DIR))
    time.sleep(1)

    print("[3] job_status —— 自动带诊断：")
    status = tools.job_status(str(DEMO_DIR), JOB)
    for line in status.splitlines()[:10]:
        print("    " + line)

    print("[4] repair_inp —— 自动修：")
    for line in tools.repair_inp(str(DEMO_DIR), JOB).splitlines()[:6]:
        print("    " + line)

    print("[5] 改后的载荷关键字：",
          [l for l in (DEMO_DIR / f"{JOB}.inp").read_text(encoding="utf-8").splitlines()
           if l.startswith(("*Dsload", "*Dload"))])

    print("[6] 重跑：", _run(argv, DEMO_DIR))
    time.sleep(1)
    print("[7] 最终状态：", tools.job_status(str(DEMO_DIR), JOB).splitlines()[0])

    root_out = (ROOT / "data" / "output").resolve()
    if DEMO_DIR.resolve().is_relative_to(root_out):
        shutil.rmtree(DEMO_DIR, ignore_errors=True)
    print("[清理] 已删除临时目录 data/output/_repair_demo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
