@echo off
chcp 65001 >nul
title VERA - Assistante personnelle

cd /d "%~dp0"

echo ==================================================
echo               DEMARRAGE DE VERA
echo ==================================================
echo.

:: 1. Verification / creation de l'environnement virtuel Python 3.13
if exist "venv\Scripts\python.exe" goto VENV_OK
echo [1/8] Environnement virtuel introuvable. Creation avec Python 3.13...
py -3.13 -m venv venv
if errorlevel 1 (
    echo.
    echo ERREUR : Impossible de creer le venv avec Python 3.13.
    echo Verifiez que Python 3.13 est bien installe sur ce PC.
    pause
    exit /b 1
)
echo       Environnement virtuel cree avec succes.
goto VERIF_DEPS

:VENV_OK
echo [1/8] Environnement virtuel Python 3.13 detecte.

:: 2. Verification des bibliotheques Python vocales
:VERIF_DEPS
set "PYTHON_VENV=%~dp0venv\Scripts\python.exe"
echo [2/8] Verification des bibliotheques vocales Python...
"%PYTHON_VENV%" -c "import speech_recognition, pyaudio, pyttsx3, piper, vosk" >nul 2>&1
if not errorlevel 1 goto DEPS_OK

echo       Installation des dependances manquantes depuis requirements.txt...
"%PYTHON_VENV%" -m pip install --upgrade pip
"%PYTHON_VENV%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERREUR : L'installation des dependances a echoue.
    echo Verifiez votre connexion Internet puis relancez ce fichier.
    pause
    exit /b 1
)
echo       Dependances installees avec succes.
goto VERIF_PIPER

:DEPS_OK
echo       Bibliotheques vocales deja installees.

:: 3. Verification du modele vocal Piper (ItsRealFortune)
:VERIF_PIPER
echo [3/8] Verification du modele vocal Piper...
if not exist "voix" mkdir "voix"

if not exist "voix\fortune-fr-multi.onnx" (
    echo       Telechargement de fortune-fr-multi.onnx...
    powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/itsrealfortune/high/fr_FR-itsrealfortune-high.onnx' -OutFile 'voix\fortune-fr-multi.onnx'"
    if errorlevel 1 echo       AVERTISSEMENT : Telechargement impossible. VERA utilisera la voix de secours Windows.
)

if not exist "voix\model.onnx.json" (
    echo       Telechargement de model.onnx.json...
    powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/itsrealfortune/high/fr_FR-itsrealfortune-high.onnx.json' -OutFile 'voix\model.onnx.json'"
    if errorlevel 1 echo       AVERTISSEMENT : Telechargement de la configuration vocale impossible.
)

if exist "voix\fortune-fr-multi.onnx" if exist "voix\model.onnx.json" (
    echo       Modele vocal Piper pret.
)

:: 4. Verification du modele de reconnaissance vocale Vosk
:VERIF_VOSK
echo [4/8] Verification du modele de reconnaissance vocale Vosk...
if exist "modele_vosk\am\final.mdl" goto VOSK_OK

echo       Telechargement et installation du modele francais Vosk (~41 Mo)...
"%PYTHON_VENV%" -c "import urllib.request, zipfile, shutil, os; urllib.request.urlretrieve('https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip', 'vosk-fr.zip'); zipfile.ZipFile('vosk-fr.zip').extractall('.'); shutil.rmtree('modele_vosk', ignore_errors=True); os.rename('vosk-model-small-fr-0.22', 'modele_vosk'); os.remove('vosk-fr.zip')"
if errorlevel 1 (
    echo       AVERTISSEMENT : Telechargement Vosk impossible. VERA utilisera Google en ligne.
    goto VERIF_VISUEL_DEPS
)
echo       Modele Vosk installe avec succes.
goto VERIF_VISUEL_DEPS

:VOSK_OK
echo       Modele Vosk pret.

:: 5. Verification des bibliotheques widget et serveur (PySide6, aiohttp, Pillow)
:VERIF_VISUEL_DEPS
echo [5/8] Verification des bibliotheques graphiques et serveur...
"%PYTHON_VENV%" -c "import PySide6, aiohttp, PIL" >nul 2>&1
if not errorlevel 1 goto VISUEL_DEPS_OK

echo       Installation de PySide6, aiohttp et Pillow...
"%PYTHON_VENV%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo       AVERTISSEMENT : Installation visuelle incomplete. VERA demarrera sans widget.
    goto VERIF_DOSSIERS
)
echo       Bibliotheques graphiques installees.
goto VERIF_DOSSIERS

:VISUEL_DEPS_OK
echo       Bibliotheques graphiques pretes.

:: 6. Creation des dossiers et de la configuration par defaut
:VERIF_DOSSIERS
echo [6/8] Verification des dossiers et de la configuration...
if not exist "config" mkdir "config"
if not exist "assets" mkdir "assets"
if not exist "data" mkdir "data"
"%PYTHON_VENV%" -c "from config_nobel import charger_config; charger_config()" >nul 2>&1
if errorlevel 1 echo       AVERTISSEMENT : Initialisation configuration en echec.
echo       Dossiers et configuration prets.

:: 7. Generation des ressources graphiques si absentes
:VERIF_ASSETS
echo [7/8] Verification des ressources graphiques de VERA...
"%PYTHON_VENV%" generer_assets.py
if errorlevel 1 echo       AVERTISSEMENT : Generation des assets impossible, dessin de secours actif.

:: 8. Lancement supervise de VERA (serveur + widget + assistante)
:LANCEMENT
echo [8/8] Lancement de VERA...
echo.
"%PYTHON_VENV%" lanceur.py

echo.
echo ==================================================
echo   VERA s'est arretee. Appuyez sur une touche...
echo ==================================================
pause