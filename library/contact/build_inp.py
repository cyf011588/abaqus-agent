# -*- coding: utf-8 -*-
"""内置案例：两方块面面接触（C3D8R + *Contact Pair，压缩）。

契约：python build_inp.py --W ... --d ... --mu ... --job JOB --out DIR
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.inpkit import (hex_mesh, fmt_nodes, fmt_elements, fmt_nset, fmt_elset,
                          elastic_material, solid_section, boundary, field_output)


def build(args):
    W = args.W
    low_nodes, low_elems, low_ns = hex_mesh(W, W, W, args.nx, args.ny, args.nz)
    high_nodes, high_elems, high_ns = hex_mesh(W, W, W, args.nx, args.ny, args.nz,
                                               origin=(0.0, 0.0, W))
    N1 = len(low_nodes)
    NE = len(low_elems)
    high_nodes2 = [(i + N1, x, y, z) for (i, x, y, z) in high_nodes]
    high_elems2 = [(e + NE, [c + N1 for c in conn]) for (e, conn) in high_elems]
    nodes = low_nodes + high_nodes2
    elements = low_elems + high_elems2

    # 接触面只能取"贴合的那一层"：
    # 下块最顶层单元（k=nz-1）的上表面 S2，上块最底层单元（k=0）的下表面 S1。
    # 之前把所有单元的 S2/S1 都写进 surface，内部面混进来就成了"不连续复合面"。
    nxy = args.nx * args.ny
    low_top_ids = [(args.nz - 1) * nxy + i + 1 for i in range(nxy)]
    high_bot_ids = [i + 1 + NE for i in range(nxy)]
    bot_top = "\n".join(f"{e}, S2" for e in low_top_ids)
    top_bot = "\n".join(f"{e}, S1" for e in high_bot_ids)

    blocks = [
        "*Heading",
        f"** Contact: two cubes stacked along z, compression d={args.d}, mu={args.mu}",
        fmt_nodes(nodes),
        fmt_elements("C3D8R", elements),
        fmt_nset("BASE", low_ns["Z0"]),
        fmt_nset("TOP", [n + N1 for n in high_ns["Z1"]]),
        fmt_elset("ALL", [e[0] for e in elements]),
        solid_section("ALL", "STEEL"),
        elastic_material("STEEL", args.E, args.nu),
        "*Surface, type=ELEMENT, name=BOT_TOP",
        bot_top,
        "*Surface, type=ELEMENT, name=TOP_BOT",
        top_bot,
        "*Surface Interaction, name=INT",
        "*Friction",
        f"{args.mu},",
        "*Contact Pair, interaction=INT",
        "BOT_TOP, TOP_BOT",
        "*Step, name=Contact, nlgeom=YES",
        "*Static",
        "1., 1., 1e-05, 1.",
        boundary("BASE", 1, 3),
        boundary("TOP", 1, 2),
        boundary("TOP", 3, 3, -args.d),
        field_output(),
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "CONTACT") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    return path


def main():
    ap = argparse.ArgumentParser(description="两方块接触 inp 生成")
    ap.add_argument("--W", type=float, default=10.0, help="方块边长")
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--d", type=float, default=0.1, help="压缩位移")
    ap.add_argument("--mu", type=float, default=0.2, help="摩擦系数")
    ap.add_argument("--nx", type=int, default=4)
    ap.add_argument("--ny", type=int, default=4)
    ap.add_argument("--nz", type=int, default=4)
    ap.add_argument("--job", default="CONTACT")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
