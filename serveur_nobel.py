import asyncio
import copy
import ctypes
import io
import json
import logging
import os
import socket
import sys
import time
import uuid

from aiohttp import WSMsgType, web
from PIL import Image

from config_nobel import (
    CONFIG_DEFAUT,
    DOSSIER_LOGS,
    DOSSIER_PROJET,
    assurer_dossiers,
    charger_config,
    ecrire_runtime,
    lire_runtime,
    mettre_a_jour_pid_runtime,
    obtenir_ou_creer_jeton,
    sauvegarder_config,
    valider_config,
)

PORT_DEFAUT = 8765
ORIGINES_AUTORISEES = {
    "http://localhost:3001",
    "http://127.0.0.1:3001",
}

EMPLACEMENTS_VALIDES = {
    "statique",
    "parole",
    "ecoute",
    "reflexion",
    "attente",
    "erreur",
    "fond",
}

SIGNATURES_AUTORISEES = {
    "PNG": ("png", 5 * 1024 * 1024),
    "GIF": ("gif", 10 * 1024 * 1024),
    "WEBP": ("webp", 10 * 1024 * 1024),
}


def configurer_logs():
    assurer_dossiers()
    chemin_log = os.path.join(DOSSIER_LOGS, "serveur.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(chemin_log, encoding="utf-8")],
    )
    return logging.getLogger("serveur_nobel")


def acquerir_mutex():
    if os.name != "nt":
        return None
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, "Global\\NOBEL_VERA_SERVEUR")
    if not handle:
        return None
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        return False
    return handle


