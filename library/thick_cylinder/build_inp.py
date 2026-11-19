# -*- coding: utf-8 -*-
"""内置案例：平面应变厚壁圆筒（CPE4，内压，Lame 解对照）。

契约：python build_inp.py --a ... --b ... --p ... --job JOB --out DIR  输出 DIR/JOB.inp
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.inpkit import (annulus_quarter_mesh, fmt_nodes, fmt_elements, fmt_nset,
                          fmt_elset, elastic_material, static_step, boundary, field_output)


def build(args):
    nodes, elements, nsets = annulus_quarter_mesh(args.a, args.b, args.nr, args.nt)
    # 内壁单元（i=0 层）的 S4 边 = 内壁，受内压
    inner_elems = [j + 1 for j in range(args.nt)]
    surf = "*Surface, type=ELEMENT, name=INSIDE\n" + "\n".join(f"{e}, S4" for e in inner_elems)

    blocks = [
        "*Heading",
        f"** Thick cylinder (plane strain): a={args.a}, b={args.b}, internal pressure p={args.p}",
        fmt_nodes(nodes),
        fmt_elements("CPE4", elements),
        fmt_nset("SYMX", nsets["SYMX"]),
        fmt_nset("SYMY", nsets["SYMY"]),
        fmt_elset("ALL", [e[0] for e in elements]),
        surf,
        "*Solid Section, elset=ALL, material=STEEL",
        "1.,",
        elastic_material("STEEL", args.E, args.nu),
        static_step("Pressure"),
        boundary("SYMX", 2, 2),
        boundary("SYMY", 1, 1),
        "*Dsload",
        f"INSIDE, P, {args.p}",
        field_output(),
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "CYL") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    return path


def main():
    ap = argparse.ArgumentParser(description="厚壁圆筒 inp 生成")
    ap.add_argument("--a", type=float, default=100.0, help="内径")
    ap.add_argument("--b", type=float, default=200.0, help="外径")
    ap.add_argument("--p", type=float, default=10.0, help="内压")
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--nr", type=int, default=8, help="径向网格层数")
    ap.add_argument("--nt", type=int, default=12, help="环向网格段数")
    ap.add_argument("--job", default="CYL")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
