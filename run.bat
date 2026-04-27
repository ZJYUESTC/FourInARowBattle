@echo off
setlocal
cd /d %~dp0

if exist .venv\Scripts\python.exe (
  set PY=.venv\Scripts\python.exe
) else (
  if exist C:\Users\HUAWEI\Downloads\AlphaZero_Gomoku-master\.venv_desktop\Scripts\python.exe (
    set PY=C:\Users\HUAWEI\Downloads\AlphaZero_Gomoku-master\.venv_desktop\Scripts\python.exe
  ) else (
    echo [ERROR] Python venv not found.
    echo Create one with:
    echo   py -3.11 -m venv .venv
    echo   .venv\Scripts\python -m pip install -U pip
    echo   .venv\Scripts\python -m pip install -r requirements.txt
    pause
    exit /b 1
  )
)

echo Using Python: %PY%
"%PY%" -m web_ui.launcher
endlocal
