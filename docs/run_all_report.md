# 自建案例真机求解汇总

- 运行时间：2026-11-18 16:52:37
- 配置：4 并发 × cpus=3，gpus=0，double=False，abq=D:\SIMULIA\Commands\abq2020.BAT
- 跳过：stiff_plate

| 案例 | 作业 | 状态 | 耗时 s | .msg ERROR |
|---|---|---|---|---|
| cantilever | ceshi1_fine | COMPLETED | 14.0 | 0 |
| dynamic_explicit | DYNAMIC_EXPLICIT | COMPLETED | 24.0 | 0 |
| dynamic_implicit | DYNAMIC_IMPLICIT | COMPLETED | 26.0 | 0 |
| harmonic | HARMONIC | COMPLETED | 26.1 | 0 |
| nl_cantilever | NL_CANTILEVER | COMPLETED | 20.0 | 0 |
| plate_nl | PLATE_NL | COMPLETED | 14.0 | 0 |
| plate_hole | PH-DEMO | COMPLETED | 14.0 | 0 |
| axisym | AXISYM | COMPLETED | 12.0 | 0 |
| buckle_column | BUCKLE_COLUMN | COMPLETED | 14.0 | 0 |
| heat_slab | HEAT_SLAB | COMPLETED | 14.0 | 0 |
| contact | CONTACT | COMPLETED | 16.0 | 0 |
| l_bracket | L_BRACKET | COMPLETED | 16.0 | 0 |
| modal_beam | MODAL_BEAM | COMPLETED | 16.0 | 0 |
| ss_beam | SS_BEAM | COMPLETED | 14.0 | 0 |
| thick_cylinder | THICK_CYLINDER | COMPLETED | 12.0 | 0 |
| plastic_plate | PLASTIC_PLATE | COMPLETED | 22.0 | 0 |
| truss | TRUSS | COMPLETED | 12.0 | 0 |
| steel_frame | IFrame-1S1B | COMPLETED | 14.0 | 0 |
| stiffened_plate | StiffPlate-L1000-W500-T10-R50x10-P1-M4 | COMPLETED | 14.0 | 0 |
| thermal_plate | THERMAL_PLATE | COMPLETED | 16.0 | 0 |
| thermal_seq | THERMAL_SEQ | COMPLETED | 14.0 | 0 |
| snap_through | SNAP_THROUGH | COMPLETED | 32.1 | 0 |
| thermal_stress | THERMAL_STRESS | COMPLETED | 16.0 | 0 |

未跑：stiff_plate（inp 内无 `*Step`，属纯网格/边界示例）
