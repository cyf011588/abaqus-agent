# -*- coding: utf-8 -*-
"""轻量 inp 结构校验（纯标准库），供内置案例库共用。

检查：
1. 关键关键字齐全（*Node / *Element / *Step / *End Step，排除 *Node Output / *Element Output）；
2. 单元引用的节点 id 均已定义（无悬空引用）。

用法：python check_inp.py <inp>    退出码 0 = 通过。
"""
import re
import sys


def _kw_present(text: str, kw: str) -> bool:
    # 精确匹配 *Node / *Element / *Step / *End Step（排除 Output 类）
    return bool(re.search(rf"^{re.escape(kw)}\s*(,|$)", text, re.M))


def main() -> None:
    if len(sys.argv) < 2:
        print("用法：check_inp.py <inp>")
        sys.exit(2)
    try:
        text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
    except OSError as e:
        print(f"[FAIL] 读取失败：{e}")
        sys.exit(1)

    errors = []
    for kw in ("*Node", "*Element", "*Step", "*End Step"):
        if not _kw_present(text, kw):
            errors.append(f"缺少 {kw}")

    # 节点 id（只在 *Node 数据段）
    node_ids = set()
    in_node = False
    for line in text.splitlines():
        s = line.strip()
        if re.match(r"\*Node\s*(,|$)", s, re.I):
            in_node = True
            continue
        if s.startswith("*"):
            in_node = False
            continue
        if in_node:
            m = re.match(r"(\d+)\s*,", s)
            if m:
                node_ids.add(int(m.group(1)))

    # 单元引用节点（只在 *Element 数据段）
    elem_refs = set()
    in_elem = False
    for line in text.splitlines():
        s = line.strip()
        if re.match(r"\*Element\s*(,|$)", s, re.I):
            in_elem = True
            continue
        if s.startswith("*"):
            in_elem = False
            continue
        if in_elem:
            parts = [p.strip() for p in s.split(",") if p.strip()]
            for p in parts[1:]:
                if p.isdigit():
                    elem_refs.add(int(p))

    if node_ids and elem_refs:
        dangling = sorted(elem_refs - node_ids)
        if dangling:
            errors.append(f"单元引用未定义节点（前 10 个）：{dangling[:10]}")

    if errors:
        print("[FAIL] " + "；".join(errors))
        sys.exit(1)
    print(f"[PASS] 结构完整：{len(node_ids)} 节点、{len(elem_refs)} 个被引用节点，关键字齐全")
    sys.exit(0)


if __name__ == "__main__":
    main()
