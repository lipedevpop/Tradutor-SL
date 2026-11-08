@echo off
setlocal
cd /d "%~dp0"
echo TRADUTOR HOT SL - DIAGNOSTICO
if exist ".active-version.json" type ".active-version.json"
if exist ".updates\result.json" type ".updates\result.json"
echo.
echo Se o programa falhou ao abrir, os detalhes estao em .updates\startup.log.
echo A chave DeepL nao faz parte deste diagnostico.
pause