def trouver_port_libre(port_prefere=PORT_DEFAUT):
    for port in [port_prefere] + list(range(8766, 8795)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class EtatServeur:
    def __init__(self, logger):
        self.logger = logger
        self.jeton = obtenir_ou_creer_jeton()
        self.port = PORT_DEFAUT
        self.config_sauvegardee = charger_config(logger)
        self.config_courante = copy.deepcopy(self.config_sauvegardee)
        self.etat_assistant = "idle"
        self.assistant_connectee = False
        self.dernier_contact_assistant = 0.0
        self.compteur_parole = 0
        self.parole_active_id = None
        self.parole_active_texte = ""
        self.clients_ws = {}
        self.tache_sauvegarde_geom = None
        self.evenement_arret = asyncio.Event()

    def _headers_cors(self, request):
        origine = request.headers.get("Origin", "")
        if origine in ORIGINES_AUTORISEES:
            return {
                "Access-Control-Allow-Origin": origine,
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, X-Nobel-Token",
                "Vary": "Origin",
            }
        return {}

    def _verifier_hote_et_origine(self, request, exiger_jeton=True):
        host = request.headers.get("Host", "")
        hote_seul = host.split(":")[0].lower()
        if hote_seul not in ("127.0.0.1", "localhost"):
            return web.json_response({"error": "En-tete Host interdit"}, status=403)

        origine = request.headers.get("Origin")
        if origine is not None and origine not in ORIGINES_AUTORISEES:
            return web.json_response({"error": "Origine non autorisee"}, status=403)

        if exiger_jeton:
            jeton_recu = request.headers.get("X-Nobel-Token") or request.query.get("token")
            if jeton_recu != self.jeton:
                return web.json_response({"error": "Jeton invalide"}, status=401)
        return None

    async def diffuser(self, message, cible_role=None):
        if not self.clients_ws:
            return
        texte = json.dumps(message, ensure_ascii=False)
        fermes = []
        for ws, role in list(self.clients_ws.items()):
            if cible_role and role != cible_role:
                continue
            try:
                await ws.send_str(texte)
            except Exception:
                fermes.append(ws)
        for ws in fermes:
            self.clients_ws.pop(ws, None)

    def _planifier_sauvegarde_geometrie(self):
        if self.tache_sauvegarde_geom and not self.tache_sauvegarde_geom.done():
            self.tache_sauvegarde_geom.cancel()

        async def _sauver_differe():
            try:
                await asyncio.sleep(0.5)
                self.config_sauvegardee["fenetre"] = copy.deepcopy(self.config_courante["fenetre"])
                sauvegarder_config(self.config_sauvegardee)
            except asyncio.CancelledError:
                pass
            except Exception as err:
                self.logger.warning("Echec sauvegarde geometrie : %s", err)

        self.tache_sauvegarde_geom = asyncio.create_task(_sauver_differe())

    async def handle_options(self, request):
        err = self._verifier_hote_et_origine(request, exiger_jeton=False)
        if err:
            return err
        return web.Response(status=204, headers=self._headers_cors(request))

    async def handle_bootstrap(self, request):
        err = self._verifier_hote_et_origine(request, exiger_jeton=False)
        if err:
            return err
        origine = request.headers.get("Origin", "")
        if origine not in ORIGINES_AUTORISEES:
            return web.json_response({"error": "Acces reserve a l'administration"}, status=403)
        return web.json_response(
            {"token": self.jeton, "port": self.port},
            headers=self._headers_cors(request),
        )

    async def handle_status(self, request):
        err = self._verifier_hote_et_origine(request, exiger_jeton=False)
        if err:
            return err
        nb_widgets = sum(1 for r in self.clients_ws.values() if r == "widget")
        nb_admins = sum(1 for r in self.clients_ws.values() if r == "admin")
        return web.json_response(
            {
                "ok": True,
                "port": self.port,
                "state": self.etat_assistant,
                "assistant_connected": self.assistant_connectee,
                "widget_connected": nb_widgets > 0,
                "widgets_count": nb_widgets,
                "admins_count": nb_admins,
                "pids": lire_runtime().get("pids", {}),
            },
            headers=self._headers_cors(request),
        )

    async def handle_get_config(self, request):
        err = self._verifier_hote_et_origine(request, exiger_jeton=False)
        if err:
            return err
        return web.json_response(self.config_courante, headers=self._headers_cors(request))

    async def handle_put_config(self, request):
        err = self._verifier_hote_et_origine(request, exiger_jeton=True)
        if err:
            return err
        try:
            brut = await request.json()
        except Exception:
            return web.json_response({"error": "JSON invalide"}, status=400, headers=self._headers_cors(request))

        valide = sauvegarder_config(brut)
        self.config_sauvegardee = copy.deepcopy(valide)
        self.config_courante = copy.deepcopy(valide)
        await self.diffuser({"type": "config", "config": self.config_courante, "persistent": True})
        return web.json_response(self.config_courante, headers=self._headers_cors(request))

    async def handle_apply_config(self, request):
        err = self._verifier_hote_et_origine(request, exiger_jeton=True)
        if err:
            return err
        try:
            brut = await request.json()
        except Exception:
            return web.json_response({"error": "JSON invalide"}, status=400, headers=self._headers_cors(request))

        self.config_courante = valider_config(brut)
        await self.diffuser({"type": "config", "config": self.config_courante, "persistent": False})
        return web.json_response(self.config_courante, headers=self._headers_cors(request))

    async def handle_reset_config(self, request):
        err = self._verifier_hote_et_origine(request, exiger_jeton=True)
        if err:
            return err
        self.config_sauvegardee = charger_config(self.logger)
        self.config_courante = copy.deepcopy(self.config_sauvegardee)
        await self.diffuser({"type": "config", "config": self.config_courante, "persistent": True})
        return web.json_response(self.config_courante, headers=self._headers_cors(request))

    async def handle_defaults_config(self, request):
        err = self._verifier_hote_et_origine(request, exiger_jeton=True)
        if err:
            return err
        return web.json_response(copy.deepcopy(CONFIG_DEFAUT), headers=self._headers_cors(request))

    async def handle_event(self, request):
        err = self._verifier_hote_et_origine(request, exiger_jeton=True)
        if err:
            return err
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "JSON invalide"}, status=400, headers=self._headers_cors(request))

        etype = data.get("type")
        self.dernier_contact_assistant = time.monotonic()

        if etype == "assistant_started":
            self.assistant_connectee = True
            self.etat_assistant = "idle"
            pid = data.get("pid")
            if isinstance(pid, int) and pid > 0:
                mettre_a_jour_pid_runtime("assistant", pid)
            await self.diffuser({"type": "assistant_status", "connected": True})
            await self.diffuser({"type": "state", "state": "idle"})

        elif etype == "assistant_stopped":
            self.assistant_connectee = False
            self.etat_assistant = "idle"
            mettre_a_jour_pid_runtime("assistant", None)
            await self.diffuser({"type": "assistant_status", "connected": False})
            await self.diffuser({"type": "state", "state": "idle"})

        elif etype == "state":
            if not self.assistant_connectee:
                self.assistant_connectee = True
                await self.diffuser({"type": "assistant_status", "connected": True})
            nouvel_etat = str(data.get("state", "idle"))
            if nouvel_etat in ("idle", "listening", "processing", "speaking", "error"):
                self.etat_assistant = nouvel_etat
                await self.diffuser({"type": "state", "state": nouvel_etat})

        elif etype == "speech_start":
            if not self.assistant_connectee:
                self.assistant_connectee = True
                await self.diffuser({"type": "assistant_status", "connected": True})
            self.compteur_parole += 1
            self.parole_active_id = self.compteur_parole
            self.parole_active_texte = str(data.get("text", ""))
            await self.diffuser(
                {"type": "speech_start", "id": self.parole_active_id, "text": self.parole_active_texte}
            )

        elif etype == "speech_end":
            sid = self.parole_active_id or self.compteur_parole
            self.parole_active_id = None
            await self.diffuser({"type": "speech_end", "id": sid})

        return web.json_response({"ok": True}, headers=self._headers_cors(request))

    async def handle_test_state(self, request):
        err = self._verifier_hote_et_origine(request, exiger_jeton=True)
        if err:
            return err
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "JSON invalide"}, status=400, headers=self._headers_cors(request))
        etat = str(data.get("state", "idle"))
        if etat not in ("idle", "listening", "processing", "speaking", "error"):
            return web.json_response({"error": "Etat inconnu"}, status=400, headers=self._headers_cors(request))
        self.etat_assistant = etat
        await self.diffuser({"type": "state", "state": etat})
        return web.json_response({"ok": True, "state": etat}, headers=self._headers_cors(request))

    async def handle_test_message(self, request):
        err = self._verifier_hote_et_origine(request, exiger_jeton=True)
        if err:
            return err
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "JSON invalide"}, status=400, headers=self._headers_cors(request))
        texte = str(data.get("text", "Bonjour maître Nobel, ceci est un test de la bulle de conversation.")).strip()
        duree_ms = int(data.get("duration_ms", 3000))
        duree_ms = max(500, min(15000, duree_ms))

        self.compteur_parole += 1
        sid = self.compteur_parole
        await self.diffuser({"type": "speech_start", "id": sid, "text": texte})
        await self.diffuser({"type": "state", "state": "speaking"})

        async def _fin_test():
            await asyncio.sleep(duree_ms / 1000.0)
            await self.diffuser({"type": "speech_end", "id": sid})
            await self.diffuser({"type": "state", "state": "idle"})

        asyncio.create_task(_fin_test())
        return web.json_response({"ok": True, "id": sid}, headers=self._headers_cors(request))

    async def handle_upload_asset(self, request):
        err = self._verifier_hote_et_origine(request, exiger_jeton=True)
        if err:
            return err
        emplacement = request.match_info.get("emplacement", "")
        if emplacement not in EMPLACEMENTS_VALIDES:
            return web.json_response({"error": "Emplacement inconnu"}, status=400, headers=self._headers_cors(request))

        try:
            lecteur = await request.multipart()
            champ = await lecteur.next()
        except Exception:
            return web.json_response({"error": "Requete multipart invalide"}, status=400, headers=self._headers_cors(request))

        if champ is None:
            return web.json_response({"error": "Aucun fichier recu"}, status=400, headers=self._headers_cors(request))

        nom_original = champ.filename or ""
        ext_orig = os.path.splitext(nom_original)[1].lower().lstrip(".")
        if ext_orig == "svg" or ext_orig not in ("png", "gif", "webp"):
            return web.json_response(
                {"error": "Format refuse : seuls PNG, GIF et WebP sont autorises."},
                status=400,
                headers=self._headers_cors(request),
            )

        tampon = bytearray()
        while True:
            morceau = await champ.read_chunk(65536)
            if not morceau:
                break
            tampon.extend(morceau)
            if len(tampon) > 10 * 1024 * 1024 + 1024:
                return web.json_response(
                    {"error": "Fichier trop volumineux (maximum 10 Mo)."},
                    status=413,
                    headers=self._headers_cors(request),
                )

        octets = bytes(tampon)
        try:
            with Image.open(io.BytesIO(octets)) as img:
                fmt = (img.format or "").upper()
                largeur, hauteur = img.size
                img.verify()
        except Exception:
            return web.json_response(
                {"error": "Fichier image corrompu ou signature invalide."},
                status=400,
                headers=self._headers_cors(request),
            )

        if fmt not in SIGNATURES_AUTORISEES:
            return web.json_response(
                {"error": "Signature binaire refusee : seuls PNG, GIF et WebP sont acceptes."},
                status=400,
                headers=self._headers_cors(request),
            )

        ext_reelle, taille_max = SIGNATURES_AUTORISEES[fmt]
        if len(octets) > taille_max:
            limite_mo = taille_max // (1024 * 1024)
            return web.json_response(
                {"error": f"Fichier trop volumineux pour {fmt} (maximum {limite_mo} Mo)."},
                status=413,
                headers=self._headers_cors(request),
            )

        if largeur > 2048 or hauteur > 2048:
            return web.json_response(
                {"error": f"Dimensions excessives ({largeur}x{hauteur} px, maximum 2048x2048 px)."},
                status=400,
                headers=self._headers_cors(request),
            )

        nom_genere = f"custom_{emplacement}_{uuid.uuid4().hex[:8]}.{ext_reelle}"
        chemin_rel = f"assets/{nom_genere}"
        chemin_abs = os.path.join(DOSSIER_PROJET, "assets", nom_genere)

        ancien_rel = self._lire_chemin_emplacement(self.config_sauvegardee, emplacement)
        if ancien_rel and os.path.basename(ancien_rel).startswith(f"custom_{emplacement}_"):
            ancien_abs = os.path.join(DOSSIER_PROJET, ancien_rel.replace("/", os.sep))
            if os.path.exists(ancien_abs):
                try:
                    os.remove(ancien_abs)
                except OSError:
                    pass

        with open(chemin_abs, "wb") as f:
            f.write(octets)

        self._ecrire_chemin_emplacement(self.config_sauvegardee, emplacement, chemin_rel)
        self._ecrire_chemin_emplacement(self.config_courante, emplacement, chemin_rel)
        sauvegarder_config(self.config_sauvegardee)

        await self.diffuser({"type": "assets_changed", "slot": emplacement, "path": chemin_rel})
        await self.diffuser({"type": "config", "config": self.config_courante, "persistent": True})
        return web.json_response(
            {"ok": True, "slot": emplacement, "path": chemin_rel, "config": self.config_courante},
            headers=self._headers_cors(request),
        )

    async def handle_delete_asset(self, request):
        err = self._verifier_hote_et_origine(request, exiger_jeton=True)
        if err:
            return err
        emplacement = request.match_info.get("emplacement", "")
        if emplacement not in EMPLACEMENTS_VALIDES:
            return web.json_response({"error": "Emplacement inconnu"}, status=400, headers=self._headers_cors(request))

        ancien_rel = self._lire_chemin_emplacement(self.config_sauvegardee, emplacement)
        if ancien_rel and os.path.basename(ancien_rel).startswith(f"custom_{emplacement}_"):
            ancien_abs = os.path.join(DOSSIER_PROJET, ancien_rel.replace("/", os.sep))
            if os.path.exists(ancien_abs):
                try:
                    os.remove(ancien_abs)
                except OSError:
                    pass

        defaut_rel = self._lire_chemin_emplacement(CONFIG_DEFAUT, emplacement)
        self._ecrire_chemin_emplacement(self.config_sauvegardee, emplacement, defaut_rel)
        self._ecrire_chemin_emplacement(self.config_courante, emplacement, defaut_rel)
        sauvegarder_config(self.config_sauvegardee)

        await self.diffuser({"type": "assets_changed", "slot": emplacement, "path": defaut_rel})
        await self.diffuser({"type": "config", "config": self.config_courante, "persistent": True})
        return web.json_response(
            {"ok": True, "slot": emplacement, "path": defaut_rel, "config": self.config_courante},
            headers=self._headers_cors(request),
        )

    def _lire_chemin_emplacement(self, cfg, emplacement):
        if emplacement == "fond":
            return cfg.get("apparence", {}).get("image_fond")
        perso = cfg.get("personnage", {})
        if emplacement == "statique":
            return perso.get("image_statique")
        if emplacement == "parole":
            return perso.get("gif_parole")
        return perso.get("expressions", {}).get(emplacement)

    def _ecrire_chemin_emplacement(self, cfg, emplacement, valeur):
        if emplacement == "fond":
            cfg.setdefault("apparence", {})["image_fond"] = valeur
            return
        perso = cfg.setdefault("personnage", {})
        if emplacement == "statique":
            perso["image_statique"] = valeur
        elif emplacement == "parole":
            perso["gif_parole"] = valeur
        else:
            perso.setdefault("expressions", {})[emplacement] = valeur

    async def handle_shutdown(self, request):
        err = self._verifier_hote_et_origine(request, exiger_jeton=True)
        if err:
            return err
        await self.diffuser({"type": "quit"})
        self.evenement_arret.set()
        return web.json_response({"ok": True}, headers=self._headers_cors(request))

    async def handle_ws(self, request):
        err = self._verifier_hote_et_origine(request, exiger_jeton=True)
        if err:
            return err
        role = request.query.get("role", "widget")
        if role not in ("widget", "admin"):
            role = "widget"

        ws = web.WebSocketResponse(heartbeat=20.0)
        await ws.prepare(request)
        self.clients_ws[ws] = role

        await ws.send_str(
            json.dumps(
                {
                    "type": "hello",
                    "version": 1,
                    "state": self.etat_assistant,
                    "assistant_connected": self.assistant_connectee,
                    "config": self.config_courante,
                },
                ensure_ascii=False,
            )
        )

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except Exception:
                        continue
                    if role == "widget" and data.get("type") == "geometry":
                        fen = self.config_courante["fenetre"]
                        for cle in ("x", "y"):
                            if isinstance(data.get(cle), int):
                                fen[cle] = data[cle]
                        if isinstance(data.get("w"), int) and isinstance(data.get("h"), int):
                            fen["largeur_px"] = max(160, data["w"])
                            fen["hauteur_px"] = max(100, data["h"])
                        if isinstance(data.get("reduit"), bool):
                            fen["reduit"] = data["reduit"]
                        if isinstance(data.get("visible"), bool):
                            fen["visible"] = data["visible"]
                        self._planifier_sauvegarde_geometrie()
                elif msg.type == WSMsgType.ERROR:
                    break
        finally:
            self.clients_ws.pop(ws, None)

        return ws


