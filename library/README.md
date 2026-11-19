# 内置案例库（Library）

把「Abaqus 建模怎么做 + 过程」沉淀为**可一键生成 inp 的模式**：每个案例是一个独立目录，含
`build_inp.py`（参数化生成器）与 `case.md`（建模过程 / 原理 / 参数 / 适用场景），并被注册成
一个 agent 技能（skill），可直接通过对话 `generate_model` 调用。

## 目录结构
```
library/
  check_inp.py          # 共享轻量结构校验（关键字 + 节点引用）
  <case>/
    build_inp.py        # argparse 生成器，契约兼容 tools._generate
    case.md             # 建模过程 / 原理 / 参数 / 适用场景
```

## build_inp.py 契约（必须遵守）
- 命令行：`python build_inp.py --flag value ... --job JOB --out DIR`
- 输出固定为 `<DIR>/<JOB>.inp`（不确定路径，不依赖「新增文件」探测）；
- 布尔参数转开关 `--flag`；非布尔参数转 `--flag value`；
- 子进程工作目录 = 案例目录，因此 import 共享工具用：
  `sys.path.insert(0, 上两级目录)` 后 `from agent.inpkit import ...`。

## 共享工具（agent/inpkit.py）
- `NodeTable`：坐标去重的节点注册（多块板共享边 / 角）；
- `hex_mesh` / `shell_rect_mesh` / `plate_hole_mesh` / `l_bracket_mesh`：网格生成；
- `fmt_*` / `elastic_material` / `*_section` / `static_step` / `boundary` / `cload`：inp 文本片段。

## 注册一个案例（三步）
1. 新建 `library/<case>/build_inp.py` + `case.md`；
2. 在 `skills.yaml` 加一段（root 用相对路径 `library/<case>`，validators 用 `../check_inp.py`）；
3. 在 `manifests/<case>.yaml` 声明参数契约（类型 / 范围 / 默认 / 说明）与 SOP。

## 当前案例
| skill | 单元 | 场景 |
|---|---|---|
| cantilever | C3D8R | 悬臂梁，端部固定 + 自由端载荷 |
| plate_hole | S4R | 带孔方板拉伸，孔边应力集中 |
| l_bracket | S4R | L 型支架，一面固定 + 一面载荷 |
| ss_beam | B31 | 简支梁，两端简支 + 跨中载荷 |
| truss | T3D2 | 平面三角桁架，两铰支座 + 顶点载荷 |
| modal_beam | C3D8R | 悬臂梁模态分析，前 N 阶固有频率 |
| thick_cylinder | CPE4 | 平面应变厚壁圆筒，内压，Lame 解对照 |
| buckle_column | C3D8R | 受压柱线性屈曲，欧拉临界载荷对照 |
| plastic_plate | S4R | 带孔板弹塑性拉伸，孔边屈服 |
| steel_frame | B31 | 平面纯钢框架，柱梁刚接+柱底铰接 |
| contact | C3D8R | 两方块面面接触，压缩 |
| heat_slab | DC2D4 | 平板稳态热传导，傅里叶定律对照 |
| axisym | CAX4 | 轴对称圆盘轴向压缩 |
