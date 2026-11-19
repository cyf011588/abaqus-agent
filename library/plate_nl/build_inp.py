# -*- coding: utf-8 -*-
"""内置案例：四边简支板大挠度（S4R + 均布压力 + nlgeom=YES，薄膜效应）。

教科书几何非线性第二类：板中心挠度达到板厚量级后，板内产生薄膜拉应力，
弯曲刚度显著提高，实际挠度小于小挠度理论值（von Karman 大挠度板方程）。
小挠度理论（四边简支方板，中心挠度）：
    w_lin = 0.00406·q·a^4 / D，D = E·t^3 / (12·(1-nu^2))
默认 (a=500, t=5, q=0.1 N/mm^2) → w_lin ≈ 10.6 mm ≈ 2.1·t，
属大挠度范围，开 nlgeom 后 Abaqus 挠度应明显小于 10.6 mm。

契约：python build_inp.py --a ... --q ... --job JOB --out DIR  输出 DIR/JOB.inp
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent.inpkit import (shell_rect_mesh, fmt_nodes, fmt_elements, fmt_nset, fmt_elset,
                          elastic_material, shell_section, field_output)


def build(args):
    nodes, elements, nsets = shell_rect_mesh(args.a, args.a, args.nx, args.ny)
    D = args.E * args.t ** 3 / (12.0 * (1.0 - args.nu ** 2))
    w_lin = 0.00406 * args.q * args.a ** 4 / D
    blocks = [
        "*Heading",
        f"** Large deflection plate: a={args.a}, t={args.t}, q={args.q} MPa, S4R, nlgeom=YES",
        fmt_nodes(nodes),
        fmt_elements("S4R", elements),
        fmt_nset("X0", nsets["X0"]),
        fmt_nset("X1", nsets["X1"]),
        fmt_nset("Y0", nsets["Y0"]),
        fmt_nset("Y1", nsets["Y1"]),
        fmt_nset("PIN1", [nsets["X0"][0]]),
        fmt_nset("PIN2", [nsets["Y0"][0]]),
        fmt_elset("ALL", [e[0] for e in elements]),
        shell_section("ALL", "STEEL", args.t),
        elastic_material("STEEL", args.E, args.nu),
        "*Step, name=LargeDeflection, nlgeom=YES",
        "*Static",
        "0.1, 1., 1e-5, 0.1",
        "*Boundary",
        "X0, 3, 3",
        "X1, 3, 3",
        "Y0, 3, 3",
        "Y1, 3, 3",
        "PIN1, 1, 1",
        "PIN2, 2, 2",
        "*Dload",
        "ALL, P, " + str(args.q),
        field_output(),
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "PLATE_NL") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    print(f"theory: D={D:.4e} N*mm, w_linear=0.00406*q*a^4/D={w_lin:.2f} mm "
          f"({w_lin / args.t:.2f}*t)；几何非线性结果应小于该值")
    return path


def main():
    ap = argparse.ArgumentParser(description="板大挠度（几何非线性）inp 生成")
    ap.add_argument("--a", type=float, default=500.0)
    ap.add_argument("--t", type=float, default=5.0)
    ap.add_argument("--nx", type=int, default=20)
    ap.add_argument("--ny", type=int, default=20)
    ap.add_argument("--q", type=float, default=0.1)
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--job", default="PLATE_NL")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
