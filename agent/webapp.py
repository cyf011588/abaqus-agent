# -*- coding: utf-8 -*-
"""Streamlit 聊天界面：豆包工作式会话组织（工作空间 → 项目 → 对话）+ 能力（skill）展示。

启动方式（二选一）：
  python -m agent.web
  streamlit run agent/webapp.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# 保证无论从哪个目录启动，都能 import 到项目根下的 agent 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from agent import config as _cfg_mod
from agent import sessions as _sessions
from agent import web_panels as _panels


def _record_run(task, ok, elapsed, error="", usage=None, tool_names=None):
    """落盘一次运行日志；失败静默，不影响界面。"""
    from agent import runlog
    try:
        runlog.save_run(task, ok, elapsed, error, tool_calls=tool_names, token_usage=usage)
    except Exception:
        pass


def _private_skill_names() -> set:
    """本地私有 / 界面导入的私有技能名：它们的产品不放进下拉列表（只用于自动预览）。"""
    names: set = set()
    try:
        import yaml

        for fname in ("skills.local.yaml", "skills.imported.yaml"):
            p = Path(__file__).resolve().parent.parent / fname
            if p.exists():
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                names |= set((data.get("skills", data) or {}).keys())
    except Exception:  # noqa: BLE001
        pass
    return names


def _list_inp_files():
    """扫描 data/output 下的主 inp（排除 *-BUCK.inp 与私有技能的产物）。"""
    out_dir = Path(__file__).resolve().parent.parent / "data" / "output"
    private = _private_skill_names()
    files = []
    if out_dir.exists():
        for p in sorted(out_dir.rglob("*.inp")):
            if "BUCK" in p.name:
                continue
            if p.parent.name in private:
                continue
            files.append(str(p))
    return files


def _inp_short(p: str) -> str:
    """下拉框只显示 data/output 下的相对路径（避免完整路径被截断看不清）。"""
    base = Path(__file__).resolve().parent.parent / "data" / "output"
    try:
        return Path(p).relative_to(base).as_posix()
    except ValueError:
        return Path(p).name


def _newest_inp() -> str | None:
    """data/output 下最新修改的主 inp（生成后自动预览用）。"""
    base = Path(__file__).resolve().parent.parent / "data" / "output"
    if not base.exists():
        return None
    files = [p for p in base.rglob("*.inp") if "BUCK" not in p.name]
    return str(max(files, key=lambda p: p.stat().st_mtime)) if files else None


def _resolve_inp_path(inp_path: str) -> Path | None:
    """把历史记录里的 inp 路径映射到当前项目目录。

    项目文件夹被整体改名/搬迁（如 F:\\old → F:\\new）后，旧会话里存的绝对路径会失效，
    这里按 `/data/output/...` 之后的相对部分在当前 ROOT 下复原，避免历史消息一点就报错。
    """
    p = Path(inp_path)
    if p.exists():
        return p
    norm = str(inp_path).replace("\\", "/")
    marker = "/data/output/"
    idx = norm.lower().find(marker)
    if idx >= 0:
        cand = _cfg_mod.ROOT / norm[idx + 1:]
        if cand.exists():
            return cand
    return None


def _render_float_3d(inp_path: str, height: int = 780) -> None:
    """渲染可拖拽/可缩放的 3D 浮窗：iframe 自身 fixed 到右下角，不占对话空间。

    注意 height 必须够大：靠 iframe 撑出画布尺寸，给 0 会让 canvas 塌成 0 高、只剩图例。
    """
    from agent import inp_viewer, viewer_html
    p = _resolve_inp_path(inp_path)
    if p is None:
        st.caption(f"找不到模型文件：{inp_path}（所属项目目录已改名/迁移，历史预览不可用）")
        return
    data = inp_viewer.parse_inp_file(str(p))
    st.caption(f"3D 浮窗：{p.stem}（右下角 · 拖标题栏移动 · 手柄缩放 · ✕ 关闭）")
    st.components.v1.html(
        viewer_html.render_float_html(data, title=p.stem),
        height=height, scrolling=False,
    )


st.set_page_config(page_title="Abaqus Agent", page_icon="🧪", layout="wide")

cfg = _cfg_mod.load_config()

# 首次运行：确保有默认工作空间 / 项目 / 对话
if not _sessions.list_workspaces():
    _sessions.ensure_default()

# --------------------------------------------------------------------------- 侧边栏
with st.sidebar:
    st.title("Abaqus Agent")
    st.caption("自然语言驱动 Abaqus 建模 / 校验 / 提交")
    st.divider()

    # ---- 工作空间 ----
    ws_list = _sessions.list_workspaces()
    if st.session_state.get("ws") not in ws_list:
        st.session_state["ws"] = ws_list[0]
    ws = st.selectbox("工作空间", ws_list, index=ws_list.index(st.session_state["ws"]))
    st.session_state["ws"] = ws

    # ---- 项目 ----
    proj_list = _sessions.list_projects(ws)
    if not proj_list:
        _sessions.add_project(ws, "默认项目")
        proj_list = _sessions.list_projects(ws)
    if st.session_state.get("proj") not in proj_list:
        st.session_state["proj"] = proj_list[0]
    proj = st.radio("项目", proj_list, index=proj_list.index(st.session_state["proj"]))
    st.session_state["proj"] = proj

    # ---- 新建对话 ----
    if st.button("➕ 新建对话", use_container_width=True):
        cid = _sessions.add_conversation(ws, proj)
        st.session_state["conv"] = cid
        st.rerun()

    # ---- 对话列表 ----
    conv_list = _sessions.list_conversations(ws, proj)
    if not conv_list:
        cid = _sessions.add_conversation(ws, proj)
        conv_list = [cid]
    if st.session_state.get("conv") not in conv_list:
        st.session_state["conv"] = conv_list[0]

    def conv_label(cid: str) -> str:
        return _sessions.get_conversation(ws, proj, cid).get("name", "新对话")

    conv = st.radio(
        "对话",
        conv_list,
        index=conv_list.index(st.session_state["conv"]),
        format_func=conv_label,
    )
    st.session_state["conv"] = conv

    if st.button("删除当前对话", use_container_width=True):
        _sessions.remove_conversation(ws, proj, conv)
        st.session_state.pop("conv", None)
        st.rerun()

    st.divider()

    # ---- 管理：项目 / 工作空间 ----
    with st.expander("管理（项目 / 工作空间）", expanded=False):
        with st.form("new_proj_form"):
            new_proj = st.text_input("新建项目名", key="new_proj_input")
            if st.form_submit_button("创建项目", use_container_width=True):
                if new_proj.strip():
                    _sessions.add_project(ws, new_proj.strip())
                    st.session_state["proj"] = new_proj.strip()
                    st.session_state.pop("conv", None)
                    st.rerun()
        if st.button("删除当前项目", use_container_width=True):
            _sessions.remove_project(ws, proj)
            st.session_state.pop("proj", None)
            st.session_state.pop("conv", None)
            st.rerun()
        with st.form("new_ws_form"):
            new_ws = st.text_input("新建工作空间名", key="new_ws_input")
            if st.form_submit_button("创建工作空间", use_container_width=True):
                if new_ws.strip():
                    _sessions.add_workspace(new_ws.strip())
                    st.session_state["ws"] = new_ws.strip()
                    st.rerun()

    st.divider()

    # ---- 能力 / Skills ----
    _panels.render_skill_import()

    with st.expander("能力 / Skills", expanded=False):
        st.caption("agent 可调用的参数化建模能力（skills.yaml）")
        _cfg_now = _cfg_mod.load_config()
        for key, p in _cfg_now.get("skills", {}).items():
            st.markdown(f"- **{key}**：{p.get('name')}")

    st.divider()

    # ---- 3D 模型预览 ----
    with st.expander("3D 模型预览", expanded=False):
        inp_files = _list_inp_files()
        if not inp_files:
            st.caption("暂无生成的 inp（先跑一次生成）。")
        else:
            sel = st.selectbox("选择 inp", inp_files, key="preview_inp", format_func=_inp_short)
            st.caption(f"路径：{_panels.mask_paths(sel)}")
            if st.button("生成 3D 预览（页面内浮层）", use_container_width=True, key="preview_btn"):
                st.session_state["show3d"] = sel
            if st.session_state.get("show3d"):
                if st.button("关闭 3D 浮层", use_container_width=True, key="close3d"):
                    st.session_state.pop("show3d", None)
                    st.rerun()

# --------------------------------------------------------------------- 案例库
_panels.render_case_board()

# --------------------------------------------------------------------------- 消息
messages = _sessions.get_messages(ws, proj, conv)


def render_message(m):
    """渲染一条消息；assistant 消息会带上完整思考/工具调用轨迹。"""
    if m["role"] == "user":
        st.chat_message("user").markdown(m["content"])
        return
    with st.chat_message("assistant"):
        for step in m.get("trace", []):
            if step["type"] == "think":
                st.markdown(f"💭 {step['text']}")
            elif step["type"] == "tool":
                with st.expander(f"🔧 调用工具 `{step['name']}`", expanded=False):
                    st.caption("参数")
                    st.json(step.get("args", {}))
            elif step["type"] == "tool_result":
                with st.expander(f"↩ `{step['name']}` 返回", expanded=False):
                    st.text(_panels.mask_paths(step.get("result", ""))[:2500])
        if m.get("content"):
            st.markdown("---")
            st.markdown("### 结论")
            st.markdown(m["content"])


for m in messages:
    render_message(m)

if not messages:
    st.info(
        "在下方输入自然语言需求，例如：\n\n"
        "`建一个 1 米长、截面 50×100 的悬臂梁，自由端受 1000 N，生成模型并提交求解`\n\n"
        "侧边栏「导入技能」可以挂载自己的参数化建模 skill；「案例库」里能看到内置案例的真实求解状态。"
    )

# 3D 浮层（主区域，可拖拽；侧边栏点"生成 3D 预览"后出现）
if st.session_state.get("show3d"):
    st.divider()
    try:
        _render_float_3d(st.session_state["show3d"])
    except Exception as e:  # noqa: BLE001
        st.error(f"预览失败：{e}")

# --------------------------------------------------------------------------- 输入
prompt = st.chat_input("描述你的建模 / 校验 / 提交需求…")
if prompt:
    messages.append({"role": "user", "content": prompt})
    _sessions.save_messages(ws, proj, conv, messages)

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            from agent.graph import build_agent
            agent = build_agent()
        except Exception as e:  # noqa: BLE001
            st.error(f"启动失败（请确认已 `pip install -r requirements.txt` 且 `.env` 配好 key）：{e}")
            st.stop()

        final = ""
        trace = []
        usage: dict = {}
        t0 = time.time()
        try:
            # 把整段会话历史（含本轮）喂给 LLM，保持跨轮记忆
            history = [(m["role"], m["content"]) for m in messages]
            stream = agent.stream({"messages": history}, stream_mode="updates")
            for chunk in stream:
                for node, upd in chunk.items():
                    for m in upd.get("messages", []):
                        if node == "chatbot":
                            content = (getattr(m, "content", "") or "").strip()
                            tool_calls = getattr(m, "tool_calls", []) or []
                            # 累积 token 用量（DeepSeek 在响应里返回 usage）
                            u = getattr(m, "response_metadata", {}).get("token_usage") or getattr(m, "usage_metadata", None)
                            if isinstance(u, dict):
                                for k, v in u.items():
                                    if isinstance(v, int):
                                        usage[k] = usage.get(k, 0) + v
                            if tool_calls:
                                if content:
                                    st.markdown(f"💭 {content}")
                                    trace.append({"type": "think", "text": content})
                                for tc in tool_calls:
                                    with st.expander(f"🔧 调用工具 `{tc['name']}`", expanded=False):
                                        st.caption("参数")
                                        st.json(tc.get("args", {}))
                                    trace.append({"type": "tool", "name": tc["name"], "args": tc.get("args", {})})
                            else:
                                final = content
                        elif node == "tools":
                            nm = getattr(m, "name", "工具")
                            res = getattr(m, "content", "") or ""
                            with st.expander(f"↩ `{nm}` 返回", expanded=False):
                                st.text(_panels.mask_paths(res)[:2500])
                            trace.append({"type": "tool_result", "name": nm, "result": res})
            _record_run(prompt, True, time.time() - t0, usage=usage,
                        tool_names=[s["name"] for s in trace if s["type"] == "tool"])
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            # 递归上限＝任务太长没收敛，不是程序错误，不要甩一屏英文给用户
            if "recursion_limit" in msg.lower() or "Recursion limit" in msg:
                st.warning(
                    "这一轮工具调用过多，已自动停下（不是程序错误）。"
                    "可以把任务拆小一点：先只建模、再单独说校验，或者直接说「继续」接着做。"
                )
            else:
                st.error(f"执行出错：{msg}")
            _record_run(prompt, False, time.time() - t0, error=msg)
            st.stop()

        if final:
            st.markdown("---")
            st.markdown("### 结论")
            st.markdown(final)
        else:
            st.warning("未获得最终回答。")

        messages.append({"role": "assistant", "content": final, "trace": trace})
        _sessions.save_messages(ws, proj, conv, messages)

        # 若本轮生成了模型，自动在 3D 浮层里预览（无需手动点）
        gen_tools = [s["name"] for s in trace if s.get("type") == "tool"]
        if any(n in ("generate_model", "write_inp", "batch_run") for n in gen_tools):
            newest = _newest_inp()
            if newest:
                st.divider()
                try:
                    _render_float_3d(newest)
                except Exception as e:  # noqa: BLE001
                    st.caption(f"3D 预览生成失败：{e}")
