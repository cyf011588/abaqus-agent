<#
Abaqus 批量运行脚本（由 abaqus-agent 提供，可自由修改）
用途：一次按顺序/限并发跑多个 job，每个 job 结束后扫 .sta 判断是否 END OF JOB。

用法：
  .\run_jobs_batch.ps1 -Jobs "A","B","C"                        # 默认 CPU 4 核、并发 1，跑当前目录的作业
  .\run_jobs_batch.ps1 -Jobs "A","B" -Cpus 12 -MaxConcurrent 2   # 12 核、同时跑 2 个
  .\run_jobs_batch.ps1 -Jobs "A" -Cpus 8 -Gpus 1 -Double          # 开 GPU（仅 Explicit）
  .\run_jobs_batch.ps1 -JobsFromFile jobs.txt                    # 从文本读 job 名（每行一个）
  .\run_jobs_batch.ps1 -Jobs "A" -StatusOnly                     # 只查状态不跑
  .\run_jobs_batch.ps1 -Jobs "A" -Dir data\output\cantilever           # 指定作业目录（不想先 cd 进去时用）

说明：GPU 只有 Abaqus/Explicit 支持；Standard（静力/模态/屈曲/Riks）请保持 -Gpus 0。
      -Abq 默认 "abq2020"；不在 PATH 时传绝对路径，如 -Abq "D:\SIMULIA\Commands\abq2020.bat"。
#>
param(
    [string[]]$Jobs = @(),
    [string]$JobsFromFile = "",
    [string]$Dir = "",
    [string]$Abq = "abq2020",
    [int]$Cpus = 4,
    [int]$Gpus = 0,
    [int]$MaxConcurrent = 1,
    [switch]$Double,
    [switch]$StatusOnly
)

$ErrorActionPreference = "Stop"
# 默认用"当前所在目录"：作业文件就在那儿。之前用 $PSScriptRoot 会把目录钉死在 scripts\，
# 导致必须在模型目录里反向引用脚本，纯属自找麻烦。
$workDir = if ($Dir) { (Resolve-Path -LiteralPath $Dir).Path } else { (Get-Location).Path }
if (-not (Test-Path -LiteralPath $workDir -PathType Container)) { throw "作业目录不存在：$workDir" }
$abq = $Abq

Set-Location -LiteralPath $workDir

if ($JobsFromFile) {
    if (-not (Test-Path -LiteralPath $JobsFromFile)) { throw "找不到 job 列表文件：$JobsFromFile" }
    $Jobs = Get-Content -LiteralPath $JobsFromFile | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith("#") }
}
if (-not $Jobs -or $Jobs.Count -eq 0) { throw "请用 -Jobs 或 -JobsFromFile 指定至少一个 job 名" }

Write-Host "工作目录: $workDir"
Write-Host "作业数: $($Jobs.Count) | 每作业 CPU: $Cpus | GPU: $Gpus | 并发上限: $MaxConcurrent`n"

function Get-JobState([string]$name) {
    $sta = Join-Path $workDir "$name.sta"
    if (-not (Test-Path -LiteralPath $sta)) { return "NOT_STARTED" }
    $txt = Get-Content -LiteralPath $sta -Raw
    if ($txt -match "THE ANALYSIS HAS COMPLETED SUCCESSFULLY" -or $txt -match "END OF JOB") { return "COMPLETED" }
    return "RUNNING"
}

if ($StatusOnly) {
    foreach ($j in $Jobs) { Write-Host ("{0,-40} {1}" -f $j, (Get-JobState $j)) }
    return
}

$abqArgsBase = @("cpus=$Cpus", "int", "ask=off")
if ($Gpus -gt 0) { $abqArgsBase += "gpus=$Gpus" }
if ($Double) { $abqArgsBase += "double=both" }

foreach ($j in $Jobs) {
    # 等到正在跑的作业少于并发上限
    while ((@(Get-Job -State Running).Count) -ge $MaxConcurrent) {
        Write-Host "WAIT $j | 当前运行中: $(@(Get-Job -State Running).Count)"
        Start-Sleep -Seconds 20
    }
    $cmd = $abqArgsBase + @("job=$j")
    Write-Host ">>>> 启动 $j | cpus=$Cpus gpus=$Gpus"
    Start-Job -ScriptBlock {
        param($abq, $args2, $wd)
        Set-Location -LiteralPath $wd
        & $abq @args2
    } -ArgumentList $abq, $cmd, $workDir | Out-Null
    Start-Sleep -Seconds 5
}

Write-Host "`n已全部加入队列，等待计算完成……"
Wait-Job * | Out-Null

Write-Host "`n==== 状态汇总 ===="
$report = @()
foreach ($j in $Jobs) {
    $state = Get-JobState $j
    Write-Host ("{0,-40} {1}" -f $j, $state)
    $report += [PSCustomObject]@{ JobName = $j; Status = $state }
}
$report | Out-File -LiteralPath (Join-Path $workDir "JobResult.txt") -Encoding utf8
Write-Host "`n状态已写入 JobResult.txt"
Get-Job | Remove-Job
