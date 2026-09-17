@echo off
"%~dp0..\server\.venv\Scripts\python.exe" "%~dp0main.py" --open
if errorlevel 1 pause
