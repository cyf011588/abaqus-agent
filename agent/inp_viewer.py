# -*- coding: utf-8 -*-
"""Abaqus inp → 网页可渲染网格几何（零第三方依赖）。

解析 *Node / *Element / *Part / *Instance：
- 展开每个 instance 的平移 + 绕轴旋转 transform；
- 壳单元(S4R/S4/S3) 三角化；
- 体单元(C3D8R/C3D8) 六面体 6 面三角化，并对共享面做外表面剔除；
- 线单元(B31/T3D2/Spring 等) 线段化。

输出可直接喂给 three.js 的扁平结构。
"""
from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Tuple

# 单元类型 -> (节点数, 几何种类)
_SHELL_TYPES = {"S4R": 4, "S4": 4, "S3": 3, "S3R": 3, "STRI3": 3, "STRI65": 6,
                "CPE4": 4, "CPE4R": 4, "CPE3": 3, "CPS4": 4, "CPS4R": 4, "CPS3": 3,
                "CPE4T": 4, "CPS4T": 4,
                "CAX4": 4, "CAX4R": 4, "CAX3": 3,
                "DC2D4": 4, "DC2D3": 3, "DC2D6": 6, "DC2D8": 8}
_SOLID_HEX_TYPES = {"C3D8R": 8, "C3D8": 8, "C3D8RT": 8, "C3D8T": 8}
_SOLID_TET_TYPES = {"C3D4": 4}
_LINE_TYPES = {"B31", "B32", "T3D2", "T3D3", "SPRINGA", "SPRING1", "SPRING2", "CONN3D2"}

_KEY_RE = re.compile(r"^\*([A-Za-z]+)")


def _floats(line: str) -> List[float]:
    out: List[float] = []
    for x in line.split(","):
        x = x.strip()
        if not x:
            continue
        try:
            out.append(float(x))
        except ValueError:
            continue
    return out


def _ints(line: str) -> List[int]:
    out: List[int] = []
    for x in line.split(","):
        x = x.strip()
        if not x:
            continue
        try:
            out.append(int(x))
        except ValueError:
            continue
    return out


def rotation_matrix(axis1: Tuple[float, float, float],
                    axis2: Tuple[float, float, float],
                    angle_deg: float) -> List[List[float]]:
    """绕 axis1→axis2 定义的轴旋转 angle_deg（右手定则），返回 3x3 行主序矩阵。"""
    ux, uy, uz = axis2[0] - axis1[0], axis2[1] - axis1[1], axis2[2] - axis1[2]
    length = math.sqrt(ux * ux + uy * uy + uz * uz)
    if length < 1e-12:
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    ux, uy, uz = ux / length, uy / length, uz / length
    t = math.radians(angle_deg)
    c, s = math.cos(t), math.sin(t)
    C = 1.0 - c
    return [
        [c + ux * ux * C, ux * uy * C - uz * s, ux * uz * C + uy * s],
        [uy * ux * C + uz * s, c + uy * uy * C, uy * uz * C - ux * s],
        [uz * ux * C - uy * s, uz * uy * C + ux * s, c + uz * uz * C],
    ]


