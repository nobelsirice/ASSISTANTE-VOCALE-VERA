import os
import shutil
import subprocess
import sys
from datetime import datetime

DOSSIER_PROJET = os.path.dirname(os.path.abspath(__file__))
DOSSIER_VOIX = os.path.join(DOSSIER_PROJET, "voix")
DOSSIER_SAUVEGARDE = os.path.join(DOSSIER_PROJET, "sauvegardes")

FICHIER_ONNX = os.path.join(DOSSIER_VOIX, "fortune-fr-multi.onnx")
FICHIER_JSON = os.path.join(DOSSIER_VOIX, "model.onnx.json")


def verifier_python():
    print(f"[1/4] Vérification de Python : {sys.version.split()[0]} ({sys.executable})")
    if sys.version_info[:2] != (3, 13):
        print("ERREUR : Lance ce script avec .\\venv\\Scripts\\python.exe")
        sys.exit(1)


def sauvegarder_fichiers():
    print("[2/4] Sauvegarde des fichiers existants...")
    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    cible = os.path.join(DOSSIER_SAUVEGARDE, f"backup_{horodatage}")
    os.makedirs(cible, exist_ok=True)

    for nom in ("assistant.py", "demarrage_nobel.bat"):
        src = os.path.join(DOSSIER_PROJET, nom)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(cible, nom))
            print(f"  -> Sauvegardé : {nom}")


def installer_piper():
    print("[3/4] Installation de piper-tts dans le venv...")
    try:
        import piper  # noqa: F401
        print("  -> piper-tts est déjà installé.")
        return
    except ImportError:
        pass

    resultat = subprocess.run([sys.executable, "-m", "pip", "install", "piper-tts"])
    if resultat.returncode != 0:
        print("ERREUR : L'installation de piper-tts a échoué.")
        sys.exit(1)
    print("  -> piper-tts installé avec succès.")


def verifier_modele():
    print("[4/4] Vérification du modèle vocal dans voix\\...")
    os.makedirs(DOSSIER_VOIX, exist_ok=True)

    if not os.path.exists(FICHIER_ONNX) or not os.path.exists(FICHIER_JSON):
        print("ERREUR : Fichiers vocaux introuvables dans :", DOSSIER_VOIX)
        print("Place ces deux fichiers dans le dossier 'voix' :")
        print("  - fortune-fr-multi.onnx")
        print("  - model.onnx.json")
        sys.exit(1)

    from piper.voice import PiperVoice
    voix = PiperVoice.load(FICHIER_ONNX, config_path=FICHIER_JSON)
    print(f"  -> Modèle chargé ! Fréquence : {voix.config.sample_rate} Hz")
    print(f"  -> Speakers disponibles : {voix.config.speaker_id_map}")


if __name__ == "__main__":
    print("=== INSTALLATION DE PIPER POUR VÉRA ===\n")
    verifier_python()
    sauvegarder_fichiers()
    installer_piper()
    verifier_modele()
    print("\nTout est prêt ! Lance maintenant : .\\venv\\Scripts\\python.exe test_vera_piper.py")