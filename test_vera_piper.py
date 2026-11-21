import json
import os
import pyaudio
from piper.config import SynthesisConfig
from piper.voice import PiperVoice

DOSSIER_PROJET = os.path.dirname(os.path.abspath(__file__))
FICHIER_ONNX = os.path.join(DOSSIER_PROJET, "voix", "fortune-fr-multi.onnx")
FICHIER_JSON = os.path.join(DOSSIER_PROJET, "voix", "model.onnx.json")

PHRASE_TEST = (
    "Bonjour Nobel. Je suis Véra, votre nouvelle assistante personnelle. "
    "Ma voix fonctionne désormais entièrement hors ligne."
)


def lire_audio_piper(voix, texte, speaker_id=0):
    config_synth = SynthesisConfig(speaker_id=speaker_id)
    p = pyaudio.PyAudio()
    flux = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=voix.config.sample_rate,
        output=True,
    )
    try:
        for chunk in voix.synthesize(texte, syn_config=config_synth):
            flux.write(chunk.audio_int16_bytes)
    finally:
        flux.stop_stream()
        flux.close()
        p.terminate()


def main():
    if not os.path.exists(FICHIER_ONNX) or not os.path.exists(FICHIER_JSON):
        print("Fichiers introuvables dans voix\\. Vérifie fortune-fr-multi.onnx et model.onnx.json.")
        return

    with open(FICHIER_JSON, "r", encoding="utf-8") as f:
        meta = json.load(f)

    speaker_map = meta.get("speaker_id_map", {})
    nb_speakers = meta.get("num_speakers", 1)

    print("Chargement du modèle ItsRealFortune...")
    voix = PiperVoice.load(FICHIER_ONNX, config_path=FICHIER_JSON)
    print(f"Modèle prêt ({nb_speakers} speakers) : {speaker_map}\n")

    id_vers_nom = {v: k for k, v in speaker_map.items()}

    while True:
        print("Options :")
        print("  - Tape un numéro (0 à 6) pour écouter un speaker précis")
        print("  - Tape 'tous' pour écouter les 7 speakers à la suite")
        print("  - Tape 'q' pour quitter")
        choix = input("\nTon choix : ").strip().lower()

        if choix == "q":
            break
        elif choix == "tous":
            for sid in range(nb_speakers):
                nom = id_vers_nom.get(sid, f"Speaker {sid}")
                print(f"\n[Speaker {sid} - {nom}] En cours de lecture...")
                lire_audio_piper(voix, PHRASE_TEST, speaker_id=sid)
        elif choix.isdigit() and 0 <= int(choix) < nb_speakers:
            sid = int(choix)
            nom = id_vers_nom.get(sid, f"Speaker {sid}")
            print(f"\n[Speaker {sid} - {nom}] En cours de lecture...")
            lire_audio_piper(voix, PHRASE_TEST, speaker_id=sid)
        else:
            print("Choix invalide.")


if __name__ == "__main__":
    main()