#Requires -Version 5.1
<#
.SYNOPSIS
    每日研究管理自动化脚本 - 使用 Cursor CLI 调用各 subagent 完成日常任务
.DESCRIPTION
    执行：1) AI 资讯搜集 2) 工程进度追踪 3) 研究思路整理
    输出落至 工作区 对应目录，可按计划任务每日定时运行
.EXAMPLE
    .\DailyResearchOps.ps1
.EXAMPLE
    .\DailyResearchOps.ps1 -SkipTask 1  # 跳过 AI 资讯任务
#>

param(
    [string[]] $SkipTask = @(),
    [string]   $WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..\\..\\..")).Path,
    [string]   $AgentCmd = "$env:LOCALAPPDATA\cursor-agent\versions\dist-package\cursor-agent.cmd",
    [int]      $TaskTimeoutSeconds = 600,
    [string]   $FeishuWebhookUrl = "",
    [string]   $FeishuSecret = ""
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$BaseDirs = @(
    "工作区",
    "工作区\01_日常事务记录",
    "工作区\02_会议纪要",
    "工作区\03_研究思路",
    "工作区\04_文献整理",
    "工作区\05_工程项目",
    "工作区\06_讨论与技术检索",
    "工作区\99_归档"
)

$DateStr = Get-Date -Format "yyyyMMdd"
$LogDir = Join-Path $WorkspaceRoot "工作区\01_日常事务记录"
$LogFile = Join-Path $LogDir "${DateStr}_每日自动化执行日志.md"

$null = Set-Location $WorkspaceRoot
foreach ($d in $BaseDirs) {
    $fullPath = Join-Path $WorkspaceRoot $d
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
        Write-Host "[INFO] 创建目录: $d"
    }
}

function Write-Log {
    param([string]$Msg, [string]$Level = "INFO")
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$Level] $Msg"
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
    Write-Host $line
}

function Invoke-AgentTask {
    param(
        [string] $TaskName,
        [string] $Prompt,
        [string] $OutputPath,
        [string] $TaskId
    )
    if ($SkipTask -contains $TaskId) {
        Write-Log "跳过任务 $TaskId : $TaskName" "SKIP"
        return $true
    }
    Write-Log "开始任务 $TaskId : $TaskName"
    $fullOutputPath = Join-Path $WorkspaceRoot $OutputPath
    $promptWithOutput = @"
$Prompt

【重要】请将完整输出写入文件：$fullOutputPath
使用 UTF-8 编码，若文件已存在则追加或覆盖均可。
"@
    try {
        $escapedPrompt = $promptWithOutput -replace '\\', '\\\\' -replace '"', '\"'
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $AgentCmd
        $psi.Arguments = "-p --force --trust --approve-mcps --model `"auto`" --workspace `"$WorkspaceRoot`" `"$escapedPrompt`""
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true
        $psi.WorkingDirectory = $WorkspaceRoot
        $p = [System.Diagnostics.Process]::Start($psi)
        $null = $p.StandardOutput.ReadToEnd()
        $stderr = $p.StandardError.ReadToEnd()
        if (-not $p.WaitForExit($TaskTimeoutSeconds * 1000)) {
            $p.Kill($true)
            Write-Log "任务 $TaskId 超时 ($TaskTimeoutSeconds 秒)" "WARN"
            return $false
        }
        if ($p.ExitCode -ne 0) {
            Write-Log "任务 $TaskId 返回非零: $($p.ExitCode)" "WARN"
            if ($stderr) { Write-Log "stderr: $stderr" "WARN" }
            return $false
        }
        Write-Log "完成任务 $TaskId"
        return $true
    } catch {
        Write-Log "任务 $TaskId 异常: $_" "ERROR"
        return $false
    }
}

$header = @"
# 每日自动化执行日志 - $DateStr
生成时间: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

"@
if (-not (Test-Path $LogFile)) { Set-Content -Path $LogFile -Value $header -Encoding UTF8 }

Write-Log "========== 每日研究管理自动化开始 =========="

$prompt1 = @"
你作为技术信息搜集专家，请完成以下任务：

1. 使用互联网检索，收集与「轨迹」「序列」「AI」相关的最新资讯、论文动态、技术博客或行业新闻。
2. 重点关注：轨迹预测、序列建模、大模型、多模态、具身智能等方向。
3. 输出结构化内容：
   - 资讯标题与来源链接
   - 一句话摘要
   - 与研究主题的相关性（高/中/低）
4. 按时间倒序排列，最多 15 条。
"@
$out1 = "工作区\06_讨论与技术检索\${DateStr}_AI资讯.md"
Invoke-AgentTask -TaskName "AI 资讯搜集" -Prompt $prompt1 -OutputPath $out1 -TaskId "1" | Out-Null

$prompt2 = @"
你扮演 engineering-tracker-agent（工程跟踪官）。职责：记录工程进展、实验日志、里程碑，维护风险台账。

请基于工作区 05_工程项目 及当前项目状态，完成：
1. 本周/当前里程碑状态（计划 vs 实际，偏差标记）
2. 风险台账更新（技术/数据/时间风险，影响与缓解措施）
3. 阻塞项与需升级事项
4. 下周工程优先级建议

遵循 engineering-tracker-agent 规范：进度记录需含时间戳与证据；风险需说明影响与缓解。
"@
$out2 = "工作区\05_工程项目\${DateStr}_工程进展与风险.md"
Invoke-AgentTask -TaskName "工程进度追踪" -Prompt $prompt2 -OutputPath $out2 -TaskId "2" | Out-Null

$prompt3 = @"
你扮演 research-ops-agent（研究思路官）。职责：维护思路卡、假设列表、课题路线，做问题拆解。

请基于工作区 03_研究思路 及当前研究主题，完成：
1. 问题拆解（主问题 + 可执行子问题）
2. 可验证假设列表（最多 3 条，须可测试）
3. 验证路径（数据/方法/指标/成功标准）
4. 下阶段实验或调研建议

遵循 research-ops-agent 规范：每个假设须可测试；区分变量与固定因素；区分「想法」与「证据」。
"@
$out3 = "工作区\03_研究思路\${DateStr}_思路整理.md"
Invoke-AgentTask -TaskName "研究思路整理" -Prompt $prompt3 -OutputPath $out3 -TaskId "3" | Out-Null

Write-Log "========== 每日研究管理自动化结束 =========="

if ($FeishuWebhookUrl) {
    try {
        $summary = "【Cursor Agent 每日自动化】`n日期: $DateStr`n任务已完成: AI资讯、工程进度、研究思路`n日志: $LogFile"
        $scriptsRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
        & "$scriptsRoot\feishu-webhook-tools\SendToFeishu.ps1" -WebhookUrl $FeishuWebhookUrl -Message $summary -Secret $FeishuSecret
        Write-Log "已推送摘要到飞书"
    } catch {
        Write-Log "飞书推送失败: $_" "WARN"
    }
}
