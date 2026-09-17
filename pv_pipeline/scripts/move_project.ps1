<#
.SYNOPSIS
  物件の作業一式を別ドライブ（外付けSSD等）へ移す。Cドライブを使いたくないとき用。

.DESCRIPTION
  設定(config.yaml / cuts.yaml)は「コピー」し、容量を食う素材・生成物は「移動」する。
  設定をリポジトリに残すのは、git pull を壊さないため（これらは追跡対象のファイル）。
  素材・生成物は .gitignore 済みなので移動して問題ない。

.EXAMPLE
  .\scripts\move_project.ps1 -To 'G:\pv\villa_test'
  .\scripts\move_project.ps1 -To 'G:\pv\villa_test' -From .\projects\villa_test
#>
param(
    [Parameter(Mandatory = $true)][string]$To,
    [string]$From = ".\projects\villa_test"
)

$ErrorActionPreference = "Stop"
$From = (Resolve-Path $From).Path

$destDrive = (Split-Path -Qualifier $To)
if ($destDrive -and -not (Test-Path $destDrive)) {
    throw "$destDrive が見つからない。外付けドライブが接続されているか確認すること。"
}

New-Item -ItemType Directory -Force -Path $To | Out-Null
Write-Host "移動先: $To"

# 1) 設定はコピー（リポジトリ側に原本を残す）
foreach ($name in @("config.yaml", "cuts.yaml")) {
    $src = Join-Path $From $name
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $To $name) -Force
        Write-Host "  コピー: $name"
    }
}

# 2) 素材と生成物は移動（容量を食うのはここ）
foreach ($sub in @("input", "stage1", "stage2", "output", "logs")) {
    $srcDir = Join-Path $From $sub
    $dstDir = Join-Path $To $sub
    New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
    if (-not (Test-Path $srcDir)) { continue }
    $items = Get-ChildItem $srcDir -Force | Where-Object { $_.Name -ne ".gitkeep" }
    if ($items.Count -eq 0) { Write-Host "  $sub : 空"; continue }
    $bytes = (Get-ChildItem $srcDir -Recurse -File -Force | Measure-Object Length -Sum).Sum
    foreach ($item in $items) { Move-Item $item.FullName $dstDir -Force }
    Write-Host ("  移動: {0} ({1:N1} MB)" -f $sub, ($bytes / 1MB))
}

Write-Host ""
Write-Host "完了。以降このパスを既定にするには、PowerShell でこれを実行して開き直すこと:" -ForegroundColor Green
Write-Host "  [Environment]::SetEnvironmentVariable('PVP_PROJECT','$To','User')"
Write-Host ""
Write-Host "今のウィンドウだけで試すなら:"
Write-Host "  `$env:PVP_PROJECT = '$To'"
Write-Host "  python run.py check"
