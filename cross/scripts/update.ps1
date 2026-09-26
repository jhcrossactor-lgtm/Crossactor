# クロス 更新スクリプト（Windows PowerShell）
# GitHub の最新版を取得して、このフォルダに上書きする。.env と config.local.js は残す。
#   使い方: このフォルダで  powershell -ExecutionPolicy Bypass -File scripts\update.ps1
param(
  [string]$Branch = "claude/vibrant-edison-y5kyhn",
  [string]$Repo = "https://github.com/jhcrossactor-lgtm/Crossactor.git"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("cross-update-" + [guid]::NewGuid().ToString("N"))

Write-Host "取得中: $Repo ($Branch)"
git clone --quiet --depth 1 -b $Branch $Repo $tmp
if ($LASTEXITCODE -ne 0) { throw "git clone に失敗" }

$src = Join-Path $tmp "cross"
Get-ChildItem -Path $src -Force | ForEach-Object {
  Copy-Item -Path $_.FullName -Destination $root -Recurse -Force
}
Remove-Item -Recurse -Force $tmp
Write-Host "更新完了: $root"
Write-Host "次: node scripts\deploy.mjs --secrets （キー変更なしなら --secrets 不要）"
