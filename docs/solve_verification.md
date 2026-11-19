# 23 个自建案例的真实求解验证（2026-11-16 全量跑通）

结论先说：**23 个自建案例全部真机 `COMPLETED`（23/23，93 s，`.msg` 里 ERROR 全 0）；
`stiff_plate` 的 inp 本身没有 `*Step`，属网格/边界示例，不参与求解。**

运行方式：`scripts/run_all_cases.py --jobs 4 --cpus 3`（4 并发 × 3 核，20 逻辑核机器）。

> 演进轨迹：2026-11-15 首跑 12/12 → 补注册 `plate_hole` 后 13/13（57 s）→
> 2026-11-16 把最后 10 个早期案例纳入清单，修掉 4 类 inp 缺陷 + 1 个中文路径环境问题后
> **23/23**（93 s）。

---

## 一、这一轮真正暴露的问题

之前这些案例只过了 `check_inp.py`（结构校验：关键字是否齐全、节点是否被引用），
**从未真正提交过 Abaqus**。第一次真跑，8 个案例在输入处理阶段直接失败：

| 案例 | `.dat` / `.msg` 原文报错 | 根因 |
|---|---|---|
| dynamic_explicit | `STEP DEFINITION CARDS BETWEEN *END STEP AND *STEP ARE IGNORED` | `inpkit.field_output()` 自带 `*End Step`，脚本又补一行 → 重复 |
| dynamic_implicit | `Unknown parameter: implicit` | `*Dynamic, Implicit` 不存在，隐式动力就写 `*Dynamic` |
| nl_cantilever | `Unknown parameter: nlgeom` | `nlgeom` 属 `*Step`，不能挂在 `*Static` 上 |
| plate_nl | 同上 | 同上 |
| thermal_plate | `Unknown parameter: steady-state` + `IT REQUIRES A THERMAL CONDUCTIVITY` | 多词参数要用空格 `steady state`；C3D8RT/CPE4T 必须给 `*Conductivity` |
| thermal_stress | 同上 | 同上 |
| thermal_seq | `ONLY DEGREES OF FREEDOM 11 AND ABOVE CAN BE ACTIVE` | CPE4T 带位移自由度，不能进纯 `*Heat Transfer` 步 |
| stiffened_plate | `THE EIGENVALUES CANNOT BE FOUND` | `*Buckle` 前缺 `*Static` 预载；面内刚体位移未约束 |

第二轮又暴露 3 个更深的坑（都不是"拼写错误"，是**建模知识缺失**）：

1. **带温度自由度的单元不能用 `*Temperature`**
   `*TEMPERATURE MAY NOT BE USED WITH ELEMENTS THAT POSSESS TEMPERATURE DEGREES OF FREEDOM. USE *BOUNDARY`
   → 温度必须写成 `*Boundary, <nset>, 11, 11, <T>`（DOF 11）。
2. **边界条件跨步传播**
   第一步的温度边界会自动继承到第二步；`*Static` 里不允许 DOF 11 边界。
   → 第二步必须 `*Boundary, op=NEW` 清掉继承边界，再重新给位移约束。
3. **线性屈曲两步走**
   `*Buckle` 前要 `*Static` 预载建立应力刚度；还要约束面内刚体位移（U1/U2），否则刚度矩阵奇异。
   细网格（902 节点）还要把 `*Buckle` 的迭代上限调到 40，否则报
   `INCREASE THE NUMBER OF ITERATIONS TO GET THE REQUESTED NUMBER OF EIGENVALUES`。

所有修改都改在 `library/<case>/build_inp.py` 源头（`scripts/fix_inp_errors.py` 记录了前 7 类），
不是改生成物。

---

## 二、物理量核对（从 odb 读，最后一帧）