async def demarrer_serveur():
    logger = configurer_logs()
    mutex = acquerir_mutex()
    if mutex is False:
        logger.info("Une instance du serveur est deja active.")
        return

    etat = EtatServeur(logger)
    etat.port = trouver_port_libre(PORT_DEFAUT)

    app = web.Application(client_max_size=12 * 1024 * 1024)
    app.router.add_route("OPTIONS", "/{tail:.*}", etat.handle_options)
    app.router.add_get("/api/bootstrap", etat.handle_bootstrap)
    app.router.add_get("/api/status", etat.handle_status)
    app.router.add_get("/api/config", etat.handle_get_config)
    app.router.add_put("/api/config", etat.handle_put_config)
    app.router.add_post("/api/config/apply", etat.handle_apply_config)
    app.router.add_post("/api/config/reset", etat.handle_reset_config)
    app.router.add_post("/api/config/defaults", etat.handle_defaults_config)
    app.router.add_post("/api/event", etat.handle_event)
    app.router.add_post("/api/test/state", etat.handle_test_state)
    app.router.add_post("/api/test/message", etat.handle_test_message)
    app.router.add_post("/api/assets/{emplacement}", etat.handle_upload_asset)
    app.router.add_delete("/api/assets/{emplacement}", etat.handle_delete_asset)
    app.router.add_post("/api/shutdown", etat.handle_shutdown)
    app.router.add_get("/ws", etat.handle_ws)
    app.router.add_static("/assets/", path=os.path.join(DOSSIER_PROJET, "assets"), show_index=False)

    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", etat.port)
    await site.start()

    runtime = lire_runtime()
    pids = runtime.get("pids") if isinstance(runtime.get("pids"), dict) else {}
    pids["serveur"] = os.getpid()
    ecrire_runtime(
        {
            "host": "127.0.0.1",
            "port": etat.port,
            "token": etat.jeton,
            "pids": pids,
            "started_at": time.time(),
        }
    )
    logger.info("Serveur VERA demarre sur http://127.0.0.1:%d", etat.port)

    try:
        await etat.evenement_arret.wait()
    finally:
        await etat.diffuser({"type": "quit"})
        await runner.cleanup()
        mettre_a_jour_pid_runtime("serveur", None)
        if mutex:
            ctypes.windll.kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    try:
        asyncio.run(demarrer_serveur())
    except KeyboardInterrupt:
        pass