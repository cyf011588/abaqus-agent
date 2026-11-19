# 项目结构总览（2026-11-15 整理版）

一句话：**这里是一个「对话 → 有限元模型 → 真机求解 → 出结果」的 Abaqus 智能体**，
代码用标准库写，案例用 Python 直写 inp，求解靠本机 Abaqus 2020。

---

## 1. 目录职责

| 目录/文件 | 装什么 | 发布时 |
|---|---|---|
| `agent/` | 智能体本体：编排（`graph.py`）、工具层（`tools.py`）、求解封装（`abaqus_run.py`）、inp 生成（`inpkit.py`）、预览（`inp_viewer.py`/`viewer_html.py`）、Web（`webapp.py`/`web.py`/**`web_panels.py`**）、知识（`modeling_knowledge.py`）、自诊断（`inp_doctor.py`）、记忆（`memory.py`） | ✅ 提交 |
| `library/<案例>/` | 每个案例的 `build_inp.py`（生成 inp）+ 说明文档；23 个目录 | ✅ 提交 |
| `scripts/` | 可复现的执行脚本：批量求解（`run_all_cases.py`）、批量修 inp（`fix_inp_errors.py`）、生成预览站（`build_demo_site.py`）、打包 three.js（`make_vendor_bundle.py`）、画架构图、批量投作业（`run_jobs_batch.ps1`）、**录屏用（`prepare_demo_job.py` 造一个真实失败作业 / `make_video_cover.py` 出封面）** | ✅ 提交 |
| `tests/` | pytest，79 个用例 | ✅ 提交 |
| `docs/` | 文档 + 截图证据（见 §4） | ✅ 提交 |
| `manifests/` | 各技能的参数契约（可行域、闸门、必问参数），agent 读它决定"要不要先问用户" | ✅ 提交 |
| `vendor/` | three.js r160 源码 + 打包产物（2.5 MB），离线预览的原料 | ✅ 提交 |
| `demo_site/` | 24 个案例的**独立 HTML 预览站**（31.7 MB），可直接挂 GitHub Pages | ✅ 提交（或另起分支） |
| `data/` | 运行产物：`output/<案例>/` 下 `.inp/.odb/.dat/.msg/.sta` 与日志；私有材料不进 git | ❌ 不提交 |
| `.venv/` | 本地虚拟环境 | ❌ 不提交 |
| `.env` | API key | ❌ 不提交 |
| `config.yaml` | 运行配置（LLM、Abaqus 命令、默认核数） | ✅ 提交（不含密钥） |
| `skills.yaml` | **公共**技能注册表（23 个自建案例，路径都是 `library/<案例>`） | ✅ 提交 |
| `skills.local.yaml` | **本机私有**技能（真实项目、绝对路径，不进 git），加载时覆盖/追加，模板见 `skills.local.example.yaml` | ❌ 不提交 |
| `skills.imported.yaml` | Web 界面「导入技能」写出的技能（上传 yaml 后合并到这里），会被加载但不受 NO_LOCAL 影响 | ❌ 不提交 |
| `LICENSE` | MIT | ✅ 提交 |
| `start.bat` / `run_web.bat` / `run_agent.bat` | 三个入口：一键启动 Web（8502）/ 只起 Web / 只起命令行 | ✅ 提交 |
| `run_a.ps1` | 单作业投递脚本（可改 `-Cpus`/`-Gpus`），由 agent 生成给用户自己跑 | ✅ 提交 |

---

## 2. 数据流

```
自然语言 → plan_model（匹配案例/列必问参数）
        → generate_model（跑 library/<案例>/build_inp.py，写 data/output/<案例>/）
        → run_check（结构校验：关键字齐全 / 节点被引用 / 几何一致）
        → [问用户] 要不要跑、几核、要不要 GPU
        → submit_job（abq2020 job=...，可后台）
        → job_status（.sta 判完成 + .dat 的 ***ERROR）
             └─ 有 ERROR → inp_doctor.diagnose（原因+修法）
                        → repair_inp（自动改确定性语法错）
                        → 重新 submit（同作业最多 3 轮）
        → 预览（inp_viewer 解析 → viewer_html 出 three.js 页面）
```

---

## 3. 启动与常用命令

| 目的 | 命令 |
|---|---|
| 一键起 Web（8502） | 双击 `start.bat` |
| 只起 Web | `run_web.bat` |
| 只起命令行智能体 | `run_agent.bat` |
| 跑测试 | `.\.venv\Scripts\python.exe -m pytest tests -q` |
| 生成某个案例 | `.\.venv\Scripts\python.exe -m agent` 后对话，或直接跑 `library/<案例>/build_inp.py` |
| **批量真机求解 23 个案例** | `.\.venv\Scripts\python.exe scripts\run_all_cases.py --jobs 4 --cpus 3 --abq "D:\SIMULIA\Commands\abq2020.bat"` |
| 补齐缺失的参数契约 | `.\.venv\Scripts\python.exe scripts\gen_manifests.py`（只补没有的，已有不动） |
| 批量投作业（PowerShell） | `.\scripts\run_jobs_batch.ps1 -Jobs "A","B" -Dir data\output\cantilever -Cpus 12 -MaxConcurrent 2` |
| 重建预览 + 列表页 | `.\.venv\Scripts\python.exe scripts\build_demo_site.py --site demo_site --exclude "demo_out"` |
| 本地看列表页 | 双击 `data/output/index.html`（离线，无 CDN） |

> Abaqus 命令：`abq2020` 通常不在 PATH，用绝对路径 `D:\SIMULIA\Commands\abq2020.bat`；
> 代码里已有兜底探测（只对 `abq*` 命令名生效）。

---

## 4. docs 里都是什么

| 文件 | 用途 |
|---|---|
| `architecture.md` / `architecture.png` | 系统架构（可编辑源 `architecture.html`，改文案后重新导出 PNG） |
| `general_modeling_skill.md` | 十步建模范式（无相似案例时的兜底方法论） |
| `run_job_guide.md` | 作业提交/批量/CPU-GPU 注意事项 |
| `solve_verification.md` | **23 个案例真机求解的验收报告**（含 5 类报错、物理量核对、未核对项、中文路径坑） |
| `run_all_report.md` | 批量求解的机器汇总表（每次跑自动覆盖） |
| `roadmap.md` | 长期路线 |
| 截图 `*.png` | 分三类：① 列表页 `index_page.png`；② 离线预览实测 `preview_offline*.png`、`preview_only_bc_offline.png`、`preview_float_static.png`；③ 早期中间版本 `preview_bc_load.png`、`preview_coord_fix.png`、`preview_only_bc.png`、`preview_plate_nl.png`、`preview_snap_through.png` 等（留作过程证据，README 只引用第 ②类） |

---

## 5. 发布边界（上传 GitHub 前必看）

**绝对不提交**：`data/`（运行产物，含私有模型）、`.env`、`.venv`、`docs/publishing.md`、
`skills.local.yaml`、任何 `.odb/.sim/.sta/.msg/.dat/.prt/.lck`。

**已处理**：
1. `skills.yaml` 只留 23 个自建案例（相对路径）；私有技能已拆到
   `skills.local.yaml`（不进 git），本机照常加载（24 条生效），别人 clone 下来是干净的 23 条；
2. `LICENSE` 已补（MIT，署名可按需改成自己名字）。

`.gitignore` 已覆盖：`data/`、`.env`、`__pycache__/`、`.pytest_cache/`、`*.bak`、
`skills.local.yaml`、求解产物。

---

## 6. 已知不一致（如实记录，未强行改）

| 现象 | 说明 |
|---|---|
| `library/` 23 个目录 = `skills.yaml` 23 条 | 已一致（2026-11-16 补注册 `plate_hole`，并全部纳入批量求解，23/23 跑通） |
| `data/output/demo_out`（31 MB） | 早期 22 案例演示的旧产物，与现在的 `demo_site` 重复；不参与发布（`data/` 整体忽略），可随时删 |
| `docs/` 里并存"最终版"与"中间版"截图 | 保留作为过程证据；README 只引用最终版 |
| `config.yaml` 的 `abaqus.command` 仍是 `"abq2020"` | 靠 `abaqus_run._find_abq()` 兜底；想彻底确定就写绝对路径 |
| `contact`/`buckle_column`/`modal_beam` 只核到量级 | 三个案例已真机跑通，但未与接触解析解、欧拉临界力、梁固有频率逐点对照 |

---

## 7. 本次整理做了什么

1. 清掉 174 个 `__pycache__` 与 `.pytest_cache`（项目体积 596 MB → 577 MB）；
2. 删掉测试残留 `data/output/pytest_mesh`、`pytest_tmp`；
3. **修 `scripts/run_jobs_batch.ps1` 真实缺陷**：原来把工作目录钉成 `$PSScriptRoot`，
   必须在 `scripts\` 下反向引用才能跑；改为默认当前目录，并新增 `-Dir`、`-Abq`；
4. 修 `docs/run_job_guide.md` 的批量示例（不再用 `.\scripts\..\..\scripts\` 绕路径），
   补 `-Abq` 绝对路径写法；
5. `.gitignore` 补 `__pycache__/`、`.pytest_cache/`、`*.bak`、`.ruff_cache/`、`skills.local.yaml`；
6. 新增本文件，作为目录/命令/发布边界的唯一索引；
7. **发布准备**：私有技能移到 `skills.local.yaml`
   （`agent/config.py` 的 `_load_skills()` 会合并本地层），公共 `skills.yaml` 只留 23 个自建；
   补 MIT `LICENSE`；`plate_hole` 补注册并纳入批量求解；
8. **修 3D 浮窗交互 bug**：`viewer_html.py` 的 `begin()` 会把 iframe 设成
   `pointerEvents='none'`（拖动时防误触），但 `end()` 只在拖动分支恢复，缩放结束后
   永久失联——表现就是"把框拖大之后画面点不动了"。改为在 `end()` 里统一恢复，
   并让缩放过程中实时 dispatch `resize` 让画布跟着重排。
   实测（同域 iframe + 真实 PointerEvent）：缩放中 `pointerEvents=none`，松手后恢复为空，
   尺寸 420×320 → 642×472。
9. **体检补齐（2026-11-16 下午）**：
   - 修 `scripts/make_arch_diagram.py` 的括号语法错（该脚本此前从未成功运行）；
   - 新增 `scripts/gen_manifests.py`，从 `build_inp.py` 的 argparse 自动补 9 份缺失契约
     （`manifests/` 现 25 份、265 参数）；
   - 10 个早期案例纳入批量清单，修掉 4 类 inp 缺陷（`*Dload`→`*Dsload`、缺 `*Solid Section`、
     接触面混入内部面），并把"中文用户名导致 Abaqus 临时文件建不出"这个坑修进运行器：
     **最终 23/23 COMPLETED，93 s**。