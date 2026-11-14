@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\run.ps1 -Entry doctor.py --mode graphics
if errorlevel 1 goto missing
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\run.ps1 -Entry run.py --mode graphics --seconds 1800 %*
set "result=%errorlevel%"
if not "%ANDROID_BENCH_NO_PAUSE%"=="1" pause
exit /b %result%
:missing
echo Run Setup-Dependencies.cmd and provide the private firmware inputs first.
if not "%ANDROID_BENCH_NO_PAUSE%"=="1" pause
exit /b 1
