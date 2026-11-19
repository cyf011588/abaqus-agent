# -*- coding: utf-8 -*-
"""内置案例：轴对称圆盘轴向压缩（CAX4，顶部压力）。

契约：python build_inp.py --r1 ... --H ... --p ... --job JOB --out DIR
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.inpkit import (shell_rect_mesh, fmt_nodes, fmt_elements, fmt_nset, fmt_elset,
                          elastic_material, solid_section, static_step, boundary, field_output)


def build(args):
    # CAX4: x=r（径向），y=z（轴向）
    nodes, elements, nsets = shell_rect_mesh(args.r1, args.H, args.nx, args.ny)

    top_elems = [args.nx * (args.ny - 1) + i + 1 for i in range(args.nx)]
    top_surf = "*Surface, type=ELEMENT, name=TOP\n" + "\n".join(f"{e}, S3" for e in top_elems)

    blocks = [
        "*Heading",
        f"** Axisymmetric disc: CAX4, top pressure p={args.p}",
        fmt_nodes(nodes),
        fmt_elements("CAX4", elements),
        fmt_nset("AXIS", nsets["X0"]),
        fmt_nset("BASE", nsets["Y0"]),
        fmt_elset("ALL", [e[0] for e in elements]),
        solid_section("ALL", "STEEL"),
        "1.,",
        elastic_material("STEEL", args.E, args.nu),
        top_surf,
        static_step("Pressure"),
        boundary("AXIS", 1, 1),
        boundary("BASE", 2, 2),
        "*Dsload",
        f"TOP, P, {args.p}",
        field_output(),
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "AXISYM") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    return path


def main():
    ap = argparse.ArgumentParser(description="轴对称圆盘 inp 生成")
    ap.add_argument("--r1", type=float, default=50.0, help="圆盘半径")
    ap.add_argument("--H", type=float, default=20.0, help="圆盘厚度（轴向）")
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--p", type=float, default=10.0, help="顶部压力")
    ap.add_argument("--nx", type=int, default=20, help="径向网格数")
    ap.add_argument("--ny", type=int, default=8, help="轴向网格数")
    ap.add_argument("--job", default="AXISYM")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
