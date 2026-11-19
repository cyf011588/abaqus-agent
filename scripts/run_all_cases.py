# -*- coding: utf-8 -*-
"""批量真机求解 data/output 下的自建案例，并汇总 .sta / .msg 结果。

用法：
    .venv\\Scripts\\python.exe scripts\\run_all_cases.py                # 全部跑，并发 4，每作业 4 核
    ... --only thermal_seq,plate_nl                                     # 只跑指定案例
    ... --cpus 8 --jobs 3                                              # 改核数/并发
    ... --dry                                                          # 只看要做的事，不提交

产物：
    data/output/<case>/<JOB>.{odb,sim,dat,msg,sta,prt} + run_<JOB>.log
    docs/run_all_report.md（汇总表）
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent import abaqus_run as ar  # noqa: E402

# 案例目录 + inp 文件名（job 名取 inp 的 stem）
CASES = [
    ("cantilever", "ceshi1_fine.inp"),
    ("dynamic_explicit", "DYNAMIC_EXPLICIT.inp"),
    ("dynamic_implicit", "DYNAMIC_IMPLICIT.inp"),
    ("harmonic", "HARMONIC.inp"),
    ("nl_cantilever", "NL_CANTILEVER.inp"),
    ("plate_nl", "PLATE_NL.inp"),
    ("plate_hole", "PH-DEMO.inp"),
    ("axisym", "AXISYM.inp"),
    ("buckle_column", "BUCKLE_COLUMN.inp"),
    ("contact", "CONTACT.inp"),
    ("heat_slab", "HEAT_SLAB.inp"),
    ("l_bracket", "L_BRACKET.inp"),
    ("modal_beam", "MODAL_BEAM.inp"),
    ("plastic_plate", "PLASTIC_PLATE.inp"),
    ("ss_beam", "SS_BEAM.inp"),
    ("thick_cylinder", "THICK_CYLINDER.inp"),
    ("truss", "TRUSS.inp"),
    ("snap_through", "SNAP_THROUGH.inp"),
    ("steel_frame", "IFrame-1S1B.inp"),
    ("stiffened_plate", "StiffPlate-L1000-W500-T10-R50x10-P1-M4.inp"),
    ("thermal_plate", "THERMAL_PLATE.inp"),
    ("thermal_seq", "THERMAL_SEQ.inp"),
    ("thermal_stress", "THERMAL_STRESS.inp"),
    ("stiff_plate", "StiffPlate-Buckle.inp"),
]
# 已知没有 *Step 的纯网格/边界示例，跑不了（Abaqus 会报 no step）
NO_STEP = {"stiff_plate"}

OUT_SUFFIXES = (".sta", ".msg", ".dat", ".odb", ".sim", ".prt", ".lck", ".log")


def count_errors(msg: Path) -> int:
    if not msg.exists():
        return -1
    text = msg.read_text(encoding="utf-8", errors="replace")
    return len(re.findall(r"\*\*\*ERROR", text))


def clean(job: str, d: Path) -> None:
    for suf in OUT_SUFFIXES:
        for p in list(d.glob(f"{job}{suf}")) + list(d.glob(f"run_{job}.log")):
            try:
                p.unlink()
            except OSError:
                pass


def one_case(case: str, inp: str, cpus: int, gpus: int, double: bool, abq: str, timeout: float):
    d = ROOT / "data" / "output" / case
    inp_path = d / inp
    if not inp_path.exists():
        return {"case": case, "job": inp, "state": "缺少 inp", "sec": 0, "err": -1, "note": ""}
    job = inp_path.stem
    clean(job, d)
    argv = ar.resolve_argv(ar.build_argv(abq, job, cpus, gpus, double, extra=["interactive", "ask_delete=OFF"]))
    log_path = d / f"run_{job}.log"
    t0 = time.time()
    proc = subprocess.Popen(
        argv, cwd=str(d),
        stdout=open(log_path, "w", encoding="utf-8", errors="replace"),
        stderr=subprocess.STDOUT,
        env=ar.abq_env(),
    )
    state = "RUNNING"
    while True:
        time.sleep(2)
        st = ar.sta_state(d, job)
        if proc.poll() is not None:
            state = st if st == "COMPLETED" else ("失败" if proc.returncode else st)
            break
        if time.time() - t0 > timeout:
            proc.kill()
            state = "超时"
            break
        state = st
    sec = round(time.time() - t0, 1)
    err = count_errors(d / f"{job}.msg")
    note = ""
    if state != "COMPLETED":
        tail = ""
        if log_path.exists():
            tail = " / ".join(
                ln.strip() for ln in log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-6:]
                if ln.strip()
            )[:300]
        note = tail
    return {"case": case, "job": job, "state": state, "sec": sec, "err": err, "note": note}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="逗号分隔的案例名，只跑这些")
    ap.add_argument("--cpus", type=int, default=4)
    ap.add_argument("--jobs", type=int, default=4, help="并发作业数")
    ap.add_argument("--gpus", type=int, default=0)
    ap.add_argument("--double", action="store_true")
    ap.add_argument("--abq", default="abq2020")
    ap.add_argument("--timeout", type=float, default=1200.0, help="单作业超时秒数")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    todo = [(c, f) for c, f in CASES if not args.only or c in [x.strip() for x in args.only.split(",") if x.strip()]]
    skip = [c for c, _ in todo if c in NO_STEP]
    todo = [(c, f) for c, f in todo if c not in NO_STEP]

    real = ar.abq_path(args.abq)
    print(f"abaqus   : {real}")
    print(f"并发/核数 : {args.jobs} x {args.cpus}   作业数 {len(todo)}")
    print(f"跳过     : {', '.join(skip) if skip else '无'}（无 *Step，纯网格示例）")
    if args.dry:
        for c, f in todo:
            print(f"  - {c:16s} {f}")
        return 0

    results = []
    running = {}
    queue = list(todo)
    t_start = time.time()
    while queue or running:
        while queue and len(running) < args.jobs:
            c, f = queue.pop(0)
            print(f"[提交] {c} ({f})", flush=True)
            import threading
            box = {}
            th = threading.Thread(
                target=lambda cc=c, ff=f, b=box: b.update(one_case(cc, ff, args.cpus, args.gpus, args.double, args.abq, args.timeout)),
                daemon=True,
            )
            th.start()
            running[c] = (th, box)
        time.sleep(3)
        done = [c for c, (th, _) in running.items() if not th.is_alive()]
        for c in done:
            th, box = running.pop(c)
            r = dict(box) or {"case": c, "job": "?", "state": "未知", "sec": 0, "err": -1, "note": ""}
            results.append(r)
            print(f"[完成] {r['case']:16s} {r['state']:12s} {r['sec']:7.1f}s  ERROR={r['err']}", flush=True)

    # 汇总
    lines = [
        "# 自建案例真机求解汇总",
        "",
        f"- 运行时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 配置：{args.jobs} 并发 × cpus={args.cpus}，gpus={args.gpus}，double={args.double}，abq={real}",
        f"- 跳过：{'、'.join(skip) if skip else '无'}",
        "",
        "| 案例 | 作业 | 状态 | 耗时 s | .msg ERROR |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(f"| {r['case']} | {r['job']} | {r['state']} | {r['sec']} | {r['err']} |")
    if skip:
        lines += ["", "未跑：" + "、".join(skip) + "（inp 内无 `*Step`，属纯网格/边界示例）"]
    bad = [r for r in results if r["state"] != "COMPLETED"]
    if bad:
        lines += ["", "## 未成功作业的末尾输出", ""]
        for r in bad:
            lines.append(f"- **{r['case']}**：`{r['note']}`")
    report = ROOT / "docs" / "run_all_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n总耗时 {time.time()-t_start:.0f}s，报告 {report}")
    ok = sum(1 for r in results if r["state"] == "COMPLETED")
    print(f"成功 {ok}/{len(results)}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
