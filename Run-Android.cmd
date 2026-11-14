@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\run.ps1 -Entry run.py %*
set "result=%errorlevel%"
if not "%ANDROID_BENCH_NO_PAUSE%"=="1" pause
exit /b %result%
