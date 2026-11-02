@echo off
cd /d "%~dp0"
py -3 houston_pipeline.py
if errorlevel 1 pause
