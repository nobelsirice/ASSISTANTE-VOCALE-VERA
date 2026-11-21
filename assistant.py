import ctypes
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import unicodedata
import urllib.parse
import webbrowser
from ctypes import wintypes
from datetime import datetime

import pyaudio
import pyttsx3
import speech_recognition as sr

try:
    from piper.config import SynthesisConfig
    from piper.voice import PiperVoice
    PIPER_DISPONIBLE = True
except ImportError:
    PIPER_DISPONIBLE = False

try:
    from vosk import KaldiRecognizer, Model as VoskModel, SetLogLevel as VoskSetLogLevel
    VOSK_DISPONIBLE = True
except ImportError:
    VOSK_DISPONIBLE = False


# ==========================================
# CONFIGURATION
# ==========================================

NOM_ASSISTANTE = "VÉRA"

DOSSIER_PROJET = os.path.dirname(os.path.abspath(__file__))
FICHIER_VOIX_ONNX = os.path.join(DOSSIER_PROJET, "voix", "fortune-fr-multi.onnx")
FICHIER_VOIX_JSON = os.path.join(DOSSIER_PROJET, "voix", "model.onnx.json")
SPEAKER_PIPER = 1  # 0: normal, 1: joyeuse, 2: storytelling, 3: colere, 4: triste, 5: surprise, 6: interrogative

DOSSIER_MODELE_VOSK = os.path.join(DOSSIER_PROJET, "modele_vosk")

URL_CLAUDE = "https://claude.ai"
URL_CHATGPT = "https://chatgpt.com"
URL_GEMINI = "https://gemini.google.com/app?hl=fr"
URL_SPOTIFY_WEB = "https://open.spotify.com"
URL_ACCUEIL_BRAVE = "https://search.brave.com"
URL_MOODLE = "https://moodle.3il.fr/my/"

# Commande "candidature"
FICHIER_CANDIDATURE = r"C:\Users\nobel\OneDrive\Documents\ELEMENTS\Nob-Candit\lancement.bat"
URL_CANDIDATURE_BRAVE = "http://localhost:3000"
URL_CANDIDATURE_CHROME = "https://app.cvlab.jobs/jobs?time_range=24h&sort=match"
DELAI_SERVEUR = 60  # secondes d'attente maximale avant d'ouvrir localhost:3000

# Processus a ne jamais fermer lors de "ferme tout" (terminaux et systeme)
PROCESSUS_PROTEGES = {
    "cmd.exe",
    "powershell.exe",
    "pwsh.exe",
    "windowsterminal.exe",
    "conhost.exe",
    "explorer.exe",
    "applicationframehost.exe",
    "shellexperiencehost.exe",
    "searchhost.exe",
    "startmenuexperiencehost.exe",
    "textinputhost.exe",
}

# Applications fermees en douceur uniquement (sans /F) pour eviter la perte de donnees
PROCESSUS_DOUX = {"code.exe"}

# Commandes reconnues : (nom, [mots ou expressions declencheurs]).
# L'ordre compte : la premiere correspondance l'emporte.
COMMANDES = [
    ("mode_local", ["mode local", "passe en local", "passer en local", "hors ligne", "local"]),
    ("mode_en_ligne", ["mode en ligne", "passe en ligne", "passer en ligne", "en ligne", "connecte"]),
    ("fermer_tout", ["ferme tout", "fermer tout", "ferme tous", "tout fermer", "ferme"]),
    ("eteindre", ["eteins", "eteint", "eteindre", "eteins l ordinateur", "eteindre l ordinateur", "arrete l ordinateur"]),
    ("masquer_tout", ["masque tout", "masquer tout", "masque tous", "affiche le bureau", "masque", "bureau"]),
    ("arret", ["arrete toi", "arrete", "au revoir", "stop", "bye bye"]),
    ("etat", [
        "comment tu vas", "comment vas tu", "comment ca va", "ca va",
        "tu vas bien", "comment te sens tu", "la forme"
    ]),
    ("bonjour", ["bonjour", "salut", "coucou"]),
    ("heure", ["heure", "quelle heure"]),
    ("candidature", ["candidature", "candidatures", "can", "candid", "cand"]),
    ("recherche", ["recherche", "cherche"]),
    ("moodle", ["moodle", "moodel", "moudule", "mon espace", "cours"]),
    ("claude", ["claude", "clode", "cloud"]),
    ("chatgpt", ["chatgpt", "chat gpt", "chat g p t", "chat gipiti", "j ai pete", "gpt", "chat", "gp"]),
    ("gemini", ["gemini", "gemini ai", "jemini"]),
    ("musique", ["musique", "spotify", "sportify"]),
    ("chrome", ["chrome", "google chrome"]),
    ("navigateur", ["navigateur", "brave"]),
    ("google", ["google"]),
    ("youtube", ["youtube", "you tube"]),
    ("calculatrice", ["calculatrice", "calculette"]),
    ("vscode", ["vs code", "visual studio code", "vscode", "vs", "code"]),
    ("vera", ["vera", "verra", "veras"]),
]

