@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在跑一次镜牢（默认 600 秒）...
python tools\run_mirror_once.py %*
echo.
echo 日志：build\run-once.log    摘要：build\last-run.json
pause
