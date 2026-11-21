import ctypes
import json
import logging
import math
import os
import subprocess
import sys
import time

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QImage,
    QMovie,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
    QRegion,
)
from PySide6.QtNetwork import QAbstractSocket
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QLabel,
    QMenu,
    QScrollArea,
    QSystemTrayIcon,
    QWidget,
)

from config_nobel import (
    DOSSIER_LOGS,
    DOSSIER_PROJET,
    assurer_dossiers,
    charger_config,
    lire_runtime,
    mettre_a_jour_pid_runtime,
)


def configurer_logs():
    assurer_dossiers()
    chemin_log = os.path.join(DOSSIER_LOGS, "widget.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(chemin_log, encoding="utf-8")],
    )
    return logging.getLogger("widget_nobel")


def acquerir_mutex():
    if os.name != "nt":
        return None
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, "Global\\NOBEL_VERA_WIDGET")
    if not handle:
        return None
    if kernel32.GetLastError() == 183:
        kernel32.CloseHandle(handle)
        return False
    return handle


def couleur_avec_alpha(hex_str, opacite):
    c = QColor(hex_str)
    if not c.isValid():
        c = QColor("#00E5FF")
    c.setAlphaF(max(0.0, min(1.0, float(opacite))))
    return c


def tronquer_proprement(texte, limite):
    texte = " ".join(texte.split())
    if len(texte) <= limite:
        return texte
    extrait = texte[:limite]
    for sep in (". ", "! ", "? "):
        idx = extrait.rfind(sep)
        if idx >= int(limite * 0.45):
            return extrait[: idx + 1] + " …"
    espace = extrait.rfind(" ")
    if espace > 0:
        return extrait[:espace] + " …"
    return extrait + " …"


def creer_silhouette_neon(pixmap, couleur_hex, epaisseur=4):
    """Genere une aura neon epousant exactement le canal alpha de l'image."""
    if pixmap is None or pixmap.isNull():
        return None
    img = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    teinte = QImage(img.size(), QImage.Format_ARGB32)
    c = QColor(couleur_hex)
    if not c.isValid():
        c = QColor("#00E5FF")
    teinte.fill(c)
    p = QPainter(teinte)
    p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    p.drawImage(0, 0, img)
    p.end()
    return QPixmap.fromImage(teinte)


