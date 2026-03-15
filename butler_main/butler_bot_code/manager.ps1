#Requires -Version 5.1
<#
.SYNOPSIS
    飞书机器人统一管理：启动、停止、查看状态
.EXAMPLE
    .\manager.ps1 list
    .\manager.ps1 start butler_bot
    .\manager.ps1 stop butler_bot
    .\manager.ps1 stop --all
    .\manager.ps1 status
#>

param(
    [Parameter(Position = 0)]
    [ValidateSet("list", "status", "start", "stop", "restart")]
    [string] $Action = "list",
    [Parameter(Position = 1)]
    [string] $BotName = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WorkspaceRoot = Split-Path -Parent $RootDir
$RegistryPath = Join-Path $RootDir "registry.json"
$RunDir = Join-Path $RootDir "run"
$LogDir = Join-Path $RootDir "logs"

function Get-PythonExecutable {
    $candidates = @(
        (Join-Path $WorkspaceRoot ".venv\Scripts\python.exe"),
        (Join-Path $RootDir "..\.venv\Scripts\python.exe")
    )
    foreach ($candidate in $candidates) {
        $resolved = [System.IO.Path]::GetFullPath($candidate)
        if (Test-Path $resolved) {
            return $resolved
        }
    }
    return "python"
}

function Get-Registry {
    if (-not (Test-Path $RegistryPath)) {
        Write-Error "未找到 registry.json"
    }
    Get-Content $RegistryPath -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Get-RegistryPSObject {
    $reg = Get-Registry
    $reg.PSObject.Properties | ForEach-Object { $_.Name }
}

function Get-BotInfo {
    param([string]$Name)
    $reg = Get-Registry
    $info = $reg.PSObject.Properties[$Name]
    if (-not $info) { return $null }
    [PSCustomObject]@{
        Name   = $Name
        Script = (Join-Path $RootDir $info.Value.script)
        Config = (Join-Path $RootDir $info.Value.config)
        Desc   = $info.Value.description
    }
}

function Get-FeishuBotProcesses {
    Get-Process python* -ErrorAction SilentlyContinue | ForEach-Object {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        if ($cmd -match "feishu-bots" -or $cmd -match "butler_bot\.py") { $_ }
    }
}

function Get-PythonProcessesByCommandPattern {
    param([string]$Pattern)
    Get-Process python* -ErrorAction SilentlyContinue | ForEach-Object {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        if ($cmd -and ($cmd -match $Pattern)) { $_ }
    }
}

function Get-ButlerMainProcesses {
    Get-PythonProcessesByCommandPattern "butler_bot\.py"
}

function Get-HeartbeatSidecarProcesses {
    Get-PythonProcessesByCommandPattern "heartbeat_service_runner\.py"
}

function Stop-ProcessesById {
    param([int[]]$ProcessIds, [string]$Label = "进程")
    $killed = @()
    foreach ($processId in ($ProcessIds | Where-Object { $_ -gt 0 } | Sort-Object -Unique)) {
        if (-not (Test-PidAlive $processId)) {
            continue
        }
        try { taskkill /PID $processId /T /F 2>$null } catch { Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue }
        $killed += $processId
    }
    foreach ($processId in $killed) {
        Write-Host "[$Label] 已停止 (PID=$processId)"
    }
    return $killed.Count
}

function Get-PidFile {
    param([string]$Name)
    Join-Path $RunDir "$Name.pid"
}

function Get-MainStateFile {
    Join-Path $RunDir "butler_bot_main_state.json"
}

function Get-HeartbeatStateFile {
    Join-Path $RunDir "heartbeat_watchdog_state.json"
}

function Get-HeartbeatPidFile {
    Join-Path $RunDir "butler_bot_heartbeat.pid"
}

function Get-MainRuntimeState {
    $stateFile = Get-MainStateFile
    if (-not (Test-Path $stateFile)) {
        return $null
    }
    try {
        return Get-Content $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Get-HeartbeatRuntimeState {
    $stateFile = Get-HeartbeatStateFile
    if (-not (Test-Path $stateFile)) {
        return $null
    }
    try {
        return Get-Content $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Test-PidAlive {
    param([int]$ProcessId)
    if ($ProcessId -le 0) {
        return $false
    }
    return $null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Convert-ToDateTimeOrNull {
    param([string]$Value)
    if (-not $Value) {
        return $null
    }
    try {
        return [DateTime]::ParseExact($Value, 'yyyy-MM-dd HH:mm:ss', [System.Globalization.CultureInfo]::InvariantCulture)
    } catch {
        try {
            return [DateTime]::Parse($Value, [System.Globalization.CultureInfo]::InvariantCulture)
        } catch {
            return $null
        }
    }
}

function Test-MainRuntimeHealthy {
    param($State)
    if (-not $State) {
        return $false
    }
    $processId = 0
    try { $processId = [int]$State.pid } catch { $processId = 0 }
    $updatedAt = Convert-ToDateTimeOrNull ([string]$State.updated_at)
    if ($processId -le 0) {
        return $false
    }
    if (-not (Test-PidAlive $processId)) {
        return $false
    }
    if (-not $updatedAt) {
        return $false
    }
    return (((Get-Date) - $updatedAt).TotalSeconds -le 90)
}

function Get-LogSegmentFile {
    param(
        [string]$Name,
        [bool]$IsError = $false,
        [int]$MaxLines = 1000
    )
    $dateTag = Get-Date -Format 'yyyyMMdd'
    $suffix = if ($IsError) { '.err.log' } else { '.log' }
    $regex = if ($IsError) {
        "^$([regex]::Escape($Name))_${dateTag}_(\d{3})\.err\.log$"
    } else {
        "^$([regex]::Escape($Name))_${dateTag}_(\d{3})\.log$"
    }

    $files = Get-ChildItem $LogDir -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match $regex } | Sort-Object Name
    if (-not $files -or $files.Count -eq 0) {
        return (Join-Path $LogDir ("{0}_{1}_{2}{3}" -f $Name, $dateTag, '001', $suffix))
    }

    $last = $files[-1]
    $lastSeg = 1
    if ($last.Name -match $regex) {
        $lastSeg = [int]$matches[1]
    }

    $lineCount = 0
    try {
        $lineCount = (Get-Content -Path $last.FullName -Encoding UTF8 -ErrorAction SilentlyContinue | Measure-Object -Line).Lines
    } catch {
        $lineCount = 0
    }

    $hasNullByte = Test-FileContainsNullByte -Path $last.FullName

    if (($lineCount -lt $MaxLines) -and (-not $hasNullByte)) {
        return $last.FullName
    }

    $nextSeg = $lastSeg + 1
    return (Join-Path $LogDir ("{0}_{1}_{2:000}{3}" -f $Name, $dateTag, $nextSeg, $suffix))
}

function Test-FileContainsNullByte {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return $false }
    try {
        $fs = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        try {
            $buffer = New-Object byte[] 8192
            while (($read = $fs.Read($buffer, 0, $buffer.Length)) -gt 0) {
                for ($i = 0; $i -lt $read; $i++) {
                    if ($buffer[$i] -eq 0) {
                        return $true
                    }
                }
            }
        } finally {
            $fs.Close()
        }
    } catch {
        return $false
    }
    return $false
}

function Start-Bot {
    param([string]$Name)
    $bot = Get-BotInfo $Name
    if (-not $bot) {
        Write-Error "未知机器人: $Name。可用: $((Get-RegistryPSObject) -join ', ')"
    }
    if (-not (Test-Path $bot.Script)) {
        Write-Error "脚本不存在: $($bot.Script)"
    }
    if (-not (Test-Path $bot.Config)) {
        Write-Error "配置文件不存在: $($bot.Config)，请复制 .example 并填写"
    }
    if ($Name -eq "butler_bot") {
        $mainState = Get-MainRuntimeState
        if (Test-MainRuntimeHealthy $mainState) {
            Write-Host "$Name 已在运行 (PID=$([int]$mainState.pid))"
            return
        }
    }
    $pidFile = Get-PidFile $Name
    if (Test-Path $pidFile) {
        $oldPid = Get-Content $pidFile -ErrorAction SilentlyContinue
        $proc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "$Name 已在运行 (PID=$oldPid)"
            return
        }
    }
    $null = New-Item -ItemType Directory -Path $RunDir -Force
    $null = New-Item -ItemType Directory -Path $LogDir -Force
    $logFile = Get-LogSegmentFile -Name $Name -IsError:$false -MaxLines 1000
    $errFile = Get-LogSegmentFile -Name $Name -IsError:$true -MaxLines 1000
    # 使用 cmd 的追加重定向，避免 PowerShell 5.1 重定向产生 UTF-16 混写乱码。
    # 配合按天+每文件最多 1000 行的分片策略，避免重启覆盖历史日志。
    $env:PYTHONIOENCODING = "utf-8"
    $pythonExe = Get-PythonExecutable
    $cmdLine = "set `"HTTP_PROXY=`" & set `"HTTPS_PROXY=`" & set `"ALL_PROXY=`" & set `"GIT_HTTP_PROXY=`" & set `"GIT_HTTPS_PROXY=`" & set `"NO_PROXY=localhost,127.0.0.1,::1`" & `"$pythonExe`" -X utf8 `"$($bot.Script)`" --config `"$($bot.Config)`" 1>> `"$logFile`" 2>> `"$errFile`""
    $argList = @('/d', '/c', $cmdLine)
    $p = Start-Process -FilePath "cmd.exe" -ArgumentList $argList -WorkingDirectory (Split-Path -Parent $bot.Script) -WindowStyle Hidden -PassThru
    $p.Id | Out-File -FilePath $pidFile -Encoding utf8
    Start-Sleep -Milliseconds 800
    if ($p.HasExited -and $p.ExitCode -ne 0) {
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        Write-Host "启动失败，请查看 err 日志: $errFile"
        return 1
    }
    Write-Host "已启动 $Name (PID=$($p.Id))，日志: $logFile"
}

function Start-HeartbeatSidecar {
    param($Bot)
    Write-Host "[heartbeat] 现由 butler 主进程内置拉起与看护"
}

function Stop-HeartbeatSidecar {
    Remove-Item (Get-HeartbeatPidFile) -Force -ErrorAction SilentlyContinue
}

function Stop-Bot {
    param([string]$Name)
    if ($Name -eq "--all") {
        $procs = Get-FeishuBotProcesses
        foreach ($p in $procs) {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            Write-Host "已终止 PID=$($p.Id)"
        }
        Get-ChildItem $RunDir -Filter "*.pid" -ErrorAction SilentlyContinue | Remove-Item -Force
        Write-Host "已停止全部飞书机器人"
        return
    }
    $pidFile = Get-PidFile $Name
    if (Test-Path $pidFile) {
        $pidVal = Get-Content $pidFile -ErrorAction SilentlyContinue
        $proc = Get-Process -Id $pidVal -ErrorAction SilentlyContinue
        if ($proc) {
            try { taskkill /PID $pidVal /T /F 2>$null } catch { Stop-Process -Id $pidVal -Force -ErrorAction SilentlyContinue }
            Write-Host "已停止 $Name (PID=$pidVal) 及子进程"
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        if ($Name -eq "butler_bot") {
            Stop-ProcessesById -ProcessIds @(Get-ButlerMainProcesses | ForEach-Object { $_.Id }) -Label "main" | Out-Null
        }
        return
    }
    if ($Name -eq "butler_bot") {
        $mainState = Get-MainRuntimeState
        if (Test-MainRuntimeHealthy $mainState) {
            $mainPid = [int]$mainState.pid
            try { taskkill /PID $mainPid /T /F 2>$null } catch { Stop-Process -Id $mainPid -Force -ErrorAction SilentlyContinue }
            Write-Host "已停止 $Name (PID=$mainPid)"
            Stop-ProcessesById -ProcessIds @(Get-ButlerMainProcesses | ForEach-Object { $_.Id }) -Label "main" | Out-Null
            return
        }
    }
    $procs = Get-FeishuBotProcesses | Where-Object {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        $cmd -match $Name
    }
    foreach ($p in $procs) {
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        Write-Host "已终止 $Name (PID=$($p.Id))"
    }
    if (-not $procs) {
        Write-Host "$Name 未在运行"
    }
}

function Show-Status {
    $mainState = Get-MainRuntimeState
    $mainHealthy = Test-MainRuntimeHealthy $mainState
    if ($mainHealthy) {
        Write-Host "运行中的飞书机器人："
        Write-Host "  butler_bot  PID=$([int]$mainState.pid)"
        $updatedText = [string]$mainState.updated_at
        $mainRunningMessage = "对话主进程：running (PID=" + ([int]$mainState.pid) + ", updated_at=" + $updatedText + ")"
        Write-Host $mainRunningMessage
    } else {
        $procs = Get-FeishuBotProcesses
        $legacyMain = $procs | Where-Object {
            $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
            $cmd -match "butler_bot"
        } | Select-Object -First 1
        if (-not $procs) {
            Write-Host "无运行中的飞书机器人"
        } else {
            Write-Host "运行中的飞书机器人："
            foreach ($p in $procs) {
                $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)" -ErrorAction SilentlyContinue).CommandLine
                $name = if ($cmd -match "butler_bot") { "butler_bot" } else { "unknown" }
                Write-Host "  $name  PID=$($p.Id)"
            }
        }
        if ($legacyMain) {
            $legacyMessage = "对话主进程：running (legacy-detect PID=" + $legacyMain.Id + "，等待新状态文件生效)"
            Write-Host $legacyMessage
        } elseif ($mainState) {
            $mainPid = 0
            try { $mainPid = [int]$mainState.pid } catch { $mainPid = 0 }
            $statusText = [string]$mainState.state
            $updatedText = [string]$mainState.updated_at
            $mainStaleMessage = "对话主进程：stale (state=" + $statusText + ", PID=" + $mainPid + ", updated_at=" + $updatedText + ")"
            Write-Host $mainStaleMessage
        } else {
            Write-Host "对话主进程：stopped"
        }
    }

    Write-Host "心跳与意识循环：现由 butler 主进程统一管理"

}

function Show-List {
    $reg = Get-Registry
    Write-Host "已注册机器人："
    $reg.PSObject.Properties | ForEach-Object {
        $n = $_.Name
        $d = $_.Value.description
        Write-Host "  $n  -  $d"
    }
}

# ----- 执行 -----
switch ($Action) {
    "list"   { Show-List; break }
    "status" { Show-Status; break }
    "start"  {
        if (-not $BotName) { Write-Error "请指定机器人名称，如: .\manager.ps1 start butler_bot"; break }
        Start-Bot $BotName
        break
    }
    "stop"   {
        if (-not $BotName) { Write-Error "请指定机器人名称或 --all"; break }
        Stop-Bot $BotName
        break
    }
    "restart" {
        if (-not $BotName) { Write-Error "请指定机器人名称"; break }
        Stop-Bot $BotName
        Start-Sleep -Seconds 4
        Start-Bot $BotName
        break
    }
}
