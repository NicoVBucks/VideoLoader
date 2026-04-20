@echo off
cd /d %~dp0
python -m uvicorn server:app --port 8000
pause
