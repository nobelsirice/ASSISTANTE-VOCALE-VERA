import React, { useCallback, useEffect, useState } from "react";
import { api, getAssetUrl } from "./api.js";
import ApercuWidget from "./components/ApercuWidget.jsx";

const SECTIONS = [
  { id: "general", label: "Général" },
  { id: "dimensions", label: "Dimensions & position" },
  { id: "personnage", label: "Personnage" },
  { id: "bulle", label: "Bulle de conversation" },
  { id: "avance", label: "Avancé" },
];

const SLOTS_ASSETS = [
  { key: "statique", label: "Image statique (repos)", pathFn: (c) => c.personnage.image_statique },
  { key: "parole", label: "Animation parole (GIF / WebP)", pathFn: (c) => c.personnage.gif_parole },
  { key: "ecoute", label: "Expression : Écoute", pathFn: (c) => c.personnage.expressions?.ecoute },
  { key: "reflexion", label: "Expression : Réflexion", pathFn: (c) => c.personnage.expressions?.reflexion },
  { key: "attente", label: "Expression : Attente", pathFn: (c) => c.personnage.expressions?.attente },
  { key: "erreur", label: "Expression : Erreur", pathFn: (c) => c.personnage.expressions?.erreur },
];

export default function App() {
  const [config, setConfig] = useState(null);
  const [savedSnapshot, setSavedSnapshot] = useState("");
  const [activeTab, setActiveTab] = useState("general");
  const [serverError, setServerError] = useState("");
  const [toast, setToast] = useState("");
  const [busy, setBusy] = useState(false);
  const [assetVersion, setAssetVersion] = useState(1);
  const [dragSlot, setDragSlot] = useState(null);

  const [simState, setSimState] = useState("idle");
  const [simMessage, setSimMessage] = useState(
    "Bonjour maître Nobel, je suis prête à recevoir vos ordres."
  );

  const hasUnsavedChanges =
    config !== null && JSON.stringify(config) !== savedSnapshot;

  const notify = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3200);
  };

  const chargerTout = useCallback(async () => {
    try {
      const cfg = await api.getConfig();
      setConfig(cfg);
      setSavedSnapshot(JSON.stringify(cfg));
      setServerError("");
    } catch (err) {
      setServerError(
        `Serveur local VÉRA injoignable (${err.message}). Nouvelle tentative automatique…`
      );
    }
  }, []);

  useEffect(() => {
    chargerTout();
  }, [chargerTout]);

  useEffect(() => {
    if (!serverError) return;
    const timer = setInterval(chargerTout, 3000);
    return () => clearInterval(timer);
  }, [serverError, chargerTout]);

  useEffect(() => {
    const handler = (e) => {
      if (!hasUnsavedChanges) return;
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [hasUnsavedChanges]);

  const updateField = (updater) => {
    setConfig((prev) => {
      const copy = structuredClone(prev);
      updater(copy);
      return copy;
    });
  };

  const handleSave = async () => {
    setBusy(true);
    try {
      const saved = await api.saveConfig(config);
      setConfig(saved);
      setSavedSnapshot(JSON.stringify(saved));
      setServerError("");
      notify("Configuration enregistrée et appliquée au widget.");
    } catch (err) {
      setServerError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleApply = async () => {
    setBusy(true);
    try {
      const applied = await api.applyConfig(config);
      setConfig(applied);
      setServerError("");
      notify("Aperçu diffusé au widget réel (non enregistré).");
    } catch (err) {
      setServerError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async () => {
    setBusy(true);
    try {
      const reloaded = await api.resetConfig();
      setConfig(reloaded);
      setSavedSnapshot(JSON.stringify(reloaded));
      notify("Retour à la dernière configuration enregistrée.");
    } catch (err) {
      setServerError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleDefaults = async () => {
    if (
      !window.confirm(
        "Restaurer tous les paramètres par défaut ? Les réglages non enregistrés seront perdus."
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      const defs = await api.defaultsConfig();
      setConfig(defs);
      notify("Valeurs par défaut chargées (cliquez sur Enregistrer pour persister).");
    } catch (err) {
      setServerError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleFileUpload = async (slot, file) => {
    if (!file) return;
    setBusy(true);
    try {
      const res = await api.uploadAsset(slot, file);
      if (res.config) {
        setConfig(res.config);
        setSavedSnapshot(JSON.stringify(res.config));
      }
      setAssetVersion((v) => v + 1);
      notify(`Ressource « ${slot} » importée avec succès.`);
    } catch (err) {
      alert(`Importation refusée : ${err.message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleDeleteAsset = async (slot) => {
    setBusy(true);
    try {
      const res = await api.deleteAsset(slot);
      if (res.config) {
        setConfig(res.config);
        setSavedSnapshot(JSON.stringify(res.config));
      }
      setAssetVersion((v) => v + 1);
      notify(`Ressource « ${slot} » réinitialisée.`);
    } catch (err) {
      alert(err.message);
    } finally {
      setBusy(false);
    }
  };

  const simulerEtatReel = async (etat) => {
    setSimState(etat);
    try {
      await api.testState(etat);
    } catch {
      // Silencieux
    }
  };

  const simulerBulleReelle = async () => {
    setSimState("speaking");
    try {
      await api.testMessage(simMessage, 3500);
      setTimeout(() => setSimState("idle"), 3500);
    } catch {
      // Silencieux
    }
  };

  return (
    <div>
      <header className="topbar">
        <div className="brand">
          <span className="brand-core" />
          <h1>VÉRA — Core Interface</h1>
          {hasUnsavedChanges && (
            <span className="badge-unsaved">Modifications non enregistrées</span>
          )}
        </div>
        <div className="toolbar-actions">
          <button
            className="btn-apply"
            onClick={handleApply}
            disabled={!config || busy}
          >
            Appliquer
          </button>
          <button
            className="btn-primary"
            onClick={handleSave}
            disabled={!config || busy}
          >
            Enregistrer
          </button>
          <button onClick={handleReset} disabled={!config || busy}>
            Réinitialiser
          </button>
          <button
            className="btn-danger"
            onClick={handleDefaults}
            disabled={!config || busy}
          >
            Défauts
          </button>
        </div>
      </header>

      {serverError && (
        <div className="banner-error">
          <span>{serverError}</span>
          <button onClick={chargerTout}>Réessayer</button>
        </div>
      )}

      {toast && <div className="banner-toast">{toast}</div>}

      {config && (
        <main className="layout">
          <div>
            <nav className="tabs">
              {SECTIONS.map((s) => (
                <button
                  key={s.id}
                  className={`tab-btn ${activeTab === s.id ? "active" : ""}`}
                  onClick={() => setActiveTab(s.id)}
                >
                  {s.label}
                </button>
              ))}
            </nav>

            {/* SECTION 1 : GENERAL */}
            {activeTab === "general" && (
              <section className="panel">
                <h2>Apparence générale & Néons</h2>
                <div className="field">
                  <label>Nom affiché sur le widget</label>
                  <input
                    type="text"
                    value={config.nom_affiche}
                    onChange={(e) =>
                      updateField((c) => (c.nom_affiche = e.target.value))
                    }
                  />
                </div>

                <div className="grid-2">
                  <div className="field">
                    <label>Couleur de fond</label>
                    <div className="color-row">
                      <input
                        type="color"
                        value={config.apparence.couleur_fond}
                        onChange={(e) =>
                          updateField(
                            (c) => (c.apparence.couleur_fond = e.target.value)
                          )
                        }
                      />
                      <input
                        type="text"
                        value={config.apparence.couleur_fond}
                        onChange={(e) =>
                          updateField(
                            (c) => (c.apparence.couleur_fond = e.target.value)
                          )
                        }
                      />
                    </div>
                  </div>

                  <div className="field">
                    <label>
                      <span>Opacité du fond</span>
                      <span>
                        {Math.round(config.apparence.opacite_fond * 100)}%
                      </span>
                    </label>
                    <input
                      type="range"
                      min="0.1"
                      max="1"
                      step="0.02"
                      value={config.apparence.opacite_fond}
                      onChange={(e) =>
                        updateField(
                          (c) =>
                            (c.apparence.opacite_fond = parseFloat(
                              e.target.value
                            ))
                        )
                      }
                    />
                  </div>

                  <div className="field">
                    <label>Couleur du contour</label>
                    <div className="color-row">
                      <input
                        type="color"
                        value={config.apparence.couleur_contour}
                        onChange={(e) =>
                          updateField(
                            (c) =>
                              (c.apparence.couleur_contour = e.target.value)
                          )
                        }
                      />
                      <input
                        type="text"
                        value={config.apparence.couleur_contour}
                        onChange={(e) =>
                          updateField(
                            (c) =>
                              (c.apparence.couleur_contour = e.target.value)
                          )
                        }
                      />
                    </div>
                  </div>

                  <div className="field">
                    <label>
                      <span>Épaisseur contour</span>
                      <span>{config.apparence.epaisseur_contour} px</span>
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="10"
                      value={config.apparence.epaisseur_contour}
                      onChange={(e) =>
                        updateField(
                          (c) =>
                            (c.apparence.epaisseur_contour = parseInt(
                              e.target.value,
                              10
                            ))
                        )
                      }
                    />
                  </div>

                  <div className="field">
                    <label>Couleur néon principal (et silhouette)</label>
                    <div className="color-row">
                      <input
                        type="color"
                        value={config.apparence.couleur_neon}
                        onChange={(e) =>
                          updateField(
                            (c) => (c.apparence.couleur_neon = e.target.value)
                          )
                        }
                      />
                      <input
                        type="text"
                        value={config.apparence.couleur_neon}
                        onChange={(e) =>
                          updateField(
                            (c) => (c.apparence.couleur_neon = e.target.value)
                          )
                        }
                      />
                    </div>
                  </div>

                  <div className="field">
                    <label>Couleur néon secondaire</label>
                    <div className="color-row">
                      <input
                        type="color"
                        value={config.apparence.couleur_neon_secondaire}
                        onChange={(e) =>
                          updateField(
                            (c) =>
                              (c.apparence.couleur_neon_secondaire =
                                e.target.value)
                          )
                        }
                      />
                      <input
                        type="text"
                        value={config.apparence.couleur_neon_secondaire}
                        onChange={(e) =>
                          updateField(
                            (c) =>
                              (c.apparence.couleur_neon_secondaire =
                                e.target.value)
                          )
                        }
                      />
                    </div>
                  </div>

                  <div className="field">
                    <label>
                      <span>Rayon des angles</span>
                      <span>{config.apparence.rayon_angles} px</span>
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="48"
                      value={config.apparence.rayon_angles}
                      onChange={(e) =>
                        updateField(
                          (c) =>
                            (c.apparence.rayon_angles = parseInt(
                              e.target.value,
                              10
                            ))
                        )
                      }
                    />
                  </div>

                  <div className="field">
                    <label>
                      <span>Transparence globale</span>
                      <span>
                        {Math.round(
                          config.apparence.transparence_globale * 100
                        )}
                        %
                      </span>
                    </label>
                    <input
                      type="range"
                      min="0.3"
                      max="1"
                      step="0.02"
                      value={config.apparence.transparence_globale}
                      onChange={(e) =>
                        updateField(
                          (c) =>
                            (c.apparence.transparence_globale = parseFloat(
                              e.target.value
                            ))
                        )
                      }
                    />
                  </div>
                </div>

                <h3>Image d'arrière-plan de la carte</h3>
                <div
                  className={`asset-card ${
                    dragSlot === "fond" ? "dragover" : ""
                  }`}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragSlot("fond");
                  }}
                  onDragLeave={() => setDragSlot(null)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragSlot(null);
                    const f = e.dataTransfer.files?.[0];
                    if (f) handleFileUpload("fond", f);
                  }}
                >
                  <strong>Fond personnalisé (PNG, GIF ou WebP)</strong>
                  {config.apparence.image_fond ? (
                    <img
                      src={getAssetUrl(
                        config.apparence.image_fond,
                        assetVersion
                      )}
                      alt="Fond widget"
                      className="asset-thumb"
                    />
                  ) : (
                    <div
                      className="asset-thumb"
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        color: "var(--text-secondary)",
                        fontSize: "0.82rem",
                      }}
                    >
                      Glissez-déposez une image de fond ici (optionnel)
                    </div>
                  )}

                  {config.apparence.image_fond && (
                    <div className="field" style={{ marginTop: "10px" }}>
                      <label>
                        <span>Opacité de l'image de fond</span>
                        <span>
                          {Math.round(
                            (config.apparence.opacite_image_fond ?? 0.65) * 100
                          )}
                          %
                        </span>
                      </label>
                      <input
                        type="range"
                        min="0.1"
                        max="1"
                        step="0.05"
                        value={config.apparence.opacite_image_fond ?? 0.65}
                        onChange={(e) =>
                          updateField(
                            (c) =>
                              (c.apparence.opacite_image_fond = parseFloat(
                                e.target.value
                              ))
                          )
                        }
                      />
                    </div>
                  )}

                  <div className="asset-actions">
                    <label
                      style={{
                        padding: "6px 12px",
                        borderRadius: "8px",
                        border: "1px solid var(--border-subtle)",
                        background: "var(--bg-panel)",
                        cursor: "pointer",
                        fontSize: "0.82rem",
                      }}
                    >
                      Choisir une image
                      <input
                        type="file"
                        accept=".png,.gif,.webp,image/png,image/gif,image/webp"
                        style={{ display: "none" }}
                        onChange={(e) =>
                          handleFileUpload("fond", e.target.files?.[0])
                        }
                      />
                    </label>
                    {config.apparence.image_fond && (
                      <button
                        className="btn-danger"
                        onClick={() => handleDeleteAsset("fond")}
                        disabled={busy}
                      >
                        Retirer le fond
                      </button>
                    )}
                  </div>
                </div>

                <h3>Halo & Animations</h3>
                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={config.apparence.halo.actif}
                    onChange={(e) =>
                      updateField(
                        (c) => (c.apparence.halo.actif = e.target.checked)
                      )
                    }
                  />
                  <span>Activer le halo lumineux derrière VÉRA</span>
                </label>

                <div className="grid-2">
                  <div className="field">
                    <label>Couleur du halo</label>
                    <div className="color-row">
                      <input
                        type="color"
                        value={config.apparence.halo.couleur}
                        onChange={(e) =>
                          updateField(
                            (c) => (c.apparence.halo.couleur = e.target.value)
                          )
                        }
                      />
                      <input
                        type="text"
                        value={config.apparence.halo.couleur}
                        onChange={(e) =>
                          updateField(
                            (c) => (c.apparence.halo.couleur = e.target.value)
                          )
                        }
                      />
                    </div>
                  </div>
                  <div className="field">
                    <label>
                      <span>Rayon du halo</span>
                      <span>{config.apparence.halo.rayon} px</span>
                    </label>
                    <input
                      type="range"
                      min="10"
                      max="120"
                      value={config.apparence.halo.rayon}
                      onChange={(e) =>
                        updateField(
                          (c) =>
                            (c.apparence.halo.rayon = parseInt(
                              e.target.value,
                              10
                            ))
                        )
                      }
                    />
                  </div>
                </div>

                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={config.apparence.animations.actives}
                    onChange={(e) =>
                      updateField(
                        (c) =>
                          (c.apparence.animations.actives = e.target.checked)
                      )
                    }
                  />
                  <span>Activer les animations lumineuses</span>
                </label>
              </section>
            )}

            {/* SECTION 2 : DIMENSIONS & POSITION */}
            {activeTab === "dimensions" && (
              <section className="panel">
                <h2>Dimensions & Positionnement</h2>
                <div className="grid-2">
                  <div className="field">
                    <label>Mode de dimensionnement</label>
                    <select
                      value={config.fenetre.mode_taille}
                      onChange={(e) =>
                        updateField(
                          (c) => (c.fenetre.mode_taille = e.target.value)
                        )
                      }
                    >
                      <option value="auto">Automatique (ratio écran)</option>
                      <option value="fixe">Fixe (pixels)</option>
                    </select>
                  </div>

                  <div className="field">
                    <label>Ancrage écran par défaut</label>
                    <select
                      value={config.fenetre.ancrage}
                      onChange={(e) =>
                        updateField((c) => (c.fenetre.ancrage = e.target.value))
                      }
                    >
                      <option value="bas_droite">Bas à droite</option>
                      <option value="bas_gauche">Bas à gauche</option>
                      <option value="haut_droite">Haut à droite</option>
                      <option value="haut_gauche">Haut à gauche</option>
                    </select>
                  </div>

                  <div className="field">
                    <label>Largeur fixe (px)</label>
                    <input
                      type="number"
                      min="200"
                      max="1920"
                      value={config.fenetre.largeur_px ?? 420}
                      onChange={(e) =>
                        updateField((c) => {
                          c.fenetre.mode_taille = "fixe";
                          c.fenetre.largeur_px =
                            parseInt(e.target.value, 10) || 420;
                        })
                      }
                    />
                  </div>

                  <div className="field">
                    <label>Hauteur carte fixe (px)</label>
                    <input
                      type="number"
                      min="120"
                      max="1080"
                      value={config.fenetre.hauteur_px ?? 200}
                      onChange={(e) =>
                        updateField((c) => {
                          c.fenetre.mode_taille = "fixe";
                          c.fenetre.hauteur_px =
                            parseInt(e.target.value, 10) || 200;
                        })
                      }
                    />
                  </div>

                  <div className="field">
                    <label>
                      <span>Marge horizontale écran</span>
                      <span>{config.fenetre.marge_x} px</span>
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="200"
                      value={config.fenetre.marge_x}
                      onChange={(e) =>
                        updateField(
                          (c) =>
                            (c.fenetre.marge_x = parseInt(e.target.value, 10))
                        )
                      }
                    />
                  </div>

                  <div className="field">
                    <label>
                      <span>Marge verticale écran</span>
                      <span>{config.fenetre.marge_y} px</span>
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="200"
                      value={config.fenetre.marge_y}
                      onChange={(e) =>
                        updateField(
                          (c) =>
                            (c.fenetre.marge_y = parseInt(e.target.value, 10))
                        )
                      }
                    />
                  </div>

                  <div className="field">
                    <label>
                      <span>Marges internes carte</span>
                      <span>{config.fenetre.marges_internes} px</span>
                    </label>
                    <input
                      type="range"
                      min="4"
                      max="48"
                      value={config.fenetre.marges_internes}
                      onChange={(e) =>
                        updateField(
                          (c) =>
                            (c.fenetre.marges_internes = parseInt(
                              e.target.value,
                              10
                            ))
                        )
                      }
                    />
                  </div>

                  <div className="field">
                    <label>
                      <span>Taille mode réduit</span>
                      <span>{config.fenetre.taille_reduite} px</span>
                    </label>
                    <input
                      type="range"
                      min="56"
                      max="180"
                      value={config.fenetre.taille_reduite}
                      onChange={(e) =>
                        updateField(
                          (c) =>
                            (c.fenetre.taille_reduite = parseInt(
                              e.target.value,
                              10
                            ))
                        )
                      }
                    />
                  </div>
                </div>

                <button
                  onClick={() =>
                    updateField((c) => {
                      c.fenetre.x = null;
                      c.fenetre.y = null;
                    })
                  }
                >
                  Recentrer sur l'ancrage par défaut
                </button>
              </section>
            )}

            {/* SECTION 3 : PERSONNAGE */}
            {activeTab === "personnage" && (
              <section className="panel">
                <h2>Personnage & Expressions</h2>
                <div className="grid-2">
                  <div className="field">
                    <label>
                      <span>Taille du personnage</span>
                      <span>{config.personnage.taille_pourcent}%</span>
                    </label>
                    <input
                      type="range"
                      min="40"
                      max="130"
                      value={config.personnage.taille_pourcent}
                      onChange={(e) =>
                        updateField(
                          (c) =>
                            (c.personnage.taille_pourcent = parseInt(
                              e.target.value,
                              10
                            ))
                        )
                      }
                    />
                  </div>
                  <div className="field">
                    <label>
                      <span>Décalage horizontal (X)</span>
                      <span>{config.personnage.decalage_x} px</span>
                    </label>
                    <input
                      type="range"
                      min="-120"
                      max="120"
                      value={config.personnage.decalage_x}
                      onChange={(e) =>
                        updateField(
                          (c) =>
                            (c.personnage.decalage_x = parseInt(
                              e.target.value,
                              10
                            ))
                        )
                      }
                    />
                  </div>
                  <div className="field">
                    <label>
                      <span>Décalage vertical (Y)</span>
                      <span>{config.personnage.decalage_y} px</span>
                    </label>
                    <input
                      type="range"
                      min="-120"
                      max="120"
                      value={config.personnage.decalage_y}
                      onChange={(e) =>
                        updateField(
                          (c) =>
                            (c.personnage.decalage_y = parseInt(
                              e.target.value,
                              10
                            ))
                        )
                      }
                    />
                  </div>
                </div>

                <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                  Glissez-déposez un fichier PNG (max 5 Mo), GIF ou WebP animé (max
                  10 Mo, 2048×2048 px max). Les fichiers SVG sont refusés.
                </p>

                <div className="asset-grid">
                  {SLOTS_ASSETS.map((slot) => {
                    const rel = slot.pathFn(config);
                    const url = getAssetUrl(rel, assetVersion);
                    return (
                      <div
                        key={slot.key}
                        className={`asset-card ${
                          dragSlot === slot.key ? "dragover" : ""
                        }`}
                        onDragOver={(e) => {
                          e.preventDefault();
                          setDragSlot(slot.key);
                        }}
                        onDragLeave={() => setDragSlot(null)}
                        onDrop={(e) => {
                          e.preventDefault();
                          setDragSlot(null);
                          const f = e.dataTransfer.files?.[0];
                          if (f) handleFileUpload(slot.key, f);
                        }}
                      >
                        <strong>{slot.label}</strong>
                        {url ? (
                          <img src={url} alt={slot.label} className="asset-thumb" />
                        ) : (
                          <div
                            className="asset-thumb"
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              color: "var(--text-secondary)",
                              fontSize: "0.8rem",
                            }}
                          >
                            Repli sur l'image statique
                          </div>
                        )}
                        <div className="asset-actions">
                          <label
                            style={{
                              padding: "6px 12px",
                              borderRadius: "8px",
                              border: "1px solid var(--border-subtle)",
                              background: "var(--bg-panel)",
                              cursor: "pointer",
                              fontSize: "0.82rem",
                            }}
                          >
                            Importer
                            <input
                              type="file"
                              accept=".png,.gif,.webp,image/png,image/gif,image/webp"
                              style={{ display: "none" }}
                              onChange={(e) =>
                                handleFileUpload(slot.key, e.target.files?.[0])
                              }
                            />
                          </label>
                          <button
                            className="btn-danger"
                            onClick={() => handleDeleteAsset(slot.key)}
                            disabled={busy}
                          >
                            Supprimer
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {/* SECTION 4 : BULLE DE CONVERSATION */}
            {activeTab === "bulle" && (
              <section className="panel">
                <h2>Bulle de conversation synchronisée</h2>
                <div className="grid-2">
                  <div className="field">
                    <label>Couleur de fond</label>
                    <div className="color-row">
                      <input
                        type="color"
                        value={config.bulle.couleur_fond}
                        onChange={(e) =>
                          updateField(
                            (c) => (c.bulle.couleur_fond = e.target.value)
                          )
                        }
                      />
                      <input
                        type="text"
                        value={config.bulle.couleur_fond}
                        onChange={(e) =>
                          updateField(
                            (c) => (c.bulle.couleur_fond = e.target.value)
                          )
                        }
                      />
                    </div>
                  </div>

                  <div className="field">
                    <label>Couleur du texte</label>
                    <div className="color-row">
                      <input
                        type="color"
                        value={config.bulle.couleur_texte}
                        onChange={(e) =>
                          updateField(
                            (c) => (c.bulle.couleur_texte = e.target.value)
                          )
                        }
                      />
                      <input
                        type="text"
                        value={config.bulle.couleur_texte}
                        onChange={(e) =>
                          updateField(
                            (c) => (c.bulle.couleur_texte = e.target.value)
                          )
                        }
                      />
                    </div>
                  </div>

                  <div className="field">
                    <label>
                      <span>Opacité de la bulle</span>
                      <span>{Math.round(config.bulle.opacite_fond * 100)}%</span>
                    </label>
                    <input
                      type="range"
                      min="0.2"
                      max="1"
                      step="0.02"
                      value={config.bulle.opacite_fond}
                      onChange={(e) =>
                        updateField(
                          (c) =>
                            (c.bulle.opacite_fond = parseFloat(e.target.value))
                        )
                      }
                    />
                  </div>

                  <div className="field">
                    <label>
                      <span>Taille de police</span>
                      <span>{config.bulle.taille_police} pt</span>
                    </label>
                    <input
                      type="range"
                      min="11"
                      max="28"
                      value={config.bulle.taille_police}
                      onChange={(e) =>
                        updateField(
                          (c) =>
                            (c.bulle.taille_police = parseInt(e.target.value, 10))
                        )
                      }
                    />
                  </div>

                  <div className="field">
                    <label>Couleur du contour</label>
                    <div className="color-row">
                      <input
                        type="color"
                        value={config.bulle.couleur_contour}
                        onChange={(e) =>
                          updateField(
                            (c) => (c.bulle.couleur_contour = e.target.value)
                          )
                        }
                      />
                      <input
                        type="text"
                        value={config.bulle.couleur_contour}
                        onChange={(e) =>
                          updateField(
                            (c) => (c.bulle.couleur_contour = e.target.value)
                          )
                        }
                      />
                    </div>
                  </div>

                  <div className="field">
                    <label>
                      <span>Arrondi des angles</span>
                      <span>{config.bulle.rayon_angles} px</span>
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="32"
                      value={config.bulle.rayon_angles}
                      onChange={(e) =>
                        updateField(
                          (c) =>
                            (c.bulle.rayon_angles = parseInt(e.target.value, 10))
                        )
                      }
                    />
                  </div>

                  <div className="field">
                    <label>
                      <span>Largeur relative</span>
                      <span>{config.bulle.largeur_pourcent}%</span>
                    </label>
                    <input
                      type="range"
                      min="40"
                      max="100"
                      value={config.bulle.largeur_pourcent}
                      onChange={(e) =>
                        updateField(
                          (c) =>
                            (c.bulle.largeur_pourcent = parseInt(
                              e.target.value,
                              10
                            ))
                        )
                      }
                    />
                  </div>

                  <div className="field">
                    <label>
                      <span>Maintien après parole</span>
                      <span>
                        {(
                          config.bulle.duree_affichage_apres_parole_ms / 1000
                        ).toFixed(1)}{" "}
                        s
                      </span>
                    </label>
                    <input
                      type="range"
                      min="1000"
                      max="15000"
                      step="500"
                      value={config.bulle.duree_affichage_apres_parole_ms}
                      onChange={(e) =>
                        updateField(
                          (c) =>
                            (c.bulle.duree_affichage_apres_parole_ms = parseInt(
                              e.target.value,
                              10
                            ))
                        )
                      }
                    />
                  </div>
                </div>
              </section>
            )}

            {/* SECTION 5 : AVANCE */}
            {activeTab === "avance" && (
              <section className="panel">
                <h2>Modes d'affichage & Paramètres avancés</h2>

                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={Boolean(config.fenetre.mode_gif_seul)}
                    onChange={(e) =>
                      updateField((c) => {
                        c.fenetre.mode_gif_seul = e.target.checked;
                        if (e.target.checked) c.fenetre.reduit = false;
                      })
                    }
                  />
                  <span>
                    <strong>Mode GIF / Silhouette néon (sans cadre)</strong> —
                    Affiche uniquement le personnage flottant avec un contour
                    néon épousant sa forme (couleur réglable dans Général)
                  </span>
                </label>

                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={config.fenetre.reduit}
                    onChange={(e) =>
                      updateField((c) => {
                        c.fenetre.reduit = e.target.checked;
                        if (e.target.checked) c.fenetre.mode_gif_seul = false;
                      })
                    }
                  />
                  <span>Mode pastille réduite</span>
                </label>

                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={config.fenetre.toujours_devant}
                    onChange={(e) =>
                      updateField(
                        (c) => (c.fenetre.toujours_devant = e.target.checked)
                      )
                    }
                  />
                  <span>Toujours au premier plan</span>
                </label>

                <div className="grid-2" style={{ marginTop: "14px" }}>
                  <div className="field">
                    <label>Police de la bulle</label>
                    <input
                      type="text"
                      value={config.bulle.famille_police}
                      onChange={(e) =>
                        updateField(
                          (c) => (c.bulle.famille_police = e.target.value)
                        )
                      }
                    />
                  </div>
                  <div className="field">
                    <label>Caractères max avant coupure</label>
                    <input
                      type="number"
                      min="60"
                      max="1000"
                      value={config.bulle.caracteres_max}
                      onChange={(e) =>
                        updateField(
                          (c) =>
                            (c.bulle.caracteres_max =
                              parseInt(e.target.value, 10) || 240)
                        )
                      }
                    />
                  </div>
                  <div className="field">
                    <label>
                      <span>Vitesse des animations</span>
                      <span>
                        {config.apparence.animations.vitesse.toFixed(1)}×
                      </span>
                    </label>
                    <input
                      type="range"
                      min="0.2"
                      max="2.5"
                      step="0.1"
                      value={config.apparence.animations.vitesse}
                      onChange={(e) =>
                        updateField(
                          (c) =>
                            (c.apparence.animations.vitesse = parseFloat(
                              e.target.value
                            ))
                        )
                      }
                    />
                  </div>
                </div>
              </section>
            )}
          </div>

          {/* COLONNE DROITE : APERCU EN TEMPS REEL & SIMULATION */}
          <aside className="preview-sticky">
            <div className="preview-header">
              <strong>Aperçu holographique</strong>
              <span style={{ fontSize: "0.78rem", color: "var(--accent-cyan)" }}>
                ÉTAT : {simState.toUpperCase()}
              </span>
            </div>
            <p className="preview-note">
              Reproduction fidèle du JSON (proche du rendu Qt natif, non identique
              au pixel près).
            </p>

            <ApercuWidget
              config={config}
              simState={simState}
              simMessage={simMessage}
              assetVersion={assetVersion}
            />

            <div className="sim-controls">
              <button onClick={() => simulerEtatReel("idle")}>Repos</button>
              <button onClick={() => simulerEtatReel("listening")}>Écoute</button>
              <button onClick={() => simulerEtatReel("processing")}>
                Traitement
              </button>
              <button onClick={() => simulerEtatReel("speaking")}>Parole</button>
              <button
                className="btn-danger"
                onClick={() => simulerEtatReel("error")}
              >
                Erreur
              </button>
            </div>

            <div className="sim-bubble-row">
              <input
                type="text"
                value={simMessage}
                onChange={(e) => setSimMessage(e.target.value)}
                placeholder="Texte de test pour la bulle…"
              />
              <button className="btn-primary" onClick={simulerBulleReelle}>
                Tester la bulle
              </button>
            </div>
          </aside>
        </main>
      )}
    </div>
  );
}