@echo off
chcp 65001 >nul
set "BRB_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%BRB_PYTHON%" (
  echo Python runtime not found. Contact the administrator.
  pause
  exit /b 1
)
"%BRB_PYTHON%" -X utf8 "%~dp0..\scripts\setup-ai.py"
pause
