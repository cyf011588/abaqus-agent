# -*- coding: utf-8 -*-
"""内置案例：热应力立方体（C3D8RT + 温度梯度 + 热膨胀约束应力）。

契约：python build_inp.py --L ... --dT ... --job JOB --out DIR  输出 DIR/JOB.inp
底面固定、底面 0°C / 顶面 dT（默认 100°C），热膨胀受阻产生压应力。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent.inpkit import (hex_mesh, fmt_nodes, fmt_elements, fmt_nset, fmt_elset,
                          solid_section, field_output)


def build(args):
    nodes, elements, nsets = hex_mesh(args.L, args.W, args.H, args.nx, args.ny, args.nz)
    blocks = [
        "*Heading",
        f"** Thermal stress: L={args.L}, W={args.W}, H={args.H}, alpha={args.alpha}, dT={args.dT}, C3D8RT",
        fmt_nodes(nodes),
        fmt_elements("C3D8RT", elements),
        fmt_nset("BOTTOM", nsets["Z0"]),
        fmt_nset("TOP", nsets["Z1"]),
        fmt_elset("ALL", [e[0] for e in elements]),
        solid_section("ALL", "STEEL"),
        "*Material, name=STEEL",
        "*Elastic",
        f"{args.E}, {args.nu}",
        "*Expansion",
        f"{args.alpha}",
        "*Conductivity",
        f"{args.k},",
        "*Step, name=HeatStress",
        "*Coupled Temperature-Displacement, steady state",
        "0.1, 1., 1e-5, 1.",
        "*Boundary",
        "BOTTOM, 1, 3",
        # C3D8RT 带温度自由度，温度约束必须写成 DOF 11 的边界（不能用 *Temperature）
        "*Boundary",
        "BOTTOM, 11, 11, 0.",
        f"TOP, 11, 11, {args.dT}",
        field_output(),
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "THERMAL_STRESS") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    return path


def main():
    ap = argparse.ArgumentParser(description="热应力立方体 inp 生成")
    ap.add_argument("--L", type=float, default=100.0)
    ap.add_argument("--W", type=float, default=100.0)
    ap.add_argument("--H", type=float, default=100.0)
    ap.add_argument("--nx", type=int, default=8)
    ap.add_argument("--ny", type=int, default=8)
    ap.add_argument("--nz", type=int, default=8)
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--alpha", type=float, default=1.2e-5)
    ap.add_argument("--k", type=float, default=0.05, help="热导率 N/(s·K)，mm-t-s 制")
    ap.add_argument("--dT", type=float, default=100.0)
    ap.add_argument("--job", default="THERMAL_STRESS")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
