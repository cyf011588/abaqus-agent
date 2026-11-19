# -*- coding: utf-8 -*-
"""内置案例：简支梁中点突加集中力（隐式动力瞬态，动力放大系数 2）。

教科书经典结论：无阻尼体系在 t=0 突然施加恒定荷载，位移从 0 开始振荡，
峰值位移恰为静力位移的 2 倍（δ_dyn,max = 2·δ_static），静力位移
    δ_static = P·L^3 / (48·E·I)，I = b·h^3/12
一阶自振频率（简支梁）
    f1 = (pi/(2·L^2))·sqrt(E·I/(rho·A))
单位 mm-t-s：E=210000 N/mm^2、rho=7.9e-9 t/mm^3。

契约：python build_inp.py --L ... --P ... --job JOB --out DIR  输出 DIR/JOB.inp
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent.inpkit import (beam_mesh, fmt_nodes, fmt_elements, fmt_nset, fmt_elset,
                          elastic_material, field_output)


def build(args):
    nodes, elements, nsets = beam_mesh(args.L, args.nx)
    I = args.b * args.h ** 3 / 12.0
    A = args.b * args.h
    d_static = args.P * args.L ** 3 / (48.0 * args.E * I)
    f1 = (math.pi / (2.0 * args.L ** 2)) * math.sqrt(args.E * I / (args.rho * A))
    t_total = args.cycles / f1
    blocks = [
        "*Heading",
        f"** Dynamic implicit: sudden mid-span load on simply supported beam, "
        f"L={args.L}, b={args.b}, h={args.h}, P={args.P}",
        fmt_nodes(nodes),
        fmt_elements("B31", elements),
        fmt_nset("LEFT", nsets["LEFT"]),
        fmt_nset("RIGHT", nsets["RIGHT"]),
        fmt_nset("MID", nsets["MID"]),
        fmt_elset("ALL", [e[0] for e in elements]),
        "*Beam Section, elset=ALL, material=STEEL, section=RECT",
        f"{args.b}, {args.h}",
        "0., 0., -1.",
        elastic_material("STEEL", args.E, args.nu),
        "*Density",
        f"{args.rho}",
        "*Step, name=Transient",
        "*Dynamic",
        f"0.001, {t_total:.6f}, 1e-8, 0.001",
        "*Boundary",
        "LEFT, 1, 1",
        "LEFT, 2, 2",
        "RIGHT, 2, 2",
        "*Cload",
        f"MID, 2, {-args.P}",
        field_output(),
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "DYNAMIC_IMPLICIT") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    print(f"theory: delta_static={d_static:.4f} mm, delta_max=2x={2 * d_static:.4f} mm, "
          f"f1={f1:.2f} Hz, T1={1.0 / f1:.5f} s, T_total={t_total:.5f} s")
    return path


def main():
    ap = argparse.ArgumentParser(description="简支梁突加荷载（隐式动力）inp 生成")
    ap.add_argument("--L", type=float, default=1000.0)
    ap.add_argument("--b", type=float, default=20.0)
    ap.add_argument("--h", type=float, default=40.0)
    ap.add_argument("--nx", type=int, default=40)
    ap.add_argument("--P", type=float, default=1000.0)
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--rho", type=float, default=7.9e-9)
    ap.add_argument("--cycles", type=float, default=3.0)
    ap.add_argument("--job", default="DYNAMIC_IMPLICIT")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
