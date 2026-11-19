# -*- coding: utf-8 -*-
"""内置案例：简支梁（B31 梁单元，两端简支、跨中集中力）。

契约：python build_inp.py --L ... --P ... --job JOB --out DIR  输出 DIR/JOB.inp
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.inpkit import (beam_mesh, fmt_nodes, fmt_elements, fmt_nset, fmt_elset,
                          elastic_material, static_step, boundary, cload, field_output)


def build(args):
    nodes, elements, nsets = beam_mesh(args.L, args.nx)

    blocks = [
        "*Heading",
        f"** Simply supported beam: L={args.L}, B31, midspan load -y",
        fmt_nodes(nodes),
        fmt_elements("B31", elements),
        fmt_nset("LEFT", nsets["LEFT"]),
        fmt_nset("RIGHT", nsets["RIGHT"]),
        fmt_nset("MID", nsets["MID"]),
        fmt_elset("ALL", [e[0] for e in elements]),
        "*Beam Section, elset=ALL, material=STEEL, section=RECT",
        f"{args.b}, {args.h}",
        "0., 1., 0.",
        elastic_material("STEEL", args.E, args.nu),
        static_step("Load"),
        boundary("LEFT", 1, 3),
        boundary("RIGHT", 2, 3),
        cload("MID", 2, -args.P),
        field_output(),
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "SSB") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    return path


def main():
    ap = argparse.ArgumentParser(description="简支梁 inp 生成")
    ap.add_argument("--L", type=float, default=1000.0, help="梁跨")
    ap.add_argument("--b", type=float, default=20.0, help="矩形截面宽")
    ap.add_argument("--h", type=float, default=40.0, help="矩形截面高")
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--P", type=float, default=1000.0, help="跨中集中力")
    ap.add_argument("--nx", type=int, default=20, help="长度方向网格数")
    ap.add_argument("--job", default="SSB")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
