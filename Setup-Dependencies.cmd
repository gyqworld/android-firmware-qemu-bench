@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\bootstrap.ps1 %*
set "result=%errorlevel%"
if not "%ANDROID_BENCH_NO_PAUSE%"=="1" pause
exit /b %result%
