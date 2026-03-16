# 扫描 docs/daily-upgrade/ 子目录，生成 INDEX.md 索引页
# 用法：在仓库根目录执行 .\docs\daily-upgrade\gen_index.ps1 或在 daily-upgrade 下执行 ..\..\docs\daily-upgrade\gen_index.ps1

$ErrorActionPreference = 'Stop'
$baseDir = $PSScriptRoot
$indexPath = Join-Path $baseDir 'INDEX.md'

$sb = [System.Text.StringBuilder]::new()
[void]$sb.AppendLine("# Daily Upgrade 索引")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("按日期目录汇总，由 `gen_index.ps1` 自动生成。")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("---")
[void]$sb.AppendLine("")

$dirs = Get-ChildItem -LiteralPath $baseDir -Directory | Where-Object { $_.Name -match '^\d{4}$' } | Sort-Object Name -Descending
foreach ($d in $dirs) {
    $label = $d.Name
    [void]$sb.AppendLine("## $label")
    [void]$sb.AppendLine("")
    $files = Get-ChildItem -LiteralPath $d.FullName -File | Sort-Object Name
    foreach ($f in $files) {
        $rel = "$label/$($f.Name)"
        $name = $f.Name
        [void]$sb.AppendLine("- [$name]($rel)")
    }
    [void]$sb.AppendLine("")
}

$sb.ToString() | Set-Content -Path $indexPath -Encoding UTF8
Write-Host "已生成: $indexPath"
