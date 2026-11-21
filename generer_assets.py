import math
import os
from PIL import Image, ImageDraw, ImageFilter

DOSSIER_PROJET = os.path.dirname(os.path.abspath(__file__))
DOSSIER_ASSETS = os.path.join(DOSSIER_PROJET, "assets")
CHEMIN_STATIQUE = os.path.join(DOSSIER_ASSETS, "vera_statique.png")
CHEMIN_GIF = os.path.join(DOSSIER_ASSETS, "vera_parole.gif")


def _dessiner_buste(taille=512, phase=0.0, parole=False):
    """Dessine un buste cybernetique original sur fond RGBA transparent."""
    calque = Image.new("RGBA", (taille, taille), (0, 0, 0, 0))
    halo = Image.new("RGBA", (taille, taille), (0, 0, 0, 0))
    d_halo = ImageDraw.Draw(halo)
    d = ImageDraw.Draw(calque)

    cx = taille // 2
    pulse = 0.5 + 0.5 * math.sin(phase)

    # Halo arriere doux
    r_halo = int(145 + (22 * pulse if parole else 8 * pulse))
    alpha_halo = int(95 + (60 * pulse if parole else 25 * pulse))
    d_halo.ellipse(
        [cx - r_halo, 195 - r_halo, cx + r_halo, 195 + r_halo],
        fill=(0, 229, 255, alpha_halo),
    )
    halo = halo.filter(ImageFilter.GaussianBlur(radius=28))
    calque = Image.alpha_composite(calque, halo)
    d = ImageDraw.Draw(calque)

    # Epaules et buste cybernetique sombre
    buste_pts = [
        (cx - 175, taille),
        (cx - 155, 360),
        (cx - 95, 315),
        (cx - 34, 295),
        (cx + 34, 295),
        (cx + 95, 315),
        (cx + 155, 360),
        (cx + 175, taille),
    ]
    d.polygon(buste_pts, fill=(22, 27, 36, 250), outline=(0, 229, 255, 220))

    # Plastron central & lignes neon
    plastron = [
        (cx - 68, 322),
        (cx + 68, 322),
        (cx + 46, 465),
        (cx - 46, 465),
    ]
    d.polygon(plastron, fill=(14, 18, 25, 255), outline=(138, 92, 255, 220))

    lum = int(185 + 70 * pulse)
    d.line([(cx, 332), (cx, 455)], fill=(0, lum, 255, 240), width=4)
    d.line([(cx - 120, 365), (cx - 62, 345)], fill=(0, lum, 255, 200), width=3)
    d.line([(cx + 120, 365), (cx + 62, 345)], fill=(0, lum, 255, 200), width=3)

    # Coeur energetique
    r_coeur = int(12 + (5 * pulse if parole else 2 * pulse))
    d.ellipse(
        [cx - r_coeur, 392 - r_coeur, cx + r_coeur, 392 + r_coeur],
        fill=(0, 245, 255, 255),
        outline=(255, 255, 255, 220),
        width=2,
    )

    # Cou
    d.rectangle([cx - 26, 248, cx + 26, 305], fill=(26, 32, 44, 255), outline=(0, 229, 255, 160))

    # Coiffure stylisee arriere
    d.ellipse([cx - 96, 82, cx + 96, 270], fill=(18, 22, 32, 255), outline=(138, 92, 255, 200), width=3)

    # Tete / visage stylise
    decalage_tete = int(-3 * math.sin(phase)) if parole else 0
    ty = 104 + decalage_tete
    d.ellipse([cx - 72, ty, cx + 72, ty + 158], fill=(30, 36, 48, 255), outline=(0, 229, 255, 235), width=3)

    # Visiere lumineuse cybernetique
    vis_h = int(26 + (5 * pulse if parole else 0))
    d.rounded_rectangle(
        [cx - 56, ty + 54, cx + 56, ty + 54 + vis_h],
        radius=12,
        fill=(0, lum, 255, 235),
        outline=(220, 252, 255, 255),
        width=2,
    )

    # Reflet sur la visiere
    d.line([(cx - 42, ty + 62), (cx + 28, ty + 62)], fill=(255, 255, 255, 210), width=3)

    # Onde vocale au niveau de la bouche lors de la parole
    if parole:
        amp = int(4 + 9 * abs(math.sin(phase * 2.0)))
        d.rounded_rectangle(
            [cx - 24, ty + 114 - amp // 2, cx + 24, ty + 114 + amp // 2],
            radius=4,
            fill=(0, 255, 210, 240),
        )
    else:
        d.line([(cx - 18, ty + 116), (cx + 18, ty + 116)], fill=(0, 229, 255, 190), width=3)

    # Antennes laterales de casque
    d.rounded_rectangle([cx - 84, ty + 48, cx - 68, ty + 96], radius=6, fill=(138, 92, 255, 245))
    d.rounded_rectangle([cx + 68, ty + 48, cx + 84, ty + 96], radius=6, fill=(138, 92, 255, 245))

    return calque


def _rgba_vers_gif_propre(img_rgba):
    """Convertit un calque RGBA en mode P avec transparence propre et fond pre-attenue."""
    alpha = img_rgba.getchannel("A")
    fond_sombre = Image.new("RGBA", img_rgba.size, (23, 23, 23, 255))
    composee = Image.alpha_composite(fond_sombre, img_rgba).convert("RGB")
    quant = composee.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    pal = quant.getpalette()
    pal.extend([0, 0, 0])
    quant.putpalette(pal)
    masque = Image.eval(alpha, lambda a: 255 if a < 96 else 0)
    quant.paste(255, mask=masque)
    return quant


def generer_si_absent(forcer=False):
    os.makedirs(DOSSIER_ASSETS, exist_ok=True)
    crees = []

    if forcer or not os.path.exists(CHEMIN_STATIQUE):
        img = _dessiner_buste(taille=512, phase=0.8, parole=False)
        img.save(CHEMIN_STATIQUE, format="PNG")
        crees.append(CHEMIN_STATIQUE)

    if forcer or not os.path.exists(CHEMIN_GIF):
        nb_images = 16
        frames = []
        for i in range(nb_images):
            phase = (2.0 * math.pi * i) / nb_images
            rgba = _dessiner_buste(taille=512, phase=phase, parole=True)
            frames.append(_rgba_vers_gif_propre(rgba))

        frames[0].save(
            CHEMIN_GIF,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=70,
            loop=0,
            disposal=2,
            transparency=255,
        )
        crees.append(CHEMIN_GIF)

    return crees


if __name__ == "__main__":
    generes = generer_si_absent(forcer=False)
    if generes:
        print("Ressources generees :", ", ".join(generes))
    else:
        print("Ressources deja presentes, aucune modification.")