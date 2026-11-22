import copy
import json
import os
import re
import secrets
import shutil
import tempfile
import time

DOSSIER_PROJET = os.path.dirname(os.path.abspath(__file__))
DOSSIER_CONFIG = os.path.join(DOSSIER_PROJET, "config")
CHEMIN_CONFIG = os.path.join(DOSSIER_CONFIG, "widget.json")
DOSSIER_DATA = os.path.join(DOSSIER_PROJET, "data")
CHEMIN_RUNTIME = os.path.join(DOSSIER_DATA, "runtime.json")

DOSSIER_APPDATA = os.path.join(
    os.environ.get("LOCALAPPDATA", tempfile.gettempdir()),
    "NobelAI",
)
DOSSIER_LOGS = os.path.join(DOSSIER_APPDATA, "logs")
DOSSIER_CACHE = os.path.join(DOSSIER_APPDATA, "cache")
CHEMIN_SESSION = os.path.join(DOSSIER_APPDATA, "session.json")

CONFIG_DEFAUT = {
    "version": 1,
    "nom_affiche": "VÉRA",
    "fenetre": {
        "mode_taille": "auto",
        "largeur_ratio": 0.3333,
        "hauteur_ratio": 0.2,
        "largeur_px": None,
        "hauteur_px": None,
        "min_largeur": 360,
        "min_hauteur": 180,
        "max_largeur_ratio": 0.6,
        "max_hauteur_ratio": 0.5,
        "ancrage": "bas_droite",
        "marge_x": 24,
        "marge_y": 24,
        "x": None,
        "y": None,
        "toujours_devant": True,
        "visible": True,
        "reduit": False,
        "mode_gif_seul": False,
        "mode_fil_neon": False,
        "taille_reduite": 96,
        "marges_internes": 16,
    },
    "apparence": {
        "couleur_fond": "#171717",
        "opacite_fond": 0.88,
        "image_fond": None,
        "opacite_image_fond": 0.65,
        "couleur_contour": "#00E5FF",
        "epaisseur_contour": 2,
        "couleur_neon": "#00E5FF",
        "couleur_neon_secondaire": "#8A5CFF",
        "intensite_neon": 0.85,
        "rayon_angles": 18,
        "halo": {
            "actif": True,
            "couleur": "#00E5FF",
            "intensite": 0.6,
            "rayon": 40,
        },
        "ombre": {
            "actif": True,
            "couleur": "#000000",
            "opacite": 0.5,
            "flou": 24,
        },
        "transparence_globale": 1.0,
        "animations": {
            "actives": True,
            "vitesse": 1.0,
            "respiration_halo": True,
        },
    },
    "personnage": {
        "image_statique": "assets/vera_statique.png",
        "gif_parole": "assets/vera_parole.gif",
        "expressions": {
            "ecoute": None,
            "reflexion": None,
            "attente": None,
            "erreur": None,
        },
        "taille_pourcent": 90,
        "decalage_x": 0,
        "decalage_y": 0,
    },
    "bulle": {
        "couleur_fond": "#2A2A2E",
        "opacite_fond": 0.92,
        "couleur_texte": "#ECECF1",
        "taille_police": 15,
        "famille_police": "Segoe UI",
        "couleur_contour": "#00E5FF",
        "epaisseur_contour": 1,
        "rayon_angles": 14,
        "largeur_pourcent": 70,
        "hauteur_max_pourcent": 60,
        "decalage_x": 0,
        "decalage_y": 0,
        "caracteres_max": 240,
        "duree_affichage_apres_parole_ms": 4000,
    },
}

_REGEX_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def assurer_dossiers():
    for dossier in (DOSSIER_CONFIG, DOSSIER_DATA, DOSSIER_APPDATA, DOSSIER_LOGS, DOSSIER_CACHE):
        os.makedirs(dossier, exist_ok=True)
    os.makedirs(os.path.join(DOSSIER_PROJET, "assets"), exist_ok=True)