REPONSES_OUI = {
    "oui", "ouais", "confirme", "je confirme", "vas y", "absolument",
    "tout a fait", "d accord", "bien sur", "ok", "affirmatif", "exact"
}
REPONSES_NON = {
    "non", "annule", "annuler", "pas du tout", "stop", "arrete", "negatif"
}

# Mots de liaison naturels pour la grammaire ciblee Vosk (inclut aussi oui/non)
MOTS_LIAISON_GRAMMAIRE = [
    "ouvre", "ouvrir", "lance", "lancer", "demarre", "affiche", "mets", "met",
    "quelle", "quel", "est", "il", "le", "la", "les", "l", "un", "une", "des",
    "mon", "ma", "mes", "ordinateur", "pc", "page", "site", "application",
    "toi", "s", "te", "plait", "merci", "hey", "ok", "dis", "véra", "éteins",
    "éteint", "éteindre", "arrête", "arrêter", "pété", "comment", "tu", "vas",
    "ça", "va", "bien", "sens", "forme", "coucou", "moodle", "chrome", "cours",
    "mode", "passe", "passer", "en", "ligne", "hors", "connecté",
    "oui", "ouais", "confirme", "je", "vas", "y", "absolument", "tout", "à", "fait",
    "accord", "sûr", "non", "annule", "annuler", "pas", "du",
]


def _construire_grammaire_vosk(modele):
    """Filtre les mots connus par le vocabulaire Vosk pour garder un terminal propre."""
    mots_candidats = set(MOTS_LIAISON_GRAMMAIRE)
    for _, declencheurs in COMMANDES:
        for expr in declencheurs:
            for mot in expr.lower().split():
                mots_candidats.add(mot)

    mots_valides = []
    for mot in sorted(mots_candidats):
        try:
            if modele.FindWord(mot) != -1:
                mots_valides.append(mot)
        except Exception:
            mots_valides.append(mot)

    mots_valides.append("[unk]")
    return json.dumps(mots_valides, ensure_ascii=False)


# ==========================================
# INITIALISATION
# ==========================================

reconnaissance = sr.Recognizer()
reconnaissance.energy_threshold = 300
reconnaissance.dynamic_energy_threshold = True
reconnaissance.dynamic_energy_adjustment_damping = 0.15
reconnaissance.dynamic_energy_ratio = 1.5
reconnaissance.pause_threshold = 0.55
reconnaissance.non_speaking_duration = 0.35
reconnaissance.phrase_threshold = 0.25

verrou_voix = threading.Lock()
moteur_piper = None
modele_vosk = None
GRAMMAIRE_VOSK_JSON = None
mode_reconnaissance_en_ligne = True  # Sera ajuste automatiquement au demarrage

if PIPER_DISPONIBLE and os.path.exists(FICHIER_VOIX_ONNX) and os.path.exists(FICHIER_VOIX_JSON):
    try:
        moteur_piper = PiperVoice.load(FICHIER_VOIX_ONNX, config_path=FICHIER_VOIX_JSON)
    except Exception as erreur_init_piper:
        print("Avertissement : impossible de charger Piper, passage sur pyttsx3 :", erreur_init_piper)
        moteur_piper = None

if VOSK_DISPONIBLE and os.path.exists(DOSSIER_MODELE_VOSK):
    try:
        VoskSetLogLevel(-1)
        modele_vosk = VoskModel(DOSSIER_MODELE_VOSK)
        GRAMMAIRE_VOSK_JSON = _construire_grammaire_vosk(modele_vosk)
    except Exception as erreur_init_vosk:
        print("Avertissement : impossible de charger Vosk :", erreur_init_vosk)
        modele_vosk = None

