# -*- coding: utf-8 -*-
"""Abaqus 通用建模知识库（纯标准库，供 LLM 在「无现成案例」时兜底）。

目标：案例库覆盖有限，用户要建的结构往往没有现成案例。本模块把 Abaqus 建模的
「基本理解」沉淀为结构化知识，让 LLM 能：
  1. 根据结构特征选对单元类型；
  2. 据材料/分析类型写对关键字；
  3. 按通用流程从零构造 inp，或改造最相近案例。

知识来源：Abaqus 官方文档 + 通用有限元教科书共识，均为稳定、可复现的规则。
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# --------------------------------------------------------------------------- 单元选择
# 结构特征关键词 → (推荐单元, 说明)
UNIT_GUIDE: Dict[str, Tuple[str, str]] = {
    "实体": ("C3D8R / C3D8 / C3D20R", "三维实体；C3D8R 减缩积分需防沙漏，C3D8 全积分无沙漏但弯剪偏刚"),
    "薄壁": ("S4R / S4", "壳单元；S4R 通用减缩积分，注意厚度与法向"),
    "混凝土": ("C3D8R / C3D8", "混凝土梁/柱/墙多用实体单元（非杆系）"),
    "薄板": ("S4R / S4", "薄板/薄壁用壳单元"),
    "梁": ("B31 / B32", "梁单元；B31 Timoshenko 一次，B32 二次更柔顺"),
    "柱": ("B31 / B32", "柱一般用梁单元（细长）或实体（短粗）"),
    "框架": ("B31", "框架杆系用梁单元，节点共享即刚接"),
    "桁架": ("T3D2", "只受轴力的二力杆，铰接"),
    "拉压杆": ("T3D2", "轴向受力杆件"),
    "平面应变": ("CPE4 / CPE4R", "长筒/坝等轴向应变为零的截面"),
    "平面应力": ("CPS4 / CPS4R", "薄板面内受力，法向应力为零"),
    "轴对称": ("CAX4 / CAX4R", "回转体，x=r（径向）、y=z（轴向）"),
    "热": ("DC2D4 / DC3D8", "热传导单元，温度自由度 11"),
    "圆盘": ("CAX4", "圆盘/回转体用轴对称"),
    "圆筒": ("CPE4 / CAX4", "长圆筒中段平面应变，短圆筒轴对称"),
}

# --------------------------------------------------------------------------- 材料
MATERIAL_GUIDE: Dict[str, str] = {
    "线弹性": "*Elastic 后给 E, nu（单位体系自洽：mm-N-MPa 或 m-N-Pa）",
    "弹塑性": "*Elastic + *Plastic；*Plastic 第一行必须是「屈服应力, 0.」，后续行为硬化点「应力, 塑性应变」",
    "热": "*Conductivity 后给导热系数 k（各向同性一行即可）",
    "超弹性": "*Hyperelastic（橡胶类，本库暂不覆盖）",
}

# --------------------------------------------------------------------------- 截面
SECTION_GUIDE: Dict[str, str] = {
    "实体": "*Solid Section, elset=..., material=...（2D 平面应变/轴对称可加厚度数据行，默认 1）",
    "壳": "*Shell Section, elset=..., material=... 后给厚度",
    "梁": "*Beam Section, elset=..., material=..., section=RECT/I 后给截面尺寸与方向向量",
    "热": "热单元一般无需截面（除非有热源/对流面）",
}

# --------------------------------------------------------------------------- 分析步
STEP_GUIDE: Dict[str, str] = {
    "静力": "*Step + *Static（几何非线性加 nlgeom=YES）",
    "几何非线性": "*Step, name=..., nlgeom=YES（位移达到构件尺度、大转动、板薄膜效应时必须开；默认线性小挠度会高估挠度/漏掉失稳）",
    "弧长法": "*Step, name=..., nlgeom=YES + *Static, Riks（数据行：初始增量, 总弧长, 最小增量, 最大增量；用于后屈曲/跳跃失稳这类荷载-位移曲线有极限点、荷载控制法无法收敛的问题）",
    "模态": "*Step, perturbation + *Frequency（Lanczos 提取前 N 阶，需密度）",
    "屈曲": "*Step, perturbation + *Buckle（线性屈曲特征值）",
    "热稳态": "*Step + *Heat Transfer, steady state（温度自由度 11 用 *Boundary 或 *Temperature 施加）",
    "热瞬态": "*Step + *Heat Transfer（默认瞬态，需 *Initial Conditions, type=Temperature）",
    "热应力（完全耦合）": "*Step + *Coupled Temperature-Displacement, steady-state（单元用 C3D8RT/CPE4T，材料加 *Expansion 热膨胀系数）",
    "热应力（顺序耦合）": "第一步 *Step + *Heat Transfer 求温度场；第二步 *Step + *Static，用 *Temperature, file=<job名>, step=1 读入温度场（file 必须与 job 名严格一致）",
    "动力隐式": "*Step + *Dynamic, Implicit（数据行：初始增量, 总时长, 最小增量, 最大增量；需 *Density；突加恒载峰值位移≈2倍静力位移）",
    "动力显式": "*Step + *Dynamic, Explicit（数据行可只给总时长，稳定增量自动；需 *Density；冲击用 *Initial Conditions, type=Velocity 给初速度，必须在 *Step 之前）",
    "稳态动力": "*Step + *Steady State Dynamics, direct（数据行：fmin, fmax, 扫频点数, bias；共振峰对照一阶固有频率 f1）",
    "响应谱": "*Step + *Response Spectrum（需先做 *Frequency 提取模态，再给谱加速度）",
    "动力": "*Step + *Dynamic（显式 Explicit / 隐式 Implicit，具体见动力隐式/动力显式两条）",
}

# --------------------------------------------------------------------------- 边界与载荷
BOUNDARY_GUIDE: str = (
    "固定：U1=U2=U3=0（刚接再加 R1=R2=R3=0）；\n"
    "铰接：只约束平动 U1=U2=U3=0，放开转动；\n"
    "对称：对称面法向位移=0、面内两转动=0；\n"
    "平面框架出平面：约束出平面平动 U3 与绕面内两轴的转动 R1、R2。\n"
    "位移自由度 1-3（U1/U2/U3），转动自由度 4-6（R1/R2/R3），温度自由度 11。"
)
LOAD_GUIDE: str = (
    "集中力：*Cload（节点集, 自由度, 值）；\n"
    "分布压力/线载：*Dload（面/边, P, 值），梁横向用 P1/P2；\n"
    "位移加载：*Boundary + 非零位移值（收敛困难时优先用位移替代力）；\n"
    "重力：*Dload GRAV 方向分量。"
)

# --------------------------------------------------------------------------- 网格原则
MESH_GUIDE: str = (
    "应力集中区（孔边/缺口/角点）加密；\n"
    "避免退化单元与过小内角（<30° 易报错）；\n"
    "减缩积分单元需注意沙漏（hourglass），必要时加密或加沙漏控制；\n"
    "壳单元保证法向一致；\n"
    "做网格收敛性检查：加密后结果变化小于阈值才算收敛。"
)

# --------------------------------------------------------------------------- 部件几何建模
PART_GUIDE: str = (
    "部件（Part）几何建模方式（选完单元类型后决定怎么造几何）：\n"
    "- 2D 平面：草图（点/线/圆弧）→ 面；平面应力/平面应变/轴对称用 2D 面。\n"
    "- 3D 实体：草图截面 → 拉伸（Extrude）/ 旋转（Revolve）/ 扫掠（Sweep）/ 放样（Loft）。\n"
    "- 3D 壳：2D 面按壳厚度赋截面；复杂曲面用旋转/扫掠生成中面。\n"
    "- 杆系：线（Wire）→ 梁/桁架；直线段即可，节点共享即刚接。\n"
    "- 几何清理：去除小面/短边、合并重合点；过度圆角/倒角会使网格失败。\n"
    "- inp 直写时：*Node（坐标）+ *Element（单元-节点连接）本身就是几何，无需草图。"
)

# --------------------------------------------------------------------------- 装配
ASSEMBLY_GUIDE: str = (
    "装配（Assembly）：\n"
    "- 每个 Part 生成 Instance（*Instance, part=..., name=...）。\n"
    "- 摆放：平移 translate、旋转 rotate；instance 引用原 part 局部坐标 + 变换。\n"
    "- 部件间连接三种：共节点（两件共享节点号，需网格对齐）/ Tie 约束（面-面绑定）/ Coupling（点-面耦合）。\n"
    "- 单件 inp 直写：节点即全局坐标，可省 *Assembly。\n"
    "- 多件装配：各 part 局部坐标，*Assembly 用 *Instance 平移/旋转摆放，再由 *Nset/*Elset 引用。"
)

# --------------------------------------------------------------------------- 相互作用（接触/约束）
INTERACTION_GUIDE: str = (
    "相互作用（Interaction）：\n"
    "- 面面接触 *Contact Pair：*Surface 定义主/从面 + *Contact Pair, interaction=...；属性 *Surface Interaction（*Friction 摩擦、硬接触默认）。\n"
    "- 通用接触 *Contact, op=NEW + *Contact Inclusions：全自动，复杂装配首选。\n"
    "- 绑定 Tie：*Tie, name=..., 主面/从面（从面节点位移=主面插值，用于焊接/连接板）。\n"
    "- 耦合 Coupling：*Coupling, kinematic/distributing, ref node=..., surface=...（点-面传力/加载）。\n"
    "- 刚体 *Rigid Body, ref node=..., elset=...（不变形部件）。\n"
    "- MPC/连接器：*MPC BEAM/TIE/PIN；弹簧 *Spring。\n"
    "- 主从面选择：硬面为主、网格粗为主；初始间隙/过盈用 *Contact Interference 处理。"
)

# --------------------------------------------------------------------------- 输出
OUTPUT_GUIDE: str = (
    "输出（Output）：\n"
    "- 场输出 *Output, field：*Node Output（U/RF/NT）、*Element Output（S/E/PE/PEEQ）。\n"
    "- 历史输出 *Output, history：指定节点/单元集。\n"
    "- 频率/间隔：*Output, field, frequency=... 或 time interval。\n"
    "- 后处理关键量：位移 U、应力 S、应变 E、支反力 RF。"
)

# --------------------------------------------------------------------------- 模型组成范式（Recipe）
MODEL_RECIPE: str = (
    "一个完整 Abaqus 模型的组成（从零到可算）：\n"
    "1. 部件 Part：几何（2D/3D/壳/梁/实体）→ 网格单元；\n"
    "2. 属性 Property：*Material（弹性/塑性/热）+ *Section（Solid/Shell/Beam）赋给 elset；\n"
    "3. 装配 Assembly：Instance 摆放（单件可省）；\n"
    "4. 相互作用 Interaction：接触 / Tie / Coupling / 刚体（多件时）；\n"
    "5. 分析步 Step：*Step + 分析类型（Static/Frequency/Buckle/Heat/Dynamic）；\n"
    "6. 边界 BC：*Boundary（固定/铰接/对称）；\n"
    "7. 载荷 Load：*Cload / *Dload / 位移；\n"
    "8. 网格 Mesh：单元类型 + 种子（应力集中加密）；\n"
    "9. 输出 Output：*Output 场/历史 + *End Step；\n"
    "10. 作业 Job：*Job（提交计）。\n"
    "最小可算模型 = Part(节点/单元) + Material + Section + Step + BC + Load + Output + End Step。"
)

# --------------------------------------------------------------------------- 从零建模流程
MODELING_FLOW: str = (
    "1. 定单元类型（据结构特征：体/壳/梁/2D/热）；\n"
    "2. 建 *Node（节点坐标）+ *Element（单元-节点连接）；\n"
    "3. 建 *Nset/*Elset 集合（供边界/载荷/材料引用）；\n"
    "4. 建 *Material（弹性/塑性/热）；\n"
    "5. 建 *Section（Solid/Shell/Beam）；\n"
    "6. inp 直写时节点即装配，无需 *Assembly；\n"
    "7. 建 *Step（分析步类型）；\n"
    "8. 施加 *Boundary + 载荷（*Cload/*Dload）；\n"
    "9. 设置 *Output（Node/Element Output）+ *End Step。"
)

# --------------------------------------------------------------------------- 案例匹配
# 需求关键词 → 内置案例 skill（按「最贴近」命中）
CASE_MATCH: Dict[str, str] = {
    "框架": "steel_frame",
    "门式": "steel_frame",
    "刚架": "steel_frame",
    "多层": "steel_frame",
    "悬臂": "cantilever",
    "孔": "plate_hole",
    "开孔": "plate_hole",
    "简支": "ss_beam",
    "桁架": "truss",
    "模态": "modal_beam",
    "频率": "modal_beam",
    "振动": "modal_beam",
    "屈曲": "buckle_column",
    "稳定": "buckle_column",
    "塑性": "plastic_plate",
    "屈服": "plastic_plate",
    "弹塑": "plastic_plate",
    "厚壁": "thick_cylinder",
    "圆筒": "thick_cylinder",
    "内压": "thick_cylinder",
    "接触": "contact",
    "螺栓": "contact",
    "装配": "contact",
    "热": "heat_slab",
    "温度": "heat_slab",
    "导热": "heat_slab",
    "轴对称": "axisym",
    "圆盘": "axisym",
    "回转": "axisym",
    "l型": "l_bracket",
    "l 型": "l_bracket",
    "支架": "l_bracket",
}

# 每个案例「必须向用户澄清」的关键参数（用户没说就必须问，不能默默用默认值）
CASE_QUESTIONS: Dict[str, List[str]] = {
    "steel_frame": ["层数", "跨数", "层高", "跨度", "柱截面", "梁截面", "荷载", "支座（铰接/刚接）", "单元类型（梁 B31 / 壳 S4R）"],
    "cantilever": ["梁长", "截面尺寸", "载荷大小/位置"],
    "plate_hole": ["板尺寸", "孔半径", "载荷类型/大小"],
    "l_bracket": ["臂长", "板厚", "载荷"],
    "ss_beam": ["跨长", "截面", "跨中载荷"],
    "truss": ["跨度", "高度", "载荷"],
    "modal_beam": ["梁长", "截面", "材料密度", "模态阶数"],
    "thick_cylinder": ["内径", "外径", "内压"],
    "buckle_column": ["柱长", "截面", "参考载荷", "模态阶数"],
    "plastic_plate": ["板尺寸", "孔半径", "屈服应力", "载荷"],
    "contact": ["几何尺寸", "摩擦系数", "载荷/压缩量"],
    "heat_slab": ["板尺寸", "导热系数", "两端温度"],
    "axisym": ["半径", "厚度", "压力"],
}

# 权威外部资料入口（URL 只保留确定存在的顶层站点，具体页用 web_search 定位）
REFERENCE_URLS: Dict[str, str] = {
    "Abaqus 官方文档门户": "https://help.3ds.com/",
}


def match_case(requirement: str) -> List[Tuple[str, int]]:
    """按关键词命中数匹配内置案例，返回 [(skill, 命中数)] 降序。"""
    low = requirement.lower()
    scored: Dict[str, int] = {}
    for kw, skill in CASE_MATCH.items():
        if kw in low:
            scored[skill] = scored.get(skill, 0) + 1
    return sorted(scored.items(), key=lambda kv: -kv[1])


def suggest_units(requirement: str) -> List[Tuple[str, str]]:
    """据需求建议单元类型：用户显式写出的单元代码优先级最高，其次才是结构关键词。"""
    low = requirement.lower()
    explicit = ["C3D20R", "C3D20", "C3D8R", "C3D8", "S4R", "S4", "B32", "B31",
                "T3D2", "CPE4R", "CPE4", "CPS4R", "CPS4", "CAX4R", "CAX4",
                "DC2D4", "DC3D8"]
    out: List[Tuple[str, str]] = []
    for code in explicit:
        cl = code.lower()
        if cl in low and not any(cl in c.lower() for c, _ in out):
            out.append((code, "用户显式指定"))
    if out:
        return out
    for kw, (unit, note) in UNIT_GUIDE.items():
        if kw in low:
            out.append((unit, note))
    return out


def guide_section(topic: str) -> str:
    """按主题返回建模知识章节；topic 为空或未命中时返回全部。"""
    key = (topic or "").strip().lower()
    sections = [
        ("部件", "部件几何建模\n" + PART_GUIDE),
        ("装配", "装配\n" + ASSEMBLY_GUIDE),
        ("相互作用", "相互作用（接触/约束）\n" + INTERACTION_GUIDE),
        ("单元", "单元选择\n" + "\n".join(f"- {k}: {v[0]} —— {v[1]}" for k, v in UNIT_GUIDE.items())),
        ("材料", "材料模型\n" + "\n".join(f"- {k}: {v}" for k, v in MATERIAL_GUIDE.items())),
        ("截面", "截面\n" + "\n".join(f"- {k}: {v}" for k, v in SECTION_GUIDE.items())),
        ("分析步", "分析步\n" + "\n".join(f"- {k}: {v}" for k, v in STEP_GUIDE.items())),
        ("边界", "边界条件\n" + BOUNDARY_GUIDE),
        ("载荷", "载荷\n" + LOAD_GUIDE),
        ("网格", "网格原则\n" + MESH_GUIDE),
        ("输出", "输出\n" + OUTPUT_GUIDE),
        ("组成", "模型组成范式\n" + MODEL_RECIPE),
        ("流程", "从零建模流程\n" + MODELING_FLOW),
    ]
    if key:
        for name, body in sections:
            if name in key:
                return body
        # 主题词直接出现在单元表/材料表/分析步表里也命中
        for kw, (unit, note) in UNIT_GUIDE.items():
            if kw in key:
                return f"单元选择：{kw} → {unit}（{note}）"
    return "\n\n".join(body for _, body in sections)


# 供 graph.py 注入 system prompt 的「建模流程 SOP + fallback 策略」精简版
MODELING_SOP: str = (
    "建模任务四步闭环：\n"
    "① 理解需求 → plan_model 匹配案例（含必问参数清单）；\n"
    "② 澄清缺失参数（用户没说先问，尤其单元类型：梁 B31 / 壳 S4R / 实体 C3D8R，禁止默认糊弄；"
    "多部件时问连接方式：共节点 / Tie / Coupling / 接触）；\n"
    "③ generate_model 生成 → run_check 校验 → 3D 预览；\n"
    "④ 结论 remember 记入长期记忆。\n\n"
    "检索不到相似案例时的 fallback（按顺序）：\n"
    "① 用 modeling_guide 查「部件 / 装配 / 相互作用 / 单元 / 材料 / 截面 / 分析步 / 边界 / 载荷 / 网格 / 输出 / 模型组成」知识，"
    "按 MODEL_RECIPE 十步组成范式从零设计（部件几何→属性→装配→相互作用→分析步→BC→载荷→网格→输出）；\n"
    "② 用 search_knowledge 在案例库检索相近做法，改造最接近的 build_inp.py；\n"
    "③ 把建模知识落实成 inp：用 mesh_inp 落盘网格骨架（描述网格类型+参数即可，勿手写几百节点坐标），"
    "再用 append_inp 分段补 *Material/*Section/*Step/*Boundary/*Cload/*Tie/*Contact（每段短），最后 run_check 校验、viewer 预览；\n"
    "④ 仍不确定（复杂接触、特殊材料本构、特殊几何）时，用 web_search 检索、web_fetch 抓 Abaqus 官方文档"
    "（help.3ds.com）等权威源，把查到的方法落地到 inp；\n"
    "⑤ 网络/搜索都不可用时，明确告诉用户缺什么资料、建议去查什么，绝不编造不确定的建模参数。"
)
