@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" goto missing
start "" ".venv\Scripts\pythonw.exe" iniciar.py
exit /b 0
:missing
echo Primeiro extraia o ZIP e execute 1_INSTALAR.bat.
pause
exit /b 1
