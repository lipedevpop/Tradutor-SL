@echo off
setlocal
cd /d "%~dp0"
title Instalar Tradutor Hot SL
echo Preparacao do Tradutor Hot SL 1.0.0 com Atualizacoes.
echo Este processo instala o detector de idioma e a interface. Aguarde.
echo.
if exist ".venv\Scripts\python.exe" goto dependencies
py -3.12 -c "import tkinter,struct; assert struct.calcsize('P') == 8" >nul 2>&1
if not errorlevel 1 goto py312
py -3.11 -c "import tkinter,struct; assert struct.calcsize('P') == 8" >nul 2>&1
if not errorlevel 1 goto py311
python -c "import sys,tkinter,struct; assert (3,11) <= sys.version_info[:2] <= (3,12); assert struct.calcsize('P') == 8" >nul 2>&1
if not errorlevel 1 goto pythondefault
echo Instale o Python 3.12 de 64 bits pelo site oficial:
echo https://www.python.org/downloads/release/python-31210/
echo Marque Add python.exe to PATH e mantenha Tcl/Tk habilitado.
echo Depois abra este arquivo novamente. Veja LEIA_PRIMEIRO.txt.
pause
exit /b 1
:py312
py -3.12 -m venv .venv
goto checkvenv
:py311
py -3.11 -m venv .venv
goto checkvenv
:pythondefault
python -m venv .venv
:checkvenv
if errorlevel 1 goto failure
:dependencies
".venv\Scripts\python.exe" -m pip install -r app\requirements.txt
if errorlevel 1 goto failure
".venv\Scripts\python.exe" -c "import sys; sys.path.insert(0, 'app'); import tkinter,ssl,json,urllib.request; import deepl_api, soft_ui; from language_filter import EnglishFilter; EnglishFilter()"
if errorlevel 1 goto failure
echo.
echo PRONTO. Abra 2_ABRIR_TRADUTOR.bat para usar.
pause
exit /b 0
:failure
echo.
echo A preparacao nao terminou. Envie um print do erro acima para receber ajuda.
pause
exit /b 1
