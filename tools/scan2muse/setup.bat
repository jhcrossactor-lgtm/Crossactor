@echo off
rem install scan2muse dependencies (first time only). See README.md
chcp 65001 >nul
set PYTHONUTF8=1
py -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 exit /b 1
py -c "import importlib.metadata as m; [print(d, m.version(d)) for d in ('oemer','onnxruntime-gpu','pymupdf','music21')]"
echo.
echo Setup done. Next: scan2muse.bat "score folder" --limit-files 1 --limit-pages 1
