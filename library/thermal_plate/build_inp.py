# -*- coding: utf-8 -*-
"""内置案例：两端固支平板均匀升温热应力（CPE4T 平面应变 + 热膨胀受阻）。

经典教科书算例：矩形平板两端 X0/X1 固支（u1=u2=0），整体均匀升温 dT。
平面应变（ε_z=0）、y 方向自由（σ_y=0），泊松约束使得
    σ_x = σ_z = -E·alpha·dT / (1 - nu)
理论解可逐点对照（默认钢：E=210000, alpha=1.2e-5, dT=100, nu=0.3 → -360 MPa）。

契约：python build_inp.py --L ... --dT ... --job JOB --out DIR  输出 DIR/JOB.inp
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent.inpkit import (shell_rect_mesh, fmt_nodes, fmt_elements, fmt_nset,
                          fmt_elset, field_output)


def build(args):
    nodes, elements, nsets = shell_rect_mesh(args.L, args.H, args.nx, args.ny)
    all_nodes = [n[0] for n in nodes]
    blocks = [
        "*Heading",
        f"** Thermal plate stress: L={args.L}, H={args.H}, alpha={args.alpha}, "
        f"dT={args.dT}, CPE4T plane strain, both ends fixed",
        fmt_nodes(nodes),
        fmt_elements("CPE4T", elements),
        fmt_nset("X0", nsets["X0"]),
        fmt_nset("X1", nsets["X1"]),
        fmt_nset("ALLN", all_nodes),
        fmt_nset("BOTTOM", nsets["Y0"]),
        fmt_nset("TOP", nsets["Y1"]),
        fmt_elset("ALL", [e[0] for e in elements]),
        "*Solid Section, elset=ALL, material=STEEL",
        "1.,",
        "*Material, name=STEEL",
        "*Elastic",
        f"{args.E}, {args.nu}",
        "*Expansion",
        f"{args.alpha}",
        "*Conductivity",
        f"{args.k},",
        "*Step, name=ThermalPlate",
        "*Coupled Temperature-Displacement, steady state",
        "0.1, 1., 1e-5, 1.",
        "*Boundary",
        "X0, 1, 2",
        "X1, 1, 2",
        # 带温度自由度的单元（CPE4T）不允许用 *Temperature，温度必须按 DOF 11 约束
        "*Boundary",
        f"ALLN, 11, 11, {args.dT}",
        field_output(),
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "THERMAL_PLATE") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    sigma = -args.E * args.alpha * args.dT / (1.0 - args.nu)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    print(f"theory sigma_x = -E*alpha*dT/(1-nu) = {sigma:.2f} MPa")
    return path


def main():
    ap = argparse.ArgumentParser(description="两端固支平板热应力 inp 生成")
    ap.add_argument("--L", type=float, default=200.0)
    ap.add_argument("--H", type=float, default=100.0)
    ap.add_argument("--nx", type=int, default=20)
    ap.add_argument("--ny", type=int, default=10)
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--alpha", type=float, default=1.2e-5)
    ap.add_argument("--k", type=float, default=0.05, help="热导率 N/(s·K)，mm-t-s 制")
    ap.add_argument("--dT", type=float, default=100.0)
    ap.add_argument("--job", default="THERMAL_PLATE")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
