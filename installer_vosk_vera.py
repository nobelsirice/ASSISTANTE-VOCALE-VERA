import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from datetime import datetime

DOSSIER_PROJET = os.path.dirname(os.path.abspath(__file__))
DOSSIER_SAUVEGARDE = os.path.join(DOSSIER_PROJET, "sauvegardes")
DOSSIER_MODELE_VOSK = os.path.join(DOSSIER_PROJET, "modele_vosk")

NOM_ARCHIVE = "vosk-model-small-fr-0.22.zip"
DOSSIER_EXTRAIT = "vosk-model-small-fr-0.22"
URL_MODELE_FR = "https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip"


def verifier_python():
    print(f"[1/5] Vérification de Python : {sys.version.split()[0]} ({sys.executable})")
    if sys.version_info[:2] != (3, 13):
        print("ERREUR : Lance ce script avec .\\venv\\Scripts\\python.exe")
        sys.exit(1)


def sauvegarder_fichiers():
    print("[2/5] Sauvegarde des fichiers existants...")
    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    cible = os.path.join(DOSSIER_SAUVEGARDE, f"backup_vosk_{horodatage}")
    os.makedirs(cible, exist_ok=True)

    for nom in ("assistant.py", "demarrage_nobel.bat", "requirements.txt"):
        src = os.path.join(DOSSIER_PROJET, nom)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(cible, nom))
            print(f"  -> Sauvegardé : {nom}")


def installer_vosk():
    print("[3/5] Vérification / Installation de vosk dans le venv...")
    try:
        import vosk  # noqa: F401
        print("  -> vosk est déjà installé.")
        return
    except ImportError:
        pass

    resultat = subprocess.run([sys.executable, "-m", "pip", "install", "vosk"])
    if resultat.returncode != 0:
        print("ERREUR : L'installation de vosk a échoué.")
        sys.exit(1)
    print("  -> vosk installé avec succès.")


def installer_modele_francais():
    print("[4/5] Installation du modèle français Vosk (vosk-model-small-fr-0.22 - ~41 Mo)...")
    if os.path.exists(os.path.join(DOSSIER_MODELE_VOSK, "am", "final.mdl")):
        print("  -> Le modèle français Vosk est déjà présent dans modele_vosk\\.")
        return

    chemin_zip = os.path.join(DOSSIER_PROJET, NOM_ARCHIVE)
    print(f"  -> Téléchargement depuis {URL_MODELE_FR}...")

    try:
        requete = urllib.request.Request(URL_MODELE_FR, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(requete, timeout=120) as reponse, open(chemin_zip, "wb") as f:
            total = int(reponse.headers.get("Content-Length", 0))
            telecharge = 0
            while True:
                bloc = reponse.read(65536)
                if not bloc:
                    break
                f.write(bloc)
                telecharge += len(bloc)
                if total > 0:
                    pct = int(telecharge * 100 / total)
                    print(f"\r     Progression : {pct}% ({telecharge // (1024*1024)} Mo)", end="", flush=True)
        print()
    except Exception as e:
        print(f"\nERREUR lors du téléchargement : {e}")
        if os.path.exists(chemin_zip):
            os.remove(chemin_zip)
        sys.exit(1)

    print("  -> Extraction de l'archive...")
    with zipfile.ZipFile(chemin_zip, "r") as zf:
        zf.extractall(DOSSIER_PROJET)

    if os.path.exists(DOSSIER_MODELE_VOSK):
        shutil.rmtree(DOSSIER_MODELE_VOSK)
    os.rename(os.path.join(DOSSIER_PROJET, DOSSIER_EXTRAIT), DOSSIER_MODELE_VOSK)
    os.remove(chemin_zip)
    print("  -> Modèle installé dans :", DOSSIER_MODELE_VOSK)


def verifier_chargement():
    print("[5/5] Test de chargement du modèle Vosk...")
    from vosk import Model, SetLogLevel
    SetLogLevel(-1)
    modele = Model(DOSSIER_MODELE_VOSK)
    del modele
    print("  -> Modèle Vosk français chargé et validé avec succès !")


if __name__ == "__main__":
    print("=== INSTALLATION DE VOSK POUR VÉRA ===\n")
    verifier_python()
    sauvegarder_fichiers()
    installer_vosk()
    installer_modele_francais()
    verifier_chargement()
    print("\nTout est prêt ! Lance maintenant : .\\venv\\Scripts\\python.exe test_vera_vosk.py")