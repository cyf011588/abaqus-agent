# -*- coding: utf-8 -*-
"""内置案例：平板顺序耦合热应力（先传热步求温度场，再静力步读温度场求应力）。

教科书两种热应力 workflow 的顺序耦合版：
  Step 1  *Heat Transfer, steady-state —— X0 端 0°C、X1 端 dT°C，线性温度场 T(x)=dT*x/L
  Step 2  *Static —— 两端固支（u1=u2=0），*Temperature, file=<job>, step=1 读入温度场
一维自由热应变被约束后，由 ∫σ dx = 0 得 ε_x = alpha·T_avg，故
    σ_x(x) = E·alpha·(T_avg - T(x)) = E·alpha·dT·(0.5 - x/L)
默认钢 (E=210000, alpha=1.2e-5, dT=100) → 左端 +126 MPa、右端 -126 MPa。

注意：*Temperature, file= 依赖 Abaqus 在同一 job 内先算完 Step 1 再读结果，
需在 Abaqus 实跑确认（本仓库只做 inp 结构校验）。

契约：python build_inp.py --L ... --dT ... --job JOB --out DIR  输出 DIR/JOB.inp
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent.inpkit import (shell_rect_mesh, fmt_nodes, fmt_elements, fmt_nset,
                          fmt_elset, field_output)


def build(args):
    nodes, elements, nsets = shell_rect_mesh(args.L, args.H, args.nx, args.ny)
    job = args.job or "THERMAL_SEQ"
    blocks = [
        "*Heading",
        f"** Sequential thermal stress: L={args.L}, H={args.H}, alpha={args.alpha}, "
        f"dT={args.dT}, CPE4T, heat transfer step then static step",
        fmt_nodes(nodes),
        fmt_elements("CPE4T", elements),
        fmt_nset("X0", nsets["X0"]),
        fmt_nset("X1", nsets["X1"]),
        fmt_nset("BOTTOM", nsets["Y0"]),
        fmt_nset("TOP", nsets["Y1"]),
        fmt_elset("ALL", [e[0] for e in elements]),
        "*Solid Section, elset=ALL, material=STEEL",
        "1.,",
        "*Material, name=STEEL",
        "*Elastic",
        f"{args.E}, {args.nu}",
        "*Expansion",
        f"{args.alpha}",
        "*Conductivity",
        f"{args.k},",
        "*Initial Conditions, type=Temperature",
        "ALL, 0.",
        "*Step, name=HeatTransfer",
        # CPE4T 带位移自由度，不能进纯 *Heat Transfer 步（Abaqus 只允许 DOF>=11 激活），
        # 因此第一步用耦合温度-位移稳态步求温度场；第二步 *Static 继承温度算热应力
        "*Coupled Temperature-Displacement, steady state",
        "0.1, 1., 1e-5, 1.",
        "*Boundary",
        "X0, 1, 2",
        "*Boundary",
        "X0, 11, 11, 0.",
        f"X1, 11, 11, {args.dT}",
        field_output(),
        "*Step, name=Static",
        "*Static",
        "0.1, 1., 1e-5, 1.",
        # 第一步温度边界（DOF 11）会跨步传播，*Static 里不允许 DOF 11 边界，
        # 必须 op=NEW 清掉继承边界，再重新给位移约束；温度作为场自动继承
        "*Boundary, op=NEW",
        "X0, 1, 2",
        "X1, 1, 2",
        # 温度场由第一步（耦合步）自动继承，无需 *Temperature, file=
        field_output(),
    ]
    # ALL 需要包含全部节点（初始温度）
    all_nodes = [n[0] for n in nodes]
    blocks.insert(9, fmt_nset("ALL", all_nodes))
    inp = "\n".join(blocks) + "\n"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, job + ".inp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(inp)
    peak = args.E * args.alpha * args.dT * 0.5
    print(f"generated {path} (nodes={len(nodes)}, elems={len(elements)})")
    print(f"theory sigma_x = +/- E*alpha*dT/2 = +/-{peak:.2f} MPa")
    return path


def main():
    ap = argparse.ArgumentParser(description="平板顺序耦合热应力 inp 生成")
    ap.add_argument("--L", type=float, default=200.0)
    ap.add_argument("--H", type=float, default=100.0)
    ap.add_argument("--nx", type=int, default=20)
    ap.add_argument("--ny", type=int, default=10)
    ap.add_argument("--E", type=float, default=210000.0)
    ap.add_argument("--nu", type=float, default=0.3)
    ap.add_argument("--alpha", type=float, default=1.2e-5)
    ap.add_argument("--k", type=float, default=0.05, help="热导率 N/(s·K)，mm-t-s 制")
    ap.add_argument("--dT", type=float, default=100.0)
    ap.add_argument("--job", default="THERMAL_SEQ")
    ap.add_argument("--out", default=".")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