# Acces a l'API Windows (gestion des fenetres et des ecrans)
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

try:
    user32.SetProcessDPIAware()  # coordonnees en pixels reels
except Exception:
    pass

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, wintypes.LPARAM)
MONITORENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
    ctypes.POINTER(wintypes.RECT), ctypes.c_void_p
)


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
user32.GetWindow.restype = wintypes.HWND
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.MoveWindow.argtypes = [
    wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL
]
user32.EnumDisplayMonitors.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, MONITORENUMPROC, ctypes.c_void_p
]
user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


# ==========================================
# OUTILS DE TEXTE & RESEAU
# ==========================================

def internet_disponible(timeout=2.0):
    """Verifie rapidement si une connexion Internet est active."""
    for hote in ("8.8.8.8", "1.1.1.1"):
        try:
            with socket.create_connection((hote, 53), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def normaliser(texte):
    """Minuscules, sans accents, sans ponctuation : facilite la comparaison."""
    texte = unicodedata.normalize("NFD", texte.lower())
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    texte = re.sub(r"[^a-z0-9 ]", " ", texte)
    return re.sub(r"\s+", " ", texte).strip()


def contient(texte, expression):
    """Vrai si l'expression apparait comme mot entier (ou suite de mots entiers)."""
    return re.search(r"\b" + re.escape(expression) + r"\b", texte) is not None


def identifier(texte):
    """Retourne le nom de la commande correspondant au texte, ou None."""
    for nom, declencheurs in COMMANDES:
        if any(contient(texte, d) for d in declencheurs):
            return nom
    return None


# ==========================================
# FONCTION POUR PARLER (PIPER + SECOURS SAPI5)
# ==========================================

MOTS_FEMININS = ["female", "zira", "hortense", "helena", "julie", "amelie", "audrey"]


def _parler_secours_sapi5(texte):
    """Solution de secours hors ligne via Windows SAPI5 si Piper rencontre un souci."""
    moteur = None
    try:
        moteur = pyttsx3.init("sapi5")
        moteur.setProperty("rate", 160)
        moteur.setProperty("volume", 1.0)

        for voix in moteur.getProperty("voices"):
            nom = normaliser(voix.name)
            if any(mot in nom for mot in MOTS_FEMININS):
                moteur.setProperty("voice", voix.id)
                break

        moteur.say(texte)
        moteur.runAndWait()
    except Exception as erreur:
        print("Erreur vocale de secours :", erreur)
    finally:
        if moteur is not None:
            try:
                moteur.stop()
            except Exception:
                pass
            del moteur


def parler(texte):
    print(f"\n{NOM_ASSISTANTE} :", texte)

    with verrou_voix:
        if moteur_piper is not None:
            audio_pa = None
            flux = None
            try:
                config_synth = SynthesisConfig(speaker_id=SPEAKER_PIPER)
                audio_pa = pyaudio.PyAudio()
                flux = audio_pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=moteur_piper.config.sample_rate,
                    output=True,
                )
                for chunk in moteur_piper.synthesize(texte, syn_config=config_synth):
                    flux.write(chunk.audio_int16_bytes)
                return
            except Exception as erreur:
                print("Erreur Piper, bascule sur la voix de secours :", erreur)
            finally:
                if flux is not None:
                    try:
                        flux.stop_stream()
                        flux.close()
                    except Exception:
                        pass
                if audio_pa is not None:
                    try:
                        audio_pa.terminate()
                    except Exception:
                        pass

        _parler_secours_sapi5(texte)


# ==========================================
# FONCTION POUR ECOUTER (GOOGLE EN LIGNE + BASCULE VOSK LOCAL)
# ==========================================

