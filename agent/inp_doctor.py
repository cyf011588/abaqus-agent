# -*- coding: utf-8 -*-
"""Abaqus 报错 → 原因 → 修法。

这套规则来自真机踩过的坑（2026-11-15 把 13 个自建案例逐个提交求解时暴露的 8 类错误），
目的不是"猜"报错，而是让 agent 跑失败后能自己给出**可直接改 inp 的修法**。

用法：
    from agent import inp_doctor
    print(inp_doctor.diagnose(out_dir, job))
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

# match: 大小写不敏感的关键子串（尽量用 Abaqus 原文，避免误判）
RULES: List[Dict[str, str]] = [
    {
        "match": "element set",
        "cause": (
            "载荷/边界关键字引用的名字解析失败。最常见：`*Dload` 的数据行填了 `*Surface` 的名字——"
            "`*Dload` 只认 elset，面载荷要用 `*Dsload`"
        ),
        "fix": (
            "① 若该名字由 `*Surface, type=ELEMENT, name=<X>` 定义 → 把 `*Dload` 改成 `*Dsload`；"
            "② 若确实是 elset → 检查 `*Elset, elset=<X>` 是否在引用之前、大小写是否一致"
        ),
    },
    {
        "match": "missing property definitions",
        "cause": (
            "单元没有截面属性：缺 `*Solid Section` / `*Shell Section` / `*Beam Section`，"
            "或 section 的 elset 没覆盖全部单元"
        ),
        "fix": (
            "补 section 并确认 elset 覆盖所有单元，例如 `*Solid Section, elset=ALL, material=STEEL` "
            "再加一行厚度（2D 单元给 1.0 即单位厚度）；`*Material` 必须存在且名字与 section 一致"
        ),
    },
    {
        "match": "is not continuous or is composed of two or more",
        "cause": "接触面不连续：把内部面或不相连的单元面一起写进了同一个 `*Surface`",
        "fix": (
            "一个 `*Surface` 只能包含一块连续面：两块叠放时下块只取顶层单元的 S2、上块只取底层单元的 S1；"
            "接触面重合时还要确认两侧法向相对"
        ),
    },
    {
        "match": ".stf",
        "cause": (
            "Abaqus 建不出 scratch 临时文件（`Unable to open ... .stf`）：用户名或 TEMP 路径含中文，"
            "特征值求解器直接退出，而 `.msg` 里一条 ERROR 都没有"
        ),
        "fix": (
            "把 TEMP/TMP 指到纯英文目录并追加 `scratch=C:\\\\Temp\\\\abqscratch`；"
            "用户名为中文时同时覆写 `USERNAME=abquser`（`agent/abaqus_run.py` 已自动处理）"
        ),
    },
    {
        "match": "unknown parameter: implicit",
        "alt": ("unknown parameter implicit",),
        "cause": "*Dynamic 没有 implicit 这个参数，隐式动力就是默认行为",
        "fix": "把 `*Dynamic, Implicit` 改成 `*Dynamic`；显式才写 `*Dynamic, Explicit`",
    },
    {
        "match": "unknown parameter: nlgeom",
        "alt": ("unknown parameter nlgeom",),
        "cause": "nlgeom 是 *Step 的参数，不是 *Static 的",
        "fix": "`*Static, nlgeom=YES` 拆成两行：`*Step, name=<步名>, nlgeom=YES` 然后 `*Static`",
    },
    {
        "match": "unknown parameter: steady-state",
        "alt": ("unknown parameter steady-state",),
        "cause": "Abaqus 多词参数用空格分隔，不用连字符",
        "fix": "`steady-state` 改成 `steady state`（*Heat Transfer / *Coupled Temperature-Displacement 同）",
    },
    {
        "match": "requires a thermal conductivity",
        "cause": "带温度自由度的单元（C3D8T/C3D8RT/CPE4T/DC2D4…）必须有热导率",
        "fix": "在 *Material 里补 `*Conductivity` + 一行数值（mm-t-s 制钢约 0.05）",
    },
    {
        "match": "may not be used with elements that possess temperature",
        "cause": "带温度自由度的单元不能用 *Temperature 指定温度",
        "fix": "改成 `*Boundary`：`<nset>, 11, 11, <温度>`（DOF 11 就是温度）",
    },
    {
        "match": "temperature boundary condition via dof 11 is specified",
        "cause": "上一步的温度边界跨步继承了，而本步是 *Static（不允许 DOF 11 边界）",
        "fix": "本步 *Boundary 之前加 `*Boundary, op=NEW` 清掉继承边界，再重新给位移约束；温度作场自动继承",
    },
    {
        "match": "only degrees of freedom 11 and above can be active",
        "cause": "耦合单元（CPE4T/C3D8T）不能进纯 *Heat Transfer 步",
        "fix": "两种解法：(a) 第一步改 `*Coupled Temperature-Displacement, steady state`；(b) 传热用纯热单元 DC2D4/DC3D8、应力另用 CPE4/C3D8",
    },
    {
        "match": "the eigenvalues cannot be found",
        "cause": "*Buckle 没有 base state（无预载），或面内刚体位移未约束导致刚度奇异",
        "fix": "① *Buckle 前加 `*Step, name=Preload` + `*Static` + 同款载荷；② 约束面内位移（如 `X0, 1, 1`、`Y0, 2, 2`）",
    },
    {
        "match": "increase the number of iterations to get the requested number of eigenvalues",
        "cause": "*Buckle 迭代上限不够（细网格常见）",
        "fix": "*Buckle 数据行补迭代上限：`<阶数>, , 40`",
    },
    {
        "match": "step definition cards between *end step",
        "cause": "出现重复的 *End Step（inpkit.field_output() 已自带一个）",
        "fix": "删掉多余的 `*End Step`；一个 step 只能有一个",
    },
    {
        "match": "is misplaced",
        "cause": "关键字层级放错（例如 *Coupling / *Surface 必须在 *Step 之前、assembly 级）",
        "fix": "把该关键字及其数据行整体移到第一个 *Step 之前（assembly 级）；*Kinematic 紧跟其所属的 *Coupling",
    },
    {
        "match": "must be greater than zero",
        "cause": "截面/单元参数给了 0 或负值（I 型截面腹板厚 t3 给 0 就会这样）",
        "fix": "按参数顺序补齐：I 型 `l, h, b1, b2, t1, t2, t3`，矩形 `b, h`；翼缘宽与腹板厚都必须 > 0",
    },
    {
        "match": "numerical singularity",
        "cause": "模型存在刚体位移（某个方向的自由度完全没约束）",
        "fix": "模型存在刚体位移：检查边界，至少约束住 6 个刚体自由度，或对该方向补一个弱约束",
    },
    {
        "match": "too many attempts made for this increment",
        "cause": "非线性步不收敛",
        "fix": "减小初始增量（如 0.01）、开 `*Static, stabilize` 或自动稳定化、检查接触/材料",
    },
    {
        "match": "element has zero",
        "cause": "单元刚度/质量为 0（截面或材料没生效）",
        "fix": "核对 *Solid Section / *Shell Section / *Beam Section 的 elset 与材料名是否与 *Material 一致",
    },
    {
        "match": "has not been defined",
        "cause": "引用了不存在的 set / 材料 / 截面",
        "fix": "核对名字拼写与大小写、*Nset/*Elset 是否在引用之前定义",
    },
    {
        "match": "unrecognizable assembly set/id",
        "cause": "把 set 名当成了关键字参数值（例如 `*Temperature, file=<job>` 的写法不被识别）",
        "fix": "顺序耦合不需要 `*Temperature, file=`，温度从上一 step 自动继承；删掉该行",
    },
]

_ERROR_RE = re.compile(r"\*\*\*ERROR", re.I)


def _blocks(path: Path, limit: int = 6) -> List[str]:
    """从 .dat/.msg 里抓 ***ERROR 及其后 2 行，合并成一条便于阅读的块。"""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: List[str] = []
    i = 0
    while i < len(lines) and len(out) < limit:
        if _ERROR_RE.search(lines[i]):
            chunk = [lines[i].strip()]
            j = i + 1
            while j < len(lines) and j <= i + 3 and not _ERROR_RE.search(lines[j]):
                t = lines[j].strip()
                if t:
                    chunk.append(t)
                j += 1
            out.append(" ".join(chunk))
            i = j
        else:
            i += 1
    return out


def match_rule(message: str) -> Dict[str, str] | None:
    low = message.lower()
    for rule in RULES:
        if rule["match"] in low:
            return rule
        for alt in rule.get("alt", ()):
            if alt in low:
                return rule
    return None


# ---------------------------------------------------------------- 自动修补
# 只处理"能确定怎么改"的语法错；结构性改动（加预载步、补约束、调收敛）一律交人工。

def _fix_nlgeom(lines: List[str], changes: List[str]) -> List[str]:
    """*Static, nlgeom=YES 紧跟 *Step → 合并到 *Step 上（中间只允许空行）。"""
    out: List[str] = []
    for cur in lines:
        low = cur.strip().lower()
        if low.startswith("*static") and "nlgeom" in low:
            j = len(out) - 1
            while j >= 0 and not out[j].strip():
                j -= 1
            if j >= 0 and out[j].strip().lower().startswith("*step"):
                out[j] = out[j].rstrip() + ", nlgeom=YES"
                cleaned = re.sub(r",?\s*nlgeom\s*=\s*[^\s,]+", "", cur, flags=re.I)
                out.append(cleaned)
                changes.append(f"`{cur.strip()}` → nlgeom 移到上一行 *Step，本行还原为 `{cleaned.strip()}`")
                continue
        out.append(cur)
    return out


def _fix_dynamic_implicit(lines: List[str], changes: List[str]) -> List[str]:
    out = []
    for cur in lines:
        if cur.strip().lower().startswith("*dynamic") and "implicit" in cur.lower():
            new = re.sub(r",\s*implicit(\s*=\s*[^\s,]+)?", "", cur, flags=re.I)
            out.append(new)
            changes.append(f"`{cur.strip()}` → `{new.strip()}`")
        else:
            out.append(cur)
    return out


def _fix_steady(lines: List[str], changes: List[str]) -> List[str]:
    out = []
    for cur in lines:
        if "steady-state" in cur.lower() or "steady_state" in cur.lower():
            new = re.sub(r"steady[-_]state", "steady state", cur, flags=re.I)
            out.append(new)
            changes.append(f"`{cur.strip()}` → `{new.strip()}`")
        else:
            out.append(cur)
    return out


def _fix_dup_endstep(lines: List[str], changes: List[str]) -> List[str]:
    """相邻（中间仅空行）的两个 *End Step，删掉后一个。"""
    out: List[str] = []
    for cur in lines:
        if cur.strip().lower() == "*end step":
            j = len(out) - 1
            while j >= 0 and not out[j].strip():
                j -= 1
            if j >= 0 and out[j].strip().lower() == "*end step":
                changes.append("删掉重复的 `*End Step`")
                continue
        out.append(cur)
    return out


def _fix_buckle_iter(lines: List[str], changes: List[str], floor: int = 40) -> List[str]:
    """*Buckle 数据行的迭代上限（第三字段）调到 floor。"""
    out = list(lines)
    for i, cur in enumerate(out):
        if cur.strip().lower().startswith("*buckle"):
            j = i + 1
            while j < len(out) and not out[j].strip():
                j += 1
            if j < len(out) and not out[j].lstrip().startswith("*"):
                parts = [p.strip() for p in out[j].split(",")]
                if len(parts) >= 3 and parts[2].isdigit() and int(parts[2]) < floor:
                    old = out[j]
                    parts[2] = str(floor)
                    out[j] = ", ".join(parts)
                    changes.append(f"*Buckle 数据行 `{old.strip()}` → `{out[j]}`")
                elif len(parts) < 3:
                    parts = (parts + ["", ""])[:2]
                    old = out[j]
                    out[j] = f"{parts[0] or '4'}, , {floor}"
                    changes.append(f"*Buckle 数据行 `{old.strip()}` → `{out[j]}`")
            break
    return out


def _fix_file_temperature(lines: List[str], changes: List[str]) -> List[str]:
    out = []
    for cur in lines:
        if cur.strip().lower().startswith("*temperature") and "file=" in cur.lower():
            changes.append(f"删掉 `{cur.strip()}`（顺序耦合的温度会自动继承，不需要 file=）")
            continue
        out.append(cur)
    return out


def _fix_conductivity(lines: List[str], changes: List[str], k: str = "0.05") -> List[str]:
    """材料段里没有 *Conductivity 就补一条（k 默认 0.05，mm-t-s 制钢的常用值）。"""
    if any(l.strip().lower().startswith("*conductivity") for l in lines):
        return lines
    out: List[str] = []
    for cur in lines:
        out.append(cur)
        if cur.strip().lower().startswith("*material"):
            out.append("*Conductivity")
            out.append(k)
            changes.append(f"在 `{cur.strip()}` 后补 `*Conductivity` + `{k}`（按 mm-t-s 制钢估算，换单位制要改）")
    return out


def _fix_temperature_to_boundary(lines: List[str], changes: List[str]) -> List[str]:
    """*Temperature, nset=X + 数据行 T → *Boundary + `X, 11, 11, T`（DOF 11 就是温度）。"""
    out: List[str] = []
    i = 0
    while i < len(lines):
        cur = lines[i]
        m = re.match(r"(?i)^\s*\*temperature\s*,?\s*nset\s*=\s*(\S+)", cur)
        if m:
            nset = m.group(1).rstrip(",")
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and not lines[j].lstrip().startswith("*"):
                temp = lines[j].split(",")[0].strip()
                out.append("*Boundary")
                out.append(f"{nset}, 11, 11, {temp}")
                changes.append(f"`{cur.strip()}` + `{lines[j].strip()}` → `*Boundary` + `{nset}, 11, 11, {temp}`")
                i = j + 1
                continue
        out.append(cur)
        i += 1
    return out


_SURF_RE = re.compile(r"\*surface.*?name=([A-Za-z0-9_.\-]+)", re.I)


def _fix_dload_surface(lines: List[str], changes: List[str]) -> List[str]:
    """`*Dload` 紧跟着的数据行如果填的是 *Surface 名 → 换成 `*Dsload`（面载荷）。"""
    surfaces = set()
    for ln in lines:
        m = _SURF_RE.search(ln)
        if m:
            surfaces.add(m.group(1).lower())
    result = list(lines)
    for i, ln in enumerate(lines):
        if not ln.strip().lower().startswith("*dload"):
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines) or lines[j].strip().startswith("*"):
            continue
        first = lines[j].strip().split(",")[0].strip().lower()
        if first in surfaces:
            result[i] = re.sub(r"\*dload", "*Dsload", ln, count=1, flags=re.I)
            changes.append(
                f"L{i + 1}: `*Dload` → `*Dsload`（数据行 `{lines[j].strip()}` 引用的是面 {first}，"
                "*Dload 只认 elset）"
            )
    return result


_FIXERS = {
    "element set": _fix_dload_surface,
    "unknown parameter: nlgeom": _fix_nlgeom,
    "unknown parameter: implicit": _fix_dynamic_implicit,
    "unknown parameter: steady-state": _fix_steady,
    "step definition cards between *end step": _fix_dup_endstep,
    "increase the number of iterations to get the requested number of eigenvalues": _fix_buckle_iter,
    "unrecognizable assembly set/id": _fix_file_temperature,
    "requires a thermal conductivity": _fix_conductivity,
    "may not be used with elements that possess temperature": _fix_temperature_to_boundary,
}

# 这些即使命中规则也不自动改：属结构性/物理性修改
_MANUAL_ONLY = {
    "the eigenvalues cannot be found",
    "temperature boundary condition via dof 11 is specified",
    "only degrees of freedom 11 and above can be active",
    "numerical singularity",
    "too many attempts made for this increment",
    "is misplaced",
    "must be greater than zero",
    "element has zero",
    "has not been defined",
    "missing property definitions",
    "is not continuous or is composed of two or more",
    ".stf",
}


def auto_patch(out_dir, job: str, k: str = "0.05") -> str:
    """按 .dat/.msg 的报错自动修 inp 里"能确定怎么改"的错，写回并备份 .inp.bak。

    返回：改了什么、哪些必须人工、备份在哪。不改的绝不动。
    """
    jdir = Path(out_dir)
    inp = jdir / f"{job}.inp"
    if not inp.exists():
        return f"[修正] 找不到 {inp}，先确认作业名。"

    hits: List[str] = []
    for name in (f"{job}.dat", f"{job}.msg"):
        for b in _blocks(jdir / name, 40):
            if b not in hits:
                hits.append(b)
    if not hits:
        return "[修正] 没有 ***ERROR，无需修改。"

    seen, ordered = set(), []
    for msg in hits:
        rule = match_rule(msg)
        if rule and rule["match"] not in seen:
            seen.add(rule["match"])
            ordered.append(rule)

    text = inp.read_text(encoding="utf-8")
    lines = text.splitlines()
    changes: List[str] = []
    for rule in ordered:
        key = rule["match"]
        fixer = _FIXERS.get(key)
        if key in _MANUAL_ONLY or fixer is None:
            continue
        lines = fixer(lines, changes, k) if fixer is _fix_conductivity else fixer(lines, changes)

    manual = [r for r in ordered if r["match"] in _MANUAL_ONLY or r["match"] not in _FIXERS]
    if not changes:
        out = [f"[修正] {job}.inp：没有可自动应用的改动。"]
        if manual:
            out.append("需人工处理：")
            out.extend(f"  - {r['cause']} → {r['fix']}" for r in manual)
        return "\n".join(out)

    backup = jdir / f"{job}.inp.bak"
    backup.write_text(text, encoding="utf-8")
    inp.write_text("\n".join(lines) + "\n", encoding="utf-8")

    out = [f"[修正] {job}.inp：自动改 {len(changes)} 处（备份 {backup.name}）"]
    out.extend(f"  {n}) {c}" for n, c in enumerate(changes, 1))
    if manual:
        out.append("仍需人工处理（自动改不安全）：")
        out.extend(f"  - {r['cause']} → {r['fix']}" for r in manual)
    out.append("改完请 run_check 再 submit_job。")
    return "\n".join(out)


def diagnose(out_dir, job: str, limit: int = 4) -> str:
    """读 .dat/.msg，返回"报错原文 + 原因 + 修法"的可读诊断。

    同一条错误 Abaqus 会换几种写法重复报（原文 / `UNKNOWN PARAMETER ...` / `LINE IMAGE:`），
    所以按"命中的规则"去重，一类错误只报一条，并给出总数。
    """
    d = Path(out_dir)
    hits: List[str] = []
    for name in (f"{job}.dat", f"{job}.msg"):
        for b in _blocks(d / name, limit * 4):
            if b not in hits:
                hits.append(b)
    if not hits:
        return "[诊断] 没有找到 ***ERROR 行。"

    known: List[tuple] = []   # [(msg, rule)]
    unknown: List[str] = []
    seen_rules = set()
    for msg in hits:
        rule = match_rule(msg)
        if rule is None:
            if not unknown:
                unknown.append(msg)
            continue
        key = rule["match"]
        if key in seen_rules:
            continue
        seen_rules.add(key)
        known.append((msg, rule))

    head = f"[诊断] {job}：共 {len(hits)} 条 ERROR"
    kinds = len(known) + (1 if unknown else 0)
    if kinds:
        head += f"，归并为 {kinds} 类"
    out = [head]
    for k, (msg, rule) in enumerate(known[:limit], 1):
        out.append(f"\n{k}) 报错：{msg[:200]}")
        out.append(f"   原因：{rule['cause']}")
        out.append(f"   修法：{rule['fix']}")
    if unknown:
        out.append(f"\n{len(known)+1}) 报错：{unknown[0][:200]}")
        out.append("   原因：未收录这类报错 → 读 .dat 上下文，或用 web_search 查 Abaqus 原文")
        out.append("   修法：确认后把这条补进 agent/inp_doctor.py 的 RULES，下次就能自动认")
    return "\n".join(out)
