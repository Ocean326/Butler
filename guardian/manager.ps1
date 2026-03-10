$ErrorActionPreference = 'Stop'

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunDir = Join-Path $RootDir 'run'
$LogDir = Join-Path $RootDir 'logs'
$PidFile = Join-Path $RunDir 'guardian_bot.pid'
$RestartLockFile = Join-Path $RunDir 'restart_stack.lock'
$ConfigPath = Join-Path $RootDir 'configs\guardian_bot.json'
$PythonExe = 'C:\Users\Lenovo\Desktop\研究生\Butler\butler_main\.venv\Scripts\python.exe'

function Get-GuardianConfig {
    if (-not (Test-Path $ConfigPath)) {
        throw "guardian config not found: $ConfigPath"
    }
    return Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Get-ButlerPaths {
    $cfg = Get-GuardianConfig
    $butlerRoot = [string]$cfg.paths.butler_root
    if (-not $butlerRoot) {
        throw "paths.butler_root is empty in guardian config"
    }
    $butlerRootPath = [System.IO.Path]::GetFullPath($butlerRoot)
    $bodyRoot = Join-Path $butlerRootPath 'butler_bot_code'
    $manager = Join-Path $bodyRoot 'manager.ps1'
    $runner = Join-Path $bodyRoot 'butler_bot\heartbeat_service_runner.py'
    $config = Join-Path $bodyRoot 'configs\butler_bot.json'
    $runDir = Join-Path $bodyRoot 'run'
    if (-not (Test-Path $manager)) { throw "butler manager not found: $manager" }
    if (-not (Test-Path $runner)) { throw "heartbeat runner not found: $runner" }
    if (-not (Test-Path $config)) { throw "butler config not found: $config" }
    [PSCustomObject]@{
        ButlerRoot = $butlerRootPath
        BodyRoot = $bodyRoot
        ButlerManager = $manager
        HeartbeatRunner = $runner
        ButlerConfig = $config
        ButlerRunDir = $runDir
    }
}

function Get-ButlerPythonExecutable {
    param([string]$BodyRoot)
    $butlerMainRoot = Split-Path -Parent $BodyRoot
    $candidates = @(
        (Join-Path $butlerMainRoot '.venv\Scripts\python.exe'),
        (Join-Path (Split-Path -Parent $butlerMainRoot) '.venv\Scripts\python.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return [System.IO.Path]::GetFullPath($candidate)
        }
    }
    return 'python'
}

function Get-HeartbeatProcessIds {
    try {
        $rows = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            $_.Name -like 'python*' -and $_.CommandLine -and ($_.CommandLine -match 'heartbeat_service_runner\.py')
        }
        return @($rows | ForEach-Object { [int]$_.ProcessId } | Where-Object { $_ -gt 0 } | Sort-Object -Unique)
    } catch {
        return @()
    }
}

