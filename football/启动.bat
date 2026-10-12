@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title AI Tactics Analyst
cd /d "%~dp0"
set PYEXE=D:\envs\yolo\Scripts\python.exe
if not exist "%PYEXE%" set PYEXE=python
"%PYEXE%" desktop.py %*
if errorlevel 1 pause
