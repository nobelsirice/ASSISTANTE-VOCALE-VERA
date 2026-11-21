import json
import os
import speech_recognition as sr
from vosk import KaldiRecognizer, Model, SetLogLevel

DOSSIER_PROJET = os.path.dirname(os.path.abspath(__file__))
DOSSIER_MODELE_VOSK = os.path.join(DOSSIER_PROJET, "modele_vosk")


def main():
    if not os.path.exists(DOSSIER_MODELE_VOSK):
        print("Modèle introuvable. Lance d'abord : .\\venv\\Scripts\\python.exe installer_vosk_vera.py")
        return

    SetLogLevel(-1)
    print("Chargement du modèle vocal français Vosk...")
    modele = Model(DOSSIER_MODELE_VOSK)
    print("Modèle Vosk prêt (100 % hors ligne).\n")

    reconnaissance = sr.Recognizer()
    reconnaissance.energy_threshold = 300
    reconnaissance.dynamic_energy_threshold = True
    reconnaissance.pause_threshold = 0.7

    with sr.Microphone() as source:
        print("Calibration du microphone (1,5 s)...")
        reconnaissance.adjust_for_ambient_noise(source, duration=1.5)
        print("Microphone prêt ! Prononce des commandes (dis 'stop' pour quitter).\n")

        while True:
            print("J'écoute...")
            try:
                audio = reconnaissance.listen(source, timeout=8, phrase_time_limit=12)
            except sr.WaitTimeoutError:
                print("  (Silence détecté)")
                continue

            donnees_pcm = audio.get_raw_data(convert_rate=16000, convert_width=2)
            rec = KaldiRecognizer(modele, 16000)
            rec.SetMaxAlternatives(3)
            rec.AcceptWaveform(donnees_pcm)
            resultat = json.loads(rec.FinalResult())

            alternatives = [
                alt["text"].strip()
                for alt in resultat.get("alternatives", [])
                if alt.get("text", "").strip()
            ]

            if not alternatives:
                print("  -> Rien compris.")
                continue

            print(f"  -> Transcription principale : \"{alternatives[0]}\"")
            if len(alternatives) > 1:
                print(f"  -> Alternatives             : {alternatives[1:]}")

            if "stop" in alternatives[0].lower():
                print("\nFin du test Vosk.")
                break


if __name__ == "__main__":
    main()