# -*- coding: utf-8 -*-
"""把 three.js 的 ESM 源码打成「无 import / 无 export」的单文件，供离线内联。

背景：three r150 之后官方不再提供 UMD 版，只给 three.module.js（ESM）。
ESM 在 file:// 下会因 CORS 被拦，所以这里做一次确定性的文本转换：

1. three.module.js 末尾的 `export { A, B, ... };`
   -> `globalThis.THREE = { A, B, ... };`
2. OrbitControls.js 顶部的 `import { ... } from 'three';`
   -> `const { ... } = globalThis.THREE;`
   末尾的 `export { OrbitControls };`
   -> `globalThis.OrbitControls = OrbitControls;`
3. 两者包进一个 IIFE，产出 vendor/three_bundle.js

用法：python scripts/make_vendor_bundle.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"


def convert_three(src: str) -> str:
    m = re.search(r"export\s*\{([^}]*)\}\s*;\s*$", src, re.S)
    if not m:
        raise SystemExit("[FAIL] three.module.js 里找不到末尾 export 块")
    items = []
    for raw in m.group(1).split(","):
        item = raw.strip()
        if not item:
            continue
        if " as " in item:
            a, b = item.split(" as ")
            items.append(f"{b.strip()}: {a.strip()}")
        else:
            items.append(item)
    head = src[: m.start()]
    tail = "\nglobalThis.THREE = {\n" + ",\n".join(items) + "\n};\n"
    return head + tail


def convert_controls(src: str) -> str:
    m = re.search(r"^import\s*\{([^}]*)\}\s*from\s*['\"]three['\"]\s*;\s*$", src, re.M | re.S)
    if not m:
        raise SystemExit("[FAIL] OrbitControls.js 里找不到 three 的 import 块")
    names = ", ".join(x.strip() for x in m.group(1).split(",") if x.strip())
    if names.count(",") == 0 and names:
        # 单名前不需要逗号；多名缺逗号会变成 "A B" 这种非法解构（曾因此白屏）
        raise SystemExit("[FAIL] 解构变量缺少逗号")
    head = src[: m.start()] + "const { " + names + " } = globalThis.THREE;\n"
    body = head + src[m.end():]
    body, n = re.subn(
        r"export\s*\{\s*OrbitControls\s*\}\s*;\s*$",
        "globalThis.OrbitControls = OrbitControls;\n",
        body,
    )
    if n != 1:
        raise SystemExit("[FAIL] OrbitControls.js 的 export 语句替换失败")
    return body


def main() -> None:
    three_path = VENDOR / "three.module.js"
    ctrl_path = VENDOR / "OrbitControls.js"
    for p in (three_path, ctrl_path):
        if not p.exists():
            raise SystemExit(f"[FAIL] 缺少 {p}，先下载 three@0.160.0 的 build 与 examples/jsm/controls")
    three = convert_three(three_path.read_text(encoding="utf-8"))
    ctrl = convert_controls(ctrl_path.read_text(encoding="utf-8"))

    out = VENDOR / "three_bundle.js"
    out.write_text(
        "/* three.js r160 + OrbitControls —— 离线打包版（无 import/export，普通 script 可直接用） */\n"
        "/* 两段独立作用域：three 先挂 globalThis.THREE，controls 再从它解构，避免同名重复声明 */\n"
        "(function () {\n'use strict';\n"
        + three
        + "\n})();\n(function () {\n'use strict';\n"
        + ctrl
        + "\n})();\n",
        encoding="utf-8",
    )
    size = out.stat().st_size
    # 同时放到 agent/static/：Streamlit 的静态路由要求 static 与 app 文件同级
    static_dir = ROOT / "agent" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "three_bundle.js").write_bytes(out.read_bytes())
    text = out.read_text(encoding="utf-8")
    # 自检：转换后不应残留模块语法（按行首判断，避免注释里的英文单词误报）
    bad = []
    if re.search(r"(?m)^\s*import\s", text):
        bad.append("行首 import")
    if re.search(r"(?m)^\s*export\s", text):
        bad.append("行首 export")
    if "import.meta" in text:
        bad.append("import.meta")
    print(f"[OK] 生成 {out}（{size/1024:.0f} KB）")
    print("残留模块语法:", bad if bad else "无")
    print("THREE 全局导出:", bool(re.search(r"globalThis\.THREE = \{", text)))
    print("OrbitControls 全局导出:", "globalThis.OrbitControls" in text)
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
