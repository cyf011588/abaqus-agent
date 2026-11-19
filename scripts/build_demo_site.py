# -*- coding: utf-8 -*-
"""为 data/output 下的模型批量生成离线可开的 3D 预览，并生成 index.html 列表页。

用法：
    python scripts/build_demo_site.py                 # 生成预览 + data/output/index.html
    python scripts/build_demo_site.py --site docs/demo  # 另存一份到发布目录（含预览副本）

生成的 preview.html 是自包含单文件（three.js 内联），file:// 双击即可看，无需服务器。
"""
import argparse
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import inp_viewer, viewer_html  # noqa: E402


def pick_inp(folder: Path) -> Path | None:
    """每目录选一个代表性 inp：优先非 -BUCK、体量最大的那个。"""
    inps = [p for p in folder.glob("*.inp") if not p.stem.upper().endswith("-BUCK")]
    if not inps:
        inps = list(folder.glob("*.inp"))
    if not inps:
        return None
    return max(inps, key=lambda p: p.stat().st_size)


def build_index(rows: list[dict], out_dir: Path, title: str) -> Path:
    cards = []
    for r in rows:
        cards.append(
            f"""  <a class="card" href="{r['dir']}/preview.html">
    <div class="name">{html.escape(r['dir'])}</div>
    <div class="meta">{html.escape(r['inp'])}</div>
    <div class="nums">{r['nodes']} 节点 · {r['elems']} 单元</div>
    <div class="go">打开 3D 预览 →</div>
  </a>"""
        )
    body = "\n".join(cards) if cards else '<p class="empty">data/output 下还没有可预览的模型。</p>'
    page = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
  :root {{ --ink:#1f2a3a; --muted:#5a6b7d; --line:#d7dee7; --bg:#f4f6f9; --accent:#3b6a9e; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:28px 20px 48px; background:var(--bg); color:var(--ink);
         font-family:"Microsoft YaHei","PingFang SC",sans-serif; }}
  .wrap {{ max-width:1080px; margin:0 auto; }}
  h1 {{ font-size:20px; margin:0 0 6px; }}
  .sub {{ color:var(--muted); font-size:13px; margin-bottom:22px; line-height:1.7; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:14px; }}
  .card {{ display:block; background:#fff; border:1px solid var(--line); border-radius:12px;
           padding:14px 16px; text-decoration:none; color:inherit;
           transition:box-shadow .15s,border-color .15s,transform .15s; }}
  .card:hover {{ border-color:#9dbada; box-shadow:0 6px 18px rgba(59,106,158,.14); transform:translateY(-1px); }}
  .name {{ font-size:15px; font-weight:600; margin-bottom:6px; }}
  .meta {{ font-size:12px; color:var(--muted); word-break:break-all; margin-bottom:4px; }}
  .nums {{ font-size:12px; color:#7a8798; margin-bottom:10px; }}
  .go {{ font-size:12px; color:var(--accent); }}
  .empty {{ color:var(--muted); }}
</style>
</head>
<body>
<div class="wrap">
  <h1>{html.escape(title)}</h1>
  <div class="sub">每个卡片是一个自包含的 HTML（three.js 已内联），点开即可旋转/缩放，不联网也能看。<br>
  列表由 <code>scripts/build_demo_site.py</code> 生成。</div>
  <div class="grid">
{body}
  </div>
</div>
</body>
</html>
"""
    p = out_dir / "index.html"
    p.write_text(page, encoding="utf-8")
    return p


def main() -> None:
    ap = argparse.ArgumentParser(description="批量生成离线 3D 预览 + index.html")
    ap.add_argument("--root", default=str(ROOT / "data" / "output"), help="模型目录")
    ap.add_argument("--exclude", default="", help="导出静态站时排除的目录（逗号分隔，如 demo_out）")
    ap.add_argument("--site", default="", help="另存一份静态站到这里（如 demo_site）")
    ap.add_argument("--title", default="Abaqus 模型 3D 预览")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        raise SystemExit(f"[FAIL] 目录不存在：{root}")

    rows = []
    fails = []
    for folder in sorted([p for p in root.iterdir() if p.is_dir()]):
        inp = pick_inp(folder)
        if inp is None:
            continue
        try:
            data = inp_viewer.parse_inp_file(str(inp))
        except Exception as e:  # noqa: BLE001
            fails.append(f"{folder.name}: {e}")
            continue
        (folder / "preview.html").write_text(
            viewer_html.render_html(data, title=f"{folder.name} · {inp.stem}"), encoding="utf-8"
        )
        rows.append({
            "dir": folder.name,
            "inp": inp.name,
            "nodes": len(data.get("nodes", [])) // 3,
            "elems": data.get("summary", {}).get("shell_tris", 0)
            + data.get("summary", {}).get("solid_tris", 0)
            + data.get("summary", {}).get("line_segs", 0),
        })

    idx = build_index(rows, root, args.title)
    print(f"[OK] 预览 {len(rows)} 个，索引 {idx}")

    if args.site:
        site = Path(args.site)
        ex = [x.strip() for x in args.exclude.split(",") if x.strip()]
        site_rows = [r for r in rows if r["dir"] not in ex]
        site.mkdir(parents=True, exist_ok=True)
        for r in site_rows:
            src = root / r["dir"] / "preview.html"
            dst = site / r["dir"]
            dst.mkdir(parents=True, exist_ok=True)
            (dst / "preview.html").write_bytes(src.read_bytes())
        build_index(site_rows, site, args.title)
        total = sum(p.stat().st_size for p in site.rglob("*.html")) / 1024 / 1024
        print(f"[OK] 静态站已导出到 {site}（{len(site_rows)} 个案例，{total:.1f} MB，可直接挂 GitHub Pages）")
        if ex:
            print(f"     已排除：{', '.join(ex)}")

    for f in fails:
        print("[SKIP]", f)


if __name__ == "__main__":
    main()
