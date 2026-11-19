# -*- coding: utf-8 -*-
"""把 .workbuddy/memory/*.md 里的历史结论批量灌入正式记忆库（facts 表）。

用法：
  python -m agent.seed_memory cantilever --preview   # 只看会提取哪些，不写入
  python -m agent.seed_memory cantilever             # 提取并写入（技能名可换成任意已注册技能）

设计取舍：
- facts 只存「简洁结论 / 规则 / 坑」，作为每次会话自动注入 system prompt 的热缓存；
- 长解释、完整推理仍躺在原始 md 里，由 search_knowledge 按需检索。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from . import config as _cfg_mod
from . import memory as _memory

_MARKERS = (
    "坑", "教训", "结论", "根因", "必须", "禁止", "不要", "可行域",
    "硬约束", "已查明", "已知", "注意", "默认", "判据", "阈值", "白名单",
    "关键", "遗留", "代价", "约定", "原则", "前提",
)

_MAX_LEN = 200  # 只保留简洁结论；长解释交给 search_knowledge


def _iter_items(text: str):
    """把 markdown 切成「列表项」级单元，自动合并缩进续行。"""
    items, cur = [], []
    for raw in text.splitlines():
        line = raw.rstrip()
        if re.match(r"^\s*[-*]\s", line):
            if cur:
                items.append(" ".join(cur))
            cur = [line.strip()]
        elif cur and line.strip() and not line.strip().startswith("#"):
            cur.append(line.strip())
        else:
            if cur:
                items.append(" ".join(cur))
                cur = []
    if cur:
        items.append(" ".join(cur))
    return items


def _clean(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^[-*>\s]+", "", s)
    s = re.sub(r"^\d+[\.\)、]\s*", "", s)
    s = re.sub(r"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫]\s*", "", s)
    s = s.replace("**", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _memory_dirs(root: Path) -> list[Path]:
    out = []
    for base in (root, root.parent):
        for p in base.glob(".workbuddy/memory"):
            if p.is_dir():
                out.append(p)
    return out


def extract(skill: str) -> list[str]:
    root = Path(_cfg_mod.load_config()["skills"][skill]["root"])
    facts, seen = [], set()
    for d in _memory_dirs(root):
        for md in sorted(d.glob("*.md")):
            text = md.read_text(encoding="utf-8", errors="replace")
            for item in _iter_items(text):
                fact = _clean(item)
                if not fact or len(fact) < 10 or len(fact) > _MAX_LEN:
                    continue
                if not any(m in fact for m in _MARKERS):
                    continue
                key = fact[:48]
                if key in seen:
                    continue
                seen.add(key)
                facts.append(fact)
    return facts


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    skill = "cantilever"
    preview = "--preview" in argv
    rest = [a for a in argv if a != "--preview"]
    if rest:
        skill = rest[0]
    facts = extract(skill)
    print(f"[seed] 从 .workbuddy/memory 提取到 {len(facts)} 条候选结论（技能 {skill}）：\n")
    for i, f in enumerate(facts, 1):
        print(f"{i:02d}. {f}")
    if not preview:
        for f in facts:
            _memory.remember_fact(skill, f)
        print(f"\n[seed] 已写入 {len(facts)} 条长期记忆。")
    else:
        print("\n[seed] 预览模式，未写入。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
