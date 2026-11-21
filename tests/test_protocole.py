import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

DOSSIER_PROJET = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DOSSIER_PROJET not in sys.path:
    sys.path.insert(0, DOSSIER_PROJET)

from config_nobel import lire_runtime
from nobel_bridge import NobelBridge


def _requete_http(port, chemin, methode="GET", corps=None, jeton=None, origine=None):
    url = f"http://127.0.0.1:{port}{chemin}"
    headers = {"Host": f"127.0.0.1:{port}"}
    if jeton:
        headers["X-Nobel-Token"] = jeton
    if origine:
        headers["Origin"] = origine
    data = None
    if corps is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
        data = json.dumps(corps).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=methode)
    with urllib.request.urlopen(req, timeout=3.0) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


async def _attendre_message(ws, predicat, timeout=4.0):
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        reste = max(0.1, fin - time.monotonic())
        msg = await ws.receive_json(timeout=reste)
        if predicat(msg):
            return msg
    raise TimeoutError("Message WebSocket attendu non recu dans le delai imparti")


async def _executer_tests_async(port, jeton):
    import aiohttp

    ws_url = f"ws://127.0.0.1:{port}/ws?role=widget&token={jeton}"
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ws_url, timeout=4.0) as ws:
            # 1. Poignee de main hello
            hello = await ws.receive_json(timeout=3.0)
            assert hello.get("type") == "hello", f"Attendu hello, recu {hello}"
            assert "config" in hello
            print("[OK] 1. Poignee de main WebSocket (hello)")

            # 2. Simulation du pont d'un faux assistant
            pont = NobelBridge()
            pont.start()
            pont.assistant_started()

            msg_status = await _attendre_message(
                ws, lambda m: m == {"type": "assistant_status", "connected": True}
            )
            assert msg_status["connected"] is True
            print("[OK] 2. Connexion faux assistant via NobelBridge")

            # 3. Changement d'etat et dedoublonnage
            pont.state("listening")
            pont.state("listening")
            m_listen = await _attendre_message(
                ws, lambda m: m == {"type": "state", "state": "listening"}
            )
            assert m_listen["state"] == "listening"
            print("[OK] 3. Transition etat listening")

            # 4. Sequence parole synchronisee
            texte_test = "Bonjour Nobel, test de synchronisation."
            pont.speech_start(texte_test)
            pont.state("speaking")

            m_sp_start = await _attendre_message(
                ws, lambda m: m.get("type") == "speech_start" and m.get("text") == texte_test
            )
            assert isinstance(m_sp_start.get("id"), int)

            await _attendre_message(
                ws, lambda m: m == {"type": "state", "state": "speaking"}
            )

            pont.speech_end()
            pont.state("idle")
            m_sp_end = await _attendre_message(
                ws, lambda m: m.get("type") == "speech_end" and m.get("id") == m_sp_start["id"]
            )
            assert m_sp_end["id"] == m_sp_start["id"]
            print("[OK] 4. Couple speech_start / speech_end avec identifiant coherent")

            # 5. Diffusion temporaire de configuration (/api/config/apply)
            cfg_test = hello["config"]
            cfg_test["nom_affiche"] = "VÉRA TEST"
            code, _ = _requete_http(
                port, "/api/config/apply", methode="POST", corps=cfg_test, jeton=jeton
            )
            assert code == 200
            m_cfg = await _attendre_message(
                ws,
                lambda m: m.get("type") == "config"
                and m.get("persistent") is False
                and m.get("config", {}).get("nom_affiche") == "VÉRA TEST",
            )
            assert m_cfg["persistent"] is False

            # Reinitialisation vers la version sauvegardee
            _requete_http(port, "/api/config/reset", methode="POST", jeton=jeton)
            await _attendre_message(ws, lambda m: m.get("type") == "config")
            print("[OK] 5. Diffusion temporaire et reinitialisation de configuration")

            # 6. Securite : rejet sans jeton et rejet origine interdite
            try:
                _requete_http(port, "/api/config/apply", methode="POST", corps=cfg_test, jeton="faux")
                raise AssertionError("Le serveur aurait du refuser un jeton invalide")
            except urllib.error.HTTPError as e:
                assert e.code == 401

            try:
                _requete_http(
                    port,
                    "/api/bootstrap",
                    methode="GET",
                    origine="http://site-externe.example.com",
                )
                raise AssertionError("Le serveur aurait du refuser une origine externe")
            except urllib.error.HTTPError as e:
                assert e.code == 403
            print("[OK] 6. Verification securite (jeton et origine)")

            pont.stop()


def main():
    print("=== TESTS DE PROTOCOLE VERA ===\n")
    serveur_demarre_ici = None
    rt = lire_runtime()
    port = rt.get("port")
    jeton = rt.get("token")

    serveur_actif = False
    if isinstance(port, int) and jeton:
        try:
            code, _ = _requete_http(port, "/api/status")
            serveur_actif = code == 200
        except Exception:
            serveur_actif = False

    if not serveur_actif:
        print("Demarrage d'une instance de serveur pour les tests...")
        serveur_demarre_ici = subprocess.Popen(
            [sys.executable, os.path.join(DOSSIER_PROJET, "serveur_nobel.py")],
            cwd=DOSSIER_PROJET,
        )
        fin = time.monotonic() + 8.0
        while time.monotonic() < fin:
            rt = lire_runtime()
            port = rt.get("port")
            jeton = rt.get("token")
            if isinstance(port, int) and jeton:
                try:
                    code, _ = _requete_http(port, "/api/status")
                    if code == 200:
                        serveur_actif = True
                        break
                except Exception:
                    pass
            time.sleep(0.25)

    assert serveur_actif, "Impossible de joindre le serveur local VERA"

    try:
        asyncio.run(_executer_tests_async(port, jeton))
        print("\nTous les tests de protocole ont reussi.")
    finally:
        if serveur_demarre_ici is not None:
            try:
                _requete_http(port, "/api/shutdown", methode="POST", jeton=jeton)
                serveur_demarre_ici.wait(timeout=4.0)
            except Exception:
                serveur_demarre_ici.terminate()


if __name__ == "__main__":
    main()