def _transcrire_vosk(audio):
    """
    Double passe Vosk locale sur le meme audio :
    1. Passe grammaire restreinte : reconnait avec precision les commandes connues.
    2. Passe libre : recupere le texte complet (utile pour 'recherche <sujet>').
    """
    if modele_vosk is None:
        return []

    donnees_pcm = audio.get_raw_data(convert_rate=16000, convert_width=2)

    rec_cible = KaldiRecognizer(modele_vosk, 16000, GRAMMAIRE_VOSK_JSON)
    rec_cible.SetMaxAlternatives(3)
    rec_cible.AcceptWaveform(donnees_pcm)
    res_cible = json.loads(rec_cible.FinalResult())

    propositions_ciblees = []
    for alt in res_cible.get("alternatives", []):
        txt = alt.get("text", "").replace("[unk]", "").strip()
        txt = re.sub(r"\s+", " ", txt)
        if txt and txt not in propositions_ciblees:
            propositions_ciblees.append(txt)

    est_recherche = any(
        contient(normaliser(p), "recherche") or contient(normaliser(p), "cherche")
        for p in propositions_ciblees
    )

    if propositions_ciblees and not est_recherche:
        return propositions_ciblees

    rec_libre = KaldiRecognizer(modele_vosk, 16000)
    rec_libre.SetMaxAlternatives(3)
    rec_libre.AcceptWaveform(donnees_pcm)
    res_libre = json.loads(rec_libre.FinalResult())

    propositions_libres = [
        alt["text"].strip()
        for alt in res_libre.get("alternatives", [])
        if alt.get("text", "").strip()
    ]

    if est_recherche and propositions_libres:
        return propositions_libres + propositions_ciblees

    return propositions_ciblees + propositions_libres


def _transcrire_google(audio):
    """Reconnaissance vocale en ligne via Google Speech Recognition."""
    resultat = reconnaissance.recognize_google(audio, language="fr-FR", show_all=True)
    if not resultat or not isinstance(resultat, dict):
        return []
    return [
        alt["transcript"].strip()
        for alt in resultat.get("alternative", [])
        if alt.get("transcript")
    ]


def ecouter(source, timeout=8, phrase_time_limit=12):
    """
    Ecoute une phrase et utilise Google en ligne si active, avec bascule
    automatique et signalee sur Vosk local en cas de perte de connexion.
    """
    global mode_reconnaissance_en_ligne

    mode_affiche = "en ligne" if mode_reconnaissance_en_ligne else "local"
    print(f"\nJ'ecoute vos ordres, maitre... [mode {mode_affiche}]")

    try:
        audio = reconnaissance.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
    except sr.WaitTimeoutError:
        print("Aucune commande detectee.")
        return []

    propositions = []

    if mode_reconnaissance_en_ligne:
        try:
            propositions = _transcrire_google(audio)
        except sr.UnknownValueError:
            print("Je n'ai pas compris votre demande.")
            return []
        except sr.RequestError:
            # Perte de connexion : bascule automatique sur Vosk local
            if modele_vosk is not None:
                mode_reconnaissance_en_ligne = False
                parler(
                    "Maître, j'ai perdu ma connexion Internet. "
                    "Je bascule immédiatement sur ma reconnaissance vocale locale."
                )
                try:
                    propositions = _transcrire_vosk(audio)
                except Exception as erreur_vosk:
                    print("Erreur Vosk :", erreur_vosk)
                    return []
            else:
                parler("Désolée maître, ma connexion est coupée et mon module local est indisponible.")
                return []
    else:
        try:
            propositions = _transcrire_vosk(audio)
        except Exception as erreur_vosk:
            print("Erreur Vosk :", erreur_vosk)
            return []

    if not propositions:
        print("Je n'ai pas compris votre demande.")
        return []

    print('\nTu as dit : "' + propositions[0].lower() + '"')
    return propositions


def choisir_commande(propositions):
    """
    Parcourt les transcriptions alternatives et retient la premiere qui
    correspond a une commande connue. Sinon, retourne la meilleure transcription.
    """
    for proposition in propositions:
        texte = normaliser(proposition)
        nom = identifier(texte)
        if nom:
            return nom, texte
    if propositions:
        return None, normaliser(propositions[0])
    return None, ""


def confirmer_action(source, question):
    """
    Demande une confirmation vocale explicite avant une action sensible.
    Retourne True uniquement en cas de reponse affirmative claire.
    """
    parler(question)
    propositions = ecouter(source, timeout=7, phrase_time_limit=6)
    for proposition in propositions:
        texte = normaliser(proposition)
        if any(contient(texte, mot) for mot in REPONSES_NON):
            return False
        if any(contient(texte, mot) for mot in REPONSES_OUI):
            return True
    return False


