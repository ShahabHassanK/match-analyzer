"""
Discovery Service - Direct WhoScored Discovery
Extracts fixture data from WhoScored's team Fixtures page HTML.
The page embeds fixture data in require.config.params['args'].fixtureMatches
"""
import ast
import json
import re
import time
from dataclasses import asdict, dataclass
from typing import Optional

from curl_cffi import requests as cffi_requests


WS_BASE = "https://www.whoscored.com"
WS_FIXTURES_URL = "https://www.whoscored.com/Teams/{team_id}/Fixtures/{team_slug}"

# Known WhoScored team IDs (confirmed from HTML inspection)
# Format: "normalized name": (team_id, "Country-TeamName-slug")
KNOWN_TEAMS = {
    "ac milan": (80, "Italy-AC-Milan"),
    "angers": (614, "France-Angers"),
    "arsenal": (13, "England-Arsenal"),
    "aston villa": (24, "England-Aston-Villa"),
    "atalanta": (300, "Italy-Atalanta"),
    "athletic club": (53, "Spain-Athletic-Club"),
    "atletico madrid": (63, "Spain-Atletico-Madrid"),
    "augsburg": (1730, "Germany-Augsburg"),
    "auxerre": (308, "France-Auxerre"),
    "barcelona": (65, "Spain-Barcelona"),
    "bayer leverkusen": (36, "Germany-Bayer-Leverkusen"),
    "bayern": (37, "Germany-Bayern-Munich"),
    "bayern munich": (37, "Germany-Bayern-Munich"),
    "bologna": (71, "Italy-Bologna"),
    "borussia dortmund": (44, "Germany-Borussia-Dortmund"),
    "borussia m.gladbach": (134, "Germany-Borussia-M.Gladbach"),
    "bournemouth": (183, "England-Bournemouth"),
    "brentford": (189, "England-Brentford"),
    "brest": (2332, "France-Brest"),
    "brighton": (211, "England-Brighton"),
    "burnley": (184, "England-Burnley"),
    "cagliari": (78, "Italy-Cagliari"),
    "celta vigo": (62, "Spain-Celta-Vigo"),
    "chelsea": (15, "England-Chelsea"),
    "como": (1290, "Italy-Como"),
    "cremonese": (2731, "Italy-Cremonese"),
    "crystal palace": (162, "England-Crystal-Palace"),
    "deportivo alaves": (60, "Spain-Deportivo-Alaves"),
    "eintracht frankfurt": (45, "Germany-Eintracht-Frankfurt"),
    "elche": (833, "Spain-Elche"),
    "espanyol": (70, "Spain-Espanyol"),
    "everton": (31, "England-Everton"),
    "fc heidenheim": (4852, "Germany-FC-Heidenheim"),
    "fc koln": (282, "Germany-FC-Koln"),
    "fiorentina": (73, "Italy-Fiorentina"),
    "freiburg": (50, "Germany-Freiburg"),
    "fulham": (170, "England-Fulham"),
    "genoa": (278, "Italy-Genoa"),
    "getafe": (819, "Spain-Getafe"),
    "girona": (2783, "Spain-Girona"),
    "hamburger sv": (38, "Germany-Hamburger-SV"),
    "hoffenheim": (1211, "Germany-Hoffenheim"),
    "inter": (75, "Italy-Inter"),
    "juventus": (87, "Italy-Juventus"),
    "lazio": (77, "Italy-Lazio"),
    "le havre": (217, "France-Le-Havre"),
    "lecce": (79, "Italy-Lecce"),
    "leeds": (19, "England-Leeds"),
    "lens": (309, "France-Lens"),
    "levante": (832, "Spain-Levante"),
    "lille": (607, "France-Lille"),
    "liverpool": (26, "England-Liverpool"),
    "lorient": (146, "France-Lorient"),
    "lyon": (228, "France-Lyon"),
    "mainz 05": (219, "Germany-Mainz-05"),
    "mallorca": (51, "Spain-Mallorca"),
    "man city": (167, "England-Manchester-City"),
    "man utd": (32, "England-Manchester-United"),
    "manchester city": (167, "England-Manchester-City"),
    "manchester united": (32, "England-Manchester-United"),
    "marseille": (249, "France-Marseille"),
    "metz": (314, "France-Metz"),
    "monaco": (248, "France-Monaco"),
    "nantes": (302, "France-Nantes"),
    "napoli": (276, "Italy-Napoli"),
    "newcastle": (23, "England-Newcastle"),
    "nice": (613, "France-Nice"),
    "nottingham forest": (174, "England-Nottingham-Forest"),
    "osasuna": (131, "Spain-Osasuna"),
    "paris fc": (2832, "France-Paris-FC"),
    "paris saint germain": (304, "France-Paris-Saint-Germain"),
    "parma calcio 1913": (24341, "Italy-Parma-Calcio-1913"),
    "pisa": (777, "Italy-Pisa"),
    "psg": (304, "France-Paris-Saint-Germain"),
    "rayo vallecano": (64, "Spain-Rayo-Vallecano"),
    "rb leipzig": (7614, "Germany-RB-Leipzig"),
    "real betis": (54, "Spain-Real-Betis"),
    "real madrid": (52, "Spain-Real-Madrid"),
    "real oviedo": (61, "Spain-Real-Oviedo"),
    "real sociedad": (68, "Spain-Real-Sociedad"),
    "rennes": (313, "France-Rennes"),
    "roma": (84, "Italy-Roma"),
    "sassuolo": (2889, "Italy-Sassuolo"),
    "sevilla": (67, "Spain-Sevilla"),
    "spurs": (30, "England-Tottenham"),
    "st. pauli": (283, "Germany-St.-Pauli"),
    "strasbourg": (148, "France-Strasbourg"),
    "sunderland": (16, "England-Sunderland"),
    "torino": (72, "Italy-Torino"),
    "tottenham": (30, "England-Tottenham"),
    "toulouse": (246, "France-Toulouse"),
    "udinese": (86, "Italy-Udinese"),
    "union berlin": (796, "Germany-Union-Berlin"),
    "valencia": (55, "Spain-Valencia"),
    "verona": (76, "Italy-Verona"),
    "vfb stuttgart": (41, "Germany-VfB-Stuttgart"),
    "villarreal": (839, "Spain-Villarreal"),
    "werder bremen": (42, "Germany-Werder-Bremen"),
    "west ham": (29, "England-West-Ham"),
    "wolfsburg": (33, "Germany-Wolfsburg"),
    "wolves": (161, "England-Wolves"),
}


