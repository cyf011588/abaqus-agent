# -*- coding: utf-8 -*-
"""内置案例：悬臂梁大挠度（几何非线性 nlgeom=YES，端部横向集中力）。

教科书几何非线性入门：小挠度理论给出端部挠度
    delta_lin = P·L^3 / (3·E·I)，I = b·h^3/12
当 delta 达到梁长的量级时，小挠度公式严重高估挠度（杆轴缩短、力臂变化），
必须用 Elastica 大挠度解。默认参数刻意选 P 使 delta_lin = 0.5·L：
    L=500, b=10, h=10, E=210000, P=1050 N → delta_lin = 250 mm (= L/2)
开具 nlgeom 后 Abaqus 结果应明显小于 250 mm，这就是几何非线性生效的直接证据。

契约：python build_inp.py --L ... --P ... --job JOB --out DIR  输出 DIR/JOB.inp
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent.inpkit import (beam_mesh, fmt_nodes, fmt_elements, fmt_nset, fmt_elset,
                          elastic_material, field_output)


def build(args):
    nodes, elements, nsets = beam_mesh(args.L, args.nx)
    I = args.b * args.h ** 3 / 12.0
    d_lin = args.P * args.L ** 3 / (3.0 * args.E * I)
    blocks = [
        "*Heading",
        f"** Geometric nonlinearity: large deflection cantilever, L={args.L}, b={args.b}, "
        f"h={args.h}, P={args.P}, nlgeom=YES",
        fmt_nodes(nodes),
        fmt_elements("B31", elements),
        fmt_nset("FIXED", nsets["LEFT"]),
        fmt_nset("TIP", nsets["RIGHT"]),
        fmt_elset("ALL", [e[0] for e in elements]),
        "*Beam Section, elset=ALL, material=STEEL, section=RECT",
        f"{args.b}, {args.h}",
        "0., 0., -1.",
        elastic_material("STEEL", args.E, args.nu),
        "*Step, name=LargeDeflection, nlgeom=YES",
        "*Static",
        f"0.1, 1., 1e-5, 0.1",
        "*Boundary",
        "FIXED, 1, 6",
        "*Cload",
        f"TIP, 2, {-args.P}",
        field_output(),
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "NL_CANTILEVER") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    print(f"theory: I={I:.1f} mm^4, delta_linear=P*L^3/(3EI)={d_lin:.2f} mm "
          f"({d_lin / args.L:.2f}*L); 几何非线性结果应显著小于该线性值")
    return path


def main():
    ap = argparse.ArgumentParser(description="大挠度悬臂梁（几何非线性）inp 生成")
    ap.add_argument("--L", type=float, default=500.0)
    ap.add_argument("--b", type=float, default=10.0)
    ap.add_argument("--h", type=float, default=10.0)
    ap.add_argument("--nx", type=int, default=40)
    ap.add_argument("--P", type=float, default=1050.0)
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--job", default="NL_CANTILEVER")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
