@echo off
chcp 65001 >nul
title VERA - Widget flottant

cd /d "%~dp0"

set "PYTHON_VENV=%~dp0venv\Scripts\python.exe"
if not exist "%PYTHON_VENV%" goto ERREUR_VENV

echo Verification du serveur local VERA...
"%PYTHON_VENV%" -c "import sys; from lanceur import serveur_repond; from config_nobel import lire_runtime; p = lire_runtime().get('port'); sys.exit(0 if isinstance(p, int) and serveur_repond(p) else 1)"
if not errorlevel 1 goto LANCER_WIDGET

echo Demarrage du serveur local en arriere-plan...
"%PYTHON_VENV%" -c "import subprocess, os; subprocess.Popen([r'%PYTHON_VENV%', 'serveur_nobel.py'], creationflags=0x08000000)"
"%PYTHON_VENV%" -c "import sys; from lanceur import attendre_serveur_pret; sys.exit(0 if attendre_serveur_pret(10.0) else 1)"
if errorlevel 1 goto ERREUR_SERVEUR

:LANCER_WIDGET
echo Ouverture du widget flottant VERA...
"%PYTHON_VENV%" -c "import subprocess; subprocess.Popen([r'%PYTHON_VENV%', 'widget_nobel.py'], creationflags=0x08000000)"
echo Widget lance.
exit /b 0

:ERREUR_VENV
echo ERREUR : Environnement virtuel introuvable. Lancez d'abord demarrage_nobel.bat.
pause
exit /b 1

:ERREUR_SERVEUR
echo ERREUR : Le serveur local VERA n'a pas demarre.
pause
exit /b 1