# ==========================================
# NAVIGATEURS ET APPLICATIONS
# ==========================================

def trouver_brave():
    chemins = [
        os.path.expandvars(r"%PROGRAMFILES%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        shutil.which("brave"),
    ]
    for chemin in chemins:
        if chemin and os.path.exists(chemin):
            return chemin
    return None


def trouver_chrome():
    chemins = [
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        shutil.which("chrome"),
    ]
    for chemin in chemins:
        if chemin and os.path.exists(chemin):
            return chemin
    return None


def ouvrir_brave(url=URL_ACCUEIL_BRAVE):
    chemin = trouver_brave()
    if chemin:
        subprocess.Popen([chemin, url])
        return True
    return False


def ouvrir_chrome(url=None):
    """Lance Google Chrome installe sur la machine, avec une URL optionnelle."""
    chemin = trouver_chrome()
    if chemin:
        if url:
            subprocess.Popen([chemin, url])
        else:
            subprocess.Popen([chemin])
        return True
    return False


def ouvrir_url(url):
    """Ouvre l'adresse dans Brave, ou dans le navigateur par defaut si Brave est introuvable."""
    if not ouvrir_brave(url):
        webbrowser.open(url)


def ouvrir_spotify():
    try:
        os.startfile("spotify:")  # application Spotify installee
    except OSError:
        ouvrir_url(URL_SPOTIFY_WEB)


def ouvrir_claude_application():
    """Lance l'application Claude installee sur l'ordinateur. Retourne False si introuvable."""
    chemins = [
        os.path.expandvars(r"%LOCALAPPDATA%\AnthropicClaude\claude.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Claude\Claude.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Claude\Claude.exe"),
    ]
    for chemin in chemins:
        if os.path.exists(chemin):
            subprocess.Popen([chemin])
            return True

    try:
        sortie = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "Get-StartApps | Where-Object { $_.Name -eq 'Claude' } "
                "| Select-Object -First 1 -ExpandProperty AppID",
            ],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()
        if sortie:
            subprocess.Popen(["explorer.exe", "shell:AppsFolder\\" + sortie])
            return True
    except Exception:
        pass

    try:
        os.startfile("claude://")
        return True
    except OSError:
        return False


def terminer(processus, force=False):
    commande = ["taskkill", "/IM", processus, "/T"]
    if force:
        commande.insert(1, "/F")
    subprocess.run(commande, capture_output=True, text=True)


def lister_processus_ouverts():
    """Retourne les noms (.exe) de toutes les applications visibles ouvertes, hors terminaux."""
    pid_courant = os.getpid()
    processus_trouves = set()

    def rappel(hwnd, param):
        if (
            user32.IsWindowVisible(hwnd)
            and user32.GetWindowTextLengthW(hwnd) > 0
            and not user32.GetWindow(hwnd, 4)  # GW_OWNER : ignore les fenetres secondaires
        ):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value != pid_courant:
                exe = nom_processus(hwnd)
                if exe and exe not in PROCESSUS_PROTEGES:
                    processus_trouves.add(exe)
        return True

    fonction = WNDENUMPROC(rappel)
    user32.EnumWindows(fonction, 0)
    return processus_trouves


def fermer_tout():
    """Ferme toutes les applications ouvertes sur le bureau sauf les terminaux."""
    cibles = lister_processus_ouverts()
    if not cibles:
        return

    # 1. Fermeture douce d'abord pour toutes les applications
    for processus in cibles:
        terminer(processus, force=False)

    time.sleep(1.5)

    # 2. Fermeture forcee pour tout ce qui reste ouvert (sauf processus doux comme VS Code)
    restants = lister_processus_ouverts()
    for processus in restants:
        if processus not in PROCESSUS_DOUX:
            terminer(processus, force=True)


def eteindre_ordinateur():
    """Arrete completement l'ordinateur Windows."""
    subprocess.run(["shutdown", "/s", "/t", "3"], capture_output=True, text=True)


def masquer_tout():
    """Equivalent de Windows + D : affiche le bureau (ou restaure les fenetres)."""
    VK_LWIN, VK_D, KEYEVENTF_KEYUP = 0x5B, 0x44, 0x0002
    user32.keybd_event(VK_LWIN, 0, 0, 0)
    user32.keybd_event(VK_D, 0, 0, 0)
    user32.keybd_event(VK_D, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)


