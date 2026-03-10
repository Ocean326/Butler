#Requires -Version 5.1
<#
.SYNOPSIS
    执行 Cursor CLI agent 并将输出推送到飞书
.EXAMPLE
    .\agent-to-feishu.ps1 -WebhookUrl "https://open.feishu.cn/..." -Prompt "整理今日 AI 资讯"
#>

param(
    [Parameter(Mandatory = $true)]
    [string] $WebhookUrl,
    [Parameter(Mandatory = $true)]
    [string] $Prompt,
    [string] $Secret = "",
    [string] $AgentCmd = "$env:LOCALAPPDATA\cursor-agent\versions\dist-package\cursor-agent.cmd",
    [string] $WorkspaceRoot = "c:\Users\Lenovo\Desktop\研究生",
    [string] $Model = "auto",
    [int]    $TimeoutSeconds = 300
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "正在执行 Cursor Agent..."
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $AgentCmd
$psi.Arguments = "-p --force --trust --approve-mcps --model `"$Model`" --output-format text --workspace `"$WorkspaceRoot`" `"$Prompt`""
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true
$psi.WorkingDirectory = $WorkspaceRoot

$p = [System.Diagnostics.Process]::Start($psi)
$stdout = $p.StandardOutput.ReadToEnd()
$stderr = $p.StandardError.ReadToEnd()
$null = $p.WaitForExit($TimeoutSeconds * 1000)
if (-not $p.HasExited) { $p.Kill($true) }

$output = $stdout.Trim()
if (-not $output) { $output = $stderr.Trim() }
if (-not $output) { $output = "（Agent 未返回内容）" }

$maxLen = 4000
if ($output.Length -gt $maxLen) {
    $output = $output.Substring(0, $maxLen) + "`n...[内容已截断]"
}

& "$scriptDir\SendToFeishu.ps1" -WebhookUrl $WebhookUrl -Message $output -Secret $Secret