def _apply(p: Tuple[float, float, float],
           R: List[List[float]],
           t: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (R[0][0] * p[0] + R[0][1] * p[1] + R[0][2] * p[2] + t[0],
            R[1][0] * p[0] + R[1][1] * p[1] + R[1][2] * p[2] + t[1],
            R[2][0] * p[0] + R[2][1] * p[1] + R[2][2] * p[2] + t[2])


def _hex_quads(conn: List[int]) -> List[Tuple[int, int, int, int]]:
    """C3D8 节点顺序(底面 0-3, 顶面 4-7) -> 6 个四边形面。"""
    return [
        (conn[0], conn[1], conn[2], conn[3]),
        (conn[4], conn[5], conn[6], conn[7]),
        (conn[0], conn[1], conn[5], conn[4]),
        (conn[1], conn[2], conn[6], conn[5]),
        (conn[2], conn[3], conn[7], conn[6]),
        (conn[3], conn[0], conn[4], conn[7]),
    ]


def _tet_tris(conn: List[int]) -> List[Tuple[int, int, int]]:
    """C3D4 四面体(4 节点) -> 4 个三角形面。"""
    return [
        (conn[0], conn[1], conn[2]),
        (conn[0], conn[3], conn[1]),
        (conn[0], conn[2], conn[3]),
        (conn[1], conn[3], conn[2]),
    ]


def parse_inp(text: str) -> dict:
    parts: Dict[str, dict] = {"__top__": {"nodes": {}, "elements": []}}  # 扁平结构（无 Part）的顶层容器
    instances: List[dict] = []           # {"part": name, "t": (x,y,z), "rot": ((a),(b),angle) or None}

    cur_part: Optional[str] = None
    cur_type: Optional[str] = None
    section: Optional[str] = None        # "node" | "element" | "nset" | "boundary" | "cload" | None
    cur_nset: Optional[str] = None
    nset_gen = False
    nodesets: Dict[str, List[int]] = {}  # nset 名 -> 节点号
    cur_elset: Optional[str] = None
    elset_gen = False
    elsets: Dict[str, List[int]] = {}    # elset 名 -> 单元号
    bcs: List[dict] = []                 # {"set","dofs","value"}
    loads: List[dict] = []               # {"set","dof","value"}
    dloads: List[dict] = []              # {"set","kind","value"} 分布载荷（*Dload）
    cur_surface: Optional[str] = None
    surfaces: Dict[str, List[int]] = {}  # surface 名 -> 构成它的单元号（*Dsload 面载荷要用）

    lines = text.splitlines()
    n = len(lines)
    i = 0
    while i < n:
        raw = lines[i]
        line = raw.strip()
        if not line or line.startswith("**"):
            i += 1
            continue

        if line.startswith("*"):
            up = line.upper()
            if up.startswith("*PART"):
                m = re.match(r"\*Part,\s*name=([^,]+)", line, re.I)
                if not m:
                    i += 1
                    continue
                name = m.group(1).strip()
                cur_part = name
                cur_type = None
                parts[name] = {"nodes": {}, "elements": []}
                section = None
                i += 1
                continue
            if up.startswith("*END PART"):
                cur_part = None
                cur_type = None
                section = None
                i += 1
                continue
            if up.startswith("*ASSEMBLY"):
                section = None
                i += 1
                continue
            if up.startswith("*END ASSEMBLY"):
                section = None
                i += 1
                continue
            if up.startswith("*INSTANCE"):
                m = re.match(r"\*Instance,\s*name=([^,]+),\s*part=([^,\s]+)", line, re.I)
                if m:
                    inst_name = m.group(1).strip()
                    part_name = m.group(2).strip()
                    i += 1
                    tv = _floats(lines[i].strip())
                    translation = tuple(tv[:3])
                    rotation = None
                    j = i + 1
                    if j < n and not lines[j].strip().startswith("*"):
                        rv = _floats(lines[j].strip())
                        if len(rv) >= 7:
                            rotation = (tuple(rv[:3]), tuple(rv[3:6]), rv[6])
                            i = j + 1
                        else:
                            i = j
                    else:
                        i = j
                    instances.append({"name": inst_name, "part": part_name, "t": translation, "rot": rotation})
                    section = None
                    continue
                i += 1
                continue
            if re.match(r"\*Node\s*(,|$)", line, re.I):
                section = "node"
                i += 1
                continue
            if re.match(r"\*Element\s*(,|$)", line, re.I):
                m = re.search(r"TYPE\s*=\s*([A-Za-z0-9]+)", up)
                cur_type = m.group(1).upper() if m else None
                section = "element"
                i += 1
                continue
            if up.startswith("*NSET"):
                m = re.search(r"nset\s*=\s*([^,\s]+)", line, re.I)
                cur_nset = m.group(1).strip() if m else None
                m2 = re.search(r"instance\s*=\s*([^,\s]+)", line, re.I)
                cur_nset_inst = m2.group(1).strip() if m2 else None
                nset_gen = "generate" in up.lower()
                section = "nset"
                i += 1
                continue
            if up.startswith("*ELSET"):
                m = re.search(r"elset\s*=\s*([^,\s]+)", line, re.I)
                cur_elset = m.group(1).strip() if m else None
                elset_gen = "generate" in up.lower()
                section = "elset"
                i += 1
                continue
            if up.startswith("*DLOAD"):
                section = "dload"
                i += 1
                continue
            if up.startswith("*DSLOAD"):
                section = "dsload"
                i += 1
                continue
            if up.startswith("*SURFACE") and "INTERACTION" not in up:
                m = re.search(r"name\s*=\s*([^,\s]+)", line, re.I)
                cur_surface = m.group(1).strip() if m else None
                section = "surface"
                i += 1
                continue
            if up.startswith("*BOUNDARY"):
                section = "boundary"
                i += 1
                continue
            if up.startswith("*TEMPERATURE"):
                section = "temperature"
                i += 1
                continue
            if up.startswith("*CLOAD"):
                section = "cload"
                i += 1
                continue
            # 其余 keyword（*Surface/*Section/...）后的数据跳过
            section = None
            i += 1
            continue

        # 数据行
        if section == "node":
            target = cur_part or "__top__"
            vals = _floats(line)
            if len(vals) >= 4:
                parts.setdefault(target, {"nodes": {}, "elements": []})
                parts[target]["nodes"][int(vals[0])] = (vals[1], vals[2], vals[3])
        elif section == "element" and cur_type is not None:
            target = cur_part or "__top__"
            vals = _ints(line)
            if len(vals) >= 2:
                parts.setdefault(target, {"nodes": {}, "elements": []})
                parts[target]["elements"].append((cur_type, vals[0], vals[1:]))
        elif section == "nset" and cur_nset:
            vals = _ints(line)
            if nset_gen and len(vals) >= 3:
                vals = list(range(vals[0], vals[1] + 1, max(1, vals[2])))
            nodesets.setdefault((cur_nset, cur_nset_inst), []).extend(vals)
        elif section == "elset" and cur_elset:
            vals = _ints(line)
            if elset_gen and len(vals) >= 3:
                vals = list(range(vals[0], vals[1] + 1, max(1, vals[2])))
            elsets.setdefault(cur_elset, []).extend(vals)
        elif section == "boundary":
            cols = [x.strip() for x in line.split(",") if x.strip()]
            if len(cols) >= 2:
                try:
                    d1 = int(cols[1])
                except ValueError:
                    d1 = None
                d2 = d1
                if len(cols) >= 3:
                    try:
                        d2 = int(cols[2])
                    except ValueError:
                        d2 = d1
                val = 0.0
                if len(cols) >= 4:
                    try:
                        val = float(cols[3])
                    except ValueError:
                        val = 0.0
                if d1 is not None:
                    bcs.append({"set": cols[0], "dofs": list(range(d1, d2 + 1)), "value": val})
        elif section == "cload":
            cols = [x.strip() for x in line.split(",") if x.strip()]
            if len(cols) >= 2:
                try:
                    dof = int(cols[1])
                except ValueError:
                    dof = None
                val = 0.0
                if len(cols) >= 3:
                    try:
                        val = float(cols[2])
                    except ValueError:
                        val = 0.0
                if dof is not None:
                    loads.append({"set": cols[0], "dof": dof, "value": val})
        elif section == "dload":
            cols = [x.strip() for x in line.split(",") if x.strip()]
            if len(cols) >= 3:
                try:
                    dval = float(cols[2])
                except ValueError:
                    dval = None
                if dval is not None:
                    dloads.append({"set": cols[0], "kind": cols[1], "value": dval})
        elif section == "dsload":
            # *Dsload：surface 名, 类型(P/TRSHR…), 数值
            cols = [x.strip() for x in line.split(",") if x.strip()]
            if len(cols) >= 3:
                try:
                    dval = float(cols[2])
                except ValueError:
                    dval = None
                if dval is not None:
                    dloads.append({"set": cols[0], "kind": cols[1], "value": dval,
                                   "surface": True})
        elif section == "surface" and cur_surface:
            cols = [x.strip() for x in line.split(",") if x.strip()]
            if cols:
                tok = cols[0]
                if "-" in tok:      # instance 前缀写法 i1-12
                    tok = tok.split("-")[-1]
                try:
                    eid = int(tok)
                except ValueError:
                    eid = None
                if eid is not None:
                    surfaces.setdefault(cur_surface, []).append(eid)
        elif section == "temperature":
            cols = [x.strip() for x in line.split(",") if x.strip()]
            if len(cols) >= 2:
                try:
                    tval = float(cols[-1])
                except ValueError:
                    tval = None
                if tval is not None:
                    bcs.append({"set": cols[0], "dofs": [11], "value": tval})
        i += 1

    # ---- 展开 instance ----
    nodes_flat: List[float] = []
    shell_faces: List[int] = []
    solid_faces: List[int] = []
    line_segs: List[int] = []
    bc_out: List[dict] = []
    load_out: List[dict] = []
    dload_out: List[dict] = []

    insts = list(instances)
    if not insts and parts.get("__top__", {}).get("nodes"):
        # 扁平结构（无 *Part/*Assembly）：把顶层节点/单元当作一个无变换的实例
        insts = [{"part": "__top__", "t": (0.0, 0.0, 0.0), "rot": None}]

    # assembly 级节点（*Node 在 *Assembly 里，独立于 instance，如参考点 rp）单独映射
    top_map: Dict[int, int] = {}
    if insts and insts[0].get("part") != "__top__" and parts.get("__top__", {}).get("nodes"):
        for nid, xyz in parts["__top__"]["nodes"].items():
            top_map[nid] = len(nodes_flat) // 3
            nodes_flat.extend(xyz)

    for inst in insts:
        part = parts.get(inst["part"])
        if part is None:
            continue
        if inst["rot"]:
            a, b, ang = inst["rot"]
            R = rotation_matrix(a, b, ang)
        else:
            R = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        t = inst["t"]

        local_to_global: Dict[int, int] = {}
        for nid, xyz in part["nodes"].items():
            gx, gy, gz = _apply(xyz, R, t)
            local_to_global[nid] = len(nodes_flat) // 3
            nodes_flat.extend((gx, gy, gz))

        # 局部单元号 -> 全局单元（供 *Dload 的 elset 寻址）
        eid_map: Dict[int, dict] = {}
        for etype, eid, conn in part["elements"]:
            gconn = [local_to_global[x] for x in conn if x in local_to_global]
            if len(gconn) == len(conn):
                eid_map[eid] = {"t": etype, "c": gconn}

        # 体单元外表面剔除：本 instance 内统计六面体/四面体面出现次数
        face_count: Dict[Tuple[int, ...], int] = {}
        pending_solid: List[Tuple[Tuple[int, ...], List[Tuple[int, int, int]]]] = []
        for etype, eid, conn in part["elements"]:
            if etype in _SOLID_HEX_TYPES and len(conn) == 8:
                for quad in _hex_quads(conn):
                    key = tuple(sorted(quad))
                    face_count[key] = face_count.get(key, 0) + 1
                    pending_solid.append((key, list(_quad_tris(quad))))
            elif etype in _SOLID_TET_TYPES and len(conn) == 4:
                for tri in _tet_tris(conn):
                    key = tuple(sorted(tri))
                    face_count[key] = face_count.get(key, 0) + 1
                    pending_solid.append((key, [tri]))
        for key, tris in pending_solid:
            if face_count[key] != 1:
                continue  # 内部共享面，剔除
            for tri in tris:
                solid_faces.extend(local_to_global[x] for x in tri)

        # 边界条件 / 载荷：把 nset 名（或裸节点号）映射到全局节点索引
        inst_name = inst.get("name")
        for bc in bcs:
            ids = nodesets.get((bc["set"], inst_name))
            if ids is None:
                try:
                    ids = [int(bc["set"])]
                except ValueError:
                    continue
            for nid in ids:
                g = local_to_global.get(nid)
                if g is not None:
                    bc_out.append({"node": g, "dofs": bc["dofs"], "value": bc["value"]})
        for ld in loads:
            ids = nodesets.get((ld["set"], inst_name))
            if ids is None:
                try:
                    ids = [int(ld["set"])]
                except ValueError:
                    continue
            for nid in ids:
                g = local_to_global.get(nid)
                if g is not None:
                    load_out.append({"node": g, "dof": ld["dof"], "value": ld["value"]})

        # 分布载荷（*Dload 用 elset，*Dsload 用 surface）
        for dl in dloads:
            ids = surfaces.get(dl["set"], []) if dl.get("surface") else elsets.get(dl["set"], [])
            for eid in ids:
                el = eid_map.get(eid)
                if el is not None:
                    dload_out.append({"t": el["t"], "c": el["c"],
                                      "kind": dl["kind"], "value": dl["value"]})

        # 壳单元 / 线单元
        for etype, eid, conn in part["elements"]:
            if etype in _SHELL_TYPES:
                if len(conn) == 4:
                    shell_faces.extend((local_to_global[conn[0]], local_to_global[conn[1]],
                                        local_to_global[conn[2]]))
                    shell_faces.extend((local_to_global[conn[0]], local_to_global[conn[2]],
                                        local_to_global[conn[3]]))
                elif len(conn) == 3:
                    shell_faces.extend(local_to_global[x] for x in conn[:3])
            elif etype in _LINE_TYPES and len(conn) >= 2:
                line_segs.extend((local_to_global[conn[0]], local_to_global[conn[1]]))

    # assembly 级（无 instance）的约束/载荷 → 用 top_map（如 rp 参考点）
    for bc in bcs:
        ids = nodesets.get((bc["set"], None))
        if ids is None:
            continue
        for nid in ids:
            g = top_map.get(nid)
            if g is not None:
                bc_out.append({"node": g, "dofs": bc["dofs"], "value": bc["value"]})
    for ld in loads:
        ids = nodesets.get((ld["set"], None))
        if ids is None:
            continue
        for nid in ids:
            g = top_map.get(nid)
            if g is not None:
                load_out.append({"node": g, "dof": ld["dof"], "value": ld["value"]})

    # 去重：同一节点同一自由度只保留最后一次定义（应对 op=NEW / 重复 *Boundary）
    _seen: Dict[Tuple[int, Tuple[int, ...]], int] = {}
    for k, b in enumerate(bc_out):
        _seen[(b["node"], tuple(sorted(b["dofs"])))] = k
    bc_out = [bc_out[i] for i in _seen.values()]

    # bbox
    xs = nodes_flat[0::3]
    ys = nodes_flat[1::3]
    zs = nodes_flat[2::3]
    bbox = None
    if xs:
        bbox = [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]

    return {
        "summary": {
            "parts": [p for p in parts if p != "__top__"],
            "instances": len(instances),
            "nodes": len(nodes_flat) // 3,
            "shell_tris": len(shell_faces) // 3,
            "solid_tris": len(solid_faces) // 3,
            "line_segs": len(line_segs) // 2,
            "bbox": bbox,
        },
        "nodes": nodes_flat,
        "shell_faces": shell_faces,
        "solid_faces": solid_faces,
        "lines": line_segs,
        "boundary": bc_out,
        "loads": load_out,
        "dloads": dload_out,
    }


def _quad_tris(q: Tuple[int, int, int, int]) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    return (q[0], q[1], q[2]), (q[0], q[2], q[3])


def parse_inp_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return parse_inp(f.read())


if __name__ == "__main__":  # 快速自检
    import json
    import sys
    d = parse_inp_file(sys.argv[1])
    print(json.dumps(d["summary"], ensure_ascii=False, indent=2))