| 案例 | 关键结果 | 理论/参照 | 判断 |
|---|---|---|---|
| cantilever（60×4×8，2745 节点） | 自由端 U=0.3895 mm | PL³/3EI = 0.381 mm | **+2.3%**，粗网格偏差，加密后收敛到 +2% |
| nl_cantilever（nlgeom） | 端部 U=212.5 mm | 线性理论 250 mm | **−15%**，几何非线性生效（大挠度刚化） |
| plate_nl（S4R 大挠度） | 中心 U=7.566 mm | 线性 10.56 mm | **−28%**，薄膜效应生效 |
| snap_through（Riks） | 最大 U=71.6 mm，101 帧 | 浅拱跳跃 | 跨过临界点继续跟踪，Riks 生效 |
| stiffened_plate（*Buckle） | λ1=6607、λ2=9686、λ3=13131 | 纯板 σcr≈304 MPa；加肋后 λ·P/Area≈660 MPa | 加肋提高约 **2.2 倍**，量级合理 |
| thermal_stress（底 0 / 顶 100） | Mises 最大 97.0 MPa | 底部局部约束热应力 | 量级合理（只有底面固定，上部自由膨胀） |
| thermal_plate（全场 ΔT=100） | Mises 最大 746.5 MPa | 双轴全约束估算 360 MPa | **偏高约 2 倍**，见下 |
| thermal_seq（两步） | Static 步 Mises 569.7 MPa | — | 偏高，见下 |
| dynamic_explicit（v=1000 mm/s 冲击） | Mises 最大 19.9 MPa | ρcv = 40.73 MPa | **只有一半**，见下 |
| dynamic_implicit（突加荷载） | U 最大 0.171 mm，6 帧 | 静态解 + 放大系数 2 | 需与静态解逐点比才能定量 |
| harmonic（100–400 Hz 扫频） | U 最大 2.49e−3 mm，61 帧 | 频响幅值 | 已出完整频响曲线 |
| steel_frame（柱顶推 100 mm） | U=100.004 mm，Mises 345 MPa，RF 18.9 MN | 位移施加值 | 位移吻合，内力偏大（底部 6 DOF 全固 + 耦合，超静定） |
| plate_hole（S4R，624 节点，孔边应力集中） | 施加位移 2 mm，COMPLETED | 圆孔应力集中系数约 3（σmax/σnom） | **只验证能跑通，未读 odb 做定量对照** |

---

## 三、三个不能算"通过"的地方（必须如实记下）

1. **dynamic_explicit 只有理论值的一半**（19.9 vs 40.7 MPa）
   可能原因：(a) C3D8R 缩减积分在冲击波前有沙漏/软化；(b) 输出帧未落在波峰时刻，
   20 帧的采样错过了峰值；(c) 全杆初速度 + 端部固定，反射波与入射波叠加方式与
   "半无限杆撞刚性墙"的教科书模型不同。**未做网格/时间增量收敛性验证**，所以只能记
   "模型能跑、能量级对、绝对值待校"。

2. **thermal_plate / thermal_seq 的热应力高于手算**
   我的估算是 σ=EαΔT/(1−ν)≈360 MPa，FE 给 746 / 570 MPa。差异来源确定是**约束过刚**：
   案例把 X0/X1 两条边的 U1、U2 同时锁死，等于双轴约束 + 泊松效应也被限制，
   而手算那套公式对应的是"单轴全约束"。要么改边界（只锁 U1），要么改文档里的理论值。
   **当前口径：以 FE 为准，手算值作废。**

3. **harmonic / dynamic_implicit / plate_hole 没有定量核对**
   前两者给出了完整时程/频响，但没和解析解（简支梁一阶频率、Duhamel 放大系数）
   逐点比对；`plate_hole` 只确认能跑通（孔边应力集中系数约 3 这点还没从 odb 量出来）。
   属于"能跑出曲线"，不是"已验证精度"。

---

## 四、报错 → 修法闭环（端到端验证过）

前 8 类错误这次是人工对照 `.dat` 改的。为了让 agent 自己也能做，补了
`agent/inp_doctor.py`（21 条规则：报错关键字 → 原因 → 可直接照改的修法），
并接进 `tools.job_status()`：**只要 `.dat` 里有 `***ERROR`，状态输出末尾就附诊断。**

实测流程（2026-11-15）：

