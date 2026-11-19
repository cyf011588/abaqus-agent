# -*- coding: utf-8 -*-
"""内置案例：带孔方板弹塑性拉伸（S4R + *Plastic，孔边屈服）。

契约：python build_inp.py --W ... --r ... --yield-stress ... --job JOB --out DIR  输出 DIR/JOB.inp
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.inpkit import (plate_hole_mesh, fmt_nodes, fmt_elements, fmt_nset, fmt_elset,
                          shell_section, static_step, boundary, field_output)


def build(args):
    nodes, elements, nsets = plate_hole_mesh(args.W, args.H, args.r, args.nr, args.nt)

    blocks = [
        "*Heading",
        f"** Plate with hole, elastoplastic: W={args.W}, r={args.r}, S4R, yield={args.yield_stress}",
        fmt_nodes(nodes),
        fmt_elements("S4R", elements),
        fmt_nset("LEFT", nsets["LEFT"]),
        fmt_nset("RIGHT", nsets["RIGHT"]),
        fmt_elset("ALL", [e[0] for e in elements]),
        shell_section("ALL", "STEEL", args.t),
        "*Material, name=STEEL",
        "*Elastic",
        f"{args.E}, {args.nu}",
        "*Plastic",
        f"{args.yield_stress}, 0.",
        f"{args.hard_stress}, {args.hard_pe}",
        static_step("Tension"),
        boundary("LEFT", 1, 1, -args.u),
        boundary("LEFT", 2, 2),
        boundary("RIGHT", 1, 1, args.u),
        field_output(),
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "PLASTIC") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    return path


def main():
    ap = argparse.ArgumentParser(description="带孔板弹塑性 inp 生成")
    ap.add_argument("--W", type=float, default=200.0, help="板宽")
    ap.add_argument("--H", type=float, default=100.0, help="板高")
    ap.add_argument("--r", type=float, default=20.0, help="孔半径")
    ap.add_argument("--t", type=float, default=2.0, help="板厚")
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--yield-stress", type=float, default=235.0, help="屈服应力")
    ap.add_argument("--hard-stress", type=float, default=300.0, help="硬化点应力")
    ap.add_argument("--hard-pe", type=float, default=0.05, help="硬化点塑性应变")
    ap.add_argument("--u", type=float, default=2.0, help="端部对称拉伸位移")
    ap.add_argument("--nr", type=int, default=12)
    ap.add_argument("--nt", type=int, default=48)
    ap.add_argument("--job", default="PLASTIC")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