@dataclass
class Fixture:
    match_id: str
    home_team: str
    away_team: str
    display_name: str       # "Arsenal vs Chelsea | 2024/2025 | Premier League | 2025-04-02"
    whoscored_url: str
    competition: str
    season: str
    date_str: str           # ISO date "YYYY-MM-DD"
    has_matchcentre: bool

    def to_dict(self) -> dict:
        return asdict(self)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_session() -> cffi_requests.Session:
    return cffi_requests.Session(impersonate="chrome120")


def _warm_up(session: cffi_requests.Session) -> None:
    try:
        session.get(WS_BASE, timeout=15)
        time.sleep(1.5)
    except Exception:
        pass


def _resolve_team(team_name: str) -> Optional[tuple]:
    """
    Resolve team name to (team_id, team_slug) using the known teams dictionary.
    Uses progressive fuzzy matching.
    """
    key = team_name.lower().strip()
    # Exact match
    if key in KNOWN_TEAMS:
        return KNOWN_TEAMS[key]
    # Substring match
    for known, data in KNOWN_TEAMS.items():
        if key in known or known in key:
            return data
    return None


def _extract_json_array(text: str, start_idx: int) -> Optional[str]:
    """Extract a balanced JSON array starting at start_idx."""
    depth = 0
    in_string = False
    escape = False
    for idx in range(start_idx, len(text)):
        ch = text[idx]
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start_idx:idx + 1]
    return None


def _parse_date(date_raw: str) -> str:
    """Convert WhoScored date 'DD-MM-YY' to ISO 'YYYY-MM-DD'."""
    try:
        parts = date_raw.split("-")
        if len(parts) == 3:
            day, month, year_short = parts
            year = f"20{year_short}" if len(year_short) == 2 else year_short
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    except Exception:
        pass
    return date_raw


def _build_match_slug(competition: str, season: str, home: str, away: str) -> str:
    """Build the WhoScored URL slug for a match."""
    def slug(s):
        return re.sub(r'[^A-Za-z0-9]+', '-', s.strip()).strip('-')
    season_slug = season.replace("/", "-")
    return f"{slug(competition)}-{season_slug}-{slug(home)}-vs-{slug(away)}"


def _fetch_and_parse_fixtures(session: cffi_requests.Session, team_id: int, team_slug: str) -> list[dict]:
    """
    Fetch the WhoScored team Fixtures page and extract the fixtureMatches array
    from require.config.params['args'].
    """
    url = WS_FIXTURES_URL.format(team_id=team_id, team_slug=team_slug)
    try:
        r = session.get(url, timeout=30)
    except Exception as e:
        raise ConnectionError(f"Failed to reach WhoScored: {e}")

    if r.status_code == 403:
        raise ConnectionError("WhoScored blocked the request (403).")
    if r.status_code != 200:
        raise ConnectionError(f"WhoScored returned status {r.status_code}.")

    html = r.text

    # Extract fixtureMatches from require.config.params['args']
    idx = html.find("fixtureMatches:")
    if idx == -1:
        return []

    arr_start = html.find("[", idx)
    if arr_start == -1:
        return []

    raw_json = _extract_json_array(html, arr_start)
    if not raw_json:
        return []

    try:
        # JS arrays can have holes like '...' ,, '...' which ast.literal_eval hates
        # Replace empty slots with None
        raw_json = re.sub(r'(?<=\[)(?=,)', 'None', raw_json)
        raw_json = re.sub(r'(?<=,)(?=,)', 'None', raw_json)
        raw_json = re.sub(r'(?<=,)(?=\])', 'None', raw_json)
        return ast.literal_eval(raw_json)
    except Exception:
        return []


