/**
 * API Client
 * ==========
 * Centralised fetch layer for all Match Analyzer backend endpoints.
 * Every function returns parsed JSON. Errors are thrown as Error objects.
 */

const BASE_URL = 'http://127.0.0.1:8000/api';


async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error: ${res.status}`);
  }
  const json = await res.json();
  return json.data !== undefined ? json.data : json;
}

/* ── Phase 1: Discovery ──────────────────────────────────────────────────── */

export function searchFixtures(team, season, competition) {
  const params = new URLSearchParams({ team });
  if (season) params.set('season', season);
  if (competition) params.set('competition', competition);
  return request(`/search-fixtures?${params}`);
}

export function fetchTeams() {
  return request('/teams');
}

/* ── Phase 2: Scraping ───────────────────────────────────────────────────── */

export function scrapeMatch(url) {
  return request('/scrape', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
}

/* ── Match Discovery ─────────────────────────────────────────────────────── */

export function fetchMatches() {
  return request('/matches');
}

/* ── Match-Level Analysis ────────────────────────────────────────────────── */

export function fetchSummary(matchId) {
  return request(`/match/${matchId}/summary`);
}

export function fetchStartingXI(matchId) {
  return request(`/match/${matchId}/starting-xi`);
}

export function fetchShots(matchId) {
  return request(`/match/${matchId}/shots`);
}

export function fetchPassNetwork(matchId, team) {
  const query = team ? `?team=${encodeURIComponent(team)}` : '';
  return request(`/match/${matchId}/pass-network${query}`);
}

export function fetchPPDA(matchId) {
  return request(`/match/${matchId}/ppda`);
}

export function fetchTerritory(matchId) {
  return request(`/match/${matchId}/territory`);
}

export function fetchMomentum(matchId, window = 5) {
  return request(`/match/${matchId}/momentum?window=${window}`);
}

export function fetchDefensiveActions(matchId) {
  return request(`/match/${matchId}/defensive-actions`);
}

export function fetchZoneEntries(matchId) {
  return request(`/match/${matchId}/zone-entries`);
}

export function fetchPassingCombos(matchId, topN = 10) {
  return request(`/match/${matchId}/passing-combos?top_n=${topN}`);
}

/* ── Player-Level Analysis ───────────────────────────────────────────────── */

export function fetchPlayerActions(matchId, playerName, actionType) {
  const query = actionType ? `?action_type=${encodeURIComponent(actionType)}` : '';
  return request(`/match/${matchId}/player/${encodeURIComponent(playerName)}/actions${query}`);
}

export function fetchPlayerHeatmap(matchId, playerName) {
  return request(`/match/${matchId}/player/${encodeURIComponent(playerName)}/heatmap`);
}

export function fetchPlayerPassSonar(matchId, playerName) {
  return request(`/match/${matchId}/player/${encodeURIComponent(playerName)}/pass-sonar`);
}

export function fetchAdvancedMetrics(matchId) {
  return request(`/match/${matchId}/advanced-metrics`);
}

export function fetchSetPieces(matchId) {
  return request(`/match/${matchId}/set-pieces`);
}
