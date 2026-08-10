const ONCOFORGE_API = "/lab/oncoforge/api";

async function oncoforgeRequest(path, options = {}) {
  const response = await fetch(`${ONCOFORGE_API}${path}`, {
    credentials: "same-origin",
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });

  const payload = await response.json().catch(() => ({
    ok: false,
    error: "OncoForge returned an unreadable response.",
  }));
  if (!response.ok) {
    throw new Error(payload.error || `OncoForge request failed (${response.status})`);
  }
  return payload;
}

export function getOncoForgeHealth() {
  return oncoforgeRequest("/health");
}

export function listOncoForgeProfiles() {
  return oncoforgeRequest("/profiles");
}

export function getOncoForgeProfile(profileId) {
  return oncoforgeRequest(`/profiles/${encodeURIComponent(profileId)}`);
}

export function runOncoForgeMission(mission) {
  return oncoforgeRequest("/portal/missions", {
    method: "POST",
    body: JSON.stringify(mission),
  });
}

export function getOncoForgeMission(missionId) {
  return oncoforgeRequest(`/portal/missions/${encodeURIComponent(missionId)}`);
}

