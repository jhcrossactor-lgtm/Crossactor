# クロス 起動スクリプト
#   1) 配信サーバー（node scripts/serve.mjs）を裏で起動（既に動いていればそのまま）
#   2) http://localhost:8787 が応答するまで待つ
#   3) Chrome（無ければ Edge）をアプリ風の全画面ウィンドウで開く
# 手動起動:  powershell -ExecutionPolicy Bypass -File scripts\launch.ps1
# 自動起動:  scripts\install-autostart.ps1 でスタートアップに登録
param(
  [int]$Port = 8787,
  [switch]$NoBrowser
)
$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path -Parent $PSScriptRoot
$url  = "http://localhost:$Port/"

function PortOpen($p) {
  try { $c = New-Object Net.Sockets.TcpClient; $c.Connect("127.0.0.1", $p); $c.Close(); return $true } catch { return $false }
}

# 1) サーバー
if (-not (PortOpen $Port)) {
  $node = (Get-Command node).Source
  if (-not $node) { Write-Host "Node.js が見つかりません。nodejs.org から LTS を入れてください。"; exit 1 }
  $env:PORT = "$Port"   # Windows PowerShell 5.1 には -Environment が無いので環境変数で渡す
  Start-Process -FilePath $node -ArgumentList "`"$root\scripts\serve.mjs`"" -WorkingDirectory $root -WindowStyle Hidden
}

# 2) 応答待ち（最大15秒）
$deadline = (Get-Date).AddSeconds(15)
while (-not (PortOpen $Port) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 300 }

if ($NoBrowser) { exit 0 }

# 3) ブラウザ（専用プロファイルで開く：マイク許可や設定を通常ブラウザと分ける）
$profile = Join-Path $env:LOCALAPPDATA "cross-browser"
$args = @(
  "--app=$url",
  "--start-fullscreen",
  "--user-data-dir=`"$profile`"",
  "--autoplay-policy=no-user-gesture-required",
  "--no-first-run", "--no-default-browser-check", "--disable-session-crashed-bubble"
) -join " "

$candidates = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
  "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
)
$browser = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($browser) { Start-Process -FilePath $browser -ArgumentList $args }
else { Start-Process $url }   # 既定ブラウザで開く（全画面にはならない）
