$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $repoRoot "工作区\temp\weixin_runtime"
$stateDir = Join-Path $repoRoot "工作区\weixin_state"
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null

$out = Join-Path $runtimeDir "weixin_client_public.out.log"
$err = Join-Path $runtimeDir "weixin_client_public.err.log"
$session = Join-Path $stateDir "weixin_session.json"

$clientProcesses = Get-CimInstance Win32_Process -Filter "name = 'python.exe'" |
    Where-Object { ($_.CommandLine -or "") -like "*-m butler_main.chat.weixi*" -and ($_.CommandLine -or "") -like "*--run-bridge-client*" }
foreach ($process in $clientProcesses) {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Milliseconds 500

if (Test-Path $out) {
    Remove-Item $out -Force
}
if (Test-Path $err) {
    Remove-Item $err -Force
}
if (Test-Path $session) {
    Remove-Item $session -Force
}

Start-Process `
    -FilePath python `
    -ArgumentList @(
        "-m",
        "butler_main.chat.weixi",
        "--run-bridge-client",
        "--weixin-state-dir",
        $stateDir
    ) `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $out `
    -RedirectStandardError $err
