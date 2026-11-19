# -*- coding: utf-8 -*-
"""内置案例：受压柱线性屈曲（C3D8R + *Buckle，欧拉临界载荷对照）。

契约：python build_inp.py --L ... --P ... --job JOB --out DIR  输出 DIR/JOB.inp
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.inpkit import (hex_mesh, fmt_nodes, fmt_elements, fmt_nset, fmt_elset,
                          elastic_material, solid_section, boundary, cload)


def build(args):
    nodes, elements, nsets = hex_mesh(args.L, args.W, args.H, args.nx, args.ny, args.nz)

    blocks = [
        "*Heading",
        f"** Column buckling: L={args.L}, C3D8R, axial compression P={args.P}",
        fmt_nodes(nodes),
        fmt_elements("C3D8R", elements),
        fmt_nset("FIXED", nsets["X0"]),
        fmt_nset("TIP", nsets["X1"]),
        fmt_elset("ALL", [e[0] for e in elements]),
        solid_section("ALL", "STEEL"),
        elastic_material("STEEL", args.E, args.nu),
        "*Step, name=Buckle, perturbation",
        "*Buckle, eigensolver=Lanczos",
        f"{args.nmodes}, , , , ,",
        boundary("FIXED", 1, 3),
        cload("TIP", 1, -args.P),
        "*Output, field",
        "*Node Output",
        "U",
        "*End Step",
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "BUCKLE") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    return path


def main():
    ap = argparse.ArgumentParser(description="受压柱屈曲 inp 生成")
    ap.add_argument("--L", type=float, default=1000.0, help="柱长（长轴）")
    ap.add_argument("--W", type=float, default=20.0, help="截面宽")
    ap.add_argument("--H", type=float, default=20.0, help="截面高")
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--P", type=float, default=1.0, help="参考轴向压力（屈曲因子基准）")
    ap.add_argument("--nmodes", type=int, default=4, help="屈曲模态阶数")
    ap.add_argument("--nx", type=int, default=40, help="长度方向网格数")
    ap.add_argument("--ny", type=int, default=2, help="截面宽网格数")
    ap.add_argument("--nz", type=int, default=2, help="截面高网格数")
    ap.add_argument("--job", default="BUCKLE")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
