#Requires -Version 5.1

param(
    [switch]$Loop,
    [int]$IntervalSeconds = 10,
    [int]$TailLines = 20
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$BodyRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $BodyRoot
$RunDir = Join-Path $BodyRoot "run"
$LogDir = Join-Path $BodyRoot "logs"

function Read-JsonFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        return $null
    }
    try {
        return Get-Content $Path -Raw -Encoding UTF8 | ConvertFrom-Json
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

function Get-LatestLogFile {
    param(
        [string]$Prefix,
        [switch]$ErrorLog
    )
    $escaped = [regex]::Escape($Prefix)
    $regex = if ($ErrorLog) { "^${escaped}.+\.err\.log$" } else { "^${escaped}.+\.log$" }
    $files = Get-ChildItem -Path $LogDir -File -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match $regex
    } | Sort-Object LastWriteTime
    if (-not $files) {
        return $null
    }
    return $files[-1]
}

function Get-LogTail {
    param([string]$Path, [int]$Lines)
    if (-not $Path -or -not (Test-Path $Path)) {
        return @()
    }
    try {
        return @(Get-Content -Path $Path -Tail $Lines -Encoding UTF8)
    } catch {
        return @("[log read failed] $Path")
    }
}

function Get-KeyAlerts {
    param([string[]]$Lines)
    $alerts = @()
    foreach ($line in ($Lines | Where-Object { $_ })) {
        if ($line -match 'EPERM|Traceback|Assertion failed|ModuleNotFoundError|执行异常|failed|crashed|ERROR') {
            $alerts += $line
        }
    }
    return $alerts | Select-Object -Last 12
}

function Show-StateLine {
    param(
        [string]$Name,
        [object]$State,
        [string]$PidField = "pid",
        [string]$PhaseField = "state"
    )
    if (-not $State) {
        Write-Host ("{0,-12}: missing" -f $Name)
        return
    }
    $processId = 0
    try { $processId = [int]$State.$PidField } catch { $processId = 0 }
    $alive = if (Test-PidAlive $processId) { "alive" } else { "dead" }
    $phase = ""
    try { $phase = [string]$State.$PhaseField } catch { $phase = "" }
    $updated = ""
    try { $updated = [string]$State.updated_at } catch { $updated = "" }
    $note = ""
    try { $note = [string]$State.note } catch { $note = "" }
    Write-Host ("{0,-12}: pid={1} ({2}) state={3} updated_at={4} note={5}" -f $Name, $processId, $alive, $phase, $updated, $note)
}

function Show-WatchSnapshot {
    try {
        Clear-Host
    } catch {
    }
    Write-Host ("[{0}] Butler Stack Watch" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
    Write-Host ""

    $mainState = Read-JsonFile (Join-Path $RunDir "butler_bot_main_state.json")
    $hbRunState = Read-JsonFile (Join-Path $RunDir "heartbeat_run_state.json")
    $hbWatchdog = Read-JsonFile (Join-Path $RunDir "heartbeat_watchdog_state.json")

    Show-StateLine -Name "main" -State $mainState -PidField "pid" -PhaseField "state"
    Show-StateLine -Name "heartbeat" -State $hbRunState -PidField "heartbeat_pid" -PhaseField "phase"
    Show-StateLine -Name "watchdog" -State $hbWatchdog -PidField "heartbeat_pid" -PhaseField "state"
    Write-Host ""

    $mainLog = Get-LatestLogFile -Prefix "butler_bot_202"
    $mainErrLog = Get-LatestLogFile -Prefix "butler_bot_202" -ErrorLog
    $hbLog = Get-LatestLogFile -Prefix "butler_bot_heartbeat_"
    $hbErrLog = Get-LatestLogFile -Prefix "butler_bot_heartbeat_" -ErrorLog

    $mainTail = Get-LogTail -Path $mainLog.FullName -Lines $TailLines
    $hbTail = Get-LogTail -Path $hbLog.FullName -Lines $TailLines
    $mainErrTail = Get-LogTail -Path $mainErrLog.FullName -Lines ([Math]::Min($TailLines, 20))
    $hbErrTail = Get-LogTail -Path $hbErrLog.FullName -Lines ([Math]::Min($TailLines, 20))
    $alerts = Get-KeyAlerts -Lines @($mainTail + $hbTail + $mainErrTail + $hbErrTail)

    Write-Host ("main log     : {0}" -f ($(if ($mainLog) { $mainLog.FullName } else { "missing" })))
    Write-Host ("heartbeat log: {0}" -f ($(if ($hbLog) { $hbLog.FullName } else { "missing" })))
    Write-Host ""

    Write-Host "[alerts]"
    if ($alerts.Count -eq 0) {
        Write-Host "  none"
    } else {
        $alerts | ForEach-Object { Write-Host "  $_" }
    }
    Write-Host ""

    Write-Host "[heartbeat tail]"
    $hbTail | ForEach-Object { Write-Host "  $_" }
    Write-Host ""

    Write-Host "[main err tail]"
    if ($mainErrTail.Count -eq 0) {
        Write-Host "  (empty)"
    } else {
        $mainErrTail | ForEach-Object { Write-Host "  $_" }
    }
    Write-Host ""

    Write-Host "[heartbeat err tail]"
    if ($hbErrTail.Count -eq 0) {
        Write-Host "  (empty)"
    } else {
        $hbErrTail | ForEach-Object { Write-Host "  $_" }
    }
}

if ($Loop) {
    while ($true) {
        Show-WatchSnapshot
        Start-Sleep -Seconds ([Math]::Max(2, $IntervalSeconds))
    }
} else {
    Show-WatchSnapshot
}
