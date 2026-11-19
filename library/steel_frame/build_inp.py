# -*- coding: utf-8 -*-
"""内置案例：平面纯钢框架（B31 梁单元，柱梁刚接，柱底铰接，楼层竖向荷载）。

契约：python build_inp.py --n-story ... --n-bay ... --h ... --L ... --job JOB --out DIR
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.inpkit import (frame_mesh, fmt_nodes, fmt_elements, fmt_nset, fmt_elset,
                          elastic_material, static_step, boundary, cload, field_output)


def build(args):
    nodes, elements, nsets = frame_mesh(args.n_story, args.n_bay, args.h, args.L)
    n_cols = args.n_story * (args.n_bay + 1)
    col_ids = [e[0] for e in elements[:n_cols]]
    beam_ids = [e[0] for e in elements[n_cols:]]

    blocks = [
        "*Heading",
        f"** Steel frame: {args.n_story} story x {args.n_bay} bay, B31, rigid beam-column joints",
        fmt_nodes(nodes),
        fmt_elements("B31", elements),
        fmt_nset("ALL", nsets["ALL"]),
        fmt_nset("BASE", nsets["BASE"]),
        fmt_nset("FLOORS", nsets["FLOORS"]),
        fmt_elset("COLS", col_ids),
        fmt_elset("BEAMS", beam_ids),
        "*Beam Section, elset=COLS, material=STEEL, section=RECT",
        f"{args.b_col}, {args.d_col}",
        "0., 0., -1.",
        "*Beam Section, elset=BEAMS, material=STEEL, section=RECT",
        f"{args.b_beam}, {args.d_beam}",
        "0., 0., -1.",
        elastic_material("STEEL", args.E, args.nu),
        static_step("Gravity"),
        boundary("ALL", 3, 3),
        boundary("ALL", 4, 5),
        boundary("BASE", 1, 2),
        cload("FLOORS", 2, -args.P),
        field_output(),
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "FRAME") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    return path


def main():
    ap = argparse.ArgumentParser(description="平面钢框架 inp 生成")
    ap.add_argument("--n-story", type=int, default=2, help="层数")
    ap.add_argument("--n-bay", type=int, default=2, help="跨数")
    ap.add_argument("--h", type=float, default=3000.0, help="层高")
    ap.add_argument("--L", type=float, default=6000.0, help="跨度")
    ap.add_argument("--b-col", type=float, default=200.0, help="柱截面宽")
    ap.add_argument("--d-col", type=float, default=200.0, help="柱截面高")
    ap.add_argument("--b-beam", type=float, default=200.0, help="梁截面宽")
    ap.add_argument("--d-beam", type=float, default=300.0, help="梁截面高")
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--P", type=float, default=100000.0, help="每层每节点竖向荷载")
    ap.add_argument("--job", default="FRAME")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
