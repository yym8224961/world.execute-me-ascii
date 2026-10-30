@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo Python 3 was not found.
    echo Install it from https://www.python.org/downloads/windows/
    echo and tick "Add python.exe to PATH" during setup.
    pause
    exit /b 1
)
%PY% "world-execute-mv-win.pyz" %*
if errorlevel 1 pause