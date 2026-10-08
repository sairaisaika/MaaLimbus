@echo off
rem Double-click entry point for tools/start-mirror.ps1 (the desktop shortcut
rem targets this file). It keeps the console open when the window stops, so the
rem reason a run ended is still on screen.
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-mirror.ps1" %*
set "TASK_EXIT=%ERRORLEVEL%"
echo.
echo The mirror window has stopped (exit code %TASK_EXIT%).
echo The console log of this window is the newest build\mirror-console-*.log
pause
exit /b %TASK_EXIT%
