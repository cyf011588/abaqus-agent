# -*- coding: utf-8 -*-
"""内置案例：带孔方板拉伸（S4R 壳，两端位移拉伸，孔边应力集中）。

契约：python build_inp.py --W ... --r ... --u ... --job JOB --out DIR
输出 DIR/JOB.inp
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.inpkit import (plate_hole_mesh, fmt_nodes, fmt_elements, fmt_nset, fmt_elset,
                          elastic_material, shell_section, static_step, boundary,
                          field_output)


def build(args):
    nodes, elements, nsets = plate_hole_mesh(args.W, args.H, args.r, args.nr, args.nt)
    all_elem = [e[0] for e in elements]

    blocks = [
        "*Heading",
        f"** Plate with hole: {args.W}x{args.H}, r={args.r}, S4R, tension u={args.u}",
        fmt_nodes(nodes),
        fmt_elements("S4R", elements),
        fmt_nset("LEFT", nsets["LEFT"]),
        fmt_nset("RIGHT", nsets["RIGHT"]),
        fmt_elset("ALL", all_elem),
        shell_section("ALL", "STEEL", args.t),
        elastic_material("STEEL", args.E, args.nu),
        static_step("Tension"),
        boundary("LEFT", 1, 1, -args.u),
        boundary("LEFT", 2, 2),
        boundary("RIGHT", 1, 1, args.u),
        field_output(),
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "PLATE_HOLE") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    return path


def main():
    ap = argparse.ArgumentParser(description="带孔方板 inp 生成")
    ap.add_argument("--W", type=float, default=200.0, help="板宽（x）")
    ap.add_argument("--H", type=float, default=100.0, help="板高（y）")
    ap.add_argument("--r", type=float, default=20.0, help="孔半径")
    ap.add_argument("--t", type=float, default=2.0, help="板厚（壳）")
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--u", type=float, default=0.5, help="端部拉伸位移（对称 ±u）")
    ap.add_argument("--nr", type=int, default=12, help="径向网格层数")
    ap.add_argument("--nt", type=int, default=48, help="环向网格段数")
    ap.add_argument("--job", default="PLATE_HOLE")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