function Stop-HeartbeatSidecar {
    param([string]$RunDir)
    $pidFile = Join-Path $RunDir 'butler_bot_heartbeat.pid'
    $ids = @()
    if (Test-Path $pidFile) {
        try { $ids += [int](Get-Content $pidFile -ErrorAction SilentlyContinue) } catch { }
    }
        $ids += @(Get-HeartbeatProcessIds)
    $ids = $ids | Where-Object { $_ -gt 0 } | Sort-Object -Unique
    foreach ($id in $ids) {
        try { taskkill /PID $id /T /F 2>$null | Out-Null } catch { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
    }
        Start-Sleep -Milliseconds 800
        $remain = @(Get-HeartbeatProcessIds)
        if ($remain.Count -gt 0) {
            foreach ($id in $remain) {
                try { taskkill /PID $id /T /F 2>$null | Out-Null } catch { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
            }
            Start-Sleep -Milliseconds 800
        }
        $still = @(Get-HeartbeatProcessIds)
        if ($still.Count -gt 0) {
            throw "failed to stop heartbeat sidecar(s): $($still -join ',')"
        }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

function Start-HeartbeatSidecar {
    param(
        [string]$BodyRoot,
        [string]$Runner,
        [string]$Config,
        [string]$PythonExe
    )
    $dateTag = Get-Date -Format 'yyyyMMdd'
    $logDir = Join-Path $BodyRoot 'logs'
    $null = New-Item -ItemType Directory -Path $logDir -Force
    $stdoutLog = Join-Path $logDir ("butler_bot_heartbeat_{0}_001.log" -f $dateTag)
    $stderrLog = Join-Path $logDir ("butler_bot_heartbeat_{0}_001.err.log" -f $dateTag)
        $existing = @(Get-HeartbeatProcessIds)
        if ($existing.Count -gt 0) {
            throw "heartbeat sidecar already exists before start: $($existing -join ',')"
        }
    $args = @('-X', 'utf8', $Runner, '--config', $Config)
    $p = Start-Process -FilePath $PythonExe -ArgumentList $args -WorkingDirectory $BodyRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog
    Start-Sleep -Milliseconds 1500
    if (-not (Test-ProcessAlive -ProcessId ([int]$p.Id))) {
        throw "heartbeat launcher exited immediately (pid=$($p.Id))"
    }
    $after = @(Get-HeartbeatProcessIds)
    if ($after.Count -lt 1) {
        throw "heartbeat sidecar missing after start"
    }

    # heartbeat runner may briefly appear as parent+worker on Windows; prefer runtime state pid when available.
    $runStatePath = Join-Path (Join-Path $BodyRoot 'run') 'heartbeat_run_state.json'
    $selectedPid = [int]$p.Id
    $deadline = (Get-Date).AddSeconds(15)
    while ((Get-Date) -lt $deadline) {
        try {
            if (Test-Path $runStatePath) {
                $runState = Get-Content $runStatePath -Raw -Encoding UTF8 | ConvertFrom-Json
                $statePid = [int]$runState.heartbeat_pid
                if ($statePid -gt 0 -and (Test-ProcessAlive -ProcessId $statePid)) {
                    $selectedPid = $statePid
                    break
                }
            }
        } catch {
        }
        Start-Sleep -Milliseconds 500
    }
    return $selectedPid
}

function Test-ProcessAlive {
    param([int]$ProcessId)
    if ($ProcessId -le 0) { return $false }
    return $null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Acquire-RestartLock {
    Ensure-Dirs
    $currentPid = [int]$PID
    for ($i = 0; $i -lt 3; $i++) {
        try {
            $fs = [System.IO.File]::Open($RestartLockFile, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
            try {
                $bytes = [System.Text.Encoding]::UTF8.GetBytes([string]$currentPid)
                $fs.Write($bytes, 0, $bytes.Length)
            } finally {
                $fs.Close()
            }
            return $currentPid
        } catch {
            $owner = 0
            try { $owner = [int](Get-Content $RestartLockFile -ErrorAction SilentlyContinue) } catch { $owner = 0 }
            if ($owner -gt 0 -and (Test-ProcessAlive -ProcessId $owner)) {
                throw "restart-stack already running by PID=$owner"
            }
            Remove-Item $RestartLockFile -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 300
        }
    }
    throw "failed to acquire restart-stack lock"
}

function Release-RestartLock {
    param([int]$OwnerPid)
    try {
        $owner = 0
        try { $owner = [int](Get-Content $RestartLockFile -ErrorAction SilentlyContinue) } catch { $owner = 0 }
        if ($owner -eq $OwnerPid) {
            Remove-Item $RestartLockFile -Force -ErrorAction SilentlyContinue
        }
    } catch {
    }
}

function Wait-ButlerStackHealthy {
    param(
        [string]$RunDir,
        [int]$TimeoutSeconds = 45
    )
    $mainPath = Join-Path $RunDir 'butler_bot_main_state.json'
    $hbPath = Join-Path $RunDir 'heartbeat_watchdog_state.json'
    $hbRunPath = Join-Path $RunDir 'heartbeat_run_state.json'
    $deadline = (Get-Date).AddSeconds([Math]::Max(10, $TimeoutSeconds))
    while ((Get-Date) -lt $deadline) {
        $mainOk = $false
        $hbOk = $false
        if (Test-Path $mainPath) {
            try {
                $main = Get-Content $mainPath -Raw -Encoding UTF8 | ConvertFrom-Json
                $mpid = [int]$main.pid
                $updated = [datetime]::Parse([string]$main.updated_at)
                $mainOk = (Test-ProcessAlive -ProcessId $mpid) -and (((Get-Date) - $updated).TotalSeconds -le 300)
            } catch { $mainOk = $false }
        }
        if (-not $mainOk) {
            $mainCandidates = Get-Process python* -ErrorAction SilentlyContinue | ForEach-Object {
                $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
                if ($cmd -and ($cmd -match 'butler_bot\.py')) { [int]$_.Id }
            }
            $mainOk = @($mainCandidates).Count -ge 1
        }
        if (Test-Path $hbPath) {
            try {
                $hb = Get-Content $hbPath -Raw -Encoding UTF8 | ConvertFrom-Json
                $hpid = [int]$hb.heartbeat_pid
                $updatedHb = [datetime]::Parse([string]$hb.updated_at)
                $hbProcessOk = (Test-ProcessAlive -ProcessId $hpid) -or (@(Get-HeartbeatProcessIds).Count -ge 1)
                $hbOk = ([string]$hb.state -eq 'running') -and $hbProcessOk -and (((Get-Date) - $updatedHb).TotalSeconds -le 600)
            } catch { $hbOk = $false }
        }
        if ((-not $hbOk) -and (Test-Path $hbRunPath)) {
            try {
                $hbRun = Get-Content $hbRunPath -Raw -Encoding UTF8 | ConvertFrom-Json
                $hpid2 = [int]$hbRun.heartbeat_pid
                $updatedRun = [datetime]::Parse([string]$hbRun.updated_at)
                $hbOk = (Test-ProcessAlive -ProcessId $hpid2) -and (((Get-Date) - $updatedRun).TotalSeconds -le 300)
            } catch { $hbOk = $false }
        }
        if ($mainOk -and $hbOk) {
            return $true
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Restart-ButlerStack {
    $lockOwner = Acquire-RestartLock
    try {
        $paths = Get-ButlerPaths
        $pythonExe = Get-ButlerPythonExecutable -BodyRoot $paths.BodyRoot

        Write-Host "[guardian] standard restart: stop heartbeat sidecar"
        Stop-HeartbeatSidecar -RunDir $paths.ButlerRunDir

        Write-Host "[guardian] standard restart: restart butler talk"
        Push-Location $paths.BodyRoot
        try {
            & $paths.ButlerManager stop butler_bot
            & $paths.ButlerManager start butler_bot
        } finally {
            Pop-Location
        }

        Write-Host "[guardian] standard restart: start heartbeat sidecar"
        try {
            $hbLauncherPid = Start-HeartbeatSidecar -BodyRoot $paths.BodyRoot -Runner $paths.HeartbeatRunner -Config $paths.ButlerConfig -PythonExe $pythonExe
        } catch {
            $msg = $_.Exception.Message
            if (-not $msg) { $msg = "unknown error" }
            throw "start heartbeat sidecar failed: $msg"
        }
        Write-Host "[guardian] heartbeat launcher pid=$hbLauncherPid"

        Write-Host "[guardian] standard restart: verify health"
        if (-not (Wait-ButlerStackHealthy -RunDir $paths.ButlerRunDir -TimeoutSeconds 120)) {
            throw "stack health check failed: main/heartbeat state not healthy within timeout"
        }
        Write-Host "[guardian] standard restart completed: butler talk + heartbeat are healthy"
    } finally {
        Release-RestartLock -OwnerPid $lockOwner
    }
}

function Ensure-Dirs {
    $null = New-Item -ItemType Directory -Path $RunDir -Force
    $null = New-Item -ItemType Directory -Path $LogDir -Force
}

function Get-GuardianProcess {
    if (-not (Test-Path $PidFile)) {
        return $null
    }
    try {
        $pidVal = [int](Get-Content $PidFile -ErrorAction SilentlyContinue)
    } catch {
        return $null
    }
    return Get-Process -Id $pidVal -ErrorAction SilentlyContinue
}

function Start-Guardian {
    Ensure-Dirs
    $proc = Get-GuardianProcess
    if ($proc) {
        Write-Host "guardian already running (PID=$($proc.Id))"
        return
    }
    $stdoutLog = Join-Path $LogDir 'guardian_bot.log'
    $stderrLog = Join-Path $LogDir 'guardian_bot.err.log'
    $cmdLine = 'set "PYTHONPATH=' + $RootDir + '" && "' + $PythonExe + '" -m guardian_bot.main --config "' + $ConfigPath + '" --loop 1>> "' + $stdoutLog + '" 2>> "' + $stderrLog + '"'
    $argList = @('/d', '/c', $cmdLine)
    $process = Start-Process -FilePath 'cmd.exe' -ArgumentList $argList -WorkingDirectory $RootDir -WindowStyle Hidden -PassThru
    $process.Id | Out-File -FilePath $PidFile -Encoding ascii -NoNewline
    Write-Host "guardian started (PID=$($process.Id))"
}

function Stop-Guardian {
    $proc = Get-GuardianProcess
    if (-not $proc) {
        Write-Host 'guardian not running'
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        return
    }
    try {
        taskkill /PID $proc.Id /T /F 2>$null | Out-Null
    } catch {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    Write-Host "guardian stopped (PID=$($proc.Id))"
}

function Show-Status {
    $proc = Get-GuardianProcess
    if ($proc) {
        Write-Host "guardian running (PID=$($proc.Id))"
    } else {
        Write-Host 'guardian not running'
    }
}

$action = if ($args.Count -gt 0) { $args[0] } else { 'status' }
switch ($action) {
    'start' { Start-Guardian }
    'stop' { Stop-Guardian }
    'restart' { Stop-Guardian; Start-Guardian }
    'restart-stack' { Restart-ButlerStack }
    'status' { Show-Status }
    default { throw "Unsupported action: $action" }
}
