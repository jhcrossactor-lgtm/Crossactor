# クロスのスタートアップ登録を解除する
$vbs = Join-Path ([Environment]::GetFolderPath("Startup")) "cross-autostart.vbs"
if (Test-Path $vbs) { Remove-Item $vbs; Write-Host "解除した: $vbs" } else { Write-Host "登録されていない" }
