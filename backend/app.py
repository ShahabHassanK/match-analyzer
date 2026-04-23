"""
Match Analyzer - FastAPI Backend
---------------------------------
Main application module. Provides REST API endpoints for the React frontend.

Phase 1: Search & Discovery — fixture search via DuckDuckGo
Phase 2: Event Scraping — WhoScored match event extraction (event_scraper.py)
Phase 3: Match Analysis — tactical analytics & visualisations (match_analyzer.py)
"""

import os
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from fastapi.responses import StreamingResponse

from services.discovery_service import search_fixtures
from services.event_scraper import scrape_whoscored
from services import match_analyzer
from services.gradient_scoring import get_gradient_scoring
from services.explain_service import stream_explanation


# ─── App Setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Match Analyzer API",
    description="Backend API for the Match Analyzer. Search fixtures, scrape events, and generate tactical analysis.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent / "data"


def _resolve_csv(match_id: str) -> str:
    """
    Resolve a match_id to the CSV filepath.

    match_id can be:
    - A filename like 'whoscored_Arsenal_vs_Liverpool_all_events'
    - A slug like 'Arsenal_vs_Liverpool'

    Returns the absolute path string, or raises 404.
    """
    # Try direct match first
    candidate = DATA_DIR / f"{match_id}.csv"
    if candidate.exists():
        return str(candidate)

    # Try with whoscored prefix
    candidate = DATA_DIR / f"whoscored_{match_id}_all_events.csv"
    if candidate.exists():
        return str(candidate)

    # Glob search for partial match
    for f in DATA_DIR.glob("*.csv"):
        if match_id.lower().replace(" ", "_") in f.stem.lower():
            return str(f)

    raise HTTPException(
        status_code=404,
        detail=f"No match data found for '{match_id}'. Available: {[f.stem for f in DATA_DIR.glob('*.csv')]}",
    )


# ─── Phase 1 Endpoints: Search & Discovery ───────────────────────────────────

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Match Analyzer API is running."}


@app.get("/api/search-fixtures")
async def api_search_fixtures(
    team: str = Query(..., description="Team name to search for (e.g. 'Arsenal', 'Real Madrid')"),
    season: Optional[str] = Query(None, description="Season filter (e.g. '2024/2025')"),
    competition: Optional[str] = Query(None, description="Competition filter (e.g. 'Premier League')"),
    max_results: int = Query(30, description="Maximum number of DuckDuckGo results to fetch"),
):
    """
    Search for WhoScored match fixtures.

    Scenarios:
    1. team only -> returns all recent fixtures across competitions, most recent first
    2. team + season -> filters by season, most recent first
    3. team + competition -> filters by competition, most recent first
    4. team + season + competition -> strict filter, most recent first

    Returns a list of fixtures with abstracted display names and WhoScored URLs.
    """
    fixtures = search_fixtures(
        team_name=team,
        season=season,
        competition=competition,
        max_results=max_results,
    )

    return {
        "status": "ok",
        "query": {
            "team": team,
            "season": season,
            "competition": competition,
        },
        "count": len(fixtures),
        "fixtures": fixtures,
    }


@app.get("/api/teams")
async def api_teams():
    """Returns a list of known teams for frontend autocomplete."""
    # Assuming KNOWN_TEAMS is accessible or we can just import it
    from services.discovery_service import KNOWN_TEAMS
    # return the string representations capitalized
    teams = [known.title() for known in KNOWN_TEAMS.keys()]
    return {"status": "ok", "teams": sorted(teams)}


class ScrapeRequest(BaseModel):
    url: str


