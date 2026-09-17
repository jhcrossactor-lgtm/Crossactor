<#
.SYNOPSIS
  作業フォルダを外付けドライブへ、成果物を Google Drive の同期フォルダへ振り分ける。

.DESCRIPTION
  Cドライブを使わない構成にする。
    - 作業フォルダ : 素材・中間ファイル・stage2 の _raw が入る。同期させない場所に置く
    - 成果物       : stage1 / stage2 / output / logs だけを同期フォルダへコピーする
  作業フォルダを移し、環境変数 PVP_PROJECT と PVP_DELIVER_TO をユーザー環境に設定する。

.EXAMPLE
  .\scripts\setup_drives.ps1 -WorkDir 'G:\pv\villa_test' -DeliverTo 'G:\GoogleDrive\villa_pv'
#>
param(
    [Parameter(Mandatory = $true)][string]$WorkDir,
    [Parameter(Mandatory = $true)][string]$DeliverTo,
    [string]$From = ".\projects\villa_test"
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

foreach ($path in @($WorkDir, $DeliverTo)) {
    $drive = Split-Path -Qualifier $path
    if ($drive -and -not (Test-Path ($drive + "\"))) {
        throw "$drive が見つからない。ドライブが接続されているか確認すること。"
    }
}
if ($WorkDir.TrimEnd('\') -ieq $DeliverTo.TrimEnd('\')) {
    throw "作業フォルダと成果物の置き場は別にすること（同じだと stage2 の _raw まで同期される）。"
}

Write-Host "作業フォルダ : $WorkDir"
Write-Host "成果物       : $DeliverTo"
Write-Host ""

# 1) 作業一式を移す
& (Join-Path $here "move_project.ps1") -To $WorkDir -From $From

# 2) 成果物の置き場を作る
New-Item -ItemType Directory -Force -Path $DeliverTo | Out-Null

# 3) 次回以降のために環境変数を保存する
[Environment]::SetEnvironmentVariable('PVP_PROJECT', $WorkDir, 'User')
[Environment]::SetEnvironmentVariable('PVP_DELIVER_TO', $DeliverTo, 'User')
Write-Host ""
Write-Host "環境変数を保存した:" -ForegroundColor Green
Write-Host "  PVP_PROJECT    = $WorkDir"
Write-Host "  PVP_DELIVER_TO = $DeliverTo"

# 今のウィンドウにも反映しておく（開き直さずに続けられるように）
$env:PVP_PROJECT = $WorkDir
$env:PVP_DELIVER_TO = $DeliverTo

Write-Host ""
Write-Host "確認:" -ForegroundColor Green
Write-Host "  python run.py check"
Write-Host "続きから:"
Write-Host "  python run.py --stage 1"
