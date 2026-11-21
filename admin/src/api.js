const API_BASE = "http://127.0.0.1:8765";

let sessionToken = null;
let serverPort = 8765;

export function getAssetUrl(relPath, cacheBust = 0) {
  if (!relPath) return null;
  const clean = relPath.replace(/^\/+/, "");
  return `http://127.0.0.1:${serverPort}/${clean}?v=${cacheBust}`;
}

export async function bootstrapSession() {
  const resp = await fetch(`${API_BASE}/api/bootstrap`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!resp.ok) {
    throw new Error(`Bootstrap refusé (${resp.status})`);
  }
  const data = await resp.json();
  sessionToken = data.token;
  if (data.port) serverPort = data.port;
  return data;
}

async function apiRequest(path, options = {}) {
  if (!sessionToken) {
    await bootstrapSession();
  }
  const headers = {
    ...(options.headers || {}),
    "X-Nobel-Token": sessionToken,
  };
  let resp = await fetch(`http://127.0.0.1:${serverPort}${path}`, {
    ...options,
    headers,
  });
  if (resp.status === 401) {
    await bootstrapSession();
    headers["X-Nobel-Token"] = sessionToken;
    resp = await fetch(`http://127.0.0.1:${serverPort}${path}`, {
      ...options,
      headers,
    });
  }
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.error || `Erreur serveur (${resp.status})`);
  }
  return data;
}

export const api = {
  getStatus: () => apiRequest("/api/status"),
  getConfig: () => apiRequest("/api/config"),
  saveConfig: (cfg) =>
    apiRequest("/api/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cfg),
    }),
  applyConfig: (cfg) =>
    apiRequest("/api/config/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cfg),
    }),
  resetConfig: () => apiRequest("/api/config/reset", { method: "POST" }),
  defaultsConfig: () => apiRequest("/api/config/defaults", { method: "POST" }),
  testState: (state) =>
    apiRequest("/api/test/state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state }),
    }),
  testMessage: (text, duration_ms = 3500) =>
    apiRequest("/api/test/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, duration_ms }),
    }),
  uploadAsset: (slot, file) => {
    const fd = new FormData();
    fd.append("file", file);
    return apiRequest(`/api/assets/${slot}`, {
      method: "POST",
      body: fd,
    });
  },
  deleteAsset: (slot) =>
    apiRequest(`/api/assets/${slot}`, {
      method: "DELETE",
    }),
};