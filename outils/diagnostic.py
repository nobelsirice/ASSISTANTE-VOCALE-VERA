import asyncio
import json
import os
import socket
import sys
import urllib.request

DOSSIER_PROJET = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DOSSIER_PROJET not in sys.path:
    sys.path.insert(0, DOSSIER_PROJET)

from config_nobel import CHEMIN_CONFIG, DOSSIER_LOGS, lire_runtime, valider_config


def ligne(label, ok, detail=""):
    statut = "OK" if ok else "KO"
    suffixe = f" - {detail}" if detail else ""
    print(f"[{statut}] {label}{suffixe}")


def verifier_port_libre(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


async def tester_ws(port, jeton):
    import aiohttp

    url = f"ws://127.0.0.1:{port}/ws?role=admin&token={jeton}"
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(url, timeout=3.0) as ws:
            msg = await ws.receive_json(timeout=3.0)
            return msg.get("type") == "hello"


def main():
    print("=== DIAGNOSTIC VERA ===\n")

    # 1. Python
    v = sys.version_info
    ligne("Version Python", v >= (3, 11), f"{v.major}.{v.minor}.{v.micro}")

    # 2. Paquets
    for mod in ("speech_recognition", "pyaudio", "pyttsx3", "piper", "vosk", "PySide6", "aiohttp", "PIL"):
        try:
            __import__(mod)
            ligne(f"Paquet {mod}", True)
        except ImportError as e:
            ligne(f"Paquet {mod}", False, str(e))

    # 3. Assets
    for rel in ("assets/vera_statique.png", "assets/vera_parole.gif"):
        chemin = os.path.join(DOSSIER_PROJET, rel.replace("/", os.sep))
        existe = os.path.exists(chemin) and os.path.getsize(chemin) > 0
        ligne(f"Ressource {rel}", existe)

    # 4. Configuration JSON
    try:
        with open(CHEMIN_CONFIG, "r", encoding="utf-8") as f:
            brut = json.load(f)
        valider_config(brut)
        ligne("Configuration config/widget.json", True)
    except Exception as e:
        ligne("Configuration config/widget.json", False, str(e))

    # 5. Logs AppData
    ligne("Dossier logs AppData", os.path.isdir(DOSSIER_LOGS), DOSSIER_LOGS)

    # 6. Runtime, serveur, WebSocket et widget actif
    rt = lire_runtime()
    port = rt.get("port")
    jeton = rt.get("token")
    if isinstance(port, int) and jeton:
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/status",
                headers={"Host": f"127.0.0.1:{port}"},
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                statut = json.loads(resp.read().decode("utf-8"))
            ligne("Serveur local HTTP", True, f"port {port}")
            ligne("Widget actif", bool(statut.get("widget_connected")), f"{statut.get('widgets_count', 0)} instance(s)")
            ws_ok = asyncio.run(tester_ws(port, jeton))
            ligne("Poignee de main WebSocket", ws_ok)
        except Exception as e:
            ligne("Serveur local HTTP", False, str(e))
            ligne("Widget actif", False, "serveur injoignable")
            ligne("Poignee de main WebSocket", False, "serveur injoignable")
    else:
        ligne("Serveur local HTTP", False, "aucun runtime.json actif")
        ligne("Port 8765 disponible", verifier_port_libre(8765))

    ligne("Port 3001 (Admin) disponible", verifier_port_libre(3001))


if __name__ == "__main__":
    main()