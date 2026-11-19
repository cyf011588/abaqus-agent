# -*- coding: utf-8 -*-
"""一次性修复：批量求解暴露出的 inp 语法错误（全部改在 library/**/build_inp.py 源头）。

修的 7 类问题：
1. inpkit.field_output() 已自带 *End Step，脚本又补一行 -> 重复 *End Step（显式动力学直接报错）
2. *Static, nlgeom=YES  ->  nlgeom 属于 *Step，不是 *Static 的参数
3. *Dynamic, Implicit   ->  隐式动力关键字就写 *Dynamic（没有 implicit 这个参数）
4. *Coupled Temperature-Displacement, steady-state -> steady state（Abaqus 多词参数用空格）
5. 带温度自由度的单元（C3D8RT/CPE4T/DC2D4）缺 *Conductivity
6. *Temperature, file=<job> 不被识别 -> 顺序耦合的第二步温度自动继承，删掉这行
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "library"

# 通用：field_output() 后面紧跟的 "*End Step" 是重复的
DUP_END = re.compile(r'(field_output\(\),\s*\n)([ \t]+"\*End Step",\s*\n)')


def patch(path: Path, old: str, new: str) -> int:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        print(f"  [未命中] {path.parent.name}: {old.strip()[:60]}")
        return 0
    text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print(f"  [已改] {path.parent.name}: {old.strip()[:60]}")
    return 1


def main() -> int:
    total = 0
    print("== 1) 去掉重复的 *End Step ==")
    for p in sorted(LIB.rglob("build_inp.py")):
        text = p.read_text(encoding="utf-8")
        m = DUP_END.search(text)
        if not m:
            continue
        text2 = DUP_END.sub(r"\1", text)
        p.write_text(text2, encoding="utf-8")
        print(f"  [已改] {p.parent.name}")
        total += 1

    print("== 2) nlgeom 移到 *Step ==")
    for c in ("nl_cantilever", "plate_nl"):
        total += patch(
            LIB / c / "build_inp.py",
            '"*Step, name=LargeDeflection",\n        "*Static, nlgeom=YES",',
            '"*Step, name=LargeDeflection, nlgeom=YES",\n        "*Static",',
        )

    print("== 3) *Dynamic, Implicit -> *Dynamic ==")
    total += patch(LIB / "dynamic_implicit" / "build_inp.py", '"*Dynamic, Implicit",', '"*Dynamic",')

    print("== 4/5) 热应力：steady state + *Conductivity ==")
    total += patch(
        LIB / "thermal_plate" / "build_inp.py",
        '"*Expansion",\n        f"{args.alpha}",\n        "*Step, name=ThermalPlate",\n        "*Coupled Temperature-Displacement, steady-state",',
        '"*Expansion",\n        f"{args.alpha}",\n        "*Conductivity",\n        f"{args.k},",\n        "*Step, name=ThermalPlate",\n        "*Coupled Temperature-Displacement, steady state",',
    )
    total += patch(
        LIB / "thermal_stress" / "build_inp.py",
        '"*Expansion",\n        f"{args.alpha}",\n        "*Step, name=HeatStress",\n        "*Coupled Temperature-Displacement, steady-state",',
        '"*Expansion",\n        f"{args.alpha}",\n        "*Conductivity",\n        f"{args.k},",\n        "*Step, name=HeatStress",\n        "*Coupled Temperature-Displacement, steady state",',
    )

    print("== 6) 顺序耦合 ==")
    total += patch(
        LIB / "thermal_seq" / "build_inp.py",
        '"*Expansion",\n        f"{args.alpha}",\n        "*Initial Conditions, type=Temperature",',
        '"*Expansion",\n        f"{args.alpha}",\n        "*Conductivity",\n        f"{args.k},",\n        "*Initial Conditions, type=Temperature",',
    )
    total += patch(
        LIB / "thermal_seq" / "build_inp.py",
        '"*Heat Transfer, steady-state",',
        '"*Heat Transfer, steady state",',
    )
    total += patch(
        LIB / "thermal_seq" / "build_inp.py",
        '        "*Temperature",\n        f"file={job}, step=1",\n',
        "        # 温度场由第一步（Heat Transfer）自动继承，无需 *Temperature, file=\n",
    )

    print(f"\n共生效 {total} 处；下面给三个热案例补 --k 参数")
    for c, default in (("thermal_plate", 0.05), ("thermal_stress", 0.05), ("thermal_seq", 0.05)):
        p = LIB / c / "build_inp.py"
        text = p.read_text(encoding="utf-8")
        if '"--alpha"' not in text:
            print(f"  [跳过] {c} 没有 --alpha")
            continue
        text = text.replace(
            '    ap.add_argument("--alpha", type=float, default=1.2e-5)',
            f'    ap.add_argument("--alpha", type=float, default=1.2e-5)\n'
            f'    ap.add_argument("--k", type=float, default={default}, help="热导率 N/(s·K)，mm-t-s 制")',
            1,
        )
        p.write_text(text, encoding="utf-8")
        print(f"  [已改] {c}: 增加 --k default={default}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
