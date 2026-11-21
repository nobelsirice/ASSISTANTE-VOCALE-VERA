import ctypes
import json
import os
import subprocess
import sys
import time
import urllib.request
from ctypes import wintypes

from config_nobel import (
    CHEMIN_CONFIG,
    DOSSIER_PROJET,
    assurer_dossiers,
    charger_config,
    lire_runtime,
    mettre_a_jour_pid_runtime,
)
from generer_assets import generer_si_absent

CREATE_NO_WINDOW = 0x08000000
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectExtendedLimitInformation = 9


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def creer_job_object():
    if os.name != "nt":
        return None
    kernel32 = ctypes.windll.kernel32
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    ok = kernel32.SetInformationJobObject(
        job,
        JobObjectExtendedLimitInformation,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    if not ok:
        kernel32.CloseHandle(job)
        return None
    return job


def assigner_au_job(job, proc):
    if not job or os.name != "nt":
        return
    try:
        ctypes.windll.kernel32.AssignProcessToJobObject(job, int(proc._handle))
    except Exception:
        pass


def serveur_repond(port):
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/status",
            headers={"Host": f"127.0.0.1:{port}"},
        )
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def attendre_serveur_pret(delai=10.0):
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        rt = lire_runtime()
        port = rt.get("port")
        if isinstance(port, int) and port > 0 and serveur_repond(port):
            return port
        time.sleep(0.25)
    return None


def verifier_modules_visuels():
    manquants = []
    for mod in ("PySide6", "aiohttp", "PIL"):
        try:
            __import__(mod)
        except ImportError:
            manquants.append(mod)
    return manquants


def main():
    premier_lancement = not os.path.exists(CHEMIN_CONFIG)
    if premier_lancement:
        print("[LANCEUR] Premier lancement detecte : initialisation des parametres...")
    else:
        print("[LANCEUR] Demarrage normal de VERA...")

    assurer_dossiers()
    charger_config()
    crees = generer_si_absent(forcer=False)
    if crees:
        print(f"[LANCEUR] Ressources graphiques generees ({len(crees)} fichier(s)).")

    manquants = verifier_modules_visuels()
    python_exe = sys.executable
    job = creer_job_object()

    proc_serveur = None
    proc_widget = None
    mode_sans_visuel = False

    def nettoyer():
        for p in (proc_widget, proc_serveur):
            if p is not None and p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
        mettre_a_jour_pid_runtime("lanceur", None)
        if job and os.name == "nt":
            try:
                ctypes.windll.kernel32.CloseHandle(job)
            except Exception:
                pass

    if os.name == "nt":
        HANDLER = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

        def _ctrl_handler(ctrl_type):
            nettoyer()
            return False

        _ref_handler = HANDLER(_ctrl_handler)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(_ref_handler, True)

    mettre_a_jour_pid_runtime("lanceur", os.getpid())

    if manquants:
        print(f"[LANCEUR] Dependances visuelles manquantes ({', '.join(manquants)}).")
        print("[LANCEUR] Bascule en mode sans visuel.")
        mode_sans_visuel = True
    else:
        rt_existant = lire_runtime()
        port_existant = rt_existant.get("port")
        if isinstance(port_existant, int) and serveur_repond(port_existant):
            print(f"[LANCEUR] Serveur local deja actif sur le port {port_existant}.")
            port_actif = port_existant
        else:
            print("[LANCEUR] Demarrage du serveur local...")
            proc_serveur = subprocess.Popen(
                [python_exe, os.path.join(DOSSIER_PROJET, "serveur_nobel.py")],
                cwd=DOSSIER_PROJET,
                creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            assigner_au_job(job, proc_serveur)
            port_actif = attendre_serveur_pret(delai=10.0)

        if port_actif is None:
            print("[LANCEUR] Le serveur local n'a pas repondu. Mode sans visuel active.")
            mode_sans_visuel = True
        else:
            print(f"[LANCEUR] Serveur local operationnel (127.0.0.1:{port_actif}).")
            print("[LANCEUR] Demarrage du widget flottant...")
            proc_widget = subprocess.Popen(
                [python_exe, os.path.join(DOSSIER_PROJET, "widget_nobel.py")],
                cwd=DOSSIER_PROJET,
                creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            assigner_au_job(job, proc_widget)
            time.sleep(0.6)
            if proc_widget.poll() is not None:
                print("[LANCEUR] Le widget s'est ferme ou etait deja actif.")
            else:
                print("[LANCEUR] Widget flottant demarre.")

    if mode_sans_visuel:
        print("[LANCEUR] Lancement de l'assistante vocale (mode sans visuel)...")
    else:
        print("[LANCEUR] Lancement de l'assistante vocale...")

    try:
        code = subprocess.call(
            [python_exe, os.path.join(DOSSIER_PROJET, "assistant.py")],
            cwd=DOSSIER_PROJET,
        )
    finally:
        nettoyer()

    sys.exit(code)


if __name__ == "__main__":
    main()