# -*- coding: utf-8 -*-
"""内置案例：加筋板线性屈曲（S4R 板 + S4R 纵向肋，T 形共节点，*Buckle）。

契约：python build_inp.py --L ... --W ... --t ... --h_r ... --t_r ... --nx ... --ny ... --P ... --nmodes ... --E ... --nu ... --job JOB --out DIR
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.inpkit import (shell_rect_mesh, fmt_nodes, fmt_elements, fmt_nset,
                          fmt_elset, elastic_material, shell_section, field_output, _f)


def build(args):
    # 板（z=0，S4R）+ 纵向肋（xz 平面，y=W/2，底边共享板中线节点，T 形截面）
    pn, pe, pns = shell_rect_mesh(args.L, args.W, args.nx, args.ny)

    def pid(i, j):
        return i + j * (args.nx + 1) + 1

    jmid = args.ny // 2
    nbase = len(pn)

    rib_nodes = [(nbase + i + 1, i * args.L / args.nx, args.W / 2.0, args.h_r)
                 for i in range(args.nx + 1)]
    rib_els = [(len(pe) + i + 1, [pid(i, jmid), pid(i + 1, jmid),
                                  nbase + i + 2, nbase + i + 1])
               for i in range(args.nx)]

    nodes = pn + rib_nodes
    elements = pe + rib_els

    blocks = [
        "*Heading",
        f"** Stiffened plate buckle: plate {args.L}x{args.W}x{args.t}, rib h={args.h_r} t={args.t_r}",
        fmt_nodes(nodes),
        fmt_elements("S4R", elements),
        fmt_elset("PLATE", [e[0] for e in pe]),
        fmt_elset("RIB", [e[0] for e in rib_els]),
        fmt_elset("ALL", [e[0] for e in elements]),
        fmt_nset("X0", pns["X0"]),
        fmt_nset("X1", pns["X1"]),
        fmt_nset("Y0", pns["Y0"]),
        fmt_nset("Y1", pns["Y1"]),
        elastic_material("STEEL", args.E, args.nu),
        shell_section("PLATE", "STEEL", args.t),
        shell_section("RIB", "STEEL", args.t_r),
        # 线性屈曲必须两步：先 *Static 预载（建立 base state 的应力刚度），再 *Buckle 求特征值。
        # 同时要约束面内刚体位移（U1/U2），否则刚度矩阵奇异 -> "THE EIGENVALUES CANNOT BE FOUND"。
        "*Step, name=Preload\n*Static\n0.1, 1., 1e-5, 0.1",
        "*Boundary",
        "X0, 1, 1, 0.",
        "Y0, 2, 2, 0.",
        "X0, 3, 3",
        "X1, 3, 3",
        "Y0, 3, 3",
        "Y1, 3, 3",
        "*Cload",
        f"X1, 1, {_f(-args.P * args.W / (args.ny + 1))}",
        field_output(),
        # *Buckle 数据行：特征值数, 精度(默认), 迭代次数。细网格 4 阶求解常因迭代不足报
        # "INCREASE THE NUMBER OF ITERATIONS TO GET THE REQUESTED NUMBER OF EIGENVALUES"，给到 40
        f"*Step, name=Buckle\n*Buckle\n{args.nmodes}, , 40",
        "*Boundary",
        "X0, 1, 1, 0.",
        "Y0, 2, 2, 0.",
        "X0, 3, 3",
        "X1, 3, 3",
        "Y0, 3, 3",
        "Y1, 3, 3",
        "*Cload",
        f"X1, 1, {_f(-args.P * args.W / (args.ny + 1))}",
        field_output(),
    ]
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, (args.job or "StiffPlate") + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    print(f"[OK] 生成 {path}（{len(nodes)} 节点 / {len(elements)} 单元）")


def main():
    ap = argparse.ArgumentParser(description="加筋板线性屈曲")
    for name, default in (("L", 1000.0), ("W", 500.0), ("t", 10.0), ("h-r", 50.0),
                          ("t-r", 10.0), ("P", 1.0), ("E", 210000.0), ("nu", 0.3)):
        ap.add_argument(f"--{name}", type=float, default=default)
    for name, default in (("nx", 20), ("ny", 10), ("nmodes", 4)):
        ap.add_argument(f"--{name}", type=int, default=default)
    ap.add_argument("--job", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    build(args)


if __name__ == "__main__":
    main()
