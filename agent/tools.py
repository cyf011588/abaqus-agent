# -*- coding: utf-8 -*-
"""工具层：把「参数化建模 + 闸门校验 + Abaqus 提交/轮询」封装成普通 Python 函数。

设计原则：
1. 这一层**不依赖 langgraph / langchain**，只依赖标准库，可单独运行与测试；
2. graph.py 会把这里的函数注册成 LLM 可调用的工具；
3. 每个工具返回**人类可读的字符串**，方便大模型直接消化与汇报。

命名约定：`cantilever`、`plate_hole` 这类「参数化建模能力」统一叫 skill（对应 skills.yaml）。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config as _cfg_mod
from . import abaqus_run as _run_mod
from . import inp_doctor as inp_doctor
from . import manifest as _manifest
from . import memory as _memory
from . import modeling_knowledge as _mk
from . import websearch as _web


# --------------------------------------------------------------------------- 基础
def _cfg() -> dict:
    return _cfg_mod.load_config()


def _skill(sname: str) -> dict:
    cfg = _cfg()
    sk = cfg.get("skills", {}).get(sname)
    if not sk:
        raise ValueError(f"未知技能 {sname!r}；可用技能：{list(cfg.get('skills', {}))}")
    return sk


def _root(sname: str) -> Path:
    p = Path(_skill(sname)["root"])
    if not p.is_absolute():
        p = _cfg_mod.ROOT / p  # 相对路径相对项目根解析（内置案例库）
    return p


def _decode(b: bytes) -> str:
    """把子进程输出按 utf-8 → gbk 顺序解码，避免 Windows 中文乱码。"""
    if not b:
        return ""
    for enc in ("utf-8", "gbk"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


def _run(cmd: List[str], cwd: Path, timeout: int = 86400) -> tuple[int, str]:
    """运行子进程，返回 (returncode, 合并的 stdout+stderr)。不在此处判成败。"""
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        timeout=timeout,
    )
    out = _decode(proc.stdout).rstrip()
    if proc.stderr:
        out = (out + "\n" + _decode(proc.stderr).rstrip()).strip()
    return proc.returncode, out


def _flag(k: str) -> str:
    """把 Python 命名转成 CLI 命名：end_cols -> --end-cols。"""
    return "--" + k.replace("_", "-")


# --------------------------------------------------------------------------- 工具
def list_skills() -> str:
    """列出当前已接入的参数化建模技能（skill）。"""
    cfg = _cfg()
    lines = []
    for key, p in cfg.get("skills", {}).items():
        lines.append(f"- {key}: {p.get('name')}  （根目录 {p.get('root')}）")
    return "\n".join(lines) if lines else "(尚未配置任何技能)"


def add_skill(
    skill: str,
    name: str,
    root: str,
    build_script: str = "build_model.py",
    jobs_dir: str = "jobs",
    checks: str = "",
) -> str:
    """新增一个参数化建模技能（写入 skills.yaml）。checks 用逗号分隔闸门脚本名，可留空。"""
    cfg = _cfg()
    skills = cfg.get("skills", {})
    if skill in skills:
        return f"[FAIL] 技能 {skill!r} 已存在；如需改名请用 rename_skill"
    validators = [
        {"script": c.strip(), "desc": c.strip()}
        for c in checks.replace("，", ",").split(",")
        if c.strip()
    ]
    skills[skill] = {
        "name": name,
        "root": root,
        "build_script": build_script,
        "jobs_dir": jobs_dir,
        "validators": validators,
    }
    _cfg_mod.save_skills(skills)
    return f"[OK] 已新增技能 {skill}（{name}），根目录 {root}，闸门 {len(validators)} 个"


def remove_skill(skill: str) -> str:
    """删除一个已接入技能（仅从注册表移除，不动技能原始文件）。"""
    cfg = _cfg()
    skills = cfg.get("skills", {})
    if skill not in skills:
        return f"[FAIL] 技能 {skill!r} 不存在"
    skills.pop(skill)
    _cfg_mod.save_skills(skills)
    return f"[OK] 已移除技能 {skill}（原始目录未改动）"


def rename_skill(skill: str, new_name: str) -> str:
    """重命名一个已接入技能的显示名称。"""
    cfg = _cfg()
    skills = cfg.get("skills", {})
    if skill not in skills:
        return f"[FAIL] 技能 {skill!r} 不存在"
    old = skills[skill].get("name")
    skills[skill]["name"] = new_name
    _cfg_mod.save_skills(skills)
    return f"[OK] 技能 {skill} 名称已从 {old!r} 改为 {new_name!r}"


def list_checks(skill: str) -> str:
    """列出某个技能可用的自检/验收闸门脚本。"""
    p = _skill(skill)
    vals = p.get("validators", [])
    if not vals:
        return "(该技能未配置闸门)"
    return "\n".join(f"- {v['script']}: {v['desc']}" for v in vals)


def _precheck(skill: str, params: Dict[str, Any]) -> Optional[str]:
    """参数预检：manifest 声明了契约时，非法参数在 spawn 子进程前被拦截。"""
    issues = _manifest.validate_params(skill, params)
    if _manifest.blocked(issues):
        return "[FAIL] 参数预检未通过（已拦截，未生成）：\n" + _manifest.format_issues(issues)
    return None


def _generate(
    skill: str,
    params: Dict[str, Any],
    job: Optional[str] = None,
    out: Optional[str] = None,
) -> tuple[bool, Path, List[str], str]:
    """生成模型内核，返回 (是否成功, 输出目录, 新增文件绝对路径列表, 脚本输出)。"""
    p = _skill(skill)
    root = _root(skill)

    # 输出目录：一律写到 agent 自己的 data/output 下，避免污染只读原始项目
    base = (_cfg_mod.ROOT / "data" / "output").resolve()
    sub = (out or skill).strip().replace("\\", "/").strip("/")
    out_dir = (base / sub).resolve() if sub else base
    if out_dir != base and not str(out_dir).startswith(str(base) + os.sep):
        out_dir = base / skill
    out_dir.mkdir(parents=True, exist_ok=True)

    argv = [sys.executable, p["build_script"]]
    mode = _manifest.cli_mode(skill)
    if mode == "params_file":
        # 该技能的生成器按 params.csv/JSON 驱动：把参数写成 JSON 传 --params-file
        pp = dict(params)
        if job:
            pp["job_name"] = str(job)
        argv += ["--params-file", _manifest.build_params_file(pp)]
    else:
        for k, v in params.items():
            if v is None:
                continue
            if isinstance(v, bool):
                if v:
                    argv.append(_flag(k))
            else:
                argv.append(_flag(k))
                argv.append(str(v))
        if job:
            argv += ["--job", str(job)]
    argv += ["--out", str(out_dir)]

    before = {str(x) for x in out_dir.iterdir()} if out_dir.exists() else set()
    code, text = _run(argv, root)
    after = {str(x) for x in out_dir.iterdir()} if out_dir.exists() else set()
    produced = sorted(after - before)
    return (code == 0), out_dir, produced, text


def generate_model(
    skill: str,
    params: Dict[str, Any],
    job: Optional[str] = None,
    out: Optional[str] = None,
) -> str:
    """运行 build_model.py 生成主模型 + BUCK 模型（单个参数组合）。

    params 为「参数名 -> 值」字典，如 {"sp": 10, "cc": 80, "end_cols": 2}；
    布尔值 True 会转成开关（如 {"fin_classic": True} -> --fin-classic）。
    输出固定落在本 agent 的 data/output/ 目录下（绝不写进只读的原始项目），
    返回的产出文件路径是绝对路径，可直接交给 run_check / read_text。
    批量参数扫描请用 batch_run。
    """
    pre = _precheck(skill, params)
    if pre:
        return pre
    ok, out_dir, produced, text = _generate(skill, params, job=job, out=out)
    if not ok:
        return f"[FAIL] 生成失败（exit 非 0）：\n{text}"

    # 自动记入记忆：这个算例的参数与结果，供后续「查历史算例」复用。
    try:
        _memory.remember_case(skill, job or "(自动命名)", json_params(params), "generated", text[-2000:])
    except Exception:
        pass

    prod = "\n".join(f"- {x}" for x in produced) if produced else "(未检测到新增文件)"
    inps = [Path(x) for x in produced if str(x).lower().endswith(".inp")]
    run_line = ""
    if inps:
        script = _attach_run_script(inps[0])
        if script:
            cfg = _cfg().get("abaqus", {}) or {}
            run_line = (
                f"\n运行脚本：{script}\n"
                f"（默认 CPU {cfg.get('cpus', 4)} 核 / GPU {cfg.get('gpus', 0)}；"
                f"改核数：.\\{Path(script).name} -Cpus 16；开 GPU：-Gpus 1，仅 Explicit 有效）\n"
                f"要不要现在提交运行？确认后我用 submit_job 按你给的 CPU/GPU 跑。\n"
            )
    return (
        f"[OK] 生成成功，输出目录：{out_dir}\n"
        f"本次产出文件：\n{prod}\n"
        f"{run_line}\n"
        f"脚本输出：\n{text}"
    )


def batch_run(
    skill: str,
    base_params: Dict[str, Any],
    sweep_param: str,
    sweep_values: List[Any],
    check: str = "",
    check_extra_args: Optional[List[str]] = None,
) -> str:
    """批量参数扫描：对 sweep_param 的每个取值，用 base_params + 该取值生成模型，
    可选地对每个模型跑一道闸门，返回汇总表。

    适合「L=80/100/120 逐个生成并校验」这类需求——一次工具调用内部循环完成，
    避免 agent 用几十次工具调用机械循环而超递归上限。

    示例（cantilever，梁长 80~120 扫描 + 结构校验）：
      batch_run(skill="cantilever",
                base_params={"W": 10, "H": 10, "nx": 40},
                sweep_param="L",
                sweep_values=[80, 100, 120],
                check="../check_inp.py",
                check_extra_args=[])
    check_extra_args 是闸门的「口径参数」；扫描参数的值会自动以 --<param> <值> 追加给闸门。
    """
    pre = _precheck(skill, base_params)
    if pre:
        return pre
    out_dir = None
    rows = []
    for v in sweep_values:
        params = dict(base_params)
        params[sweep_param] = v
        vpre = _precheck(skill, params)
        if vpre:
            rows.append((f"{sweep_param}={v}", "预检FAIL", "-", "", vpre.strip().splitlines()[-1]))
            continue
        ok, od, produced, text = _generate(skill, params)
        out_dir = out_dir or od
        if not ok:
            rows.append((f"{sweep_param}={v}", "生成FAIL", "-", "", text.strip()[-160:]))
            continue
        main = next((x for x in produced if x.endswith(".inp") and "BUCK" not in x), None)
        verdict, main_inp, note = "已生成", (main or ""), ""
        if check and main:
            args = list(check_extra_args or [])
            args += [_flag(sweep_param), str(v)]
            cres = run_check(skill, check, main, extra_args=args)
            verdict = "PASS" if cres.startswith("[PASS]") else "FAIL"
            note = cres.strip().splitlines()[-1] if cres.strip() else ""
        rows.append((f"{sweep_param}={v}", "OK", verdict, main_inp, note))

    lines = [f"[OK] 批量扫描完成（{sweep_param} ∈ {sweep_values}），共 {len(rows)} 组"]
    if out_dir:
        lines.append(f"输出目录：{out_dir}")
    lines.append("")
    lines.append("| 参数 | 生成 | 校验 | 主 inp | 备注 |")
    lines.append("|---|---|---|---|---|")
    for label, gen, ver, main, note in rows:
        lines.append(f"| {label} | {gen} | {ver} | {main} | {note} |")
    return "\n".join(lines)


def _name_matches(script: str, check_name: str) -> bool:
    s = os.path.basename((script or "").removesuffix(".py"))
    c = os.path.basename((check_name or "").removesuffix(".py"))
    return s == c


def _attach_run_script(inp_path: Path) -> str:
    """给已生成的 inp 落一个 run_<JOB>.ps1（用户可改 -Cpus/-Gpus 直接运行）。"""
    try:
        cfg = _cfg().get("abaqus", {}) or {}
        jn = Path(inp_path).stem
        return str(_run_mod.write_run_script(
            Path(inp_path).parent,
            jn,
            cpus=int(cfg.get("cpus", 4)),
            gpus=int(cfg.get("gpus", 0)),
            abq=cfg.get("command", "abq2020"),
        ))
    except Exception:
        return ""


def _inp_path(job: str, out: str = "custom") -> Path:
    """解析 data/output/<out>/<job>.inp 的安全路径（防路径穿越，只取文件名）。"""
    base = (_cfg_mod.ROOT / "data" / "output").resolve()
    sub = (out or "custom").strip().replace("\\", "/").strip("/")
    out_dir = (base / sub).resolve() if sub else base
    if out_dir != base and not str(out_dir).startswith(str(base) + os.sep):
        out_dir = base / "custom"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = os.path.basename(str(job).strip() or "custom")
    if not name.lower().endswith(".inp"):
        name += ".inp"
    return out_dir / name


def write_inp(content: str, job: str, out: str = "custom") -> str:
    """把 LLM 构造的 inp 文本整体写到 data/output/<out>/<job>.inp（内容短时用）。

    无现成案例时，LLM 依据建模知识/联网检索结果写 inp 落盘，再 run_check 校验、viewer 预览。
    内容较长时建议用 mesh_inp（落盘网格骨架）+ append_inp（分段补短内容），避免长输出截断。
    """
    path = _inp_path(job, out)
    path.write_text(content, encoding="utf-8")
    script = _attach_run_script(path)
    suffix = f" 运行脚本：{script}" if script else ""
    return (f"[OK] 已写入 {path}（{len(content)} 字符）{suffix}。"
            f"下一步用 run_check 校验；确认无误后要不要提交运行？")


def mesh_inp(kind: str, params: str = "{}", job: str = "custom", out: str = "custom") -> str:
    """从零建模：按网格类型生成 inp 骨架并直接落盘（节点/单元/集合由 inpkit 确定性生成）。

    无现成案例时，LLM 用本工具落盘网格骨架（避免手写几百个节点坐标、避免长输出截断），
    再用 append_inp 分段补 *Material/*Section/*Step/*Boundary/*Cload，最后 run_check 校验。
    """
    import json

    from . import inpkit

    kind = (kind or "").strip().lower()
    try:
        p = json.loads(params) if isinstance(params, str) else dict(params or {})
    except Exception:
        return '[FAIL] params 需为 JSON 对象（如 {"L":1000,"W":500,"nx":20,"ny":10}）。'

    try:
        if kind in ("hex", "block"):
            n, e, s = inpkit.hex_mesh(
                p["L"], p["W"], p["H"], int(p["nx"]), int(p["ny"]), int(p["nz"]),
                tuple(p.get("origin", [0.0, 0.0, 0.0])))
            etype = "C3D8R"
        elif kind in ("rect_shell", "shell", "plate"):
            n, e, s = inpkit.shell_rect_mesh(
                p["L"], p["W"], int(p["nx"]), int(p["ny"]),
                tuple(p.get("origin", [0.0, 0.0, 0.0])))
            etype = "S4R"
        elif kind == "beam":
            n, e, s = inpkit.beam_mesh(
                p["L"], int(p["nx"]), tuple(p.get("origin", [0.0, 0.0, 0.0])))
            etype = "B31"
        elif kind == "frame":
            n, e, s = inpkit.frame_mesh(int(p["n_story"]), int(p["n_bay"]), p["h"], p["L"])
            etype = "B31"
        elif kind in ("annulus", "annulus_quarter"):
            n, e, s = inpkit.annulus_quarter_mesh(p["a"], p["b"], int(p["nr"]), int(p["nt"]))
            etype = "CPE4"
        elif kind == "truss":
            n, e, s = inpkit.truss_mesh(p["L"], p["H"])
            etype = "T3D2"
        elif kind in ("plate_hole", "hole"):
            n, e, s = inpkit.plate_hole_mesh(p["W"], p["H"], p["r"], int(p["nr"]), int(p["nt"]))
            etype = "S4R"
        elif kind == "l_bracket":
            n, e, s = inpkit.l_bracket_mesh(
                p["H"], p["L"], p["t"], int(p["nx1"]), int(p["my"]), int(p["nx2"]))
            etype = "S4R"
        else:
            return "[FAIL] 不支持的网格类型。可选：hex/rect_shell/beam/frame/annulus/truss/plate_hole/l_bracket。"
    except KeyError as exc:
        return f"[FAIL] 缺少参数 {exc}。"
    except Exception as exc:  # noqa: BLE001
        return f"[FAIL] 网格生成失败：{exc}。"

    skeleton = ["*Heading", f"** 网格骨架（{kind} / {etype}），节点/单元/集合已生成，请在下方补材料/截面/分析步/边界/载荷"]
    skeleton.append(inpkit.fmt_nodes(n))
    skeleton.append(inpkit.fmt_elements(etype, e))
    skeleton.append(inpkit.fmt_elset("ALL", [eid for eid, _ in e]))
    for name, ids in s.items():
        skeleton.append(inpkit.fmt_nset(name, ids))
    skeleton.append("** ---------- 请补 *Material / *Section ----------")
    skeleton.append("** ---------- 请补 *Step / *Boundary / *Cload / *Output ----------")

    path = _inp_path(job, out)
    path.write_text("\n".join(skeleton), encoding="utf-8")
    return (f"[OK] 已写网格骨架：{len(n)} 节点、{len(e)} 单元（{etype}）。文件 {path}。"
            f"下一步用 append_inp 补 *Material/*Section/*Step/*Boundary/*Cload，再 run_check 校验。")


def append_inp(content: str, job: str, out: str = "custom") -> str:
    """把短内容追加到已有 inp 文件末尾（从零建模的分步补全工具）。

    配合 mesh_inp 使用：mesh_inp 先落盘网格骨架，本工具分段追加材料/截面/分析步/边界/载荷，
    每段内容短，避免 LLM 一次输出长 inp 被截断。
    """
    path = _inp_path(job, out)
    if not path.exists():
        return f"[FAIL] 文件不存在：{path}。先用 mesh_inp 生成网格骨架。"
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + content)
    script = _attach_run_script(path)
    suffix = f" 运行脚本：{script}" if script else ""
    return (f"[OK] 已追加 {len(content)} 字符到 {path}。{suffix}"
            f"可继续 append_inp 补全，或 run_check 校验后提交运行。")


def run_check(
    skill: str,
    check_name: str,
    inp_path: str,
    extra_args: Optional[List[str]] = None,
) -> str:
    """对某个 .inp 跑一道闸门（如 validate_model.py / check_geom.py / inp_datcheck.py）。

    inp_path 用绝对路径或相对技能根目录的路径；extra_args 为额外的命令行参数列表。
    闸门契约优先读 skills.yaml 注册表，manifest 里声明的闸门作补充来源。
    """
    p = _skill(skill)
    root = _root(skill)
    val = next(
        (v for v in p.get("validators", []) if _name_matches(v["script"], check_name)),
        None,
    )
    if val is None:
        mvals = _manifest.load_manifest(skill).get("validators", [])
        val = next(
            (v for v in mvals if _name_matches(v.get("script", ""), check_name)),
            None,
        )
    if val is None:
        return f"[FAIL] 技能 {skill} 没有闸门 {check_name}；可用：\n{list_checks(skill)}"

    argv = [sys.executable, val["script"], inp_path] + (extra_args or [])
    code, text = _run(argv, root, timeout=7200)
    status = "PASS" if code == 0 else "FAIL"
    return f"[{status}] {check_name}：\n{text}"


def submit_job(
    job_dir: str,
    job: str,
    buck: bool = False,
    cpus: Optional[int] = None,
    gpus: Optional[int] = None,
    double: bool = False,
    wait: bool = True,
) -> str:
    """用 Abaqus 提交作业。cpus / gpus 可自由填写，wait=False 时后台跑。

    参数：
      cpus —— CPU 核数；留空取 config.yaml 的 abaqus.cpus。
      gpus —— GPU 数；留空取 abaqus.gpus（默认 0）。注意只有 Abaqus/Explicit 支持 GPU 加速，
               Standard（静力/模态/屈曲/Riks）填了可能被忽略或报错，一般保持 0。
      double —— 是否双精度（double=both），显式动力/接触问题建议开。
      wait —— True 阻塞等结果（适合小模型）；False 立即返回 PID，适合长作业。
      buck —— True 时提交 <job>-BUCK（屈曲模型，必须先于主模型跑出 .fil）。

    运行前会检查 .inp 是否存在。建议先用 run_check 过结构闸门再提交。
    后台模式用 job_status 查进度，或直接跑输出目录里的 run_<JOB>.ps1 -Status。
    """
    cfg = _cfg()
    abq_cfg = cfg.get("abaqus", {}) or {}
    abq = abq_cfg.get("command", "abq2020")
    cpus = int(cpus or abq_cfg.get("cpus", 4))
    gpus = int(gpus if gpus is not None else abq_cfg.get("gpus", 0))
    jdir = Path(job_dir)
    if not jdir.exists():
        return f"[FAIL] 目录不存在：{job_dir}"
    job_name = job + ("-BUCK" if buck else "")
    inp = jdir / f"{job_name}.inp"
    if not inp.exists():
        return (f"[FAIL] 找不到 {inp}。先 generate_model 生成，或检查 job 名；"
                f"屈曲请先 buck=True 提交。")

    argv = _run_mod.resolve_argv(_run_mod.build_argv(abq, job_name, cpus=cpus, gpus=gpus, double=double))
    desc = _run_mod.describe(job_name, cpus, gpus, double)
    if not wait:
        log = jdir / f"{job_name}.run.log"
        try:
            pid = _run_mod.launch_background(argv, jdir, log)
        except OSError as e:
            return _run_fail(abq, job_name, e)
        return (
            f"[OK] 已后台提交：{desc}\n"
            f"命令：{' '.join(argv)}\n"
            f"PID={pid}，日志：{log}\n"
            f"用 job_status('{job_dir}', '{job}') 轮询，或运行 run_{job_name}.ps1 -Status"
        )

    try:
        code, text = _run(argv, jdir, timeout=86400)
    except FileNotFoundError as e:
        return _run_fail(abq, job_name, e)
    except subprocess.TimeoutExpired:
        return (f"[FAIL] 超过 24h 未结束，已放弃等待：{job_name}。"
                f"长作业请改用 submit_job(..., wait=False) 后台提交，再用 job_status 轮询。")
    state = _run_mod.sta_state(jdir, job_name)
    if code != 0:
        return f"[FAIL] Abaqus 运行失败（exit={code}，状态 {state}）：\n{desc}\n{text}"
    return f"[OK] {job_name} 运行结束（状态 {state}）：{desc}\n{text}"


def _run_fail(abq: str, job_name: str, err: Exception) -> str:
    """命令找不到时的诊断与替代方案（不是静默失败）。"""
    found = _run_mod.abq_path(abq)
    tip = (f"找到命令但执行失败：{found}" if found
           else f"PATH 里找不到 {abq}")
    return (
        f"[FAIL] 无法启动 Abaqus：{tip}（{err}）。\n"
        f"  1) 确认已装 Abaqus，把 config.yaml 的 abaqus.command 改成绝对路径，"
        f"如 D:\\SIMULIA\\Commands\\abq2020.bat；\n"
        f"  2) 或在装 Abaqus 的机器上运行 data/output 里的 run_{job_name}.ps1；\n"
        f"  3) 模型本身已生成并通过校验，不依赖求解即可交付。"
    )


def repair_inp(job_dir: str, job: str, k: str = "0.05") -> str:
    """按 .dat/.msg 的报错自动修 inp 里"能确定怎么改"的语法错（会备份 .inp.bak）。

    适用：nlgeom 放错层、*Dynamic, Implicit、steady-state、重复 *End Step、
    *Buckle 迭代上限、*Temperature, file=、缺 *Conductivity、*Temperature 改 *Boundary DOF 11。
    不适用（只给建议不动手）：缺预载步、约束不足、不收敛、截面参数错误等结构性/物理性问题。
    """
    return inp_doctor.auto_patch(job_dir, job, k=k)


def job_status(job_dir: str, job: str, buck: bool = False) -> str:
    """读取已有作业的 .sta/.dat/.msg，判断完成状态与 ERROR/WARNING 数量。

    判据沿用技能约定：.sta 出现 COMPLETED/END OF JOB 视为跑完；
    .dat 出现 END OF USER INPUT PROCESSING 且 ***ERROR==0 视为输入处理通过。
    """
    jdir = Path(job_dir)
    name = job + ("-BUCK" if buck else "")
    sta, dat, msg = jdir / f"{name}.sta", jdir / f"{name}.dat", jdir / f"{name}.msg"
    if not any(p.exists() for p in (sta, dat, msg)):
        return f"[INFO] {name} 在 {job_dir} 下没有 .sta/.dat/.msg，可能尚未运行。"

    lines = []
    if sta.exists():
        text = sta.read_text(encoding="utf-8", errors="replace")
        if "THE ANALYSIS HAS COMPLETED SUCCESSFULLY" in text:
            lines.append("STATUS: COMPLETED")
        elif "END OF JOB" in text:
            lines.append("STATUS: END OF JOB")
        else:
            lines.append("STATUS: RUNNING / INCOMPLETE")
    if dat.exists():
        text = dat.read_text(encoding="utf-8", errors="replace")
        errs = text.count("***ERROR")
        warns = text.count("***WARNING")
        lines.append(f"ERROR 条数: {errs}")
        lines.append(f"WARNING 条数: {warns}")
        if "END OF USER INPUT PROCESSING" in text and not errs:
            lines.append("INPUT: 输入处理通过（END OF USER INPUT PROCESSING）")
        elif errs:
            lines.append(f"INPUT: 输入处理失败（{errs} 条 ERROR，见下方诊断）")
        else:
            lines.append("INPUT: 未走到 END OF USER INPUT PROCESSING")
        if errs:
            # 有 ERROR 就顺手给"原因 + 修法"，让 agent 能直接改 inp 再跑
            lines.append("")
            lines.append(inp_doctor.diagnose(jdir, name))
    return "\n".join(lines) if lines else f"[INFO] {name} 无可读状态。"


def modeling_guide(topic: str = "") -> str:
    """返回 Abaqus 通用建模知识（单元选择/材料/截面/分析步/边界/载荷/网格/流程）。

    无现成案例时用它兜底：据结构特征选单元、写关键字、从零构造 inp。
    """
    return _mk.guide_section(topic)


def plan_model(requirement: str) -> str:
    """把用户建模需求转成可执行计划：匹配案例 + 必问参数 + 无匹配时的 fallback。

    这是「对话式建模」的入口工具：先理解需求、匹配案例、列出必须澄清的参数；
    检索不到相似案例时，给出「选单元 → 查知识 → 改造/从零构造 → 查文献」的兜底路径。
    """
    matches = _mk.match_case(requirement)
    units = _mk.suggest_units(requirement)
    lines = []
    if matches:
        lines.append("已匹配到以下案例（按相关度排序）：")
        for skill, score in matches[:3]:
            try:
                name = _skill(skill).get("name", skill)
            except ValueError:
                name = skill
            lines.append(f"- {skill}: {name}")
            qs = _mk.CASE_QUESTIONS.get(skill)
            if qs:
                lines.append(f"  必问参数：{'、'.join(qs)}")
        lines.append("下一步：先向用户澄清缺失的必问参数，再 generate_model 生成、run_check 校验。")
    else:
        lines.append("未匹配到高度相似的内置案例，按 fallback 兜底：")
        if units:
            lines.append("建议单元：" + "；".join(f"{u}（{n}）" for u, n in units))
        else:
            lines.append("先调用 modeling_guide('单元') 按结构特征选单元类型。")
        lines.append("再调用 modeling_guide 查材料/分析步/边界/载荷，据从零建模流程构造 inp，")
        lines.append("或改造最相近案例；仍不确定时，明确告知用户缺什么资料、建议查什么文献，禁止编造参数。")
    return "\n".join(lines)


def web_search(query: str, max_hits: int = 5) -> str:
    """联网搜索（DuckDuckGo Lite，尽力而为）。

    本地案例/知识覆盖不到时，用它在网上检索 Abaqus 文档/文献/教程；
    失败会明确返回失败原因，由上层 fallback 兜底。
    """
    return _web.search(query, max_hits)


def web_fetch(url: str, max_chars: int = 4000) -> str:
    """抓取网页正文（去标签提取文本）。

    用于抓 Abaqus 官方文档/维基/教程等已知权威 URL；纯 JS 渲染页可能抓不到正文。
    """
    return _web.fetch(url, max_chars)


def search_knowledge(skill: str, query: str, max_hits: int = 6) -> str:
    """在技能的方法论/踩坑清单/验证记录等 markdown 文档里检索相关内容。

    这是「让 AI 理解模型」的关键：先用它查清参数含义、可行域、已知坑，
    再去 generate_model，避免闭着眼睛改参数。
    """
    root = _root(skill)
    dirs = [root, root.parent]
    terms = [t for t in query.lower().split() if t]
    hits: List[tuple[int, str, int, str]] = []  # (score, relpath, lineno, text)
    seen = set()
    for d in dirs:
        if not d.exists():
            continue
        for md in d.glob("**/*.md"):
            try:
                text = md.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            lines = text.splitlines()
            for i, ln in enumerate(lines):
                low = ln.lower()
                score = sum(1 for t in terms if t in low)
                if score:
                    rel = md.relative_to(root.parent) if md.is_relative_to(root.parent) else str(md)
                    key = (rel, i, ln)
                    if key in seen:
                        continue
                    seen.add(key)
                    hits.append((score, str(rel), i + 1, ln.strip()))
    hits.sort(key=lambda r: (-r[0], r[1], r[2]))
    if not hits:
        return f"[INFO] 未在 {skill} 的知识文档里找到与 {query!r} 相关的内容。"
    out = []
    for score, rel, lineno, txt in hits[:max_hits]:
        out.append(f"{rel}:{lineno}  {txt}")
    return "\n".join(out)


def read_text(path: str, max_lines: int = 200) -> str:
    """读取文本文件（如 .inp / .dat / .sta / .md），返回前 max_lines 行。"""
    p = Path(path)
    if not p.exists():
        return f"[FAIL] 文件不存在：{path}"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"[FAIL] 读取失败：{e}"
    lines = text.splitlines()
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + f"\n...（共 {len(lines)} 行，已截断）"
    return text


def remember(skill: str, fact: str) -> str:
    """把一条领域事实/经验教训写入长期记忆，供后续任务检索。"""
    _memory.remember_fact(skill, fact)
    return f"[OK] 已记住（技能 {skill}）：{fact}"


# --------------------------------------------------------------------------- 辅助
def json_params(params: Dict[str, Any]) -> str:
    import json
    return json.dumps(params, ensure_ascii=False, sort_keys=True)