class BulleConversation(QWidget):
    """Bulle de dialogue synchronisee avec queue pointant vers le personnage."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._cfg_bulle = {}
        self._texte = ""
        self._visible_bulle = False
        self._queue_x = 0

        self._effet_opacite = QGraphicsOpacityEffect(self)
        self._effet_opacite.setOpacity(0.0)
        self.setGraphicsEffect(self._effet_opacite)

        self._anim_fondu = QPropertyAnimation(self._effet_opacite, b"opacity", self)
        self._anim_fondu.setDuration(220)
        self._anim_fondu.setEasingCurve(QEasingCurve.OutCubic)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setStyleSheet("background: transparent;")

        self._label = QLabel(self._scroll)
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._label.setStyleSheet("background: transparent;")
        self._scroll.setWidget(self._label)

        self._timer_defilement = QTimer(self)
        self._timer_defilement.setInterval(40)
        self._timer_defilement.timeout.connect(self._avancer_defilement)

        self.hide()

    def appliquer_config(self, cfg_bulle):
        self._cfg_bulle = cfg_bulle
        self._ajuster_police()
        self.update()

    def definir_position_queue(self, x_local):
        self._queue_x = x_local
        self.update()

    def afficher_message(self, texte):
        limite = self._cfg_bulle.get("caracteres_max", 240)
        self._texte = tronquer_proprement(texte, limite)
        self._label.setText(self._texte)
        self._ajuster_police()
        self._scroll.verticalScrollBar().setValue(0)

        self._visible_bulle = True
        self.show()
        self._anim_fondu.stop()
        self._anim_fondu.setStartValue(self._effet_opacite.opacity())
        self._anim_fondu.setEndValue(1.0)
        self._anim_fondu.start()

        if self._scroll.verticalScrollBar().maximum() > 0:
            self._timer_defilement.start()
        else:
            self._timer_defilement.stop()
        self.update()

    def masquer_bulle(self):
        self._timer_defilement.stop()
        if not self._visible_bulle:
            return
        self._visible_bulle = False
        self._anim_fondu.stop()
        self._anim_fondu.setStartValue(self._effet_opacite.opacity())
        self._anim_fondu.setEndValue(0.0)
        self._anim_fondu.finished.connect(self._fin_masquage)
        self._anim_fondu.start()

    def _fin_masquage(self):
        try:
            self._anim_fondu.finished.disconnect(self._fin_masquage)
        except Exception:
            pass
        if not self._visible_bulle:
            self.hide()
            if self.parent():
                self.parent().mettre_a_jour_masque_clics()

    def _avancer_defilement(self):
        barre = self._scroll.verticalScrollBar()
        if barre.value() < barre.maximum():
            barre.setValue(barre.value() + 1)
        else:
            self._timer_defilement.stop()

    def _ajuster_police(self):
        famille = self._cfg_bulle.get("famille_police", "Segoe UI")
        taille_base = self._cfg_bulle.get("taille_police", 15)
        couleur_txt = self._cfg_bulle.get("couleur_texte", "#ECECF1")
        self._label.setStyleSheet(f"color: {couleur_txt}; background: transparent;")

        marge_h = 14
        marge_v = 12
        hauteur_queue = 10
        self._scroll.setGeometry(
            marge_h,
            marge_v,
            max(40, self.width() - 2 * marge_h),
            max(24, self.height() - 2 * marge_v - hauteur_queue),
        )

        if not self._texte:
            self._label.setFont(QFont(famille, taille_base))
            return

        largeur_dispo = max(40, self._scroll.width() - 8)
        hauteur_dispo = max(24, self._scroll.height())
        for taille in range(taille_base, 9, -1):
            police = QFont(famille, taille)
            fm = QFontMetrics(police)
            rect = fm.boundingRect(
                QRect(0, 0, largeur_dispo, 2000),
                Qt.TextWordWrap,
                self._texte,
            )
            if rect.height() <= hauteur_dispo:
                self._label.setFont(police)
                return
        self._label.setFont(QFont(famille, 10))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._ajuster_police()

    def paintEvent(self, event):
        if not self._visible_bulle and self._effet_opacite.opacity() <= 0.01:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        hauteur_queue = 10
        ep = self._cfg_bulle.get("epaisseur_contour", 1)
        marge = max(1, ep)
        rect_corps = QRectF(
            marge,
            marge,
            max(10, self.width() - 2 * marge),
            max(10, self.height() - hauteur_queue - 2 * marge),
        )
        rayon = min(self._cfg_bulle.get("rayon_angles", 14), rect_corps.height() / 2)

        chemin = QPainterPath()
        chemin.addRoundedRect(rect_corps, rayon, rayon)

        qx = max(rect_corps.left() + rayon + 10, min(rect_corps.right() - rayon - 10, self._queue_x))
        bas_y = rect_corps.bottom()
        queue = QPainterPath()
        queue.moveTo(qx - 8, bas_y - 1)
        queue.lineTo(qx, bas_y + hauteur_queue - 1)
        queue.lineTo(qx + 8, bas_y - 1)
        queue.closeSubpath()
        chemin = chemin.united(queue)

        fond = couleur_avec_alpha(
            self._cfg_bulle.get("couleur_fond", "#2A2A2E"),
            self._cfg_bulle.get("opacite_fond", 0.92),
        )
        painter.fillPath(chemin, fond)

        if ep > 0:
            contour = couleur_avec_alpha(self._cfg_bulle.get("couleur_contour", "#00E5FF"), 0.85)
            painter.setPen(QPen(contour, ep))
            painter.drawPath(chemin)


class WidgetVera(QWidget):
    """Widget flottant cybernetique sans bordure ni vol de focus."""

    def __init__(self, logger):
        super().__init__(None)
        self.logger = logger
        self.cfg = charger_config(logger)
        self.etat = "idle"
        self.assistant_connectee = False
        self.serveur_connecte = False
        self.phase = 0.0
        self.debut_erreur = 0.0

        self._glissement = False
        self._redimensionnement = False
        self._pos_depart_souris = QPoint()
        self._geom_depart = QRect()

        self._pixmap_fond = None
        self._pixmap_statique = None
        self._pixmaps_expressions = {}
        self._movie_parole = None
        self._movie_actif = False

        self.setWindowTitle("VÉRA Widget")
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self.bulle = BulleConversation(self)
        self._timer_disparition_bulle = QTimer(self)
        self._timer_disparition_bulle.setSingleShot(True)
        self._timer_disparition_bulle.timeout.connect(self._masquer_bulle_et_masque)

        self._timer_anim = QTimer(self)
        self._timer_anim.setInterval(33)
        self._timer_anim.timeout.connect(self._tick_animation)

        self._timer_reconnexion = QTimer(self)
        self._timer_reconnexion.setInterval(2000)
        self._timer_reconnexion.timeout.connect(self._connecter_ws)
        self._perte_serveur_depuis = None

        self.ws = QWebSocket()
        self.ws.connected.connect(self._sur_ws_connecte)
        self.ws.disconnected.connect(self._sur_ws_deconnecte)
        self.ws.textMessageReceived.connect(self._sur_ws_message)

        self._creer_icone_notification()
        self._recharger_ressources()
        self._appliquer_geometrie_initiale()
        self._connecter_ws()
        self._ajustement_cadence_animation()

    # ---- Icone zone de notification ----

    def _creer_icone_notification(self):
        pix = QPixmap(32, 32)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setBrush(QColor("#171717"))
        p.setPen(QPen(QColor("#00E5FF"), 2.5))
        p.drawEllipse(3, 3, 26, 26)
        p.setBrush(QColor("#00E5FF"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(11, 11, 10, 10)
        p.end()

        self.tray = QSystemTrayIcon(QIcon(pix), self)
        self.tray.setToolTip("VÉRA - Assistante vocale")
        menu = QMenu()

        act_afficher = QAction("Afficher / Masquer le widget", self)
        act_afficher.triggered.connect(self._basculer_visibilite)
        menu.addAction(act_afficher)

        act_reduire = QAction("Mode pastille réduite", self)
        act_reduire.triggered.connect(self._basculer_reduit)
        menu.addAction(act_reduire)

        act_gif = QAction("Mode silhouette néon (sans cadre)", self)
        act_gif.triggered.connect(self._basculer_mode_gif)
        menu.addAction(act_gif)

        act_admin = QAction("Ouvrir l'administration", self)
        act_admin.triggered.connect(self._ouvrir_administration)
        menu.addAction(act_admin)

        menu.addSeparator()
        act_quitter = QAction("Fermer le widget", self)
        act_quitter.triggered.connect(self._fermer_widget)
        menu.addAction(act_quitter)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._sur_clic_tray)
        self.tray.show()

    def _sur_clic_tray(self, raison):
        if raison in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._basculer_visibilite()

    def _basculer_visibilite(self):
        if self.isVisible():
            self.hide()
            self.cfg["fenetre"]["visible"] = False
        else:
            self.show()
            self.cfg["fenetre"]["visible"] = True
            self.mettre_a_jour_masque_clics()
        self._ajustement_cadence_animation()
        self._envoyer_geometrie()

    def _basculer_reduit(self):
        reduit = not self.cfg["fenetre"].get("reduit", False)
        self.cfg["fenetre"]["reduit"] = reduit
        if reduit:
            self.cfg["fenetre"]["mode_gif_seul"] = False
            self.bulle.hide()
        self._appliquer_geometrie_initiale(conserver_ancrage=True)
        self._envoyer_geometrie()

    def _basculer_mode_gif(self):
        actif = not self.cfg["fenetre"].get("mode_gif_seul", False)
        self.cfg["fenetre"]["mode_gif_seul"] = actif
        if actif:
            self.cfg["fenetre"]["reduit"] = False
        self._appliquer_geometrie_initiale(conserver_ancrage=True)
        self._envoyer_geometrie()

    def _ouvrir_administration(self):
        bat_admin = os.path.join(DOSSIER_PROJET, "lancer_admin.bat")
        if os.path.exists(bat_admin):
            subprocess.Popen(
                ["cmd.exe", "/c", bat_admin],
                cwd=DOSSIER_PROJET,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )

    def _fermer_widget(self):
        self.tray.hide()
        self.ws.close()
        QApplication.quit()

    # ---- Ressources graphiques ----

    def _charger_pixmap(self, rel_path):
        if not rel_path:
            return None
        chemin = os.path.join(DOSSIER_PROJET, rel_path.replace("/", os.sep))
        if os.path.exists(chemin):
            pix = QPixmap(chemin)
            if not pix.isNull():
                return pix
        return None

    def _recharger_ressources(self):
        app_cfg = self.cfg.get("apparence", {})
        self._pixmap_fond = self._charger_pixmap(app_cfg.get("image_fond"))

        perso = self.cfg.get("personnage", {})
        self._pixmap_statique = self._charger_pixmap(perso.get("image_statique"))

        self._pixmaps_expressions = {}
        for cle, rel in perso.get("expressions", {}).items():
            pix = self._charger_pixmap(rel)
            if pix is not None:
                self._pixmaps_expressions[cle] = pix

        if self._movie_parole is not None:
            self._movie_parole.stop()
            self._movie_parole.deleteLater()
            self._movie_parole = None
            self._movie_actif = False

        rel_gif = perso.get("gif_parole")
        if rel_gif:
            chemin_gif = os.path.join(DOSSIER_PROJET, rel_gif.replace("/", os.sep))
            if os.path.exists(chemin_gif):
                movie = QMovie(chemin_gif)
                if movie.isValid():
                    movie.frameChanged.connect(self.update)
                    self._movie_parole = movie

    # ---- Geometrie & Masque de clics ----

    def _zone_bulle_hauteur(self):
        if self.cfg["fenetre"].get("reduit", False):
            return 0
        h_carte = self._hauteur_carte()
        pct = self.cfg.get("bulle", {}).get("hauteur_max_pourcent", 60)
        return max(90, int(h_carte * (pct / 100.0)) + 20)

    def _hauteur_carte(self):
        fen = self.cfg["fenetre"]
        if fen.get("reduit", False):
            return fen.get("taille_reduite", 96)
        ecran = QApplication.primaryScreen()
        zone = ecran.availableGeometry() if ecran else QRect(0, 0, 1920, 1040)
        if fen.get("mode_taille") == "fixe" and fen.get("hauteur_px"):
            h = fen["hauteur_px"]
        else:
            h = int(zone.height() * fen.get("hauteur_ratio", 0.2))
        h_min = fen.get("min_hauteur", 180)
        h_max = int(zone.height() * fen.get("max_hauteur_ratio", 0.5))
        return max(h_min, min(max(h_min, h_max), h))

    def _largeur_carte(self):
        fen = self.cfg["fenetre"]
        if fen.get("reduit", False):
            return fen.get("taille_reduite", 96)
        if fen.get("mode_gif_seul", False):
            return max(220, int(self._hauteur_carte() * 1.15))
        ecran = QApplication.primaryScreen()
        zone = ecran.availableGeometry() if ecran else QRect(0, 0, 1920, 1040)
        if fen.get("mode_taille") == "fixe" and fen.get("largeur_px"):
            w = fen["largeur_px"]
        else:
            w = int(zone.width() * fen.get("largeur_ratio", 0.3333))
        w_min = fen.get("min_largeur", 360)
        w_max = int(zone.width() * fen.get("max_largeur_ratio", 0.6))
        return max(w_min, min(max(w_min, w_max), w))

    def _appliquer_geometrie_initiale(self, conserver_ancrage=False):
        fen = self.cfg["fenetre"]
        w = self._largeur_carte()
        h_carte = self._hauteur_carte()
        h_totale = h_carte + self._zone_bulle_hauteur()

        ecran = QApplication.primaryScreen()
        zone = ecran.availableGeometry() if ecran else QRect(0, 0, 1920, 1040)

        x_enregistre = fen.get("x")
        y_enregistre = fen.get("y")

        if (
            not conserver_ancrage
            and isinstance(x_enregistre, int)
            and isinstance(y_enregistre, int)
        ):
            cible = QRect(x_enregistre, y_enregistre, w, h_totale)
            ecran_trouve = False
            for scr in QApplication.screens():
                if scr.availableGeometry().intersects(cible.adjusted(20, 20, -20, -20)):
                    ecran_trouve = True
                    break
            if ecran_trouve:
                self.setGeometry(cible)
                self._placer_bulle()
                self.mettre_a_jour_masque_clics()
                return

        mx = fen.get("marge_x", 24)
        my = fen.get("marge_y", 24)
        ancrage = fen.get("ancrage", "bas_droite")

        if ancrage == "bas_gauche":
            x = zone.left() + mx
            y = zone.bottom() - h_totale - my + 1
        elif ancrage == "haut_droite":
            x = zone.right() - w - mx + 1
            y = zone.top() + my
        elif ancrage == "haut_gauche":
            x = zone.left() + mx
            y = zone.top() + my
        else:
            x = zone.right() - w - mx + 1
            y = zone.bottom() - h_totale - my + 1

        self.setGeometry(x, y, w, h_totale)
        self._placer_bulle()
        self.mettre_a_jour_masque_clics()

    def _rect_carte(self):
        h_bulle = self._zone_bulle_hauteur()
        return QRect(0, h_bulle, self.width(), max(60, self.height() - h_bulle))

    def _placer_bulle(self):
        self.bulle.appliquer_config(self.cfg.get("bulle", {}))
        if self.cfg["fenetre"].get("reduit", False):
            self.bulle.hide()
            return

        rect_c = self._rect_carte()
        bcfg = self.cfg.get("bulle", {})
        if self.cfg["fenetre"].get("mode_gif_seul", False):
            bw = max(240, rect_c.width())
        else:
            bw = max(180, int(rect_c.width() * (bcfg.get("largeur_pourcent", 70) / 100.0)))
        bh = max(72, self._zone_bulle_hauteur() - 10)
        dx = bcfg.get("decalage_x", 0)
        dy = bcfg.get("decalage_y", 0)

        bx = max(0, min(self.width() - bw, self.width() - bw - 6 + dx))
        by = max(0, self._zone_bulle_hauteur() - bh - 4 + dy)
        self.bulle.setGeometry(bx, by, bw, bh)

        centre_perso_x = (
            rect_c.center().x()
            if self.cfg["fenetre"].get("mode_gif_seul", False)
            else rect_c.right() - int(rect_c.height() * 0.5)
        )
        self.bulle.definir_position_queue(centre_perso_x - bx)

    def mettre_a_jour_masque_clics(self):
        """Les zones transparentes autour de la carte et de la bulle laissent passer les clics."""
        rect_c = self._rect_carte()
        region = QRegion(rect_c)
        if self.bulle.isVisible():
            region = region.united(QRegion(self.bulle.geometry()))
        self.setMask(region)

    def _masquer_bulle_et_masque(self):
        self.bulle.masquer_bulle()
        QTimer.singleShot(250, self.mettre_a_jour_masque_clics)

    # ---- WebSocket & Serveur ----

    def _connecter_ws(self):
        if self.ws.state() in (QAbstractSocket.ConnectedState, QAbstractSocket.ConnectingState):
            return
        runtime = lire_runtime()
        port = runtime.get("port")
        jeton = runtime.get("token")
        if not port or not jeton:
            self._gerer_perte_serveur()
            return
        url = QUrl(f"ws://127.0.0.1:{port}/ws?role=widget&token={jeton}")
        self.ws.open(url)

    def _sur_ws_connecte(self):
        self.serveur_connecte = True
        self._perte_serveur_depuis = None
        self._timer_reconnexion.stop()
        mettre_a_jour_pid_runtime("widget", os.getpid())
        self.update()

    def _sur_ws_deconnecte(self):
        self.serveur_connecte = False
        self.assistant_connectee = False
        self._gerer_perte_serveur()
        self.update()

    def _gerer_perte_serveur(self):
        if self._perte_serveur_depuis is None:
            self._perte_serveur_depuis = time.monotonic()
        if not self._timer_reconnexion.isActive():
            self._timer_reconnexion.start()
        if (time.monotonic() - self._perte_serveur_depuis) > 15.0:
            self.logger.info("Serveur absent depuis plus de 15 s, fermeture propre du widget.")
            self._fermer_widget()

    def _sur_ws_message(self, texte):
        try:
            msg = json.loads(texte)
        except Exception:
            return

        mtype = msg.get("type")
        if mtype == "hello":
            self.assistant_connectee = bool(msg.get("assistant_connected", False))
            if isinstance(msg.get("config"), dict):
                self._appliquer_config_complete(msg["config"])
            self._changer_etat(msg.get("state", "idle"))

        elif mtype == "config":
            if isinstance(msg.get("config"), dict):
                self._appliquer_config_complete(msg["config"])

        elif mtype == "assets_changed":
            self._recharger_ressources()
            self.update()

        elif mtype == "assistant_status":
            self.assistant_connectee = bool(msg.get("connected", False))
            self.update()

        elif mtype == "state":
            self._changer_etat(msg.get("state", "idle"))

        elif mtype == "speech_start":
            self._timer_disparition_bulle.stop()
            if not self.cfg["fenetre"].get("reduit", False):
                self.bulle.afficher_message(msg.get("text", ""))
                self.mettre_a_jour_masque_clics()

        elif mtype == "speech_end":
            delai = self.cfg.get("bulle", {}).get("duree_affichage_apres_parole_ms", 4000)
            self._timer_disparition_bulle.start(delai)

        elif mtype == "quit":
            self._fermer_widget()

    def _appliquer_config_complete(self, nouvelle_cfg):
        self.cfg = nouvelle_cfg
        self._recharger_ressources()
        self._appliquer_geometrie_initiale(conserver_ancrage=False)
        self.setWindowOpacity(self.cfg.get("apparence", {}).get("transparence_globale", 1.0))
        if self.cfg["fenetre"].get("visible", True):
            if not self.isVisible():
                self.show()
        else:
            self.hide()
        self._ajustement_cadence_animation()
        self.update()

    def _changer_etat(self, nouvel_etat):
        if nouvel_etat not in ("idle", "listening", "processing", "speaking", "error"):
            nouvel_etat = "idle"
        self.etat = nouvel_etat
        if nouvel_etat == "error":
            self.debut_erreur = time.monotonic()

        if nouvel_etat == "speaking" and self._movie_parole is not None:
            if not self._movie_actif:
                self._movie_parole.start()
                self._movie_actif = True
        else:
            if self._movie_parole is not None and self._movie_actif:
                self._movie_parole.stop()
                self._movie_actif = False

        self._ajustement_cadence_animation()
        self.update()

    def _envoyer_geometrie(self):
        if self.ws.state() != QAbstractSocket.ConnectedState:
            return
        rect_c = self._rect_carte()
        payload = {
            "type": "geometry",
            "x": self.x(),
            "y": self.y(),
            "w": rect_c.width(),
            "h": rect_c.height(),
            "reduit": bool(self.cfg["fenetre"].get("reduit", False)),
            "visible": bool(self.isVisible()),
        }
        try:
            self.ws.sendTextMessage(json.dumps(payload))
        except Exception:
            pass

    # ---- Animations & Performance ----

    def _ajustement_cadence_animation(self):
        anim = self.cfg.get("apparence", {}).get("animations", {})
        if not self.isVisible() or not anim.get("actives", True):
            self._timer_anim.stop()
            return
        if self.etat in ("listening", "processing", "speaking", "error"):
            self._timer_anim.setInterval(33)
            if not self._timer_anim.isActive():
                self._timer_anim.start()
        elif anim.get("respiration_halo", True):
            self._timer_anim.setInterval(65)
            if not self._timer_anim.isActive():
                self._timer_anim.start()
        else:
            self._timer_anim.stop()

    def _tick_animation(self):
        vitesse = self.cfg.get("apparence", {}).get("animations", {}).get("vitesse", 1.0)
        self.phase = (self.phase + 0.08 * vitesse) % (2 * math.pi)
        if self.etat == "error" and (time.monotonic() - self.debut_erreur) >= 2.0:
            self._changer_etat("idle")
            return
        self.update()

    # ---- Souris : deplacement & redimensionnement ----

    def _dans_poignee_redimension(self, pos):
        if self.cfg["fenetre"].get("reduit", False):
            return False
        rc = self._rect_carte()
        return QRect(rc.left(), rc.top(), 18, 18).contains(pos)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            if self._dans_poignee_redimension(pos):
                self._redimensionnement = True
                self._pos_depart_souris = event.globalPosition().toPoint()
                self._geom_depart = self.geometry()
                event.accept()
                return
            if self._rect_carte().contains(pos):
                self._glissement = True
                self._pos_depart_souris = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
                return
        elif event.button() == Qt.RightButton:
            self.tray.contextMenu().popup(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if self._dans_poignee_redimension(pos):
            self.setCursor(Qt.SizeFDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

        if self._redimensionnement:
            delta = event.globalPosition().toPoint() - self._pos_depart_souris
            fen = self.cfg["fenetre"]
            min_w = fen.get("min_largeur", 360)
            min_h_carte = fen.get("min_hauteur", 180)
            h_bulle = self._zone_bulle_hauteur()

            nouv_w = max(min_w, self._geom_depart.width() - delta.x())
            nouv_h_carte = max(min_h_carte, (self._geom_depart.height() - h_bulle) - delta.y())
            nouv_h_totale = nouv_h_carte + h_bulle

            nouv_x = self._geom_depart.right() - nouv_w + 1
            nouv_y = self._geom_depart.bottom() - nouv_h_totale + 1
            self.setGeometry(nouv_x, nouv_y, nouv_w, nouv_h_totale)
            self._placer_bulle()
            self.mettre_a_jour_masque_clics()
            event.accept()
        elif self._glissement:
            nouv_pos = event.globalPosition().toPoint() - self._pos_depart_souris
            self.move(nouv_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._glissement or self._redimensionnement:
            self._glissement = False
            self._redimensionnement = False
            fen = self.cfg["fenetre"]
            fen["mode_taille"] = "fixe"
            fen["x"] = self.x()
            fen["y"] = self.y()
            rc = self._rect_carte()
            fen["largeur_px"] = rc.width()
            fen["hauteur_px"] = rc.height()
            self._envoyer_geometrie()
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self._rect_carte().contains(event.position().toPoint()):
            self._basculer_reduit()

    # ---- Rendu QPainter ----

    def _image_active(self):
        if self.etat == "speaking" and self._movie_parole is not None:
            pix = self._movie_parole.currentPixmap()
            if not pix.isNull():
                return pix
        correspondance = {
            "listening": "ecoute",
            "processing": "reflexion",
            "idle": "attente",
            "error": "erreur",
        }
        cle = correspondance.get(self.etat)
        if cle and cle in self._pixmaps_expressions:
            return self._pixmaps_expressions[cle]
        return self._pixmap_statique

    def _dessiner_personnage_secours(self, painter, cible):
        cx = cible.center().x()
        cy = cible.center().y()
        r = min(cible.width(), cible.height()) * 0.34
        neon = QColor(self.cfg["apparence"]["couleur_neon"])
        painter.setPen(QPen(neon, 2.5))
        painter.setBrush(QColor(22, 28, 38, 220))
        painter.drawEllipse(QPointF(cx, cy - r * 0.25), r * 0.55, r * 0.65)
        painter.drawRoundedRect(
            QRectF(cx - r * 0.85, cy + r * 0.45, r * 1.7, r * 0.9), 18, 18
        )
        painter.setBrush(neon)
        painter.drawRoundedRect(
            QRectF(cx - r * 0.36, cy - r * 0.35, r * 0.72, r * 0.18), 6, 6
        )

    def _dessiner_silhouette_neon_et_personnage(self, painter, scaled, px, py, couleur_neon_hex, intensite, pulse):
        """Dessine un contour lumineux epousant la silhouette du personnage puis le personnage."""
        aura = creer_silhouette_neon(scaled, couleur_neon_hex)
        if aura is not None:
            rayon = max(2, int(3 + 3 * pulse))
            decalages = [
                (-rayon, 0),
                (rayon, 0),
                (0, -rayon),
                (0, rayon),
                (-rayon, -rayon),
                (rayon, -rayon),
                (-rayon, rayon),
                (rayon, rayon),
            ]
            painter.save()
            painter.setOpacity(min(1.0, 0.22 + 0.25 * intensite * (0.7 + 0.3 * pulse)))
            for ox, oy in decalages:
                painter.drawPixmap(px + ox, py + oy, aura)
            painter.restore()
        painter.drawPixmap(px, py, scaled)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        app = self.cfg["apparence"]
        fen = self.cfg["fenetre"]
        perso_cfg = self.cfg["personnage"]
        rc = QRectF(self._rect_carte()).adjusted(2, 2, -2, -2)
        mode_gif_seul = bool(fen.get("mode_gif_seul", False))

        pulse = 0.5 + 0.5 * math.sin(self.phase)

        couleur_etat = QColor(app["couleur_neon"])
        if self.etat == "error":
            couleur_etat = QColor("#FF3B5C")
        elif self.etat == "listening":
            couleur_etat = QColor("#00FFA3")
        elif self.etat == "processing":
            couleur_etat = QColor(app["couleur_neon_secondaire"])

        if not self.assistant_connectee:
            painter.setOpacity(0.68)

        # MODE SILHOUETTE NEON SANS CADRE (GIF / Personnage detoure)
        if mode_gif_seul:
            pix = self._image_active()
            echelle = perso_cfg.get("taille_pourcent", 90) / 100.0
            dx = perso_cfg.get("decalage_x", 0)
            dy = perso_cfg.get("decalage_y", 0)
            h_cible = max(48, int(rc.height() * echelle))
            couleur_contour_sil = (
                couleur_etat.name() if self.etat != "idle" else app["couleur_neon"]
            )
            if pix is not None and not pix.isNull():
                scaled = pix.scaledToHeight(h_cible, Qt.SmoothTransformation)
                px = int(rc.center().x() - scaled.width() / 2 + dx)
                py = int(rc.bottom() - scaled.height() + dy)
                self._dessiner_silhouette_neon_et_personnage(
                    painter,
                    scaled,
                    px,
                    py,
                    couleur_contour_sil,
                    app.get("intensite_neon", 0.8),
                    pulse,
                )
            else:
                zone_secours = QRectF(
                    rc.center().x() - h_cible / 2 + dx,
                    rc.bottom() - h_cible + dy,
                    h_cible,
                    h_cible,
                )
                self._dessiner_personnage_secours(painter, zone_secours)
            return

        # MODE CARTE CLASSIQUE / PASTILLE REDUITE
        rayon = rc.height() / 2 if fen.get("reduit", False) else app["rayon_angles"]
        fond = couleur_avec_alpha(app["couleur_fond"], app["opacite_fond"])
        chemin_carte = QPainterPath()
        chemin_carte.addRoundedRect(rc, rayon, rayon)
        painter.fillPath(chemin_carte, fond)

        # Image de fond personnalisee si configuree
        if self._pixmap_fond is not None and not self._pixmap_fond.isNull():
            painter.save()
            painter.setClipPath(chemin_carte)
            painter.setOpacity(app.get("opacite_image_fond", 0.65))
            fond_scaled = self._pixmap_fond.scaled(
                rc.size().toSize(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            fx = int(rc.center().x() - fond_scaled.width() / 2)
            fy = int(rc.center().y() - fond_scaled.height() / 2)
            painter.drawPixmap(fx, fy, fond_scaled)
            painter.restore()

        # Halo anime derriere le personnage
        halo_cfg = app.get("halo", {})
        if halo_cfg.get("actif", True):
            centre_halo = (
                rc.center()
                if fen.get("reduit", False)
                else QPointF(rc.right() - rc.height() * 0.52, rc.center().y())
            )
            rayon_halo = halo_cfg.get("rayon", 40) + (
                14 * pulse if self.etat in ("speaking", "listening") else 6 * pulse
            )
            c_halo = QColor(
                couleur_etat if self.etat != "idle" else halo_cfg.get("couleur", "#00E5FF")
            )
            intensite = halo_cfg.get("intensite", 0.6) * (0.65 + 0.35 * pulse)
            grad = QRadialGradient(centre_halo, max(24.0, rayon_halo * 1.8))
            c_centre = QColor(c_halo)
            c_centre.setAlphaF(min(1.0, intensite * 0.65))
            c_bord = QColor(c_halo)
            c_bord.setAlphaF(0.0)
            grad.setColorAt(0.0, c_centre)
            grad.setColorAt(1.0, c_bord)
            painter.save()
            painter.setClipPath(chemin_carte)
            painter.fillRect(rc, grad)
            painter.restore()

        # Effets lumineux d'etat autour du personnage
        centre_p = (
            rc.center()
            if fen.get("reduit", False)
            else QPointF(rc.right() - rc.height() * 0.5, rc.center().y())
        )
        rayon_effet = min(rc.width(), rc.height()) * 0.42
        if self.etat == "listening":
            painter.setPen(QPen(couleur_etat, 2.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(
                centre_p,
                rayon_effet * (0.85 + 0.18 * pulse),
                rayon_effet * (0.85 + 0.18 * pulse),
            )
        elif self.etat == "processing":
            pen_arc = QPen(couleur_etat, 3.0)
            pen_arc.setCapStyle(Qt.RoundCap)
            painter.setPen(pen_arc)
            rect_arc = QRectF(
                centre_p.x() - rayon_effet,
                centre_p.y() - rayon_effet,
                rayon_effet * 2,
                rayon_effet * 2,
            )
            angle_depart = int(math.degrees(self.phase) * 16)
            painter.drawArc(rect_arc, angle_depart, 110 * 16)

        # Personnage ancre en bas a droite
        pix = self._image_active()
        echelle = perso_cfg.get("taille_pourcent", 90) / 100.0
        dx = perso_cfg.get("decalage_x", 0)
        dy = perso_cfg.get("decalage_y", 0)
        h_cible = max(32, int(rc.height() * echelle))

        painter.save()
        painter.setClipPath(chemin_carte)
        if pix is not None and not pix.isNull():
            scaled = pix.scaledToHeight(h_cible, Qt.SmoothTransformation)
            if fen.get("reduit", False):
                px = int(rc.center().x() - scaled.width() / 2 + dx)
                py = int(rc.bottom() - scaled.height() + dy)
            else:
                px = int(rc.right() - scaled.width() - 10 + dx)
                py = int(rc.bottom() - scaled.height() + dy)
            painter.drawPixmap(px, py, scaled)
        else:
            zone_secours = QRectF(
                rc.right() - h_cible - 8 + dx, rc.bottom() - h_cible + dy, h_cible, h_cible
            )
            self._dessiner_personnage_secours(painter, zone_secours)
        painter.restore()

        # Texte et statut dans la carte (hors mode reduit)
        if not fen.get("reduit", False):
            marge_in = fen.get("marges_internes", 16)
            nom = self.cfg.get("nom_affiche", "VÉRA")
            painter.setPen(QColor("#ECECF1"))
            painter.setFont(QFont("Segoe UI", 14, QFont.Bold))
            painter.drawText(
                QRectF(rc.left() + marge_in, rc.top() + marge_in, rc.width() * 0.55, 28),
                Qt.AlignLeft | Qt.AlignVCenter,
                nom,
            )

            libelles = {
                "idle": "En veille",
                "listening": "Écoute en cours…",
                "processing": "Analyse…",
                "speaking": "Parole…",
                "error": "Erreur détectée",
            }
            statut_txt = (
                libelles.get(self.etat, "En veille")
                if self.assistant_connectee
                else "Assistante hors ligne"
            )
            painter.setPen(couleur_etat if self.assistant_connectee else QColor("#9CA3AF"))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(
                QRectF(rc.left() + marge_in, rc.top() + marge_in + 26, rc.width() * 0.55, 22),
                Qt.AlignLeft | Qt.AlignVCenter,
                statut_txt,
            )

            c_point = QColor("#00FFA3") if self.assistant_connectee else QColor("#6B7280")
            painter.setBrush(c_point)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(
                QPointF(rc.left() + marge_in + 5, rc.bottom() - marge_in - 5), 4.5, 4.5
            )

            pen_poignee = QPen(couleur_avec_alpha(app["couleur_contour"], 0.45), 1.5)
            painter.setPen(pen_poignee)
            painter.drawLine(
                int(rc.left() + 6), int(rc.top() + 12), int(rc.left() + 12), int(rc.top() + 6)
            )

        # Contour neon
        ep = app.get("epaisseur_contour", 2)
        if ep > 0:
            c_contour = couleur_avec_alpha(
                "#FF3B5C" if self.etat == "error" else app["couleur_contour"],
                0.75 + 0.25 * app.get("intensite_neon", 0.8),
            )
            painter.setPen(QPen(c_contour, ep))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(chemin_carte)


def main():
    logger = configurer_logs()
    mutex = acquerir_mutex()
    if mutex is False:
        logger.info("Une instance du widget est deja active.")
        return

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    widget = WidgetVera(logger)
    if widget.cfg["fenetre"].get("visible", True):
        widget.show()
        widget.mettre_a_jour_masque_clics()

    code = app.exec()
    mettre_a_jour_pid_runtime("widget", None)
    if mutex:
        ctypes.windll.kernel32.CloseHandle(mutex)
    sys.exit(code)


if __name__ == "__main__":
    main()