import os
import subprocess
from PIL import Image, ImageDraw

DOSSIER_PROJET = os.path.dirname(os.path.abspath(__file__))
DOSSIER_ASSETS = os.path.join(DOSSIER_PROJET, "assets")
IMAGE_SOURCE = os.path.join(DOSSIER_ASSETS, "vera_statique.png")
ICONE_CIBLE = os.path.join(DOSSIER_ASSETS, "vera.ico")
BAT_CIBLE = os.path.join(DOSSIER_PROJET, "demarrage_nobel.bat")


def generer_icone():
    os.makedirs(DOSSIER_ASSETS, exist_ok=True)
    if os.path.exists(IMAGE_SOURCE):
        img = Image.open(IMAGE_SOURCE).convert("RGBA")
        cote = max(img.width, img.height)
        carre = Image.new("RGBA", (cote, cote), (0, 0, 0, 0))
        carre.paste(img, ((cote - img.width) // 2, (cote - img.height) // 2))
    else:
        # Icone cybernetique de secours si vera_statique.png n'est pas encore present
        carre = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(carre)
        draw.ellipse((12, 12, 244, 244), fill=(23, 23, 23, 255), outline=(0, 229, 255, 255), width=14)
        draw.ellipse((88, 88, 168, 168), fill=(0, 229, 255, 255))

    carre.save(
        ICONE_CIBLE,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )


def trouver_bureau():
    candidats = [
        os.path.join(os.path.expanduser("~"), "Desktop"),
        os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop"),
    ]
    for chemin in candidats:
        if os.path.isdir(chemin):
            return chemin
    return None


def creer_raccourci():
    if not os.path.exists(ICONE_CIBLE):
        generer_icone()

    bureau = trouver_bureau()
    if not bureau:
        return

    raccourci_lnk = os.path.join(bureau, "VÉRA.lnk")
    if os.path.exists(raccourci_lnk):
        return

    ps_script = (
        "$WshShell = New-Object -ComObject WScript.Shell; "
        f"$Shortcut = $WshShell.CreateShortcut('{raccourci_lnk}'); "
        f"$Shortcut.TargetPath = '{BAT_CIBLE}'; "
        f"$Shortcut.WorkingDirectory = '{DOSSIER_PROJET}'; "
        f"$Shortcut.IconLocation = '{ICONE_CIBLE}, 0'; "
        "$Shortcut.Description = 'Lancer VÉRA - Assistante vocale'; "
        "$Shortcut.WindowStyle = 7; "
        "$Shortcut.Save();"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        capture_output=True,
    )


if __name__ == "__main__":
    creer_raccourci()