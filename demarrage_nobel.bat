@echo off
chcp 65001 >nul
title VÉRA - Initialisation et Demarrage
cd /d "%~dp0"

echo ==================================================
echo               DEMARRAGE DE VERA
echo ==================================================
echo.

REM --------------------------------------------------
REM [1/9] Verification de Python et de l'environnement virtuel
REM --------------------------------------------------
if not exist "venv\Scripts\python.exe" (
    echo [1/9] Creation de l'environnement virtuel Python...
    where py >nul 2>&1
    if %errorlevel%==0 (
        py -3 -m venv venv
    ) else (
        python -m venv venv
    )
    if not exist "venv\Scripts\python.exe" (
        echo [ERREUR] Python 3 est introuvable sur cette machine.
        echo Installez Python 3.11+ depuis https://www.python.org/downloads/
        pause
        exit /b 1
    )
)
for /f "tokens=2 delims= " %%v in ('"venv\Scripts\python.exe" --version 2^>^&1') do set PY_VER=%%v
echo [1/9] Environnement virtuel Python %PY_VER% detecte.

REM --------------------------------------------------
REM [2/9] Installation automatique des bibliotheques Python
REM --------------------------------------------------
echo [2/9] Verification des bibliotheques Python...
"venv\Scripts\python.exe" -c "import speech_recognition, pyaudio, pyttsx3, piper, vosk, aiohttp, PySide6, PIL" >nul 2>&1
if not %errorlevel%==0 (
    echo       Installation des dependances manquantes ^(veuillez patienter^)...
    "venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
    "venv\Scripts\python.exe" -m pip install SpeechRecognition pyaudio pyttsx3 piper-tts vosk aiohttp PySide6 pillow --quiet
)
echo       Bibliotheques Python pretes.

REM --------------------------------------------------
REM [3/9] Verification / Telechargement du modele vocal Piper
REM --------------------------------------------------
echo [3/9] Verification du modele vocal Piper...
if not exist "voix" mkdir "voix"
if not exist "voix\fortune-fr-multi.onnx" (
    echo       Telechargement de la voix francaise Piper...
    powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx' -OutFile 'voix\fortune-fr-multi.onnx'"
    powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json' -OutFile 'voix\model.onnx.json'"
)
echo       Modele vocal Piper pret.

REM --------------------------------------------------
REM [4/9] Verification / Telechargement du modele Vosk (hors ligne)
REM --------------------------------------------------
echo [4/9] Verification du modele de reconnaissance vocale Vosk...
if not exist "modele_vosk\am" (
    echo       Telechargement du modele Vosk francais ^(~40 Mo^)...
    powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip' -OutFile 'vosk_tmp.zip'; Expand-Archive -Path 'vosk_tmp.zip' -DestinationPath 'vosk_extract' -Force; if (Test-Path 'modele_vosk') { Remove-Item 'modele_vosk' -Recurse -Force }; Move-Item 'vosk_extract\vosk-model-small-fr-0.22' 'modele_vosk'; Remove-Item 'vosk_tmp.zip','vosk_extract' -Recurse -Force"
)
echo       Modele Vosk pret.

REM --------------------------------------------------
REM [5/9] Verification des dossiers et de la configuration
REM --------------------------------------------------
echo [5/9] Verification des dossiers et de la configuration...
if not exist "assets" mkdir "assets"
if not exist "config" mkdir "config"
if not exist "data" mkdir "data"
"venv\Scripts\python.exe" -c "from config_nobel import charger_config; charger_config()" >nul 2>&1
echo       Dossiers et configuration prets.

REM --------------------------------------------------
REM [6/9] Verification des ressources graphiques par defaut
REM --------------------------------------------------
echo [6/9] Verification des ressources graphiques de VERA...
if exist "generer_assets_defaut.py" (
    "venv\Scripts\python.exe" generer_assets_defaut.py
)

REM --------------------------------------------------
REM [7/9] Compilation de l'interface d'administration si absente
REM --------------------------------------------------
echo [7/9] Verification de l'interface d'administration...
if not exist "admin\dist\index.html" (
    if exist "admin\package.json" (
        where npm >nul 2>&1
        if %errorlevel%==0 (
            echo       Compilation de l'interface d'administration React...
            pushd admin
            call npm install --silent
            call npm run build
            popd
        )
    )
)
echo       Interface d'administration prete.

REM --------------------------------------------------
REM [8/9] Creation de l'icone et du raccourci Bureau VERA
REM --------------------------------------------------
echo [8/9] Verification de l'icone et du raccourci Bureau...
if exist "creer_raccourci_vera.py" (
    "venv\Scripts\python.exe" creer_raccourci_vera.py
)
echo       Raccourci d'application pret.

REM --------------------------------------------------
REM [9/9] Lancement de VERA (Serveur + Widget + Assistante)
REM --------------------------------------------------
echo [9/9] Lancement de VERA...
echo.
"venv\Scripts\python.exe" lanceur.py

echo.
echo ==================================================
echo   VERA s'est arretee. Appuyez sur une touche...
echo ==================================================
pause >nul