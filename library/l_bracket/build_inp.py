# -*- coding: utf-8 -*-
"""内置案例：L 型支架（S4R 壳，一面固定、另一面自由端载荷）。

契约：python build_inp.py --H ... --L ... --t ... --job JOB --out DIR
输出 DIR/JOB.inp
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.inpkit import (l_bracket_mesh, fmt_nodes, fmt_elements, fmt_nset, fmt_elset,
                          elastic_material, shell_section, static_step, boundary,
                          cload, field_output)


def build(args):
    nodes, elements, nsets = l_bracket_mesh(args.H, args.L, args.t, args.nx1, args.my, args.nx2)
    all_elem = [e[0] for e in elements]
    per_node = args.P / len(nsets["TIP"])

    blocks = [
        "*Heading",
        f"** L-bracket: H={args.H}, L={args.L}, t={args.t}, S4R shell",
        fmt_nodes(nodes),
        fmt_elements("S4R", elements),
        fmt_nset("FIXED", nsets["FIXED"]),
        fmt_nset("TIP", nsets["TIP"]),
        fmt_elset("ALL", all_elem),
        shell_section("ALL", "STEEL", args.thk),
        elastic_material("STEEL", args.E, args.nu),
        static_step("Load"),
        boundary("FIXED", 1, 6),
        cload("TIP", 2, -per_node),
        field_output(),
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "L_BRACKET") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    return path


def main():
    ap = argparse.ArgumentParser(description="L 型支架 inp 生成")
    ap.add_argument("--H", type=float, default=100.0, help="竖直臂高")
    ap.add_argument("--L", type=float, default=100.0, help="水平臂长")
    ap.add_argument("--t", type=float, default=20.0, help="臂宽（共享区厚度）")
    ap.add_argument("--thk", type=float, default=5.0, help="板厚（壳 section）")
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--P", type=float, default=1000.0, help="自由端总载荷")
    ap.add_argument("--nx1", type=int, default=4, help="臂宽方向网格数")
    ap.add_argument("--my", type=int, default=20, help="竖直臂总网格数")
    ap.add_argument("--nx2", type=int, default=16, help="水平臂网格数")
    ap.add_argument("--job", default="L_BRACKET")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
