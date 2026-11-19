# -*- coding: utf-8 -*-
"""Web 界面的两个业务面板（供 webapp.py 调用）：

1. 案例库：把 docs/run_all_report.md 的真实求解结果做成表格，可点开诊断、自动修；
2. 技能导入：上传技能定义 yaml → 合并进 skills.local.yaml → 立即生效（不动公共 skills.yaml）。

另外提供 mask_paths()，对外演示时把本机绝对路径折叠掉（环境变量 ABAQUS_AGENT_MASK=1 开启）。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "run_all_report.md"
IMPORTED_SKILLS = ROOT / "skills.imported.yaml"
DEMO_SITE = ROOT / "demo_site"

_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s,;:'\"\)\]】]+")


def mask_on() -> bool:
    return os.environ.get("ABAQUS_AGENT_MASK") == "1"


def mask_paths(text: str) -> str:
    """演示模式下折叠本机绝对路径（只留末级文件名），避免把个人目录拍进画面。"""
    if not mask_on() or not text:
        return text

    def _short(m: re.Match) -> str:
        raw = m.group(0)
        tail = Path(raw).name
        return f"…/{tail}" if tail else "…"

    return _PATH_RE.sub(_short, text)


# --------------------------------------------------------------------- 案例库

def _probe(d: Path, job: str) -> tuple[str, str, str]:
    """没有报告行时，直接看 .sta / .dat / .msg 判断一个作业的状态。

    注意：输入处理失败时 Abaqus 也会留一个空 .odb，所以必须先看报错，不能凭 .odb 判完成。
    """
    sta, dat, msg, odb = d / f"{job}.sta", d / f"{job}.dat", d / f"{job}.msg", d / f"{job}.odb"
    err = 0
    for p in (dat, msg):
        if p.exists():
            err += p.read_text(encoding="utf-8", errors="replace").count("***ERROR")
    if sta.exists():
        txt = sta.read_text(encoding="utf-8", errors="replace")
        if "COMPLETED SUCCESSFULLY" in txt or "END OF JOB" in txt:
            return "✅ 完成", "-", str(err)
        if err:
            return "❌ 失败", "-", str(err)
        return "🔄 运行中", "-", str(err)
    if err:
        return "❌ 失败", "-", str(err)
    if odb.exists():
        return "✅ 完成", "-", "0"
    return "❓ 未运行", "-", "0"


def case_rows() -> List[dict]:
    """先读 run_all_report.md，再扫描 data/output 下未入报告的作业（比如演示用的失败件）。"""
    rows: List[dict] = []
    if REPORT.exists():
        for line in REPORT.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) != 5 or cells[2] not in ("COMPLETED", "NOT_STARTED", "RUNNING"):
                continue
            case, job, status, sec, err = cells
            rows.append({
                "案例": case,
                "作业": job,
                "状态": "✅ 完成" if status == "COMPLETED" else ("⏳ 未完成" if status == "NOT_STARTED" else "🔄 运行中"),
                "耗时(s)": sec,
                "ERROR": err,
                "3D 预览": "有" if (DEMO_SITE / case / "preview.html").exists() else "—",
            })

    seen = {(r["案例"], r["作业"]) for r in rows}
    out_root = ROOT / "data" / "output"
    # 只补录屏/演示用的额外作业，避免把本地其它项目（含私有技能产物）混进对外界面
    if out_root.exists():
        extra = [d for pat in ("broken_demo", "demo_*")
                 for d in out_root.glob(pat) if d.is_dir() and d.name != "demo_out"]
        for d in sorted(extra):
            for inp in sorted(d.glob("*.inp")):
                if (d.name, inp.stem) in seen:
                    continue
                st_txt, sec, err = _probe(d, inp.stem)
                rows.append({
                    "案例": d.name,
                    "作业": inp.stem,
                    "状态": st_txt,
                    "耗时(s)": sec,
                    "ERROR": err,
                    "3D 预览": "有" if (DEMO_SITE / d.name / "preview.html").exists() else "—",
                })
    return rows


def _job_dir(case: str, job: str) -> Path:
    return ROOT / "data" / "output" / case


def render_case_board() -> None:
    """可展开的案例库：表格 + 单案例诊断/自动修。"""
    rows = case_rows()
    with st.expander("📦 案例库（内置案例的真实求解状态）", expanded=False):
        if not rows:
            st.caption("还没有求解报告：先跑一次 `scripts/run_all_cases.py`。")
            return
        ok = sum(1 for r in rows if r["状态"].startswith("✅"))
        st.caption(f"共 {len(rows)} 个案例，{ok} 个已完成；数字来自 Abaqus 真机求解，不是模拟。")

        opts = [f"{r['案例']} / {r['作业']}" for r in rows]
        idx = next((i for i, r in enumerate(rows) if r["状态"].startswith("❌")), 0)
        pick = st.selectbox(
            "对单个作业做诊断 / 修复",
            opts,
            index=idx,
            key="case_pick",
        )
        case, job = [x.strip() for x in pick.split("/")]
        jdir = _job_dir(case, job)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if st.button("查看诊断", key="diag_btn", use_container_width=True):
                st.session_state["case_action"] = "diag"
        with c2:
            if st.button("自动修复", key="fix_btn", use_container_width=True):
                st.session_state["case_action"] = "fix"
        with c3:
            if st.button("重跑", key="rerun_btn", use_container_width=True):
                st.session_state["case_action"] = "rerun"
        with c4:
            if st.button("看这个模型", key="view_btn", use_container_width=True):
                st.session_state["case_action"] = "view"

        act = st.session_state.pop("case_action", None)
        if act == "diag":
            from agent import inp_doctor

            st.text(mask_paths(inp_doctor.diagnose(jdir, job)))
        elif act == "fix":
            from agent import tools

            st.text(mask_paths(tools.repair_inp(str(jdir), job)))
        elif act == "view":
            inp = jdir / f"{job}.inp"
            if inp.exists():
                st.session_state["show3d"] = str(inp)
                st.info(f"已在下方弹出 3D 浮窗：{job}（可旋转 / 缩放 / 只看边界条件）")
            else:
                st.warning("这个作业没有对应的 inp 文件。")
        elif act == "rerun":
            from agent import abaqus_run as ar

            abq = ar.abq_path("abq2020") or "abq2020"
            argv = ar.resolve_argv(ar.build_argv(abq, job, 2, 0, False,
                                                extra=["interactive", "ask_delete=OFF"]))
            with st.spinner(f"正在跑 {job} …"):
                proc = subprocess.run(argv, cwd=str(jdir), capture_output=True, text=True,
                                      env=ar.abq_env(), timeout=600)
            tail = (proc.stdout or "").strip().splitlines()
            st.text(mask_paths("\n".join(tail[-6:]) if tail else "(无输出)"))

        # 给底部固定的输入框让出位置，避免按钮被它压住点不到
        st.markdown("<div style='height:80px'></div>", unsafe_allow_html=True)
        st.divider()
        try:
            import pandas as pd

            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True, height=360)
        except Exception:
            for r in rows:
                st.markdown(f"- **{r['案例']}** · {r['状态']} · {r['耗时(s)']} s · ERROR {r['ERROR']}")

        st.divider()
        if st.button("全部重跑（内置案例真机求解，约 2 分钟）", key="rerun_all_btn",
                     use_container_width=True):
            script = ROOT / "scripts" / "run_all_cases.py"
            if not script.exists():
                st.error("缺少 scripts/run_all_cases.py")
            else:
                with st.spinner("正在逐个提交 Abaqus 作业，请等表格刷新…"):
                    proc = subprocess.run([sys.executable, str(script), "--jobs", "4", "--cpus", "3"],
                                          cwd=str(ROOT), capture_output=True, text=True,
                                          env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                                          timeout=1800)
                tail = (proc.stdout or "").strip().splitlines()
                st.text(mask_paths("\n".join(tail[-5:]) if tail else "(无输出)"))
                if proc.returncode == 0:
                    st.success("全部案例已重跑完成，表格与报告已更新。")
                else:
                    st.warning("部分案例未完成，展开案例库查看状态。")


# ------------------------------------------------------------------- 技能导入

def _merge_into_imported(new_skills: dict) -> List[str]:
    """把上传的技能写进 skills.imported.yaml（不动 skills.local.yaml / skills.yaml）。"""
    import yaml

    existing: dict = {}
    if IMPORTED_SKILLS.exists():
        data = yaml.safe_load(IMPORTED_SKILLS.read_text(encoding="utf-8")) or {}
        existing = data.get("skills", data) or {}
    changed = []
    for key, val in new_skills.items():
        if not isinstance(val, dict) or "root" not in val:
            continue
        existing[key] = val
        changed.append(key)
    IMPORTED_SKILLS.write_text(
        yaml.safe_dump({"skills": existing}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return changed


def render_skill_import() -> None:
    """侧边栏：上传技能定义并启用（写 skills.imported.yaml，重新渲染即生效）。"""
    with st.expander("🧩 导入技能（本地私有）", expanded=False):
        st.caption("上传技能定义 yaml（含 root / build_script），导入后立刻出现在能力列表里。")
        up = st.file_uploader("选择 yaml", type=["yaml", "yml"], key="skill_up")
        if up:
            try:
                import yaml

                data = yaml.safe_load(up.getvalue().decode("utf-8")) or {}
            except Exception as e:  # noqa: BLE001
                st.error(f"解析失败：{e}")
                data = None
            skills = (data or {}).get("skills", data) if data is not None else None
            if skills is not None:
                if not isinstance(skills, dict) or not skills:
                    st.error("yaml 里没有找到技能定义（需要 `skills: {<名字>: {root: ...}}`）。")
                else:
                    names = [k for k, v in skills.items() if isinstance(v, dict) and "root" in v]
                    if not names:
                        st.error("技能条目缺少 `root` 字段。")
                    else:
                        st.success(f"识别到 {len(names)} 个技能：{', '.join(names)}")
                        for k in names:
                            st.caption(f"{k} → {mask_paths(str(skills[k].get('root', '')))}")
                        if st.button("确认导入并启用", key="skill_import_btn",
                                     use_container_width=True):
                            from agent import config as _cfg

                            changed = _merge_into_imported(skills)
                            now = _cfg.load_config().get("skills", {})
                            st.success(f"已启用：{', '.join(changed)}；当前共 {len(now)} 个技能"
                                       "（下方列表已更新）")

        if IMPORTED_SKILLS.exists():
            if st.button("清空已导入的技能", key="skill_clear_btn", use_container_width=True):
                from agent import config as _cfg

                IMPORTED_SKILLS.unlink()
                st.success(f"已清空；当前共 {len(_cfg.load_config().get('skills', {}))} 个技能")
