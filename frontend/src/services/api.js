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

function periodParam(period) {
  return period ? `period=${encodeURIComponent(period)}` : '';
}

function buildQuery(parts) {
  const filled = parts.filter(Boolean);
  return filled.length ? `?${filled.join('&')}` : '';
}

export function fetchSummary(matchId, period) {
  return request(`/match/${matchId}/summary${buildQuery([periodParam(period)])}`);
}

export function fetchStartingXI(matchId) {
  return request(`/match/${matchId}/starting-xi`);
}

export function fetchGradientScoring(matchId) {
  return request(`/match/${matchId}/gradient-scoring`);
}

export function fetchShots(matchId, period) {
  return request(`/match/${matchId}/shots${buildQuery([periodParam(period)])}`);
}

export function fetchPassNetwork(matchId, team, period) {
  const parts = [
    team ? `team=${encodeURIComponent(team)}` : '',
    periodParam(period),
  ];
  return request(`/match/${matchId}/pass-network${buildQuery(parts)}`);
}

export function fetchPPDA(matchId) {
  return request(`/match/${matchId}/ppda`);
}

export function fetchMomentum(matchId, window = 5, period) {
  const parts = [`window=${window}`, periodParam(period)];
  return request(`/match/${matchId}/momentum${buildQuery(parts)}`);
}

export function fetchDefensiveActions(matchId, period) {
  return request(`/match/${matchId}/defensive-actions${buildQuery([periodParam(period)])}`);
}

export function fetchZoneEntries(matchId, period) {
  return request(`/match/${matchId}/zone-entries${buildQuery([periodParam(period)])}`);
}

export function fetchSubstitutionImpact(matchId) {
  return request(`/match/${matchId}/substitution-impact`);
}

/* ── Player-Level Analysis ───────────────────────────────────────────────── */

export function fetchPlayerActions(matchId, playerName, actionType, period) {
  const parts = [
    actionType ? `action_type=${encodeURIComponent(actionType)}` : '',
    periodParam(period),
  ];
  return request(`/match/${matchId}/player/${encodeURIComponent(playerName)}/actions${buildQuery(parts)}`);
}

export function fetchAdvancedMetrics(matchId) {
  return request(`/match/${matchId}/advanced-metrics`);
}

export function fetchSetPieces(matchId, period) {
  return request(`/match/${matchId}/set-pieces${buildQuery([periodParam(period)])}`);
}

export function fetchAverageShape(matchId, period) {
  return request(`/match/${matchId}/average-shape${buildQuery([periodParam(period)])}`);
}

export function fetchGoalBuildUps(matchId, period) {
  return request(`/match/${matchId}/goal-build-ups${buildQuery([periodParam(period)])}`);
}

export function fetchXGBreakdown(matchId) {
  return request(`/match/${matchId}/xg-breakdown`);
}

/* ── AI Guide ────────────────────────────────────────────────────────────── */

// Returns raw fetch Response for SSE streaming
export function explainFeature(matchId, feature) {
  return fetch(`${BASE_URL}/match/${matchId}/explain`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ feature }),
  });
}
