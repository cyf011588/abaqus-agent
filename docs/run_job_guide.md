# 作业运行指南（CPU / GPU 可填）

模型生成后，可以在三种方式里任选一种运行；CPU 核数与 GPU 数都能改。

## 1. 生成即得运行脚本（推荐）

`generate_model` / `write_inp` / `append_inp` 成功后，会在**模型所在目录**自动写一个
`run_<JOB>.ps1`，默认核数取自 `config.yaml` 的 `abaqus.cpus` / `abaqus.gpus`。

```powershell
cd .\data\output\thermal_plate
.\run_THERMAL_PLATE.ps1                  # 默认参数，前台跑并等待
.\run_THERMAL_PLATE.ps1 -Cpus 16         # 改 CPU 核数
.\run_THERMAL_PLATE.ps1 -Gpus 1          # 开 GPU（仅 Abaqus/Explicit 有效）
.\run_THERMAL_PLATE.ps1 -Cpus 8 -Gpus 1 -Double
.\run_THERMAL_PLATE.ps1 -NoWait          # 后台启动，不等结果
.\run_THERMAL_PLATE.ps1 -Status          # 只查 .sta 状态，不启动计算
```

脚本里 `$abq = "abq2020"`，若命令不在 PATH，改成绝对路径（如 `D:\SIMULIA\Commands\abq2020`）；
若需要先加载环境，取消注释 `& "C:\SIMULIA\2020\EstablishEnvironment.bat"` 那一行。

## 2. 对话里直接让 agent 跑

生成完成后 agent 会主动问「要不要现在提交运行？CPU 核数、要不要开 GPU」。

- 回复「跑一下，12 核」→ `submit_job(cpus=12)`
- 回复「用 8 核 + 1 张 GPU」→ `submit_job(cpus=8, gpus=1)`
- 大模型/长作业：`submit_job(..., wait=False)` 后台提交，返回 PID，随后 `job_status` 轮询

## 3. 批量（多作业 + 并发上限）

```powershell
# 方式一：先进作业目录，再调脚本（绝对路径最省事）
cd .\data\output\cantilever
.\scripts\run_jobs_batch.ps1 -Jobs "A","B","C" -Cpus 12 -MaxConcurrent 1

# 方式二：不切目录，用 -Dir 指过去（推荐）
.\scripts\run_jobs_batch.ps1 -Jobs "A","B" -Dir data\output\cantilever -Cpus 12 -MaxConcurrent 2
.\scripts\run_jobs_batch.ps1 -JobsFromFile jobs.txt -Dir data\output\cantilever -Cpus 12 -MaxConcurrent 2 -Gpus 1
.\scripts\run_jobs_batch.ps1 -Jobs "A","B" -Dir data\output\cantilever -StatusOnly

# abq2020 不在 PATH 时，加 -Abq 传绝对路径
.\scripts\run_jobs_batch.ps1 -Jobs "A" -Dir data\output\cantilever -Abq "D:\SIMULIA\Commands\abq2020.bat"
```

跑完把每个 job 的 `.sta` 状态汇总写入同目录 `JobResult.txt`。

## CPU / GPU 注意事项

| 项 | 说明 |
|---|---|
| `cpus` | 指定求解核数；超过本机物理核数会退化为分布式 MPI 调度，通常不划算 |
| `gpus` | **只有 Abaqus/Explicit 支持 GPU 加速**（需 NVIDIA + CUDA 驱动）。Standard（静力/模态/屈曲/Riks/隐式动力）填了会被忽略或报错，一般保持 0 |
| `double` | 加 `double=both` 双精度，显式冲击、接触、大变形问题建议开；代价是内存与耗时增加 |
| 内存/临时目录 | 大模型可用 `abaqus ... scratch=<目录>` 指定 scratch，避免默认目录写满 |

## Windows 上的一个坑（已处理）

Abaqus 的命令行入口 `abq2020` 实际是 `D:\SIMULIA\Commands\abq2020.bat`（批处理）。
Windows 的 CreateProcess **不能直接执行 .bat**，直接开子进程会报
`WinError 2: 系统找不到指定的文件`——看起来像"没装 Abaqus"，其实装了。

agent 侧已统一在 `abaqus_run.resolve_argv()` 里做转换：

```
abq2020  →  D:\SIMULIA\Commands\abq2020.bat  →  cmd /c <绝对路径> job=... cpus=...
```

`submit_job` 前台/后台两条路径都会先经过它；找不到命令时返回的是可诊断的 FAIL
（提示改 `config.yaml` 的 `abaqus.command` 为绝对路径），而不是抛异常。

## 状态判定

统一以 `.sta` 是否出现 `THE ANALYSIS HAS COMPLETED SUCCESSFULLY` 或 `END OF JOB` 为完成判据；
`.msg` 里 `***ERROR` 条数用于判断失败原因；`.dat` 出现 `END OF USER INPUT PROCESSING` 说明输入处理通过。
agent 侧的 `job_status` 会一次性把这几个信息汇总给你。
