import http.client
import json
import os
import queue
import threading
import time

DOSSIER_PROJET = os.path.dirname(os.path.abspath(__file__))
CHEMIN_RUNTIME = os.path.join(DOSSIER_PROJET, "data", "runtime.json")


class NobelBridge:
    """Pont non bloquant entre assistant.py et le serveur local."""

    def __init__(self, taille_file=100):
        self._file = queue.Queue(maxsize=taille_file)
        self._arret = threading.Event()
        self._thread = None
        self._dernier_etat = None
        self._lock = threading.Lock()
        self._conn = None
        self._hote = "127.0.0.1"
        self._port = None
        self._jeton = None
        self._derniere_lecture_runtime = 0.0

    def start(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._arret.clear()
            self._thread = threading.Thread(
                target=self._boucle_envoi,
                name="NobelBridgeSender",
                daemon=True,
            )
            self._thread.start()

    def stop(self):
        self._arret.set()
        try:
            self._file.put_nowait(None)
        except Exception:
            pass
        if self._thread is not None:
            try:
                self._thread.join(timeout=0.5)
            except Exception:
                pass
        self._fermer_connexion()

    def _enfiler(self, payload):
        if self._arret.is_set():
            return
        try:
            self._file.put_nowait(payload)
        except queue.Full:
            pass
        except Exception:
            pass

    def state(self, nom):
        if not nom or not isinstance(nom, str):
            return
        if nom != "error" and nom == self._dernier_etat:
            return
        self._dernier_etat = nom
        self._enfiler({"type": "state", "state": nom})

    def speech_start(self, texte):
        if not isinstance(texte, str):
            return
        self._enfiler({"type": "speech_start", "text": texte})

    def speech_end(self):
        self._enfiler({"type": "speech_end"})

    def assistant_started(self):
        self._dernier_etat = "idle"
        self._enfiler({"type": "assistant_started", "pid": os.getpid()})

    def assistant_stopped(self):
        self._enfiler({"type": "assistant_stopped", "pid": os.getpid()})

    def _charger_runtime(self, forcer=False):
        maintenant = time.monotonic()
        if not forcer and (maintenant - self._derniere_lecture_runtime) < 2.0:
            return self._port is not None and bool(self._jeton)
        self._derniere_lecture_runtime = maintenant
        try:
            with open(CHEMIN_RUNTIME, "r", encoding="utf-8") as f:
                data = json.load(f)
            port = data.get("port")
            jeton = data.get("token")
            if isinstance(port, int) and port > 0 and isinstance(jeton, str) and jeton:
                if port != self._port:
                    self._fermer_connexion()
                self._port = port
                self._jeton = jeton
                return True
        except Exception:
            pass
        self._port = None
        self._jeton = None
        return False

    def _fermer_connexion(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _envoyer_http(self, payload):
        if not self._charger_runtime(forcer=False):
            return False

        corps = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        en_tetes = {
            "Content-Type": "application/json; charset=utf-8",
            "Host": f"{self._hote}:{self._port}",
            "X-Nobel-Token": self._jeton,
            "Connection": "keep-alive",
        }

        for essai in range(2):
            try:
                if self._conn is None:
                    self._conn = http.client.HTTPConnection(
                        self._hote, self._port, timeout=1.5
                    )
                self._conn.request("POST", "/api/event", body=corps, headers=en_tetes)
                resp = self._conn.getresponse()
                resp.read()
                if resp.status == 200:
                    return True
                if resp.status in (401, 403):
                    self._fermer_connexion()
                    self._charger_runtime(forcer=True)
                    en_tetes["X-Nobel-Token"] = self._jeton or ""
            except Exception:
                self._fermer_connexion()
                if essai == 0:
                    self._charger_runtime(forcer=True)
        return False

    def _boucle_envoi(self):
        attente = 0.25
        while not self._arret.is_set():
            try:
                evenement = self._file.get(timeout=0.5)
            except queue.Empty:
                continue

            if evenement is None:
                break

            if self._envoyer_http(evenement):
                attente = 0.25
            else:
                time.sleep(attente)
                attente = min(3.0, attente * 1.5)


bridge = NobelBridge()