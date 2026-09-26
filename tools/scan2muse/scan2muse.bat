@echo off
rem scan2muse: scanned score folder -> MuseScore (.mscz). See README.md
rem usage: scan2muse.bat "C:\path\to\folder" [options]
chcp 65001 >nul
set PYTHONUTF8=1
if "%~1"=="" (
  echo usage: scan2muse.bat "score folder" [--list] [--limit-files N] [--limit-pages N]
  exit /b 2
)
py "%~dp0scan2muse.py" %*
exit /b %ERRORLEVEL%