# fixtureMatches row indices (confirmed from HTML inspection of Arsenal page):
# [0]  matchId
# [1]  ? (type/neutral flag)
# [2]  date string 'DD-MM-YY'
# [3]  kick-off time 'HH:MM'
# [4]  homeTeamId
# [5]  homeTeamName
# [6]  ? (formation/0)
# [7]  awayTeamId
# [8]  awayTeamName
# [9]  ? (formation/0)
# [10] score 'H : A'
# [11] half-time score 'H : A'
# [12] ?
# [13] ?
# [14] status ('FT', 'AET', etc.)
# [15] season '2025/2026'
# [16] competition 'Premier League'
# ...
# [22] competition code 'EPL'

def _parse_row(row: list) -> Optional[Fixture]:
    """Parse a single fixtureMatches row into a Fixture."""
    try:
        if not isinstance(row, list) or len(row) < 17:
            return None

        match_id = str(row[0])
        date_str = _parse_date(str(row[2]))
        home_team = str(row[5])
        away_team = str(row[8])
        score = str(row[10])
        status = str(row[14])
        season = str(row[15])
        competition = str(row[16])

        has_matchcentre = status.upper() in {"FT", "AET", "PEN", "FIN"}

        slug = _build_match_slug(competition, season, home_team, away_team)
        whoscored_url = f"https://www.whoscored.com/Matches/{match_id}/Live/{slug}"

        display_name = f"{home_team} vs {away_team} | {season} | {competition}"
        if date_str:
            display_name += f" | {date_str}"

        return Fixture(
            match_id=match_id,
            home_team=home_team,
            away_team=away_team,
            display_name=display_name,
            whoscored_url=whoscored_url,
            competition=competition,
            season=season,
            date_str=date_str,
            has_matchcentre=has_matchcentre,
        )
    except Exception:
        return None


# ── Filter helpers ────────────────────────────────────────────────────────────

def _normalize_season(s: str) -> str:
    s = str(s).strip()
    m = re.match(r'(\d{4})\s*[-/]\s*(\d{2,4})', s)
    if m:
        start, end = m.group(1), m.group(2)
        if len(end) == 2:
            end = start[:2] + end
        return f"{start}/{end}"
    return s


def _matches_season(fixture_season: str, filter_season: str) -> bool:
    if not filter_season:
        return True
    return _normalize_season(fixture_season) == _normalize_season(filter_season)


def _matches_competition(fixture_comp: str, filter_comp: str) -> bool:
    if not filter_comp:
        return True
    return filter_comp.lower() in fixture_comp.lower() or fixture_comp.lower() in filter_comp.lower()


# ── Public API ────────────────────────────────────────────────────────────────

def search_fixtures(
    team_name: str,
    season: Optional[str] = None,
    competition: Optional[str] = None,
    played_only: bool = True,
    max_results: int = 100,
    debug: bool = False,
) -> list[dict]:
    """
    Search for WhoScored fixtures for a team.
    Supports 4 filter scenarios (team only / +season / +competition / all).
    By default, only returns matches that have already been played (MatchCentre = True).
    Returns list of Fixture dicts sorted most recent first.
    """
    # Step 1: Resolve team ID
    team_info = _resolve_team(team_name)
    if not team_info:
        if debug:
            print(f"   [DEBUG] Unknown team: {team_name!r}. Add it to KNOWN_TEAMS.")
        return []

    team_id, team_slug = team_info
    if debug:
        print(f"   [DEBUG] Resolved: {team_name!r} -> ID={team_id}, Slug={team_slug}")

    # Step 2: Fetch and parse fixtures from WhoScored
    session = _make_session()
    _warm_up(session)

    if debug:
        print(f"   [DEBUG] Fetching: {WS_FIXTURES_URL.format(team_id=team_id, team_slug=team_slug)}")

    raw_rows = _fetch_and_parse_fixtures(session, team_id, team_slug)

    if debug:
        print(f"   [DEBUG] Raw rows extracted: {len(raw_rows)}")
        if raw_rows:
            print(f"   [DEBUG] Sample row: {raw_rows[0]}")

    # Step 3: Parse rows
    fixtures = [f for row in raw_rows if (f := _parse_row(row)) is not None]

    # Step 4: Apply filters
    if season:
        fixtures = [f for f in fixtures if _matches_season(f.season, season)]
    if competition:
        fixtures = [f for f in fixtures if _matches_competition(f.competition, competition)]
    if played_only:
        fixtures = [f for f in fixtures if f.has_matchcentre]

    # Step 5: Sort most recent first, limit
    fixtures.sort(key=lambda f: f.date_str or "", reverse=True)
    fixtures = fixtures[:max_results]

    return [f.to_dict() for f in fixtures]
