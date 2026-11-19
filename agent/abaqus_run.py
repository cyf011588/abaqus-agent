# -*- coding: utf-8 -*-
"""Abaqus 作业提交与运行脚本生成（CPU/GPU 参数化）。

两个用途：
1. build_argv —— 给 tools.submit_job 拼 `abaqus job=... cpus=... gpus=... int ask=off` 命令行；
2. write_run_script —— 模型生成后，在其输出目录落一个可手改、可双击的 run_<JOB>.ps1，
   里面把 job 名、目录、默认核数写死，用户只改 -Cpus / -Gpus 就能跑。

GPU 说明：Abaqus/Explicit 支持 `gpus=n` 加速（需 NVIDIA CUDA 环境）；
Abaqus/Standard 不支持 GPU 加速，传 gpus 会被忽略甚至报错，所以默认 0、仅显式分析才开。
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

# Windows: 让子进程脱离父进程独立存活（后台跑长作业用）
_DETACHED = 0x00000008 if os.name == "nt" else 0

_BAT_SUFFIXES = (".bat", ".cmd")

# Abaqus 装好后通常不会自动进 PATH，这里按安装惯例兜底探测
_ABQ_CANDIDATES = (
    r"D:\SIMULIA\Commands\abq2020.bat",
    r"C:\SIMULIA\Commands\abq2020.bat",
    r"D:\SIMULIA\Commands\abaqus.bat",
    r"C:\SIMULIA\Commands\abaqus.bat",
)


def _find_abq(exe: str) -> Optional[str]:
    """PATH 里找不到 abaqus 命令时，按常见安装路径兜底（本机实测 PATH 里常常没有）。

    只对 abq* / abaqus* 这类命令名兜底，别的命令找不到就该返回 None。
    """
    found = shutil.which(exe)
    if found:
        return found
    if not exe.lower().startswith(("abq", "abaqus")):
        return None
    for cand in _ABQ_CANDIDATES:
        if Path(cand).exists():
            return cand
    return None


def resolve_argv(argv: List[str]) -> List[str]:
    """把 argv[0] 解析成真实可执行文件，必要时包一层 cmd /c。

    Windows 的 CreateProcess 不能直接执行 .bat/.cmd（Abaqus 的 abq2020 就是批处理），
    直接开子进程会抛 WinError 2「系统找不到指定的文件」，所以这里统一转换：
      abq2020 -> D:\\SIMULIA\\Commands\\abq2020.bat -> cmd /c <bat> <args...>
    """
    if not argv:
        return argv
    exe = argv[0]
    if not (os.path.isabs(exe) or os.sep in exe or "/" in exe):
        exe = _find_abq(exe) or exe
    rest = [str(a) for a in argv[1:]]
    if os.name == "nt" and exe.lower().endswith(_BAT_SUFFIXES):
        comspec = os.environ.get("ComSpec", "cmd.exe")
        if " " in exe:
            # 路径含空格时，路径与参数拼成一个整体再交给 cmd /c
            return [comspec, "/c", f'"{exe}" ' + " ".join(rest)]
        return [comspec, "/c", exe] + rest
    return [exe] + rest


def abq_path(abq: str) -> Optional[str]:
    """探到 Abaqus 命令的真实路径（供诊断用），找不到返回 None。"""
    if os.path.isabs(abq):
        return abq if Path(abq).exists() else None
    return _find_abq(abq)


def build_argv(
    abq: str,
    job: str,
    cpus: Optional[int] = None,
    gpus: int = 0,
    double: bool = False,
    extra: Optional[List[str]] = None,
) -> List[str]:
    """拼 Abaqus 命令行。gpus>0 才追加 `gpus=`；double 追加 `double=both`。"""
    argv = [abq, f"job={job}"]
    if cpus:
        argv.append(f"cpus={int(cpus)}")
    if gpus and int(gpus) > 0:
        argv.append(f"gpus={int(gpus)}")
    if double:
        argv.append("double=both")
    argv += ["int", "ask=off"]
    sc = scratch_arg()
    if sc:
        argv.append(sc)
    if extra:
        argv += [str(x) for x in extra]
    return argv


def describe(job: str, cpus: Optional[int], gpus: int, double: bool) -> str:
    """人读的一行参数摘要，用于日志与回答。"""
    gpu_txt = f"{int(gpus)} GPU" if gpus and int(gpus) > 0 else "无 GPU"
    dbl = "双精度" if double else "单精度"
    return f"job={job} | CPU {cpus or '默认'} 核 | {gpu_txt} | {dbl}"


def _is_ascii(text: str) -> bool:
    try:
        text.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


# Abaqus 会在 scratch 下建 `<用户名>_<作业名>_<PID>/`，路径只要含中文，
# 特征值分析（*Frequency / *Buckle）创建 .stf 时就会 "Unable to open ... .stf." 然后整个分析退出，
# 而 .msg/.dat 里一条 ***ERROR 都没有，极难排查。实测本机就是这种情况。
_ASCII_SCRATCH = r"C:\Temp\abqscratch"
_ASCII_USER = "abquser"


def abq_env() -> Optional[dict]:
    """TEMP/USERNAME 含非 ASCII 时，返回一份改好的环境变量给 Abaqus 子进程；否则 None。"""
    temp = os.environ.get("TEMP") or os.environ.get("TMP") or ""
    user = os.environ.get("USERNAME") or ""
    if _is_ascii(temp) and _is_ascii(user):
        return None
    env = dict(os.environ)
    env["TEMP"] = env["TMP"] = _ASCII_SCRATCH
    if not _is_ascii(user):
        env["USERNAME"] = _ASCII_USER
    Path(_ASCII_SCRATCH).mkdir(parents=True, exist_ok=True)
    return env


def scratch_arg() -> Optional[str]:
    """中文路径环境下给命令行补 `scratch=C:\\Temp\\abqscratch`。"""
    if abq_env() is None:
        return None
    Path(_ASCII_SCRATCH).mkdir(parents=True, exist_ok=True)
    return f"scratch={_ASCII_SCRATCH}"


PS1_TEMPLATE = """<#
Abaqus 作业运行脚本（由 abaqus-agent 自动生成，可自由修改）
用法：
  .\\run_{job}.ps1                  # 用默认参数，前台运行并等待
  .\\run_{job}.ps1 -Cpus 16         # 改 CPU 核数
  .\\run_{job}.ps1 -Gpus 1          # 开 GPU 加速（仅 Abaqus/Explicit 生效，需 CUDA）
  .\\run_{job}.ps1 -Cpus 8 -Gpus 1 -Double
  .\\run_{job}.ps1 -NoWait         # 后台启动，不等结果
  .\\run_{job}.ps1 -Status         # 只查 .sta 状态，不启动计算
