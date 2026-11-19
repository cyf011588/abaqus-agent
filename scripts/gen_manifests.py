# -*- coding: utf-8 -*-
"""从 library/<案例>/build_inp.py 的 argparse 定义自动补 manifests/<案例>.yaml。

只补"没有任何 manifest"的案例，已有的一律不改。
不猜 min/max（不设限就不拦），只填 type / default / choices / desc，保证参数预检与
必问清单一类信息不缺。跑完请人工看一眼 desc 是否通顺。

用法：python scripts/gen_manifests.py [--dry]
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "library"
MANS = ROOT / "manifests"

CLI_TYPE = {"float": "float", "int": "int", "str": "str"}

# build_inp.py 里没写 help 时，按常见参数名补一句通顺描述（只补认识的，不臆造）
GENERIC_DESC = {
    "L": "长度（x 向）", "W": "宽度（y 向）", "H": "高度（z 向）",
    "E": "弹性模量", "nu": "泊松比", "rho": "密度",
    "P": "载荷", "F": "集中力", "q": "均布压力", "u": "施加位移",
    "T": "温度", "k": "热导率", "alpha": "线膨胀系数",
    "nx": "x 向网格数", "ny": "y 向网格数", "nz": "z 向网格数",
    "n": "数量/阶数", "r": "半径/孔径", "t": "厚度", "theta": "角度",
    "a": "几何参数 a", "b": "几何参数 b", "h": "截面高 / 板厚",
    "nmodes": "提取模态/特征值阶数", "v": "速度", "f0": "起始频率", "f1": "终止频率",
    "job": "作业名",
}


def _find_argparse_calls(tree: ast.AST):
    """返回该文件里所有 add_argument(...) 调用的 AST 节点。"""
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "add_argument":
                calls.append(node)
    return calls


def _kw(call: ast.Call, name: str):
    for k in call.keywords:
        if k.arg == name:
            return k.value
    return None


def _literal(node, default=None):
    try:
        return ast.literal_eval(node)
    except Exception:
        return default


def parse_flags(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    params = {}
    for call in _find_argparse_calls(tree):
        if not call.args:
            continue
        flag = _literal(call.args[0])
        if not isinstance(flag, str) or not flag.startswith("--"):
            continue
        name = flag.lstrip("-")
        t_node = _kw(call, "type")
        type_name = getattr(t_node, "id", None) if t_node is not None else None
        typ = CLI_TYPE.get(type_name or "", "str")
        default = _literal(_kw(call, "default"))
        choices = _literal(_kw(call, "choices"))
        help_txt = _literal(_kw(call, "help"), "")
        item = {"type": typ}
        if default is not None:
            item["default"] = default
        if choices:
            item["choices"] = list(choices)
        if help_txt:
            item["desc"] = str(help_txt).strip()
        elif name in GENERIC_DESC:
            item["desc"] = GENERIC_DESC[name]
        params[name] = item
    return params


def to_yaml(skill: str, title: str, params: dict) -> str:
    lines = [f'name: "{title}"', 'build_script: "build_inp.py"', 'jobs_dir: "."', "", "cli:", "  mode: flags", "", "params:"]
    for name, item in params.items():
        lines.append(f"  {name}:")
        lines.append(f"    type: {item['type']}")
        if "choices" in item:
            lines.append("    choices: [" + ", ".join(f'"{c}"' for c in item["choices"]) + "]")
        if "default" in item:
            d = item["default"]
            lines.append(f"    default: {d if isinstance(d, (int, float)) else repr(d)}")
        if "desc" in item:
            lines.append(f'    desc: "{item["desc"]}"')
    lines += [
        "",
        "validators:",
        '  - script: "../check_inp.py"',
        "    key: structure",
        '    desc: "inp 结构完整性（关键字 + 节点引用）"',
        '    cli: "check_inp.py <inp>"',
        "",
        "sop: |",
        f"  {title}；参数含义见上面逐项 desc，未设 min/max 的表示不限制。",
        "  生成后先 run_check(structure)，再用 3D 预览确认几何与边界位置。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="只打印将生成的内容，不落盘")
    args = ap.parse_args()

    import yaml

    skills = yaml.safe_load((ROOT / "skills.yaml").read_text(encoding="utf-8"))["skills"]
    made, skipped = [], []
    for name, cfg in skills.items():
        script = LIB / name / cfg.get("build_script", "build_inp.py")
        target = MANS / f"{name}.yaml"
        if target.exists():
            skipped.append(name)
            continue
        if not script.exists():
            skipped.append(name + "（无脚本）")
            continue
        params = parse_flags(script)
        if not params:
            skipped.append(name + "（argparse 里没找到 --参数）")
            continue
        text = to_yaml(name, cfg.get("name", name), params)
        if args.dry:
            print(f"--- {name}.yaml ---")
            print(text)
        else:
            target.write_text(text, encoding="utf-8")
        made.append((name, len(params)))

    print(f"生成 {len(made)} 个: {made}")
    print(f"跳过 {len(skipped)} 个: {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