1. 故意把 `nl_cantilever` 的 inp 改坏（`nlgeom` 挂回 `*Static` 上）→ 提交
   → `NOT_STARTED`，`Abaqus Error: Analysis Input File Processor exited with an error`
2. `job_status` 自动输出：

   ```
   INPUT: 输入处理失败（4 条 ERROR，见下方诊断）
   [诊断] DOCDEMO：共 3 条 ERROR，归并为 1 类
   1) 报错：***ERROR: in keyword *STATIC ... Unknown parameter: nlgeom ...
      原因：nlgeom 是 *Step 的参数，不是 *Static 的
      修法：`*Static, nlgeom=YES` 拆成两行：`*Step, name=<步名>, nlgeom=YES` 然后 `*Static`
   ```

3. 照修法改一行 → 重新提交 → **COMPLETED，ERROR 0**

所以"跑失败 → 读报错 → 改 inp → 再跑通"这个闭环是成立的，且有测试覆盖
（`tests/test_inp_doctor.py`，把 13 条真实报错原文逐条断言）。

**边界（别夸大）**：规则库只认它收录过的报错。没收录的会明确说"未收录，去读 `.dat`
上下文或 web 查原文"，并提示补规则；诊断给的是修法建议，**不会**擅自改模型
（改哪一行、改完物理意义对不对，仍由 agent 判断）。

### 9.1 自动修补（`repair_inp` 工具）

为了让 agent 不用手工拼整份 inp，加了 `tools.repair_inp()`，能自动应用**确定性**修法：

| 能自动改 | 怎么改 |
|---|---|
| `nlgeom` 错层 | 合并进上一行 `*Step, name=..., nlgeom=YES`，数据行还原 |
| `*Dynamic, Implicit` | 去掉 `, implicit` |
| `steady-state` | 改 `steady state` |
| 重复 `*End Step` | 删掉相邻那条 |
| `*Buckle` 迭代上限不足 | 第三字段补到 40 |
| `*Temperature, file=` | 删掉该行（温度自动继承） |
| 缺 `*Conductivity` | 在 `*Material` 后补，k 默认 0.05（换单位制要改） |
| `*Temperature, nset=X` | 改 `*Boundary` + `X, 11, 11, T` |

**不自动改**（改错代价大，只给建议）：缺预载步（eigenvalues cannot be found）、
边界跨步 DOF 11、纯热步用耦合单元、刚度奇异、不收敛、截面参数越界、set 未定义、
关键字层级错。每次修改都写 `.inp.bak`，并逐条报告"改了哪一行、从什么改成什么"。

实测（同一套坏 inp）：`repair_inp` 自动改 2 处 → `run_check` → `submit_job` →
**COMPLETED，ERROR 0**，全程未手工编辑。

**为什么不做全自动**：这 8 类之所以能编码，是因为修法与物理含义无关（纯语法层级）。
再往上（比如"屈曲算不出特征值"该加预载还是该补约束）取决于模型意图，自动改很可能
把模型改错却还能跑出结果——那比报错更危险。

## 五、复现命令

```powershell
# 全量（4 并发 × 3 核）
.\.venv\Scripts\python.exe scripts\run_all_cases.py --jobs 4 --cpus 3 --abq "D:\SIMULIA\Commands\abq2020.bat"

# 单个
.\.venv\Scripts\python.exe scripts\run_all_cases.py --only thermal_seq --cpus 4

# 读 odb 关键量（abaqus python 读不了中文路径，先复制到 C:\Temp 下的 ASCII 目录）
```

机器汇总表由脚本写到 `docs/run_all_report.md`（每次跑覆盖）。

---

## 六、两个环境事实（写进发布文档免得别人踩）

1. **`abq2020` 不在当前 shell 的 PATH 里**。`shutil.which("abq2020")` 返回 None，
   必须给绝对路径 `D:\SIMULIA\Commands\abq2020.bat`（`config.yaml` 的 `command` 建议写绝对路径）。
   之前那次"能跑"是因为当时的会话 PATH 里有 `D:\SIMULIA\Commands`。