@app.post("/api/scrape")
async def api_scrape(req: ScrapeRequest):
    """
    Scrape a WhoScored Match Centre page.

    Accepts a full WhoScored URL (e.g. https://www.whoscored.com/Matches/1234567/Live/...).
    Runs the Phase 2 scraper, saves the CSV to backend/data/, and returns the
    match_id so the frontend can immediately navigate to the analysis dashboard.
    """
    url = req.url.strip()
    if "whoscored.com" not in url.lower():
        raise HTTPException(status_code=400, detail="URL must be a WhoScored Match Centre link.")

    try:
        app_dir = str(Path(__file__).parent)
        df = scrape_whoscored(url, app_dir=app_dir)

        # Extract the match_id from saved CSV filename
        home_team = df["homeTeam"].dropna().iloc[0] if "homeTeam" in df.columns else "Home"
        away_team = df["awayTeam"].dropna().iloc[0] if "awayTeam" in df.columns else "Away"

        # Find the saved CSV
        saved_csvs = sorted(DATA_DIR.glob(f"whoscored_*{home_team.replace(' ', '_')}*vs*{away_team.replace(' ', '_')}*.csv"))
        if saved_csvs:
            match_id = saved_csvs[-1].stem
        else:
            # Fallback: just find the most recently modified CSV
            all_csvs = sorted(DATA_DIR.glob("whoscored_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
            match_id = all_csvs[0].stem if all_csvs else "unknown"

        return {
            "status": "ok",
            "match_id": match_id,
            "event_count": len(df),
            "home_team": home_team,
            "away_team": away_team,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


# ─── Phase 3 Endpoints: Match Analysis ───────────────────────────────────────

@app.get("/api/matches")
async def list_matches():
    """List all available match CSVs in the data directory, most recent first."""
    import csv
    from datetime import datetime

    csvs = list(DATA_DIR.glob("whoscored_*.csv"))
    matches = []
    for f in csvs:
        stem = f.stem.replace("whoscored_", "").replace("_all_events", "")
        display_name = stem.replace("_", " ")

        # Extract homeTeam / awayTeam from the CSV header row
        home_team = ""
        away_team = ""
        try:
            with open(f, "r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                first_row = next(reader, None)
                if first_row:
                    home_team = first_row.get("homeTeam", "")
                    away_team = first_row.get("awayTeam", "")
                    if home_team and away_team:
                        display_name = f"{home_team} vs {away_team}"
        except Exception:
            pass

        # File modification time as "scraped date"
        mtime = f.stat().st_mtime
        scraped_date = datetime.fromtimestamp(mtime).strftime("%b %d, %Y %H:%M")

        matches.append({
            "id": f.stem,
            "displayName": display_name,
            "homeTeam": home_team,
            "awayTeam": away_team,
            "scrapedAt": scraped_date,
            "scrapedTimestamp": mtime,
        })

    # Sort by scraped timestamp, newest first
    matches.sort(key=lambda m: m["scrapedTimestamp"], reverse=True)

    return {"status": "ok", "count": len(matches), "matches": matches}


@app.get("/api/match/{match_id}/summary")
async def api_match_summary(
    match_id: str,
    period: Optional[str] = Query(None, description="Filter by period: FirstHalf or SecondHalf"),
):
    """Basic match facts: scoreline, shots, saves, cards, possession."""
    csv_path = _resolve_csv(match_id)
    return {"status": "ok", "data": match_analyzer.get_match_summary(csv_path, period=period)}


@app.get("/api/match/{match_id}/starting-xi")
async def api_starting_xi(match_id: str):
    """Starting XIs for both teams."""
    csv_path = _resolve_csv(match_id)
    return {"status": "ok", "data": match_analyzer.get_starting_xi(csv_path)}


@app.get("/api/match/{match_id}/shots")
async def api_shot_map(
    match_id: str,
    period: Optional[str] = Query(None, description="Filter by period: FirstHalf or SecondHalf"),
):
    """Shot map with locations and outcome categories."""
    csv_path = _resolve_csv(match_id)
    return {"status": "ok", "data": match_analyzer.get_shot_map(csv_path, period=period)}


@app.get("/api/match/{match_id}/pass-network")
async def api_pass_network(
    match_id: str,
    team: Optional[str] = Query(None, description="Filter by team name"),
    period: Optional[str] = Query(None, description="Filter by period: FirstHalf or SecondHalf"),
):
    """Pass network: player positions + weighted edges."""
    csv_path = _resolve_csv(match_id)
    return {"status": "ok", "data": match_analyzer.get_pass_network(csv_path, team=team, period=period)}


@app.get("/api/match/{match_id}/ppda")
async def api_ppda(match_id: str):
    """PPDA (pressing intensity) per team, overall and per half."""
    csv_path = _resolve_csv(match_id)
    return {"status": "ok", "data": match_analyzer.get_ppda(csv_path)}



@app.get("/api/match/{match_id}/average-shape")
async def api_average_shape(
    match_id: str,
    period: Optional[str] = Query(None, description="Filter by period: FirstHalf or SecondHalf"),
):
    """Average in-possession tactical shape per player."""
    csv_path = _resolve_csv(match_id)
    return {"status": "ok", "data": match_analyzer.get_average_shape(csv_path, period=period)}


@app.get("/api/match/{match_id}/momentum")
async def api_momentum(
    match_id: str,
    window: int = Query(5, description="Smoothing window size in minutes"),
    period: Optional[str] = Query(None, description="Filter by period: FirstHalf or SecondHalf"),
):
    """xT momentum timeline showing match dominance over time."""
    csv_path = _resolve_csv(match_id)
    return {"status": "ok", "data": match_analyzer.get_xT_momentum(csv_path, window=window, period=period)}


@app.get("/api/match/{match_id}/defensive-actions")
async def api_defensive_actions(
    match_id: str,
    period: Optional[str] = Query(None, description="Filter by period: FirstHalf or SecondHalf"),
):
    """Defensive action scatter (tackles, interceptions, fouls)."""
    csv_path = _resolve_csv(match_id)
    return {"status": "ok", "data": match_analyzer.get_defensive_actions(csv_path, period=period)}


@app.get("/api/match/{match_id}/zone-entries")
async def api_zone_entries(
    match_id: str,
    period: Optional[str] = Query(None, description="Filter by period: FirstHalf or SecondHalf"),
):
    """Final third and Zone 14 entry vectors."""
    csv_path = _resolve_csv(match_id)
    return {"status": "ok", "data": match_analyzer.get_zone_entries(csv_path, period=period)}



@app.get("/api/match/{match_id}/player/{player_name}/actions")
async def api_player_actions(
    match_id: str,
    player_name: str,
    action_type: Optional[str] = Query(None, description="Filter: pass, shot, tackle, carry, cross, aerial, take_on, interception, clearance, block"),
    period: Optional[str] = Query(None, description="Filter by period: FirstHalf or SecondHalf"),
):
    """All events for a specific player, optionally filtered by action type."""
    csv_path = _resolve_csv(match_id)
    return {"status": "ok", "data": match_analyzer.get_player_actions(csv_path, player_name, action_type, period=period)}




@app.get("/api/match/{match_id}/advanced-metrics")
async def api_advanced_metrics(match_id: str):
    """Advanced tactical metrics panel: pressing, progression, possession, aggression, creativity, duels, shape."""
    csv_path = _resolve_csv(match_id)
    return {"status": "ok", "data": match_analyzer.get_advanced_metrics(csv_path)}


@app.get("/api/match/{match_id}/gradient-scoring")
async def api_gradient_scoring(match_id: str):
    """Exhaustive 42-variable index scoring breakdown out of 100."""
    csv_path = _resolve_csv(match_id)
    return {"status": "ok", "data": get_gradient_scoring(csv_path)}


@app.get("/api/match/{match_id}/set-pieces")
async def api_set_pieces(
    match_id: str,
    period: Optional[str] = Query(None, description="Filter by period: FirstHalf or SecondHalf"),
):
    """Set piece analysis: corners, free kicks, deliveries, first contact, outcomes."""
    csv_path = _resolve_csv(match_id)
    return {"status": "ok", "data": match_analyzer.get_set_piece_analysis(csv_path, period=period)}


@app.get("/api/match/{match_id}/goal-build-ups")
async def api_goal_build_ups(
    match_id: str,
    period: Optional[str] = Query(None, description="Filter by period: FirstHalf or SecondHalf"),
):
    """Event sequences leading up to goals for 2D animated replay."""
    csv_path = _resolve_csv(match_id)
    return {"status": "ok", "data": match_analyzer.get_goal_build_ups(csv_path, period=period)}


@app.get("/api/match/{match_id}/substitution-impact")
async def api_substitution_impact(match_id: str):
    """Substitution impact analysis: metrics before vs. after each substitution."""
    csv_path = _resolve_csv(match_id)
    return {"status": "ok", "data": match_analyzer.get_substitution_impact(csv_path)}


class ExplainRequest(BaseModel):
    feature: str


@app.post("/api/match/{match_id}/explain")
async def api_explain_feature(match_id: str, req: ExplainRequest):
    """Stream a contextual AI explanation of a specific feature for this match."""
    csv_path = _resolve_csv(match_id)
    return StreamingResponse(
        stream_explanation(csv_path, req.feature),
        media_type="text/event-stream",
    )
