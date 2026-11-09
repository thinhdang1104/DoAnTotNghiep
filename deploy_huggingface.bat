@echo off
chcp 65001 >nul
title Deploy len Hugging Face Space: MinhThinh/DoAn
cd /d "%~dp0"
python deploy_hf.py
echo.
pause
