# -*- coding: utf-8 -*-
"""内置案例：悬臂梁（C3D8R 体单元，一端固定、自由端集中力）。

契约：python build_inp.py --L ... --P ... --job JOB --out DIR
输出 DIR/JOB.inp
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.inpkit import (hex_mesh, fmt_nodes, fmt_elements, fmt_nset, fmt_elset,
                          elastic_material, solid_section, static_step, boundary,
                          cload, field_output)


def build(args):
    nodes, elements, nsets = hex_mesh(args.L, args.W, args.H, args.nx, args.ny, args.nz)
    all_elem = [e[0] for e in elements]
    per_node = args.P / len(nsets["X1"])  # 自由端每节点分担，保证总力 = P

    blocks = [
        "*Heading",
        f"** Cantilever beam: {args.L}x{args.W}x{args.H}, C3D8R, tip load -z",
        fmt_nodes(nodes),
        fmt_elements("C3D8R", elements),
        fmt_nset("FIXED", nsets["X0"]),
        fmt_nset("TIP", nsets["X1"]),
        fmt_elset("ALL", all_elem),
        solid_section("ALL", "STEEL"),
        elastic_material("STEEL", args.E, args.nu),
        static_step("Load"),
        boundary("FIXED", 1, 3),
        cload("TIP", 3, -per_node),
        field_output(),
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "CANT") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    return path


def main():
    ap = argparse.ArgumentParser(description="悬臂梁 inp 生成")
    ap.add_argument("--L", type=float, default=100.0, help="梁长")
    ap.add_argument("--W", type=float, default=10.0, help="梁宽")
    ap.add_argument("--H", type=float, default=10.0, help="梁高")
    ap.add_argument("--E", type=float, default=210000.0, help="弹性模量")
    ap.add_argument("--nu", type=float, default=0.3, help="泊松比")
    ap.add_argument("--P", type=float, default=1000.0, help="自由端总载荷")
    ap.add_argument("--nx", type=int, default=20, help="长度方向网格数")
    ap.add_argument("--ny", type=int, default=2, help="宽度方向网格数")
    ap.add_argument("--nz", type=int, default=2, help="高度方向网格数")
    ap.add_argument("--job", default="CANT")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
