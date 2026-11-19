# -*- coding: utf-8 -*-
"""内置案例：平面三角桁架（T3D2，两铰支座 + 顶点集中力）。

契约：python build_inp.py --L ... --H ... --job JOB --out DIR  输出 DIR/JOB.inp
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.inpkit import (truss_mesh, fmt_nodes, fmt_elements, fmt_nset, fmt_elset,
                          elastic_material, static_step, boundary, cload, field_output)


def build(args):
    nodes, elements, nsets = truss_mesh(args.L, args.H)

    blocks = [
        "*Heading",
        f"** Triangular truss: L={args.L}, H={args.H}, T3D2, apex load -y",
        fmt_nodes(nodes),
        fmt_elements("T3D2", elements),
        fmt_nset("A", nsets["A"]),
        fmt_nset("B", nsets["B"]),
        fmt_nset("C", nsets["C"]),
        fmt_elset("ALL", [e[0] for e in elements]),
        "*Solid Section, elset=ALL, material=STEEL",
        f"{args.area},",
        elastic_material("STEEL", args.E, args.nu),
        static_step("Load"),
        boundary("A", 1, 3),
        boundary("B", 2, 2),
        cload("C", 2, -args.P),
        field_output(),
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "TRUSS") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    return path


def main():
    ap = argparse.ArgumentParser(description="三角桁架 inp 生成")
    ap.add_argument("--L", type=float, default=1000.0, help="底边跨")
    ap.add_argument("--H", type=float, default=500.0, help="顶点高")
    ap.add_argument("--area", type=float, default=100.0, help="杆截面积")
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--P", type=float, default=1000.0, help="顶点集中力")
    ap.add_argument("--job", default="TRUSS")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
