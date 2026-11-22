from collections import deque
from PIL import Image, ImageSequence

FICHIER_ENTREE = "gif4.gif"
FICHIER_SORTIE = "vera_parole_transparent.gif"
HAUTEUR_CIBLE = 260  # Taille ideale et fluide pour le widget VERA


def est_pixel_damier(r, g, b, a):
    if a < 20:
        return True
    # Supprime uniquement les carres gris clair / blancs du damier (R ≈ G ≈ B >= 180)
    return abs(r - g) <= 14 and abs(g - b) <= 14 and min(r, g, b) >= 180


def nettoyer_frame(frame):
    rgba = frame.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()
    visite = [[False] * w for _ in range(h)]
    file = deque()

    # Depart uniquement depuis les 4 bords exterieurs (preserve le blanc du tablier et de la coiffe)
    for x in range(w):
        for y in (0, h - 1):
            if est_pixel_damier(*px[x, y]):
                visite[y][x] = True
                file.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if not visite[y][x] and est_pixel_damier(*px[x, y]):
                visite[y][x] = True
                file.append((x, y))

    while file:
        x, y = file.popleft()
        px[x, y] = (0, 0, 0, 0)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not visite[ny][nx]:
                if est_pixel_damier(*px[nx, ny]):
                    visite[ny][nx] = True
                    file.append((nx, ny))

    return rgba


im = Image.open(FICHIER_ENTREE)
frames_brutes = [nettoyer_frame(f) for f in ImageSequence.Iterator(im)]

# Calcul de la zone utile (recadrage serre autour du personnage)
bbox_globale = None
for f in frames_brutes:
    bbox = f.getbbox()
    if bbox:
        if bbox_globale is None:
            bbox_globale = list(bbox)
        else:
            bbox_globale[0] = min(bbox_globale[0], bbox[0])
            bbox_globale[1] = min(bbox_globale[1], bbox[1])
            bbox_globale[2] = max(bbox_globale[2], bbox[2])
            bbox_globale[3] = max(bbox_globale[3], bbox[3])

frames_finales = []
for f in frames_brutes:
    if bbox_globale:
        f = f.crop(tuple(bbox_globale))
    ratio = HAUTEUR_CIBLE / float(f.height)
    nouvelle_largeur = max(1, int(round(f.width * ratio)))
    f = f.resize((nouvelle_largeur, HAUTEUR_CIBLE), Image.Resampling.LANCZOS)
    frames_finales.append(f)

duree = im.info.get("duration", 60)
frames_finales[0].save(
    FICHIER_SORTIE,
    save_all=True,
    append_images=frames_finales[1:],
    duration=duree,
    loop=0,
    disposal=2,
)
print(f"Termine ! Fichier pret : {FICHIER_SORTIE} ({frames_finales[0].width}x{HAUTEUR_CIBLE}px)")