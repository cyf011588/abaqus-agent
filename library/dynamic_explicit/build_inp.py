# -*- coding: utf-8 -*-
"""内置案例：细长实心杆轴向冲击（显式动力，一维应力波，sigma = sqrt(E*rho)*v）。

教科书一维波动经典问题：一端突然固定、整杆以速度 v 运动的弹性杆，
固定端反射产生应力波，杆内峰值压应力
    sigma = rho · c · v = sqrt(E·rho) · v     （c = sqrt(E/rho) 为纵波波速）
单位 mm-t-s：E=210000 N/mm^2、rho=7.9e-9 t/mm^3、v 取 mm/s。
默认 (E=210000, rho=7.9e-9, v=1000 mm/s) → sigma ≈ 40.7 MPa，
波速 c ≈ 5.16e6 mm/s，500 mm 杆单程约 9.7e-5 s。

契约：python build_inp.py --L ... --v ... --job JOB --out DIR  输出 DIR/JOB.inp
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent.inpkit import (hex_mesh, fmt_nodes, fmt_elements, fmt_nset, fmt_elset,
                          elastic_material, solid_section, field_output)


def build(args):
    nodes, elements, nsets = hex_mesh(args.L, args.W, args.H, args.nx, args.ny, args.nz)
    all_nodes = [n[0] for n in nodes]
    c = math.sqrt(args.E / args.rho)
    sigma = math.sqrt(args.E * args.rho) * args.v
    t_through = args.L / c
    blocks = [
        "*Heading",
        f"** Explicit impact: axial stress wave, L={args.L}, W={args.W}, H={args.H}, "
        f"v={args.v} mm/s",
        fmt_nodes(nodes),
        fmt_elements("C3D8R", elements),
        fmt_nset("X0", nsets["X0"]),
        fmt_nset("X1", nsets["X1"]),
        fmt_nset("ALLV", all_nodes),
        fmt_elset("ALL", [e[0] for e in elements]),
        solid_section("ALL", "STEEL"),
        "1.,",
        elastic_material("STEEL", args.E, args.nu),
        "*Density",
        f"{args.rho}",
        "*Initial Conditions, type=Velocity",
        f"ALLV, 1, {-args.v}",
        "*Step, name=Impact",
        "*Dynamic, Explicit",
        f", {args.time:.6f}",
        "*Boundary",
        "X0, 1, 3",
        field_output(),
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "DYNAMIC_EXPLICIT") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    print(f"theory: c={c:.3e} mm/s, sigma=sqrt(E*rho)*v={sigma:.2f} MPa, "
          f"wave transit L/c={t_through:.3e} s, step time={args.time:.3e} s")
    return path


def main():
    ap = argparse.ArgumentParser(description="杆轴向冲击（显式动力）inp 生成")
    ap.add_argument("--L", type=float, default=500.0)
    ap.add_argument("--W", type=float, default=20.0)
    ap.add_argument("--H", type=float, default=20.0)
    ap.add_argument("--nx", type=int, default=25)
    ap.add_argument("--ny", type=int, default=2)
    ap.add_argument("--nz", type=int, default=2)
    ap.add_argument("--v", type=float, default=1000.0)
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--rho", type=float, default=7.9e-9)
    ap.add_argument("--time", type=float, default=2e-4)
    ap.add_argument("--job", default="DYNAMIC_EXPLICIT")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