#>
param(
    [int]$Cpus = {cpus},
    [int]$Gpus = {gpus},
    [switch]$Double,
    [switch]$NoWait,
    [switch]$Status
)

$ErrorActionPreference = "Stop"
$workDir = $PSScriptRoot
$job = "{job}"
$abq = "{abq}"

Set-Location -LiteralPath $workDir
$staFile = Join-Path $workDir "$job.sta"

function Show-Status {{
    if (Test-Path -LiteralPath $staFile) {{
        $txt = Get-Content -LiteralPath $staFile -Raw
        if ($txt -match "THE ANALYSIS HAS COMPLETED SUCCESSFULLY" -or $txt -match "END OF JOB") {{
            Write-Host "[SUCCESS] $job 已运行完成（.sta 出现 END OF JOB）"
        }} else {{
            Write-Host "[RUNNING/INCOMPLETE] $job 未完成，详见 $job.sta / $job.msg"
        }}
        $msg = Join-Path $workDir "$job.msg"
        if (Test-Path -LiteralPath $msg) {{
            $err = (Select-String -LiteralPath $msg -Pattern "***ERROR" -SimpleMatch).Count
            Write-Host "  .msg 中 ***ERROR 条数: $err"
        }}
    }} else {{
        Write-Host "[INFO] 未找到 $staFile，作业可能尚未启动"
    }}
}}