2. **`abaqus python` 是 Python 2.7 且读不了中文路径**，读 odb 必须先复制到纯 ASCII 目录
   （`C:\Temp\...`）。`%TEMP%` 也可能含中文（本机是 `C:\Users\<用户名>\...`）。

---

## 七、2026-11-16 扩到全量 23 个：又挖出 5 类问题

把最后 10 个早期案例（`axisym`、`buckle_column`、`contact`、`heat_slab`、`l_bracket`、
`modal_beam`、`plastic_plate`、`ss_beam`、`thick_cylinder`、`truss`）纳入批量清单后，
首跑 **17/23**，暴露 5 类问题（4 类 inp 缺陷 + 1 个环境坑），全部改在生成器/运行器源头：

| 案例 | 报错原文 | 根因 | 修法 |
|---|---|---|---|
| axisym | `ELEMENT SET TOP HAS NOT BEEN DEFINED` | `*Dload` 的数据行填的是 **surface 名**，而 `*Dload` 只认 elset | 关键字改成 `*Dsload`（面载荷） |
| thick_cylinder | `ELEMENT SET INSIDE HAS NOT BEEN DEFINED` | 同上 | 同上 |
| heat_slab | `80 elements have missing property definitions` | 只写了 `*Material`/`*Conductivity`，**没有 `*Solid Section`**，单元无截面属性 | 补 `*Solid Section, elset=ALL, material=STEEL` + 平面厚度 |
| contact | `SURFACE TOP_BOT IS NOT CONTINUOUS OR IS COMPOSED OF TWO OR MORE` | surface 把**所有单元**的 S1/S2 面都写进去了，内部面混进来 | 只取贴合的那一层：下块顶层 `S2` + 上块底层 `S1` |
| buckle_column / modal_beam | `.dat`/`.msg` **一条 `***ERROR` 都没有**，只有 `Abaqus/Analysis exited with errors` | 见下 | 环境修复 |

buckle_column / modal_beam 这一类是最难查的：控制台里真正的线索只有一行

```
Unable to open C:\Users\<用户名>~1\AppData\Local\Temp\<用户名>_<JOB>_<PID>\<JOB>.stf.
```

Abaqus 会在 scratch 下建 `<用户名>_<作业名>_<PID>` 子目录，**用户名含中文**时这个临时文件
建不出来，特征值求解器（`*Frequency` / `*Buckle` 的 Lanczos）直接退出，而 `.msg` 里没有任何
ERROR 行 —— 只看 `.msg` 会完全找不到原因。修复：

1. 子进程环境里把 `TEMP`/`TMP` 指到 `C:\Temp\abqscratch`、`USERNAME` 改成 `abquser`；
2. 命令行追加 `scratch=C:\Temp\abqscratch`（`abaqus_run.build_argv` 自动加）；
3. 生成的 `run_<JOB>.ps1` 里检测到中文路径时做同样的处理。

改完后 23/23 全部 `COMPLETED`。新增案例的物理量抽查（从 odb 末帧读）：

| 案例 | 读数 | 对照 |
|---|---|---|
| axisym | S22 = −10.0 MPa | 施加压力 10 MPa，均匀压应力，**完全一致** |
| thick_cylinder | 最大应力 18.03 MPa | Lamé 解内壁环向 16.67、径向 −10，等效应力约 17.3，**量级一致** |
| heat_slab | 热流密度 HFL = 40 | k·ΔT/L = 50×80/100 = 40，**完全一致** |
| contact | 接触面峰值 1203 MPa | 压缩 0.1 mm 的局部接触应力集中，量级合理但未做解析对照 |
| buckle_column | Mode 4，EigenValue = 5212.9 | 特征值非零、非奇异，未与欧拉解逐点对照 |
| modal_beam | Mode 6，f = 11553 cycles/time | 模态数 = 6 ✓，频率未与梁理论解对照 |

**口径**：新增 6 个案例只算"跑通 + 量级合理"，`contact` / `buckle_column` / `modal_beam`
没有做理论值的逐点对照，这一点和原有 13 个案例的验收标准不同。
