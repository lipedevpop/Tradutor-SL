@echo off
setlocal
cd /d "%~dp0"
if not exist ".previous-version.json" goto missing
if not exist ".venv\Scripts\pythonw.exe" goto missing
echo Feche o tradutor antes de continuar.
pause
start "" ".venv\Scripts\pythonw.exe" iniciar.py --rollback
exit /b 0
:missing
echo Ainda nao existe uma versao anterior disponivel nesta instalacao.
pause
exit /b 1
