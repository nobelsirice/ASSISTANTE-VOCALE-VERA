import React from "react";
import { getAssetUrl } from "../api.js";

function hexToRgba(hex, alpha) {
  const clean = (hex || "#171717").replace("#", "");
  if (clean.length !== 6) return `rgba(23, 23, 23, ${alpha})`;
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

const LIBELLES_ETAT = {
  idle: "En veille",
  listening: "Écoute en cours…",
  processing: "Analyse…",
  speaking: "Parole…",
  error: "Erreur détectée",
};

export default function ApercuWidget({
  config,
  simState,
  simMessage,
  assetVersion,
}) {
  if (!config) return null;

  const { fenetre, apparence, personnage, bulle } = config;
  const isError = simState === "error";
  const isListening = simState === "listening";
  const isProcessing = simState === "processing";
  const isSpeaking = simState === "speaking";
  const modeGifSeul = Boolean(fenetre.mode_gif_seul);
  const modeFilNeon = Boolean(fenetre.mode_fil_neon);

  let stateColor = apparence.couleur_neon;
  if (isError) stateColor = "#FF3B5C";
  else if (isListening) stateColor = "#00FFA3";
  else if (isProcessing) stateColor = apparence.couleur_neon_secondaire;

  const secondaryColor = apparence.couleur_neon_secondaire || "#8A5CFF";

  const cardWidth = fenetre.reduit
    ? fenetre.taille_reduite
    : modeGifSeul
    ? 230
    : Math.min(440, Math.max(280, fenetre.largeur_px || 380));
  const cardHeight = fenetre.reduit
    ? fenetre.taille_reduite
    : Math.min(230, Math.max(150, fenetre.hauteur_px || 185));

  let relAsset = personnage.image_statique;
  if (isSpeaking && personnage.gif_parole) {
    relAsset = personnage.gif_parole;
  } else if (isListening && personnage.expressions?.ecoute) {
    relAsset = personnage.expressions.ecoute;
  } else if (isProcessing && personnage.expressions?.reflexion) {
    relAsset = personnage.expressions.reflexion;
  } else if (simState === "idle" && personnage.expressions?.attente) {
    relAsset = personnage.expressions.attente;
  } else if (isError && personnage.expressions?.erreur) {
    relAsset = personnage.expressions.erreur;
  }

  const imgSrc = getAssetUrl(relAsset, assetVersion);
  const bgImgSrc = getAssetUrl(apparence.image_fond, assetVersion);

  const shadowStyle = apparence.ombre?.actif
    ? `0 10px ${apparence.ombre.flou}px ${hexToRgba(
        apparence.ombre.couleur,
        apparence.ombre.opacite
      )}`
    : "none";

  const texteBulle = (simMessage || "").slice(0, bulle.caracteres_max || 240);

  return (
    <div className="preview-stage">
      {/* Bulle au-dessus du widget */}
      {!fenetre.reduit && texteBulle && (
        <div
          style={{
            position: "relative",
            width: modeGifSeul ? `${cardWidth}px` : `${bulle.largeur_pourcent}%`,
            maxWidth: `${cardWidth}px`,
            marginBottom: "12px",
            marginRight: `${Math.max(0, 12 - (bulle.decalage_x || 0))}px`,
            transform: `translateY(${bulle.decalage_y || 0}px)`,
            background: hexToRgba(bulle.couleur_fond, bulle.opacite_fond),
            color: bulle.couleur_texte,
            fontFamily: bulle.famille_police,
            fontSize: `${bulle.taille_police}px`,
            lineHeight: 1.4,
            padding: "10px 14px",
            borderRadius: `${bulle.rayon_angles}px`,
            border: `${bulle.epaisseur_contour}px solid ${bulle.couleur_contour}`,
            boxShadow: "0 6px 18px rgba(0,0,0,0.35)",
            wordBreak: "break-word",
          }}
        >
          {texteBulle}
          <div
            style={{
              position: "absolute",
              bottom: "-8px",
              right: modeGifSeul ? "50%" : "46px",
              width: "14px",
              height: "14px",
              background: hexToRgba(bulle.couleur_fond, bulle.opacite_fond),
              borderRight: `${bulle.epaisseur_contour}px solid ${bulle.couleur_contour}`,
              borderBottom: `${bulle.epaisseur_contour}px solid ${bulle.couleur_contour}`,
              transform: "rotate(45deg)",
            }}
          />
        </div>
      )}

      {/* MODE SILHOUETTE NEON SANS CADRE */}
      {modeGifSeul ? (
        <div
          style={{
            position: "relative",
            width: `${cardWidth}px`,
            height: `${cardHeight}px`,
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "center",
          }}
        >
          {modeFilNeon && (
            <div
              style={{
                position: "absolute",
                inset: "6px",
                borderRadius: "50%",
                padding: "3px",
                background: `conic-gradient(from 0deg, #ffffff, ${stateColor}, ${secondaryColor}, transparent 45%, #ffffff 50%, ${stateColor} 58%, ${secondaryColor} 75%, transparent 95%)`,
                WebkitMask:
                  "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
                WebkitMaskComposite: "xor",
                maskComposite: "exclude",
                animation: "neonSnakeSpin 2.4s linear infinite",
                pointerEvents: "none",
              }}
            />
          )}
          {imgSrc && (
            <img
              src={imgSrc}
              alt="Silhouette VÉRA"
              style={{
                height: `${personnage.taille_pourcent}%`,
                objectFit: "contain",
                transform: `translate(${personnage.decalage_x || 0}px, ${
                  personnage.decalage_y || 0
                }px)`,
                filter: `drop-shadow(0 0 1.5px #ffffff) drop-shadow(0 0 6px ${stateColor}) drop-shadow(0 0 14px ${secondaryColor})`,
              }}
            />
          )}
        </div>
      ) : (
        /* MODE CARTE CLASSIQUE / PASTILLE REDUITE */
        <div
          style={{
            position: "relative",
            width: `${cardWidth}px`,
            height: `${cardHeight}px`,
            borderRadius: fenetre.reduit
              ? "999px"
              : `${apparence.rayon_angles}px`,
            background: hexToRgba(
              apparence.couleur_fond,
              apparence.opacite_fond
            ),
            border: `${apparence.epaisseur_contour}px solid ${
              isError ? "#FF3B5C" : apparence.couleur_contour
            }`,
            boxShadow: modeFilNeon
              ? `0 0 18px ${hexToRgba(stateColor, 0.55)}, inset 0 0 12px ${hexToRgba(
                  secondaryColor,
                  0.45
                )}`
              : shadowStyle,
            opacity: apparence.transparence_globale,
            overflow: "hidden",
            transition: "all 0.2s ease",
          }}
        >
          {/* Serpent fil neon sur le bord */}
          {modeFilNeon && (
            <div
              style={{
                position: "absolute",
                inset: "-40%",
                background: `conic-gradient(from 0deg, #ffffff, ${stateColor}, ${secondaryColor}, transparent 42%, #ffffff 50%, ${stateColor} 58%, ${secondaryColor} 75%, transparent 92%)`,
                animation: "neonSnakeSpin 2.5s linear infinite",
                padding: "3px",
                pointerEvents: "none",
                opacity: 0.45,
              }}
            />
          )}

          {/* Image de fond personnalisee */}
          {bgImgSrc && (
            <img
              src={bgImgSrc}
              alt=""
              style={{
                position: "absolute",
                inset: 0,
                width: "100%",
                height: "100%",
                objectFit: "cover",
                opacity: apparence.opacite_image_fond ?? 0.65,
                pointerEvents: "none",
              }}
            />
          )}

          {/* Halo arriere */}
          {apparence.halo?.actif && (
            <div
              style={{
                position: "absolute",
                right: fenetre.reduit ? "10%" : "18px",
                top: "50%",
                transform: "translateY(-50%)",
                width: `${apparence.halo.rayon * 2.4}px`,
                height: `${apparence.halo.rayon * 2.4}px`,
                borderRadius: "50%",
                background: `radial-gradient(circle, ${hexToRgba(
                  simState === "idle" ? apparence.halo.couleur : stateColor,
                  apparence.halo.intensite * 0.65
                )} 0%, transparent 70%)`,
                pointerEvents: "none",
              }}
            />
          )}

          {/* Anneau d'ecoute */}
          {isListening && (
            <div
              style={{
                position: "absolute",
                right: fenetre.reduit ? "12%" : "22px",
                top: "14%",
                width: `${cardHeight * 0.72}px`,
                height: `${cardHeight * 0.72}px`,
                borderRadius: "50%",
                border: `2.5px solid ${stateColor}`,
                animation: apparence.animations?.actives
                  ? "pulseRing 1.3s infinite ease-in-out"
                  : "none",
                pointerEvents: "none",
              }}
            />
          )}

          {/* Arc de traitement */}
          {isProcessing && (
            <div
              style={{
                position: "absolute",
                right: fenetre.reduit ? "12%" : "22px",
                top: "14%",
                width: `${cardHeight * 0.72}px`,
                height: `${cardHeight * 0.72}px`,
                borderRadius: "50%",
                border: "3px solid transparent",
                borderTopColor: stateColor,
                borderRightColor: stateColor,
                animation: apparence.animations?.actives
                  ? "spinArc 1s linear infinite"
                  : "none",
                pointerEvents: "none",
              }}
            />
          )}

          {/* Personnage ancre en bas a droite */}
          {imgSrc && (
            <img
              src={imgSrc}
              alt="Personnage VÉRA"
              style={{
                position: "absolute",
                bottom: `${-(personnage.decalage_y || 0)}px`,
                right: fenetre.reduit
                  ? "50%"
                  : `${10 - (personnage.decalage_x || 0)}px`,
                transform: fenetre.reduit
                  ? `translateX(calc(50% + ${personnage.decalage_x || 0}px))`
                  : "none",
                height: `${personnage.taille_pourcent}%`,
                objectFit: "contain",
                pointerEvents: "none",
              }}
            />
          )}

          {/* Titre et statut */}
          {!fenetre.reduit && (
            <div
              style={{
                position: "relative",
                zIndex: 2,
                padding: `${fenetre.marges_internes}px`,
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                height: "100%",
                maxWidth: "56%",
              }}
            >
              <div>
                <div style={{ fontWeight: 700, fontSize: "1.05rem" }}>
                  {config.nom_affiche || "VÉRA"}
                </div>
                <div
                  style={{
                    fontSize: "0.82rem",
                    color: stateColor,
                    marginTop: "4px",
                  }}
                >
                  {LIBELLES_ETAT[simState] || "En veille"}
                </div>
              </div>
              <div
                style={{
                  width: "9px",
                  height: "9px",
                  borderRadius: "50%",
                  background: "#00FFA3",
                }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}