def ecrire_json_atomique(chemin, donnees, backup=False):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    if backup and os.path.exists(chemin):
        try:
            shutil.copy2(chemin, chemin + ".bak")
        except OSError:
            pass

    fd, chemin_tmp = tempfile.mkstemp(
        prefix=".tmp_",
        suffix=".json",
        dir=os.path.dirname(chemin),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(donnees, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        for tentative in range(8):
            try:
                os.replace(chemin_tmp, chemin)
                return
            except PermissionError:
                if tentative == 7:
                    raise
                time.sleep(0.08 * (tentative + 1))
    finally:
        if os.path.exists(chemin_tmp):
            try:
                os.remove(chemin_tmp)
            except OSError:
                pass


def _valider_hex(val, defaut):
    if isinstance(val, str) and _REGEX_HEX.match(val.strip()):
        return val.strip().upper()
    return defaut


def _valider_float(val, defaut, mini, maxi):
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return float(max(mini, min(maxi, val)))
    return float(defaut)


def _valider_int(val, defaut, mini, maxi):
    if isinstance(val, int) and not isinstance(val, bool):
        return int(max(mini, min(maxi, val)))
    if isinstance(val, float):
        return int(max(mini, min(maxi, round(val))))
    return int(defaut)


def _valider_int_opt(val, defaut, mini, maxi):
    if val is None:
        return None
    return _valider_int(val, defaut if defaut is not None else mini, mini, maxi)


def _valider_bool(val, defaut):
    if isinstance(val, bool):
        return val
    return bool(defaut)


def _valider_chemin_interne(val, defaut):
    if val is None:
        return None
    if not isinstance(val, str) or not val.strip():
        return defaut
    rel = val.strip().replace("\\", "/")
    if rel.startswith("/") or ".." in rel.split("/"):
        return defaut
    cible = os.path.abspath(os.path.join(DOSSIER_PROJET, rel))
    base = os.path.abspath(DOSSIER_PROJET)
    if not (cible == base or cible.startswith(base + os.sep)):
        return defaut
    return rel


def valider_config(brut):
    """Valide un dictionnaire de configuration et ignore toute cle inconnue."""
    cfg = copy.deepcopy(CONFIG_DEFAUT)
    if not isinstance(brut, dict):
        return cfg

    if isinstance(brut.get("nom_affiche"), str) and brut["nom_affiche"].strip():
        cfg["nom_affiche"] = brut["nom_affiche"].strip()[:40]

    fen = brut.get("fenetre")
    if isinstance(fen, dict):
        d = cfg["fenetre"]
        if fen.get("mode_taille") in ("auto", "fixe"):
            d["mode_taille"] = fen["mode_taille"]
        d["largeur_ratio"] = _valider_float(fen.get("largeur_ratio"), d["largeur_ratio"], 0.1, 0.9)
        d["hauteur_ratio"] = _valider_float(fen.get("hauteur_ratio"), d["hauteur_ratio"], 0.08, 0.9)
        d["largeur_px"] = _valider_int_opt(fen.get("largeur_px"), d["largeur_px"], 200, 3840)
        d["hauteur_px"] = _valider_int_opt(fen.get("hauteur_px"), d["hauteur_px"], 120, 2160)
        d["min_largeur"] = _valider_int(fen.get("min_largeur"), d["min_largeur"], 160, 1920)
        d["min_hauteur"] = _valider_int(fen.get("min_hauteur"), d["min_hauteur"], 100, 1080)
        d["max_largeur_ratio"] = _valider_float(fen.get("max_largeur_ratio"), d["max_largeur_ratio"], 0.2, 1.0)
        d["max_hauteur_ratio"] = _valider_float(fen.get("max_hauteur_ratio"), d["max_hauteur_ratio"], 0.15, 1.0)
        if fen.get("ancrage") in ("bas_droite", "bas_gauche", "haut_droite", "haut_gauche"):
            d["ancrage"] = fen["ancrage"]
        d["marge_x"] = _valider_int(fen.get("marge_x"), d["marge_x"], 0, 500)
        d["marge_y"] = _valider_int(fen.get("marge_y"), d["marge_y"], 0, 500)
        d["x"] = _valider_int_opt(fen.get("x"), d["x"], -7680, 7680)
        d["y"] = _valider_int_opt(fen.get("y"), d["y"], -4320, 4320)
        d["toujours_devant"] = _valider_bool(fen.get("toujours_devant"), d["toujours_devant"])
        d["visible"] = _valider_bool(fen.get("visible"), d["visible"])
        d["reduit"] = _valider_bool(fen.get("reduit"), d["reduit"])
        d["mode_gif_seul"] = _valider_bool(fen.get("mode_gif_seul"), d["mode_gif_seul"])
        d["mode_fil_neon"] = _valider_bool(fen.get("mode_fil_neon"), d["mode_fil_neon"])
        d["taille_reduite"] = _valider_int(fen.get("taille_reduite"), d["taille_reduite"], 48, 240)
        d["marges_internes"] = _valider_int(fen.get("marges_internes"), d["marges_internes"], 0, 64)

    app = brut.get("apparence")
    if isinstance(app, dict):
        d = cfg["apparence"]
        d["couleur_fond"] = _valider_hex(app.get("couleur_fond"), d["couleur_fond"])
        d["opacite_fond"] = _valider_float(app.get("opacite_fond"), d["opacite_fond"], 0.1, 1.0)
        d["image_fond"] = _valider_chemin_interne(app.get("image_fond"), None)
        d["opacite_image_fond"] = _valider_float(app.get("opacite_image_fond"), d["opacite_image_fond"], 0.05, 1.0)
        d["couleur_contour"] = _valider_hex(app.get("couleur_contour"), d["couleur_contour"])
        d["epaisseur_contour"] = _valider_int(app.get("epaisseur_contour"), d["epaisseur_contour"], 0, 12)
        d["couleur_neon"] = _valider_hex(app.get("couleur_neon"), d["couleur_neon"])
        d["couleur_neon_secondaire"] = _valider_hex(app.get("couleur_neon_secondaire"), d["couleur_neon_secondaire"])
        d["intensite_neon"] = _valider_float(app.get("intensite_neon"), d["intensite_neon"], 0.0, 1.0)
        d["rayon_angles"] = _valider_int(app.get("rayon_angles"), d["rayon_angles"], 0, 60)
        d["transparence_globale"] = _valider_float(app.get("transparence_globale"), d["transparence_globale"], 0.2, 1.0)

        halo = app.get("halo")
        if isinstance(halo, dict):
            dh = d["halo"]
            dh["actif"] = _valider_bool(halo.get("actif"), dh["actif"])
            dh["couleur"] = _valider_hex(halo.get("couleur"), dh["couleur"])
            dh["intensite"] = _valider_float(halo.get("intensite"), dh["intensite"], 0.0, 1.0)
            dh["rayon"] = _valider_int(halo.get("rayon"), dh["rayon"], 0, 160)

        ombre = app.get("ombre")
        if isinstance(ombre, dict):
            do = d["ombre"]
            do["actif"] = _valider_bool(ombre.get("actif"), do["actif"])
            do["couleur"] = _valider_hex(ombre.get("couleur"), do["couleur"])
            do["opacite"] = _valider_float(ombre.get("opacite"), do["opacite"], 0.0, 1.0)
            do["flou"] = _valider_int(ombre.get("flou"), do["flou"], 0, 80)

        anim = app.get("animations")
        if isinstance(anim, dict):
            da = d["animations"]
            da["actives"] = _valider_bool(anim.get("actives"), da["actives"])
            da["vitesse"] = _valider_float(anim.get("vitesse"), da["vitesse"], 0.1, 3.0)
            da["respiration_halo"] = _valider_bool(anim.get("respiration_halo"), da["respiration_halo"])

    perso = brut.get("personnage")
    if isinstance(perso, dict):
        d = cfg["personnage"]
        d["image_statique"] = _valider_chemin_interne(perso.get("image_statique"), d["image_statique"])
        d["gif_parole"] = _valider_chemin_interne(perso.get("gif_parole"), d["gif_parole"])
        d["taille_pourcent"] = _valider_int(perso.get("taille_pourcent"), d["taille_pourcent"], 30, 140)
        d["decalage_x"] = _valider_int(perso.get("decalage_x"), d["decalage_x"], -300, 300)
        d["decalage_y"] = _valider_int(perso.get("decalage_y"), d["decalage_y"], -300, 300)
        expr = perso.get("expressions")
        if isinstance(expr, dict):
            for cle in ("ecoute", "reflexion", "attente", "erreur"):
                d["expressions"][cle] = _valider_chemin_interne(expr.get(cle), None)

    bulle = brut.get("bulle")
    if isinstance(bulle, dict):
        d = cfg["bulle"]
        d["couleur_fond"] = _valider_hex(bulle.get("couleur_fond"), d["couleur_fond"])
        d["opacite_fond"] = _valider_float(bulle.get("opacite_fond"), d["opacite_fond"], 0.1, 1.0)
        d["couleur_texte"] = _valider_hex(bulle.get("couleur_texte"), d["couleur_texte"])
        d["taille_police"] = _valider_int(bulle.get("taille_police"), d["taille_police"], 10, 36)
        if isinstance(bulle.get("famille_police"), str) and bulle["famille_police"].strip():
            d["famille_police"] = bulle["famille_police"].strip()[:60]
        d["couleur_contour"] = _valider_hex(bulle.get("couleur_contour"), d["couleur_contour"])
        d["epaisseur_contour"] = _valider_int(bulle.get("epaisseur_contour"), d["epaisseur_contour"], 0, 8)
        d["rayon_angles"] = _valider_int(bulle.get("rayon_angles"), d["rayon_angles"], 0, 40)
        d["largeur_pourcent"] = _valider_int(bulle.get("largeur_pourcent"), d["largeur_pourcent"], 30, 100)
        d["hauteur_max_pourcent"] = _valider_int(bulle.get("hauteur_max_pourcent"), d["hauteur_max_pourcent"], 20, 150)
        d["decalage_x"] = _valider_int(bulle.get("decalage_x"), d["decalage_x"], -400, 400)
        d["decalage_y"] = _valider_int(bulle.get("decalage_y"), d["decalage_y"], -400, 400)
        d["caracteres_max"] = _valider_int(bulle.get("caracteres_max"), d["caracteres_max"], 40, 2000)
        d["duree_affichage_apres_parole_ms"] = _valider_int(
            bulle.get("duree_affichage_apres_parole_ms"),
            d["duree_affichage_apres_parole_ms"],
            500,
            60000,
        )

    return cfg


def charger_config(logger=None):
    assurer_dossiers()
    if not os.path.exists(CHEMIN_CONFIG):
        cfg = copy.deepcopy(CONFIG_DEFAUT)
        ecrire_json_atomique(CHEMIN_CONFIG, cfg, backup=False)
        return cfg

    try:
        with open(CHEMIN_CONFIG, "r", encoding="utf-8") as f:
            brut = json.load(f)
        return valider_config(brut)
    except Exception as err:
        if logger:
            logger.warning("Configuration invalide (%s), repli sur defaut : %s", CHEMIN_CONFIG, err)
        return copy.deepcopy(CONFIG_DEFAUT)


def sauvegarder_config(cfg):
    valide = valider_config(cfg)
    ecrire_json_atomique(CHEMIN_CONFIG, valide, backup=True)
    return valide


def lire_runtime():
    try:
        with open(CHEMIN_RUNTIME, "r", encoding="utf-8") as f:
            donnees = json.load(f)
        if isinstance(donnees, dict):
            return donnees
    except Exception:
        pass
    return {}


def ecrire_runtime(donnees):
    assurer_dossiers()
    ecrire_json_atomique(CHEMIN_RUNTIME, donnees, backup=False)


def mettre_a_jour_pid_runtime(cle, pid):
    courant = lire_runtime()
    pids = courant.get("pids")
    if not isinstance(pids, dict):
        pids = {}
    if pid is None:
        pids.pop(cle, None)
    else:
        pids[cle] = int(pid)
    courant["pids"] = pids
    ecrire_runtime(courant)


def obtenir_ou_creer_jeton():
    assurer_dossiers()
    try:
        with open(CHEMIN_SESSION, "r", encoding="utf-8") as f:
            data = json.load(f)
        jeton = data.get("token")
        if isinstance(jeton, str) and len(jeton) >= 32:
            return jeton
    except Exception:
        pass

    jeton = secrets.token_hex(32)
    ecrire_json_atomique(CHEMIN_SESSION, {"token": jeton, "created_at": time.time()})
    return jeton