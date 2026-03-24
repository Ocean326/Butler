$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $repoRoot "工作区\temp\weixin_runtime"
$stateDir = Join-Path $runtimeDir "weixin_state_official"
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null

$out = Join-Path $runtimeDir "weixin_client_official.out.log"
$err = Join-Path $runtimeDir "weixin_client_official.err.log"
$session = Join-Path $stateDir "weixin_session.json"
$localQrPage = Join-Path $stateDir "weixin_login_qr.html"
$bootstrapFile = Join-Path $runtimeDir "weixin_client_official_bootstrap.py"
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}
$bootstrap = @"
import pathlib
import runpy
import sys

sys.path.insert(0, str(pathlib.Path(r"$repoRoot")))
sys.argv = [
    "butler_main.chat.weixi",
    "--run-bridge-client",
    "--weixin-state-dir",
    r"$stateDir",
    "--official-bridge-base-url",
    "https://ilinkai.weixin.qq.com",
    "--official-cdn-base-url",
    "https://novac2c.cdn.weixin.qq.com/c2c",
]
runpy.run_module("butler_main.chat.weixi", run_name="__main__")
"@

$clientProcesses = Get-CimInstance Win32_Process -Filter "name = 'python.exe'" |
    Where-Object {
        $commandLine = $_.CommandLine -or ""
        $commandLine -like "*weixin_client_official_bootstrap.py*" -or
        ($commandLine -like "*-m butler_main.chat.weixi*" -and $commandLine -like "*--run-bridge-client*")
    }
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
if (Test-Path $localQrPage) {
    Remove-Item $localQrPage -Force
}
if (Test-Path $bootstrapFile) {
    Remove-Item $bootstrapFile -Force
}
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
$bootstrap | Set-Content -Path $bootstrapFile -Encoding UTF8

Start-Process `
    -FilePath $python `
    -ArgumentList @(
        $bootstrapFile
    ) `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $out `
    -RedirectStandardError $err
