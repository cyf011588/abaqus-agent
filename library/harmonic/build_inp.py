# -*- coding: utf-8 -*-
"""内置案例：悬臂梁端部简谐激励（稳态动力直接法扫频，共振峰对照一阶固有频率）。

教科书频域动力经典问题：悬臂梁自由端作用幅值 F 的简谐力，扫频后位移响应在
一阶固有频率处出现共振峰。悬臂梁一阶横向固有频率
    f1 = (1.875^2 / (2*pi*L^2))·sqrt(E·I/(rho·A))，I = b·h^3/12
单位 mm-t-s：E=210000 N/mm^2、rho=7.9e-9 t/mm^3。
默认 (L=200, b=20, h=10) → f1 约 208 Hz，扫频 100~400 Hz。

契约：python build_inp.py --L ... --fmin ... --job JOB --out DIR  输出 DIR/JOB.inp
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent.inpkit import (beam_mesh, fmt_nodes, fmt_elements, fmt_nset, fmt_elset,
                          elastic_material)


def build(args):
    nodes, elements, nsets = beam_mesh(args.L, args.nx)
    I = args.b * args.h ** 3 / 12.0
    A = args.b * args.h
    f1 = (1.875 ** 2 / (2.0 * math.pi * args.L ** 2)) * math.sqrt(args.E * I / (args.rho * A))
    blocks = [
        "*Heading",
        f"** Harmonic response: cantilever tip excitation, L={args.L}, b={args.b}, "
        f"h={args.h}, F={args.F}, sweep {args.fmin}-{args.fmax} Hz",
        fmt_nodes(nodes),
        fmt_elements("B31", elements),
        fmt_nset("FIXED", nsets["LEFT"]),
        fmt_nset("TIP", nsets["RIGHT"]),
        fmt_elset("ALL", [e[0] for e in elements]),
        "*Beam Section, elset=ALL, material=STEEL, section=RECT",
        f"{args.b}, {args.h}",
        "0., 0., -1.",
        elastic_material("STEEL", args.E, args.nu),
        "*Density",
        f"{args.rho}",
        "*Step, name=Harmonic",
        "*Steady State Dynamics, direct",
        f"{args.fmin}, {args.fmax}, {args.npoints}, 3.",
        "*Boundary",
        "FIXED, 1, 6",
        "*Cload",
        f"TIP, 2, {-args.F}",
        "*Output, field",
        "*Node Output",
        "U",
        "*End Step",
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "HARMONIC") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    print(f"theory: I={I:.1f} mm^4, A={A:.1f} mm^2, f1={f1:.1f} Hz "
          f"(sweep {args.fmin}-{args.fmax} Hz covers it)")
    return path


def main():
    ap = argparse.ArgumentParser(description="悬臂梁谐响应（稳态动力）inp 生成")
    ap.add_argument("--L", type=float, default=200.0)
    ap.add_argument("--b", type=float, default=20.0)
    ap.add_argument("--h", type=float, default=10.0)
    ap.add_argument("--nx", type=int, default=20)
    ap.add_argument("--F", type=float, default=1.0)
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--rho", type=float, default=7.9e-9)
    ap.add_argument("--fmin", type=float, default=100.0)
    ap.add_argument("--fmax", type=float, default=400.0)
    ap.add_argument("--npoints", type=int, default=60)
    ap.add_argument("--job", default="HARMONIC")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
