# -*- coding: utf-8 -*-
"""内置案例：浅拱跳跃失稳 snap-through（B31 + *Static, Riks 弧长法 + nlgeom=YES）。

教科书几何非线性"难题"：抛物线浅拱在拱顶竖向集中力作用下，
荷载-位移曲线存在极限点，越过极限点后拱顶突然下跳（snap-through）到另一平衡态。
普通 *Static（荷载控制）在该点无法收敛，必须用弧长法 *Static, Riks 追踪平衡路径。
拱轴线：y(x) = f·[1 - (2x/L - 1)^2]，x∈[0, L]，矢高比 f/L≈0.04 属"浅拱"范围。

契约：python build_inp.py --L ... --f ... --P ... --job JOB --out DIR  输出 DIR/JOB.inp
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent.inpkit import (fmt_nodes, fmt_elements, fmt_nset, fmt_elset,
                          elastic_material, field_output)


def arch_mesh(L: float, f: float, nx: int):
    nodes = []
    for i in range(nx + 1):
        x = i * L / nx
        u = 2.0 * i / nx - 1.0
        y = f * (1.0 - u * u)
        nodes.append((i + 1, x, y, 0.0))
    elements = [(i + 1, [i + 1, i + 2]) for i in range(nx)]
    crown = nx // 2 + 1
    nsets = {"LEFT": [1], "RIGHT": [nx + 1], "CROWN": [crown],
             "ALL": [n[0] for n in nodes]}
    return nodes, elements, nsets


def build(args):
    nodes, elements, nsets = arch_mesh(args.L, args.f, args.nx)
    blocks = [
        "*Heading",
        f"** Snap-through of shallow arch: L={args.L}, f={args.f}, P={args.P}, "
        f"*Static, Riks arc-length, nlgeom=YES",
        fmt_nodes(nodes),
        fmt_elements("B31", elements),
        fmt_nset("LEFT", nsets["LEFT"]),
        fmt_nset("RIGHT", nsets["RIGHT"]),
        fmt_nset("CROWN", nsets["CROWN"]),
        fmt_nset("ALL", nsets["ALL"]),
        fmt_elset("ALL", [e[0] for e in elements]),
        "*Beam Section, elset=ALL, material=STEEL, section=RECT",
        f"{args.b}, {args.h}",
        "0., 0., -1.",
        elastic_material("STEEL", args.E, args.nu),
        "*Step, name=SnapThrough, nlgeom=YES",
        "*Static, Riks",
        "0.02, 1., 1e-5, 0.2",
        "*Boundary",
        "LEFT, 1, 2",
        "RIGHT, 2, 2",
        "ALL, 3, 3",
        "ALL, 4, 5",
        "*Cload",
        f"CROWN, 2, {-args.P}",
        "*Output, field",
        "*Node Output",
        "U",
        "*Element Output",
        "S, E",
        "*End Step",
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "SNAP_THROUGH") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    print(f"geometry: rise/span f/L={args.f / args.L:.3f}；"
          f"荷载-位移曲线应出现极限点与 snap-through 跳跃（Riks 可追踪）")
    return path


def main():
    ap = argparse.ArgumentParser(description="浅拱跳跃失稳（Riks 弧长法）inp 生成")
    ap.add_argument("--L", type=float, default=1000.0)
    ap.add_argument("--f", type=float, default=40.0)
    ap.add_argument("--b", type=float, default=20.0)
    ap.add_argument("--h", type=float, default=20.0)
    ap.add_argument("--nx", type=int, default=20)
    ap.add_argument("--P", type=float, default=500.0)
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--job", default="SNAP_THROUGH")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