if ($Status) {{
    Show-Status
    return
}}

# Abaqus 命令（若 abq2020 不在 PATH，把下面这行改成绝对路径，如 D:\\SIMULIA\\Commands\\abq2020）
# 如需先加载 Abaqus 环境，取消注释并改正路径：
# & "C:\\SIMULIA\\2020\\EstablishEnvironment.bat"

$abqArgs = @("job=$job", "cpus=$Cpus", "int", "ask=off")
# 用户名或 TEMP 路径含中文时，Abaqus 建不出临时文件（`Unable to open ...stf`），
# 特征值分析会在 .msg 里一条 ERROR 都没有的情况下直接退出 —— 改用英文 scratch 目录与用户名。
if ("$env:USERNAME $env:TEMP" -match '[^\x00-\x7F]') {{
    $scratchDir = "C:\\Temp\\abqscratch"
    if (-not (Test-Path -LiteralPath $scratchDir)) {{ New-Item -ItemType Directory -Path $scratchDir -Force | Out-Null }}
    $env:TEMP = $scratchDir
    $env:TMP = $scratchDir
    $env:USERNAME = "abquser"
    $abqArgs += "scratch=$scratchDir"
    Write-Host "[INFO] 检测到中文路径，已改用 scratch=$scratchDir"
}}
if ($Gpus -gt 0) {{ $abqArgs += "gpus=$Gpus" }}
if ($Double) {{ $abqArgs += "double=both" }}

Write-Host ("运行 {job} | cpus=$Cpus gpus=$Gpus double=$($Double.IsPresent)")
Write-Host ("命令: " + $abq + " " + ($abqArgs -join " "))
Write-Host ("目录: " + $workDir)

if ($NoWait) {{
    $p = Start-Process -FilePath $abq -ArgumentList $abqArgs -WorkingDirectory $workDir -PassThru -WindowStyle Hidden
    Write-Host "已后台启动，PID=$($p.Id)。稍后用 .\\run_{job}.ps1 -Status 查看进度"
}} else {{
    & $abq @abqArgs
    Show-Status
}}
"""


def run_script_text(job: str, cpus: int = 4, gpus: int = 0, abq: str = "abq2020") -> str:
    """生成 run_<job>.ps1 的文本（PowerShell 5.1/7 通用，纯 ASCII 结构 + 中文注释）。"""
    return PS1_TEMPLATE.format(job=job, cpus=int(cpus or 4), gpus=int(gpus or 0), abq=abq)


def write_run_script(
    out_dir: Path,
    job: str,
    cpus: int = 4,
    gpus: int = 0,
    abq: str = "abq2020",
) -> Path:
    """在模型输出目录写 run_<job>.ps1，返回脚本路径。"""
    path = Path(out_dir) / f"run_{job}.ps1"
    path.parent.mkdir(parents=True, exist_ok=True)
    # PowerShell 脚本用 UTF-8 BOM，保证中文注释在 5.1 下也正常
    path.write_text(run_script_text(job, cpus=cpus, gpus=gpus, abq=abq), encoding="utf-8-sig")
    return path


def launch_background(argv: List[str], cwd: Path, log_path: Path) -> int:
    """后台启动 Abaqus，返回 PID；输出重定向到 log_path。"""
    cwd = Path(cwd)
    cwd.mkdir(parents=True, exist_ok=True)
    argv = resolve_argv(argv)
    log = open(str(log_path), "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        argv,
        cwd=str(cwd),
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=_DETACHED,
        env=abq_env(),
    )
    return proc.pid


def sta_state(out_dir: Path, job: str) -> str:
    """读 .sta 判断状态，供 submit_job/job_status 共用。"""
    sta = Path(out_dir) / f"{job}.sta"
    if not sta.exists():
        return "NOT_STARTED"
    text = sta.read_text(encoding="utf-8", errors="replace")
    if "THE ANALYSIS HAS COMPLETED SUCCESSFULLY" in text or "END OF JOB" in text:
        return "COMPLETED"
    return "RUNNING"
