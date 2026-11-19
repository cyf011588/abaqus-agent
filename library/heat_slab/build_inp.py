# -*- coding: utf-8 -*-
"""内置案例：平板稳态热传导（DC2D4，两端固定温度，傅里叶定律对照）。

契约：python build_inp.py --L ... --T1 ... --T2 ... --job JOB --out DIR
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.inpkit import shell_rect_mesh, fmt_nodes, fmt_elements, fmt_nset, fmt_elset


def build(args):
    nodes, elements, nsets = shell_rect_mesh(args.L, args.H, args.nx, args.ny)

    blocks = [
        "*Heading",
        f"** Heat slab: DC2D4, steady state, T_left={args.T1}, T_right={args.T2}",
        fmt_nodes(nodes),
        fmt_elements("DC2D4", elements),
        fmt_nset("LEFT", nsets["X0"]),
        fmt_nset("RIGHT", nsets["X1"]),
        fmt_elset("ALL", [e[0] for e in elements]),
        "*Solid Section, elset=ALL, material=STEEL",
        "1.,",
        "*Material, name=STEEL",
        "*Conductivity",
        f"{args.k},",
        "*Step, name=Heat",
        "*Heat Transfer, steady state",
        "*Boundary",
        f"LEFT, 11, 11, {args.T1}",
        f"RIGHT, 11, 11, {args.T2}",
        "*Output, field",
        "*Node Output",
        "NT",
        "*Element Output",
        "HFL",
        "*End Step",
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "HEAT") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    return path


def main():
    ap = argparse.ArgumentParser(description="平板热传导 inp 生成")
    ap.add_argument("--L", type=float, default=100.0, help="板长")
    ap.add_argument("--H", type=float, default=20.0, help="板高")
    ap.add_argument("--k", type=float, default=50.0, help="导热系数")
    ap.add_argument("--T1", type=float, default=100.0, help="左端温度")
    ap.add_argument("--T2", type=float, default=20.0, help="右端温度")
    ap.add_argument("--nx", type=int, default=20)
    ap.add_argument("--ny", type=int, default=4)
    ap.add_argument("--job", default="HEAT")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
