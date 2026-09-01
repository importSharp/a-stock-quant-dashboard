@echo off
chcp 65001 >nul
title 停止涨停雷达
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-mobile.ps1"
pause
