# -*- coding: utf-8 -*-
"""内置案例：悬臂梁模态分析（C3D8R + *Frequency，前 N 阶固有频率）。

契约：python build_inp.py --L ... --nmodes ... --job JOB --out DIR  输出 DIR/JOB.inp
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.inpkit import (hex_mesh, fmt_nodes, fmt_elements, fmt_nset, fmt_elset,
                          elastic_material, solid_section, boundary)


def build(args):
    nodes, elements, nsets = hex_mesh(args.L, args.W, args.H, args.nx, args.ny, args.nz)

    blocks = [
        "*Heading",
        f"** Cantilever modal analysis: L={args.L}, C3D8R, first {args.nmodes} modes",
        fmt_nodes(nodes),
        fmt_elements("C3D8R", elements),
        fmt_nset("FIXED", nsets["X0"]),
        fmt_elset("ALL", [e[0] for e in elements]),
        solid_section("ALL", "STEEL"),
        elastic_material("STEEL", args.E, args.nu),
        "*Density",
        f"{args.rho},",
        "*Step, name=Frequency, perturbation",
        "*Frequency, eigensolver=Lanczos",
        f"{args.nmodes}, , , , ,",
        boundary("FIXED", 1, 3),
        "*Output, field",
        "*Node Output",
        "U",
        "*End Step",
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "MODAL") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    return path


def main():
    ap = argparse.ArgumentParser(description="悬臂梁模态 inp 生成")
    ap.add_argument("--L", type=float, default=100.0, help="梁长")
    ap.add_argument("--W", type=float, default=10.0, help="梁宽")
    ap.add_argument("--H", type=float, default=10.0, help="梁高")
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--rho", type=float, default=7.85e-09, help="密度（t/mm³）")
    ap.add_argument("--nmodes", type=int, default=6, help="提取模态阶数")
    ap.add_argument("--nx", type=int, default=20)
    ap.add_argument("--ny", type=int, default=2)
    ap.add_argument("--nz", type=int, default=2)
    ap.add_argument("--job", default="MODAL")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