# ==========================================
# GESTION DES FENETRES ET DES ECRANS
# ==========================================

def nom_processus(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    poignee = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not poignee:
        return ""
    try:
        tampon = ctypes.create_unicode_buffer(520)
        taille = wintypes.DWORD(520)
        if kernel32.QueryFullProcessImageNameW(poignee, 0, tampon, ctypes.byref(taille)):
            return os.path.basename(tampon.value).lower()
        return ""
    finally:
        kernel32.CloseHandle(poignee)


def lister_fenetres(exe):
    """Liste les fenetres principales visibles appartenant au programme donne."""
    trouvees = []

    def rappel(hwnd, param):
        if (
            user32.IsWindowVisible(hwnd)
            and user32.GetWindowTextLengthW(hwnd) > 0
            and not user32.GetWindow(hwnd, 4)  # GW_OWNER : ignore les fenetres secondaires
            and nom_processus(hwnd) == exe
        ):
            trouvees.append(hwnd)
        return True

    fonction = WNDENUMPROC(rappel)
    user32.EnumWindows(fonction, 0)
    return trouvees


def attendre_nouvelle_fenetre(exe, avant, delai=20):
    """Attend l'apparition d'une nouvelle fenetre du programme et la retourne."""
    fin = time.time() + delai
    while time.time() < fin:
        nouvelles = [h for h in lister_fenetres(exe) if h not in avant]
        if nouvelles:
            time.sleep(0.8)  # laisse la fenetre finir de s'afficher
            return nouvelles[0]
        time.sleep(0.4)
    existantes = lister_fenetres(exe)
    return existantes[0] if existantes else None


def ouvrir_fenetre(chemin, exe, url):
    """Ouvre l'adresse dans une nouvelle fenetre et retourne sa poignee."""
    avant = set(lister_fenetres(exe))
    subprocess.Popen([chemin, "--new-window", url])
    return attendre_nouvelle_fenetre(exe, avant)


def lister_ecrans():
    """Retourne les zones utiles des ecrans (gauche, haut, droite, bas), tries de gauche a droite."""
    ecrans = []

    def rappel(moniteur, hdc, rect, param):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(moniteur, ctypes.byref(info)):
            r = info.rcWork
            ecrans.append((r.left, r.top, r.right, r.bottom))
        return True

    fonction = MONITORENUMPROC(rappel)
    user32.EnumDisplayMonitors(None, None, fonction, 0)
    ecrans.sort()
    return ecrans


def placer_fenetres(fenetre_gauche, fenetre_droite):
    """
    Deux ecrans ou plus : une fenetre maximisee par ecran.
    Un seul ecran : les deux fenetres cote a cote, moitie gauche et moitie droite.
    """
    ecrans = lister_ecrans()
    if not ecrans:
        return

    if len(ecrans) >= 2:
        cibles = [(fenetre_gauche, ecrans[0]), (fenetre_droite, ecrans[1])]
        maximiser = True
    else:
        g, h, d, b = ecrans[0]
        milieu = (g + d) // 2
        cibles = [(fenetre_gauche, (g, h, milieu, b)), (fenetre_droite, (milieu, h, d, b))]
        maximiser = False

    for hwnd, (g, h, d, b) in cibles:
        if not hwnd:
            continue
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.MoveWindow(hwnd, g, h, d - g, b - h, True)
        if maximiser:
            user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE


# ==========================================
# COMMANDE "CANDIDATURE"
# ==========================================

def lancer_fichier_bat():
    """Execute le fichier .bat dans sa propre console, reduite dans la barre des taches."""
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = 7  # SW_SHOWMINNOACTIVE
    subprocess.Popen(
        ["cmd.exe", "/c", FICHIER_CANDIDATURE],
        cwd=os.path.dirname(FICHIER_CANDIDATURE),
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        startupinfo=info,
    )


def attendre_serveur(hote, port, delai):
    """Attend que le serveur local reponde. Retourne False si le delai est depasse."""
    fin = time.time() + delai
    while time.time() < fin:
        try:
            with socket.create_connection((hote, port), timeout=1):
                return True
        except OSError:
            time.sleep(1)
    return False


def lancer_candidature():
    if not os.path.exists(FICHIER_CANDIDATURE):
        parler("Je ne trouve pas le fichier de lancement, maître.")
        return

    chemin_brave = trouver_brave()
    chemin_chrome = trouver_chrome()

    if not chemin_brave:
        parler("Je ne parviens pas à localiser Brave, maître.")
        return
    if not chemin_chrome:
        parler("Je ne parviens pas à localiser Chrome, maître.")
        return

    parler("Je lance votre espace de candidature, maître.")
    lancer_fichier_bat()

    if not attendre_serveur("localhost", 3000, DELAI_SERVEUR):
        parler("Le serveur local met du temps à démarrer, maître. J'ouvre quand même vos pages.")

    fenetre_brave = ouvrir_fenetre(chemin_brave, "brave.exe", URL_CANDIDATURE_BRAVE)
    fenetre_chrome = ouvrir_fenetre(chemin_chrome, "chrome.exe", URL_CANDIDATURE_CHROME)

    placer_fenetres(fenetre_brave, fenetre_chrome)


# ==========================================
# EXECUTION DES COMMANDES
# ==========================================

def executer(nom, texte, source):
    """Retourne False pour arreter l'assistante, True sinon."""
    global mode_reconnaissance_en_ligne

    if nom == "mode_local":
        if modele_vosk is None:
            parler("Désolée maître, mon module de reconnaissance locale n'est pas disponible.")
        elif not mode_reconnaissance_en_ligne:
            parler("Je suis déjà en mode de reconnaissance locale, maître.")
        else:
            mode_reconnaissance_en_ligne = False
            parler("Entendu maître. Je passe en mode de reconnaissance vocale locale, entièrement hors ligne.")

    elif nom == "mode_en_ligne":
        if mode_reconnaissance_en_ligne:
            parler("Je suis déjà connectée au service de reconnaissance en ligne, maître.")
        elif internet_disponible():
            mode_reconnaissance_en_ligne = True
            parler("Parfait maître. Je repasse sur le service de reconnaissance en ligne pour une précision maximale.")
        else:
            parler("Désolée maître, aucune connexion Internet n'est détectée. Je reste en mode local.")

    elif nom == "fermer_tout":
        parler("Je ferme toutes les applications, maître. Il ne restera que le terminal.")
        fermer_tout()

    elif nom == "eteindre":
        if confirmer_action(source, "Êtes-vous bien sûr de vouloir éteindre l'ordinateur, maître ?"):
            parler("Très bien, j'éteins votre ordinateur, maître. À bientôt.")
            eteindre_ordinateur()
            return False
        else:
            parler("Très bien maître, j'annule l'extinction de l'ordinateur.")

    elif nom == "masquer_tout":
        parler("J'affiche le bureau, maître.")
        masquer_tout()

    elif nom == "arret":
        parler("Comme vous voudrez, maître. Je vous souhaite une excellente journée.")
        return False

    elif nom == "etat":
        parler(
            "Je me porte à merveille, maître, surtout maintenant que vous êtes là. "
            "Et vous, comment allez-vous ?"
        )

    elif nom == "bonjour":
        parler(
            "Bonjour mon cher et tendre maître Nobel. "
            "Je suis ravie de vous retrouver. "
            "Que puis-je faire pour vous aujourd'hui ?"
        )

    elif nom == "vera":
        parler(
            "Oui, maître ? Je suis toute à vous. "
            "Dites-moi ce qui vous ferait plaisir."
        )

    elif nom == "heure":
        heure = datetime.now().strftime("%H heures %M")
        parler("Il est actuellement " + heure + ", maître.")

    elif nom == "candidature":
        lancer_candidature()

    elif nom == "recherche":
        recherche = re.sub(r"^.*?\b(recherche|cherche)\b", "", texte, count=1).strip()
        if recherche:
            parler("Bien entendu maître. Je m'occupe de votre recherche.")
            ouvrir_url("https://search.brave.com/search?q=" + urllib.parse.quote_plus(recherche))
        else:
            parler("Que souhaitez-vous rechercher, maître ?")

    elif nom == "moodle":
        parler("J'ouvre Moodle sur Chrome, maître.")
        if not ouvrir_chrome(URL_MOODLE):
            parler("Je ne trouve pas Chrome sur votre machine, maître. J'ouvre Moodle dans votre navigateur par défaut.")
            webbrowser.open(URL_MOODLE)

    elif nom == "claude":
        parler("J'ouvre Claude, maître.")
        if not ouvrir_claude_application():
            parler("Je ne trouve pas l'application Claude, maître. J'ouvre la version web.")
            ouvrir_url(URL_CLAUDE)

    elif nom == "chatgpt":
        parler("J'ouvre ChatGPT, maître.")
        ouvrir_url(URL_CHATGPT)

    elif nom == "gemini":
        parler("J'ouvre Gemini, maître.")
        ouvrir_url(URL_GEMINI)

    elif nom == "musique":
        parler("Je lance Spotify, maître.")
        ouvrir_spotify()

    elif nom == "chrome":
        parler("J'ouvre Google Chrome, maître.")
        if not ouvrir_chrome():
            parler("Je suis désolée maître, je ne parviens pas à localiser Chrome sur votre ordinateur.")

    elif nom == "navigateur":
        parler("Avec plaisir maître. Je vous ouvre votre navigateur préféré.")
        if not ouvrir_brave():
            parler("Je suis désolée maître, je ne parviens pas à localiser Brave.")

    elif nom == "google":
        parler("Je vous ouvre Google, maître.")
        ouvrir_url("https://www.google.com")

    elif nom == "youtube":
        parler("Je vous ouvre YouTube, maître.")
        ouvrir_url("https://www.youtube.com")

    elif nom == "calculatrice":
        parler("Je vous ouvre votre calculatrice, maître.")
        subprocess.Popen("calc.exe")

    elif nom == "vscode":
        parler("Je lance votre environnement de développement, maître.")
        subprocess.Popen("code", shell=True)

    else:
        parler("Je suis désolée maître, je ne connais pas encore cette commande.")

    return True


# ==========================================
# PROGRAMME PRINCIPAL
# ==========================================

def main():
    global mode_reconnaissance_en_ligne

    print("\n===================================")
    print(f"              {NOM_ASSISTANTE}")
    print("       Votre assistante")
    print("===================================\n")

    if moteur_piper is not None:
        print(f"Synthèse vocale      : Piper hors ligne (ItsRealFortune - speaker {SPEAKER_PIPER})")
    else:
        print("Synthèse vocale      : Secours Windows SAPI5")

    connexion_active = internet_disponible()
    if connexion_active:
        mode_reconnaissance_en_ligne = True
        print("Reconnaissance vocale: Google en ligne (secours Vosk local prêt)")
    elif modele_vosk is not None:
        mode_reconnaissance_en_ligne = False
        print("Reconnaissance vocale: Vosk local hors ligne (aucun Internet détecté)")
    else:
        mode_reconnaissance_en_ligne = True
        print("Reconnaissance vocale: Indisponible (ni Internet ni Vosk)")

    try:
        with sr.Microphone() as source:
            print("\nCalibration du microphone...")
            reconnaissance.adjust_for_ambient_noise(source, duration=1.5)
            print("Microphone opérationnel.")

            parler(
                "Bonjour mon cher et tendre maître Nobel. "
                "Je suis Véra, votre assistante personnelle. "
                "Je suis prête à recevoir vos ordres."
            )

            if mode_reconnaissance_en_ligne:
                parler(
                    "Pour votre information, maître, mon service de reconnaissance vocale "
                    "est connecté en ligne pour une précision optimale."
                )
            elif modele_vosk is not None:
                parler(
                    "Sachez toutefois, maître, qu'en l'absence de connexion Internet, "
                    "j'utilise mon service de reconnaissance vocale local."
                )

            echecs = 0
            continuer = True

            while continuer:
                propositions = ecouter(source)
                nom, texte = choisir_commande(propositions)

                if not propositions:
                    echecs += 1
                    # Apres plusieurs silences ou echecs, on recalibre le bruit ambiant.
                    if echecs >= 3:
                        reconnaissance.adjust_for_ambient_noise(source, duration=0.7)
                        echecs = 0
                    continue

                echecs = 0
                continuer = executer(nom, texte, source)

    except OSError as erreur:
        print("Erreur microphone :", erreur)
        input("Appuyez sur Entrée pour quitter...")
        return

    print(f"\n{NOM_ASSISTANTE} : Assistante arrêtée.")


if __name__ == "__main__":
    main()