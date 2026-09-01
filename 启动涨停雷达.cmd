@echo off
chcp 65001 >nul
title 启动涨停雷达
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-mobile.ps1"
if errorlevel 1 (
  echo.
  echo 启动失败，请查看 data\runtime 下的日志。
  pause
)
