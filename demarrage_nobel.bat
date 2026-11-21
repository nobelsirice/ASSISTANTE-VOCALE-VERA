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
echo [1/5] Environnement virtuel introuvable. Creation avec Python 3.13...
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
echo [1/5] Environnement virtuel Python 3.13 detecte.

:: 2. Verification des bibliotheques Python
:VERIF_DEPS
set "PYTHON_VENV=%~dp0venv\Scripts\python.exe"
echo [2/5] Verification des bibliotheques Python...
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
echo       Toutes les dependances sont deja installees.

:: 3. Verification du modele vocal Piper (ItsRealFortune)
:VERIF_PIPER
echo [3/5] Verification du modele vocal Piper...
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
echo [4/5] Verification du modele de reconnaissance vocale Vosk...
if exist "modele_vosk\am\final.mdl" goto VOSK_OK

echo       Telechargement et installation du modele francais Vosk (~41 Mo)...
"%PYTHON_VENV%" -c "import urllib.request, zipfile, shutil, os; urllib.request.urlretrieve('https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip', 'vosk-fr.zip'); zipfile.ZipFile('vosk-fr.zip').extractall('.'); shutil.rmtree('modele_vosk', ignore_errors=True); os.rename('vosk-model-small-fr-0.22', 'modele_vosk'); os.remove('vosk-fr.zip')"
if errorlevel 1 (
    echo       AVERTISSEMENT : Telechargement Vosk impossible. VERA utilisera Google en ligne.
    goto LANCEMENT
)
echo       Modele Vosk installe avec succes.
goto LANCEMENT

:VOSK_OK
echo       Modele Vosk pret.

:: 5. Lancement de VERA
:LANCEMENT
echo [5/5] Lancement de VERA...
echo.
"%PYTHON_VENV%" assistant.py

echo.
echo ==================================================
echo   VERA s'est arretee. Appuyez sur une touche...
echo ==================================================
pause