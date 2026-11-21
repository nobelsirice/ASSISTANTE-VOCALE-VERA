@echo off
chcp 65001 >nul
title VERA - Administration

cd /d "%~dp0"

echo ==================================================
echo         ADMINISTRATION VISUELLE DE VERA
echo ==================================================
echo.

:: 1. Verification de Node.js et npm
where node >nul 2>&1
if errorlevel 1 goto NODE_ABSENT
where npm >nul 2>&1
if errorlevel 1 goto NODE_ABSENT
goto NODE_OK

:NODE_ABSENT
echo ERREUR : Node.js ou npm est introuvable sur cet ordinateur.
echo L'interface d'administration React requiert Node.js (version LTS).
echo.
set /p "CHOIX_NODE=Voulez-vous installer Node.js LTS via winget maintenant ? (O/N) : "
if /i "%CHOIX_NODE%"=="O" goto INSTALLER_NODE
echo Installation annulee. Installez Node.js puis relancez lancer_admin.bat.
pause
exit /b 1

:INSTALLER_NODE
winget install OpenJS.NodeJS.LTS
if errorlevel 1 (
    echo ERREUR : L'installation via winget a echoue.
    pause
    exit /b 1
)
echo.
echo Node.js a ete installe. Fermez ce terminal et rouvrez-le pour actualiser le PATH,
echo puis relancez lancer_admin.bat.
pause
exit /b 0

:NODE_OK
echo [1/5] Node.js et npm detectes.

:: 2. Verification du port 3001 (ne jamais tuer un processus tiers)
echo [2/5] Verification de la disponibilite du port 3001...
powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 3001 -State Listen -ErrorAction SilentlyContinue; if ($c) { $p = Get-Process -Id $c[0].OwningProcess -ErrorAction SilentlyContinue; Write-Host 'OCCUPE par PID' $c[0].OwningProcess '(' $p.ProcessName ')'; exit 1 } else { exit 0 }"
if not errorlevel 1 goto PORT_3001_OK

echo.
echo ERREUR : Le port 3001 est deja utilise (peut-etre par Nob-Candit ou une autre instance).
echo Aucun processus tiers n'a ete arrete. Liberez le port 3001 puis relancez.
pause
exit /b 1

:PORT_3001_OK
echo       Port 3001 disponible.

:: 3. Verification des dependances React
echo [3/5] Verification des dependances React...
if not exist "admin\package.json" goto ERREUR_ADMIN_MANQUANT

set "APPDATA_NOBEL=%LOCALAPPDATA%\NobelAI"
if not exist "%APPDATA_NOBEL%" mkdir "%APPDATA_NOBEL%"
set "EMPREINTE_FILE=%APPDATA_NOBEL%\admin_package.sha256"

powershell -NoProfile -Command "$h = (Get-FileHash 'admin\package.json' -Algorithm SHA256).Hash; $old = if (Test-Path '%EMPREINTE_FILE%') { Get-Content '%EMPREINTE_FILE%' -Raw } else { '' }; if ($h -eq $old.Trim() -and (Test-Path 'admin\node_modules\.bin\vite.cmd')) { exit 0 } else { exit 1 }"
if not errorlevel 1 goto DEPS_REACT_OK

echo       Installation des paquets npm (premier lancement ou package.json modifie)...
pushd admin
call npm install
if errorlevel 1 (
    popd
    echo ERREUR : npm install a echoue.
    pause
    exit /b 1
)
popd
powershell -NoProfile -Command "(Get-FileHash 'admin\package.json' -Algorithm SHA256).Hash | Set-Content '%EMPREINTE_FILE%'"
echo       Dependances React installees.
goto VERIF_SERVEUR

:DEPS_REACT_OK
echo       Dependances React deja a jour.

:: 4. Verification ou demarrage temporaire du serveur local VERA
:VERIF_SERVEUR
echo [4/5] Verification du serveur local VERA...
set "PYTHON_VENV=%~dp0venv\Scripts\python.exe"
set "SERVEUR_LANCE_ICI=0"

if not exist "%PYTHON_VENV%" goto ERREUR_VENV

"%PYTHON_VENV%" -c "import sys; from lanceur import serveur_repond; from config_nobel import lire_runtime; p = lire_runtime().get('port'); sys.exit(0 if isinstance(p, int) and serveur_repond(p) else 1)"
if not errorlevel 1 goto SERVEUR_OK

echo       Serveur absent : demarrage temporaire du serveur local...
"%PYTHON_VENV%" -c "import subprocess; subprocess.Popen([r'%PYTHON_VENV%', 'serveur_nobel.py'], creationflags=0x08000000)"
"%PYTHON_VENV%" -c "import sys; from lanceur import attendre_serveur_pret; sys.exit(0 if attendre_serveur_pret(10.0) else 1)"
if errorlevel 1 goto ERREUR_SERVEUR
set "SERVEUR_LANCE_ICI=1"

:SERVEUR_OK
echo       Serveur local pret.

:: 5. Lancement de Vite sur port 3001 et ouverture dans Brave
echo [5/5] Demarrage de l'interface React sur http://localhost:3001 ...
start "VERA-Vite" /min /D "%~dp0admin" cmd /c "npm run dev"

"%PYTHON_VENV%" -c "import sys; from assistant import attendre_serveur; sys.exit(0 if attendre_serveur('127.0.0.1', 3001, 20) else 1)"
if errorlevel 1 goto ERREUR_VITE

echo Ouverture de http://localhost:3001 dans Brave...
"%PYTHON_VENV%" -c "from assistant import ouvrir_url; ouvrir_url('http://localhost:3001')"

echo.
echo Interface d'administration active sur http://localhost:3001
echo Appuyez sur une touche dans cette fenetre pour arreter l'administration.
echo.

:ATTENTE_ADMIN
pause >nul

taskkill /FI "WINDOWTITLE eq VERA-Vite*" /T /F >nul 2>&1

if "%SERVEUR_LANCE_ICI%"=="1" (
    echo Arret du serveur local demarre par cette session...
    "%PYTHON_VENV%" -c "import urllib.request; from config_nobel import lire_runtime; rt = lire_runtime(); p = rt.get('port'); t = rt.get('token'); req = urllib.request.Request(f'http://127.0.0.1:{p}/api/shutdown', method='POST', headers={'Host': f'127.0.0.1:{p}', 'X-Nobel-Token': t}); urllib.request.urlopen(req, timeout=2)" >nul 2>&1
)
exit /b 0

:ERREUR_ADMIN_MANQUANT
echo ERREUR : Dossier admin\package.json introuvable.
pause
exit /b 1

:ERREUR_VENV
echo ERREUR : Environnement virtuel Python introuvable. Lancez d'abord demarrage_nobel.bat.
pause
exit /b 1

:ERREUR_SERVEUR
echo ERREUR : Impossible de demarrer le serveur local VERA.
pause
exit /b 1

:ERREUR_VITE
echo ERREUR : Le serveur Vite n'a pas repondu sur le port 3001.
taskkill /FI "WINDOWTITLE eq VERA-Vite*" /T /F >nul 2>&1
pause
exit /b 1