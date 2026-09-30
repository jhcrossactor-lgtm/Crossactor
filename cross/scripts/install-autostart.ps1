# クロをWindowsのスタートアップに登録する（ログオン時に自動起動）
#   powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1
# 解除:  powershell -ExecutionPolicy Bypass -File scripts\uninstall-autostart.ps1
$ErrorActionPreference = "Stop"
$root    = Split-Path -Parent $PSScriptRoot
$startup = [Environment]::GetFolderPath("Startup")
$vbs     = Join-Path $startup "cross-autostart.vbs"
$launch  = Join-Path $root "scripts\launch.ps1"

# VBS 経由で起動すると黒い窓が出ない
$content = @"
Set sh = CreateObject("WScript.Shell")
sh.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""$launch""", 0, False
"@
Set-Content -Path $vbs -Value $content -Encoding ASCII
Write-Host "登録した: $vbs"
Write-Host "次回ログオン時から自動で起動する。今すぐ試すなら:  wscript `"$vbs`""
