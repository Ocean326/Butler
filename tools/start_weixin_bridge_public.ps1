$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $repoRoot "工作区\temp\weixin_runtime"
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null

$out = Join-Path $runtimeDir "weixin_bridge_public.out.log"
$err = Join-Path $runtimeDir "weixin_bridge_public.err.log"

$bridgeProcesses = Get-CimInstance Win32_Process -Filter "name = 'python.exe'" |
    Where-Object { ($_.CommandLine -or "") -like "*-m butler_main.chat.weixi*" -and ($_.CommandLine -or "") -like "*--serve-bridge*" }
foreach ($process in $bridgeProcesses) {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Milliseconds 500

if (Test-Path $out) {
    Remove-Item $out -Force
}
if (Test-Path $err) {
    Remove-Item $err -Force
}

Start-Process `
    -FilePath python `
    -ArgumentList @(
        "-m",
        "butler_main.chat.weixi",
        "--serve-bridge",
        "--bridge-host",
        "0.0.0.0",
        "--bridge-port",
        "8789",
        "--bridge-public-base-url",
        "http://10.134.143.61:8789"
    ) `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $out `
    -RedirectStandardError $err
