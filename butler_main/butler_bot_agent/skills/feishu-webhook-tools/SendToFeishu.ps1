#Requires -Version 5.1
<#
.SYNOPSIS
    向飞书群推送消息（用于 Cursor CLI Agent 输出转发）
.EXAMPLE
    .\SendToFeishu.ps1 -WebhookUrl "https://open.feishu.cn/..." -Message "测试消息"
#>

param(
    [Parameter(Mandatory = $true)]
    [string] $WebhookUrl,
    [Parameter(Mandatory = $true)]
    [string] $Message,
    [string] $Secret = ""
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$body = @{
    msg_type = "text"
    content  = @{ text = $Message }
}

if ($Secret) {
    $timestamp = [int][double]::Parse((Get-Date -UFormat %s))
    $stringToSign = "$timestamp`n$Secret"
    $hmac = New-Object System.Security.Cryptography.HMACSHA256
    $hmac.Key = [System.Text.Encoding]::UTF8.GetBytes($Secret)
    $hash = $hmac.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($stringToSign))
    $sign = [Convert]::ToBase64String($hash)
    $body["timestamp"] = $timestamp
    $body["sign"] = $sign
}

try {
    $json = $body | ConvertTo-Json -Depth 3 -Compress
    $response = Invoke-RestMethod -Uri $WebhookUrl -Method Post -Body $json -ContentType "application/json; charset=utf-8"
    if ($response.code -and $response.code -ne 0) {
        Write-Error "飞书返回错误: $($response.msg) (code: $($response.code))"
        exit 1
    }
    Write-Host "消息已推送到飞书"
} catch {
    Write-Error "推送失败: $_"
    exit 1
}