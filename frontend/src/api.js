const defaultApiBase =
  typeof window !== "undefined" && !["localhost", "127.0.0.1"].includes(window.location.hostname)
    ? window.location.origin
    : "http://localhost:8000";

const API_BASE = import.meta.env.VITE_API_BASE ?? defaultApiBase;

async function fetchJson(path, options) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.json();
}

export { API_BASE };

export async function getHealth() {
  return fetchJson("/api/health");
}

export async function getDemoSources() {
  return fetchJson("/api/demo/sources");
}

export async function getRuns() {
  return fetchJson("/api/analysis/runs");
}

export async function getRun(runId) {
  return fetchJson(`/api/analysis/runs/${runId}`);
}

export async function createRun(payload) {
  return fetchJson("/api/analysis/runs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function uploadMedia(file) {
  const formData = new FormData();
  formData.append("file", file);
  return fetchJson("/api/uploads/media", {
    method: "POST",
    body: formData,
  });
}

export async function exportCvat(runId) {
  return fetchJson(`/api/analysis/runs/${runId}/export-cvat`, {
    method: "POST",
  });
}

export async function getTimeline(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`Unable to load timeline: ${response.status}`);
  }
  return response.json();
}
