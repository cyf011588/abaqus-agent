# -*- coding: utf-8 -*-
"""inp 生成共享工具（纯标准库），供内置 Abaqus 案例库复用。

提供：
- NodeTable：按坐标去重的节点注册表（用于多块板共享边/角）；
- 网格生成：规则六面体 / 矩形壳 / 带孔方板（映射）/ L 型支架；
- inp 文本片段：节点、单元、集合、材料、截面、分析步、边界、载荷。
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

# --------------------------------------------------------------------------- 格式化


def _f(x: float) -> str:
    """浮点 → 简洁可被 Abaqus 接受的字符串（去尾零，保留 6 位有效）。"""
    s = f"{x:.6g}"
    return s


# --------------------------------------------------------------------------- 节点表


class NodeTable:
    """按坐标去重的节点注册表：多块板共享边/角时，相同坐标只建一个节点。"""

    def __init__(self):
        self.nodes: List[Tuple[int, float, float, float]] = []
        self._index: Dict[Tuple[float, float, float], int] = {}

    def add(self, x: float, y: float, z: float = 0.0) -> int:
        key = (round(x, 6), round(y, 6), round(z, 6))
        nid = self._index.get(key)
        if nid is not None:
            return nid
        nid = len(self.nodes) + 1
        self.nodes.append((nid, x, y, z))
        self._index[key] = nid
        return nid


# --------------------------------------------------------------------------- 网格生成


def hex_mesh(L: float, W: float, H: float, nx: int, ny: int, nz: int,
             origin: Tuple[float, float, float] = (0.0, 0.0, 0.0)):
    """规则六面体网格（C3D8R）。返回 (nodes, elements, nsets)。"""
    ox, oy, oz = origin

    def nid(i: int, j: int, k: int) -> int:
        return i + j * (nx + 1) + k * (nx + 1) * (ny + 1) + 1

    nodes = []
    for k in range(nz + 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                nodes.append((nid(i, j, k), ox + i * L / nx, oy + j * W / ny, oz + k * H / nz))

    elements = []
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                elements.append((len(elements) + 1, [
                    nid(i, j, k), nid(i + 1, j, k), nid(i + 1, j + 1, k), nid(i, j + 1, k),
                    nid(i, j, k + 1), nid(i + 1, j, k + 1), nid(i + 1, j + 1, k + 1), nid(i, j + 1, k + 1),
                ]))

    nsets = {
        "X0": [nid(0, j, k) for j in range(ny + 1) for k in range(nz + 1)],
        "X1": [nid(nx, j, k) for j in range(ny + 1) for k in range(nz + 1)],
        "Y0": [nid(i, 0, k) for i in range(nx + 1) for k in range(nz + 1)],
        "Y1": [nid(i, ny, k) for i in range(nx + 1) for k in range(nz + 1)],
        "Z0": [nid(i, j, 0) for i in range(nx + 1) for j in range(ny + 1)],
        "Z1": [nid(i, j, nz) for i in range(nx + 1) for j in range(ny + 1)],
    }
    return nodes, elements, nsets


def shell_rect_mesh(L: float, W: float, nx: int, ny: int,
                    origin: Tuple[float, float, float] = (0.0, 0.0, 0.0)):
    """矩形壳网格（xy 平面，S4R）。返回 (nodes, elements, nsets)。"""
    ox, oy, oz = origin

    def nid(i: int, j: int) -> int:
        return i + j * (nx + 1) + 1

    nodes = []
    for j in range(ny + 1):
        for i in range(nx + 1):
            nodes.append((nid(i, j), ox + i * L / nx, oy + j * W / ny, oz))

    elements = []
    for j in range(ny):
        for i in range(nx):
            elements.append((len(elements) + 1,
                             [nid(i, j), nid(i + 1, j), nid(i + 1, j + 1), nid(i, j + 1)]))

    nsets = {
        "X0": [nid(0, j) for j in range(ny + 1)],
        "X1": [nid(nx, j) for j in range(ny + 1)],
        "Y0": [nid(i, 0) for i in range(nx + 1)],
        "Y1": [nid(i, ny) for i in range(nx + 1)],
    }
    return nodes, elements, nsets


def plate_hole_mesh(W: float, H: float, r: float, nr: int, nt: int):
    """带孔方板映射网格（xy 平面，S4R）：中心圆孔 r，方形外边界 W×H。

    径向 nr 层（0=孔边界，nr=外边界），环向 nt 段。返回 (nodes, elements, nsets)。
    """
    def nid(i: int, j: int) -> int:
        return i * nt + j + 1

    nodes = []
    for i in range(nr + 1):
        for j in range(nt):
            th = 2.0 * math.pi * j / nt
            c, s = math.cos(th), math.sin(th)
            hx, hy = r * c, r * s
            tx = (W / 2.0) / abs(c) if abs(c) > 1e-12 else float("inf")
            ty = (H / 2.0) / abs(s) if abs(s) > 1e-12 else float("inf")
            t = min(tx, ty)
            ox, oy = t * c, t * s
            f = i / nr
            nodes.append((nid(i, j), hx + f * (ox - hx), hy + f * (oy - hy), 0.0))

    elements = []
    for i in range(nr):
        for j in range(nt):
            j2 = (j + 1) % nt
            elements.append((len(elements) + 1,
                             [nid(i, j), nid(i + 1, j), nid(i + 1, j2), nid(i, j2)]))

    outer = [(nid(nr, j), nodes[nid(nr, j) - 1][1], nodes[nid(nr, j) - 1][2])
             for j in range(nt)]
    left = [n for n, x, y in outer if x < -1e-9]
    right = [n for n, x, y in outer if x > 1e-9]
    nsets = {"LEFT": left, "RIGHT": right, "OUTER": [n for n, _, _ in outer]}
    return nodes, elements, nsets


def l_bracket_mesh(H: float, L: float, t: float, nx1: int, my: int, nx2: int):
    """L 型支架壳中面（xy 平面，S4R）。

    竖直板 x∈[0,t]、y∈[0,H]；水平板 x∈[t,L]、y∈[0,t]；共享边 x=t、y∈[0,t]。
    nx1 为臂宽（厚度方向）分段，my 为竖直臂总分段，nx2 为水平臂分段（需 my>nx1）。
    返回 (nodes, elements, nsets)，nsets 含 FIXED（竖直板底部 y=0）与 TIP（水平板自由端 x=L）。
    """
    nt = NodeTable()

    # 竖直板：x∈[0,t] nx1 段；y = [0,t] nx1 段 + [t,H] (my-nx1) 段（与水平板对齐）
    vx = [i * t / nx1 for i in range(nx1 + 1)]
    vy = [j * t / nx1 for j in range(nx1 + 1)] + \
         [t + (j - nx1) * (H - t) / (my - nx1) for j in range(nx1 + 1, my + 1)]
    for j in range(my + 1):
        for i in range(nx1 + 1):
            nt.add(vx[i], vy[j], 0.0)

    # 水平板：x∈[t,L] nx2 段；y∈[0,t] nx1 段
    hx = [t + i * (L - t) / nx2 for i in range(nx2 + 1)]
    hy = [j * t / nx1 for j in range(nx1 + 1)]
    for j in range(nx1 + 1):
        for i in range(nx2 + 1):
            nt.add(hx[i], hy[j], 0.0)

    elements = []
    # 竖直板单元
    for j in range(my):
        for i in range(nx1):
            elements.append((len(elements) + 1, [
                nt.add(vx[i], vy[j]), nt.add(vx[i + 1], vy[j]),
                nt.add(vx[i + 1], vy[j + 1]), nt.add(vx[i], vy[j + 1]),
            ]))
    # 水平板单元
    for j in range(nx1):
        for i in range(nx2):
            elements.append((len(elements) + 1, [
                nt.add(hx[i], hy[j]), nt.add(hx[i + 1], hy[j]),
                nt.add(hx[i + 1], hy[j + 1]), nt.add(hx[i], hy[j + 1]),
            ]))

    nsets = {
        "FIXED": [nt.add(vx[i], 0.0) for i in range(nx1 + 1)],
        "TIP": [nt.add(L, hy[j]) for j in range(nx1 + 1)],
    }
    return nt.nodes, elements, nsets


def beam_mesh(L: float, nx: int, origin: Tuple[float, float, float] = (0.0, 0.0, 0.0)):
    """简支梁线单元（B31），沿 x 轴。返回 (nodes, elements, nsets)。"""
    ox, oy, oz = origin
    nodes = [(i + 1, ox + i * L / nx, oy, oz) for i in range(nx + 1)]
    elements = [(i + 1, [i + 1, i + 2]) for i in range(nx)]
    nsets = {"LEFT": [1], "RIGHT": [nx + 1], "MID": [nx // 2 + 1]}
    return nodes, elements, nsets


def truss_mesh(L: float, H: float):
    """等腰三角桁架（T3D2）：A(0,0) B(L,0) C(L/2,H)，3 杆。返回 (nodes, elements, nsets)。"""
    nodes = [(1, 0.0, 0.0, 0.0), (2, L, 0.0, 0.0), (3, L / 2, H, 0.0)]
    elements = [(1, [1, 2]), (2, [1, 3]), (3, [2, 3])]
    nsets = {"A": [1], "B": [2], "C": [3]}
    return nodes, elements, nsets


def annulus_quarter_mesh(a: float, b: float, nr: int, nt: int):
    """1/4 圆环（第一象限）极坐标网格（CPE4 平面应变）。

    内径 a、外径 b，径向 nr 层、环向 nt 段（θ∈[0, π/2]）。
    返回 (nodes, elements, nsets)：INNER（内壁 r=a）、OUTER（外壁 r=b）、SYMX（θ=0）、SYMY（θ=π/2）。
    """
    def nid(i: int, j: int) -> int:
        return i * (nt + 1) + j + 1

    nodes = []
    for i in range(nr + 1):
        r = a + i * (b - a) / nr
        for j in range(nt + 1):
            th = (math.pi / 2) * j / nt
            nodes.append((nid(i, j), r * math.cos(th), r * math.sin(th), 0.0))

    elements = []
    for i in range(nr):
        for j in range(nt):
            elements.append((len(elements) + 1,
                             [nid(i, j), nid(i + 1, j), nid(i + 1, j + 1), nid(i, j + 1)]))

    nsets = {
        "INNER": [nid(0, j) for j in range(nt + 1)],
        "OUTER": [nid(nr, j) for j in range(nt + 1)],
        "SYMX": [nid(i, 0) for i in range(nr + 1)],
        "SYMY": [nid(i, nt) for i in range(nr + 1)],
    }
    return nodes, elements, nsets


def frame_mesh(n_story: int, n_bay: int, h: float, L: float):
    """平面钢框架（B31 梁单元，x-y 平面内，z 出平面）。

    节点 (story, col)：story=0..n_story，col=0..n_bay，坐标 (col*L, story*h, 0)。
    柱单元在前（story=0..n_story-1 × col=0..n_bay），梁单元在后（story=1..n_story × col=0..n_bay-1）。
    返回 (nodes, elements, nsets)：BASE（柱底）、FLOORS（各层楼面节点）、ALL（全部节点）。
    """
    def nid(story: int, col: int) -> int:
        return story * (n_bay + 1) + col + 1

    nodes = []
    for story in range(n_story + 1):
        for col in range(n_bay + 1):
            nodes.append((nid(story, col), col * L, story * h, 0.0))

    elements = []
    for story in range(n_story):
        for col in range(n_bay + 1):
            elements.append((len(elements) + 1, [nid(story, col), nid(story + 1, col)]))
    for story in range(1, n_story + 1):
        for col in range(n_bay):
            elements.append((len(elements) + 1, [nid(story, col), nid(story, col + 1)]))

    nsets = {
        "BASE": [nid(0, col) for col in range(n_bay + 1)],
        "FLOORS": [nid(story, col) for story in range(1, n_story + 1)
                   for col in range(n_bay + 1)],
        "ALL": [nid(story, col) for story in range(n_story + 1) for col in range(n_bay + 1)],
    }
    return nodes, elements, nsets


# --------------------------------------------------------------------------- inp 文本片段


def fmt_nodes(nodes) -> str:
    lines = ["*Node"]
    lines += [f"{nid}, {_f(x)}, {_f(y)}, {_f(z)}" for nid, x, y, z in nodes]
    return "\n".join(lines)


def fmt_elements(etype: str, elements) -> str:
    lines = [f"*Element, type={etype}"]
    for eid, conn in elements:
        lines.append(", ".join([str(eid)] + [str(n) for n in conn]))
    return "\n".join(lines)


def fmt_nset(name: str, ids) -> str:
    lines = [f"*Nset, nset={name}"]
    for k in range(0, len(ids), 16):
        lines.append(", ".join(str(x) for x in ids[k:k + 16]))
    return "\n".join(lines)


def fmt_elset(name: str, ids) -> str:
    lines = [f"*Elset, elset={name}"]
    for k in range(0, len(ids), 16):
        lines.append(", ".join(str(x) for x in ids[k:k + 16]))
    return "\n".join(lines)


def elastic_material(name: str, E: float, nu: float) -> str:
    return f"*Material, name={name}\n*Elastic\n{_f(E)}, {_f(nu)}"


def solid_section(elset: str, mat: str) -> str:
    return f"*Solid Section, elset={elset}, material={mat}"


def shell_section(elset: str, mat: str, thickness: float) -> str:
    return f"*Shell Section, elset={elset}, material={mat}\n{_f(thickness)}, 5"


def static_step(name: str = "Load") -> str:
    return f"*Step, name={name}\n*Static\n1., 1., 1e-05, 1."


def boundary(nset: str, d1: int, d2: int = None, value: float = None) -> str:
    if d2 is None:
        return f"*Boundary\n{nset}, {d1}, {d1}"
    if value is None:
        return f"*Boundary\n{nset}, {d1}, {d2}"
    return f"*Boundary\n{nset}, {d1}, {d2}, {_f(value)}"


def cload(nset: str, dof: int, value: float) -> str:
    return f"*Cload\n{nset}, {dof}, {_f(value)}"


def field_output() -> str:
    return "*Output, field\n*Node Output\nU\n*Element Output\nS, E\n*End Step"
