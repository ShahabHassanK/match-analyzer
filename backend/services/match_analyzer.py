"""
match_analyzer.py
=================
Core analytics engine for the Pure Match Analyzer.

Takes a WhoScored events CSV filepath and produces structured analysis payloads
covering every phase of play: attack, defense, possession, pressing, and goalkeeping.

All coordinate outputs are normalised to the WhoScored 0-100 scale for direct
consumption by the frontend pitch visualisation component.
"""

import math
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd


# ── Constants ─────────────────────────────────────────────────────────────────

SHOT_TYPES = {"SavedShot", "MissedShot", "Goal", "ShotOnPost", "BlockedShot"}
DEFENSIVE_ACTIONS = {"Tackle", "Interception", "Foul", "Challenge", "BlockedPass"}
PROGRESSIVE_THRESHOLD = 0.25  # 25% of remaining distance to goal

# Zone 14: the central area just outside the penalty box (WhoScored 0-100 scale)
ZONE_14_X_MIN, ZONE_14_X_MAX = 72, 83
ZONE_14_Y_MIN, ZONE_14_Y_MAX = 30, 70

# Final third starts at x=67 on the WhoScored 0-100 scale
FINAL_THIRD_X = 67


# ── Data Loading ──────────────────────────────────────────────────────────────

def _load_match(csv_path: str) -> pd.DataFrame:
    """Load and lightly clean a WhoScored events CSV."""
    df = pd.read_csv(csv_path)

    # Normalise boolean columns — WhoScored exports mix TRUE/FALSE strings and NaN
    bool_cols = [c for c in df.columns if c.startswith("is_")]
    for col in bool_cols:
        df[col] = (
            df[col]
            .map({"TRUE": True, "True": True, True: True})
            .fillna(False)
            .infer_objects(copy=False)
            .astype(bool)
        )

    # Ensure numeric coords
    for col in ("x", "y", "endX", "endY", "minute", "second"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Derive a single match-minutes column for timeline analysis
    df["match_minute"] = df["minute"].fillna(0).astype(int)

    return df


def _team_names(df: pd.DataFrame) -> tuple[str, str]:
    """Return (home_team, away_team) from the metadata columns."""
    home = df["homeTeam"].dropna().iloc[0]
    away = df["awayTeam"].dropna().iloc[0]
    return home, away


# ══════════════════════════════════════════════════════════════════════════════
#  1. MATCH SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

def get_match_summary(csv_path: str) -> dict:
    """
    Basic match facts: scoreline, shots, shots on target, saves, fouls, cards,
    corners, and possession estimate.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)

    # Pre-compute own goal adjustments once
    all_goals = df[df["type"] == "Goal"]
    own_goals_by_team = {
        home: len(all_goals[(all_goals["team"] == home) & (all_goals["is_own_goal"] == True)]),
        away: len(all_goals[(all_goals["team"] == away) & (all_goals["is_own_goal"] == True)]),
    }
    opponent = {home: away, away: home}

    def _team_stats(team: str) -> dict:
        t = df[df["team"] == team]

        # Regular goals minus own goals committed, plus own goals committed by the opponent
        raw_goals = len(t[t["type"] == "Goal"])
        goals = raw_goals - own_goals_by_team[team] + own_goals_by_team[opponent[team]]
        shots = len(t[t["type"].isin(SHOT_TYPES)])
        shots_on_target = len(t[t["type"].isin({"SavedShot", "Goal"})])
        saves = len(t[t["is_gk_save"] == True])
        fouls = len(t[t["type"] == "Foul"])
        corners = len(t[t["type"] == "CornerAwarded"])
        yellows = len(t[(t["is_yellow_card"] == True)])
        reds = len(t[(t["is_red_card"] == True) | (t["is_second_yellow"] == True)])

        # Possession proxy: % of successful passes
        total_passes = len(df[df["type"] == "Pass"])
        team_passes = len(t[t["type"] == "Pass"])
        possession = round(team_passes / total_passes * 100, 1) if total_passes else 50.0

        passes_completed = len(t[(t["type"] == "Pass") & (t["outcomeType"] == "Successful")])
        pass_accuracy = round((passes_completed / team_passes * 100), 1) if team_passes else 0.0

        bc_shot = (t["is_big_chance_shot"] == True) if "is_big_chance_shot" in t.columns else False
        bc_pass = (t["is_big_chance"] == True) if "is_big_chance" in t.columns else False
        big_chances = len(t[(t["type"].isin(SHOT_TYPES)) & (bc_shot | bc_pass)])
        
        tackles = len(t[t["type"] == "Tackle"])
        interceptions = len(t[t["type"] == "Interception"])
        clearances = len(t[t["type"] == "Clearance"])

        return {
            "goals": goals,
            "shots": shots,
            "shotsOnTarget": shots_on_target,
            "saves": saves,
            "fouls": fouls,
            "corners": corners,
            "yellowCards": yellows,
            "redCards": reds,
            "possession": possession,
            "totalPasses": team_passes,
            "passesCompleted": passes_completed,
            "passAccuracy": pass_accuracy,
            "bigChances": big_chances,
            "tackles": tackles,
            "interceptions": interceptions,
            "clearances": clearances,
        }

    return {
        "homeTeam": home,
        "awayTeam": away,
        "homeStats": _team_stats(home),
        "awayStats": _team_stats(away),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  2. STARTING XI
# ══════════════════════════════════════════════════════════════════════════════

def get_starting_xi(csv_path: str) -> dict:
    """
    Extract starting XIs by collecting unique player names that appear in
    events during the first 2 minutes of the match (before any subs).
    Players who only appear in SubstitutionOn events are excluded.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)

    # Events in the opening minutes (excluding system events and subs)
    early = df[
        (df["match_minute"] <= 1)
        & (df["playerName"].notna())
        & (~df["type"].isin({"Start", "End", "SubstitutionOn", "SubstitutionOff"}))
    ]

    # Also consider all first-half players minus subs-on, as some may not get
    # an event in the first 2 minutes
    first_half = df[
        (df["period"] == "FirstHalf")
        & (df["playerName"].notna())
        & (~df["type"].isin({"Start", "End", "SubstitutionOn", "SubstitutionOff"}))
    ]
    subs_on = set(
        df[df["type"] == "SubstitutionOn"]["playerName"].dropna().unique()
    )

    def _xi(team: str) -> list[str]:
        # Start with early-event players
        candidates = set(early[early["team"] == team]["playerName"].unique())
        # Augment with first-half players who were NOT substituted ON
        first_half_players = set(first_half[first_half["team"] == team]["playerName"].unique())
        candidates = (candidates | first_half_players) - subs_on
        return sorted(candidates)

    def _subs(team: str, xi: list[str]) -> list[str]:
        all_team_players = set(df[(df["team"] == team) & (df["playerName"].notna())]["playerName"].unique())
        return sorted(all_team_players - set(xi))

    home_xi_list = _xi(home)
    away_xi_list = _xi(away)

    return {
        "homeTeam": home,
        "awayTeam": away,
        "homeXI": home_xi_list,
        "awayXI": away_xi_list,
        "homeSubs": _subs(home, home_xi_list),
        "awaySubs": _subs(away, away_xi_list),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  3. SHOT MAP
# ══════════════════════════════════════════════════════════════════════════════

def get_shot_map(csv_path: str) -> dict:
    """
    All shots with location and outcome category.
    Outcome colours: Goal (green), On Target/Saved (amber), Missed/Blocked (red).
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)
    shots = df[df["type"].isin(SHOT_TYPES)].copy()

    def _outcome_category(row) -> str:
        if row["type"] == "Goal":
            return "goal"
        elif row["type"] == "SavedShot":
            return "on_target"
        else:
            return "off_target"

    results = []
    for _, row in shots.iterrows():
        results.append({
            "player": row["playerName"],
            "team": row["team"],
            "minute": int(row["match_minute"]),
            "x": round(float(row["x"]), 1),
            "y": round(float(row["y"]), 1),
            "outcome": _outcome_category(row),
            "isBigChance": bool(row.get("is_big_chance", False)),
            "isHeader": bool(row.get("is_header", False)),
            "goalMouthY": round(float(row["goal_mouth_y"]), 1) if pd.notna(row.get("goal_mouth_y")) else None,
            "goalMouthZ": round(float(row["goal_mouth_z"]), 1) if pd.notna(row.get("goal_mouth_z")) else None,
        })

    return {
        "homeTeam": home, "awayTeam": away,
        "shots": results,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  4. PASS NETWORK
# ══════════════════════════════════════════════════════════════════════════════

def get_pass_network(csv_path: str, team: str | None = None) -> dict:
    """
    Passing network: average position of each player + weighted edges between
    passers and receivers.

    We infer the receiver by looking at the *next* event in chronological order:
    if it's from the same team and has a playerName, that player received the ball.
    Only successful passes are counted.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)
    teams_to_process = [team] if team else [home, away]

    networks = {}
    for t in teams_to_process:
        # Find the minute of the first substitution for this team
        subs = df[(df["team"] == t) & (df["type"] == "SubstitutionOff")]
        if not subs.empty:
            max_minute = int(subs["match_minute"].min())
        else:
            max_minute = int(df["match_minute"].max())

        # Isolate the match context up until the substitution
        team_events = df[(df["team"] == t) & (df["match_minute"] < max_minute)].copy()
        passes = team_events[(team_events["type"] == "Pass") & (team_events["outcomeType"] == "Successful")]

        # Build a recipient map: for each pass event, find the next event from the same team
        pass_indices = passes.index.tolist()
        team_event_indices = team_events.index.tolist()

        edge_counts = defaultdict(int)
        player_positions = defaultdict(lambda: {"x_sum": 0, "y_sum": 0, "count": 0})

        for idx in pass_indices:
            row = df.loc[idx]
            passer = row["playerName"]
            if pd.isna(passer):
                continue

            # Record passer position
            if pd.notna(row["x"]) and pd.notna(row["y"]):
                player_positions[passer]["x_sum"] += row["x"]
                player_positions[passer]["y_sum"] += row["y"]
                player_positions[passer]["count"] += 1

            # Find the next event from the same team
            pos_in_team = team_event_indices.index(idx) if idx in team_event_indices else -1
            if pos_in_team >= 0 and pos_in_team + 1 < len(team_event_indices):
                next_idx = team_event_indices[pos_in_team + 1]
                next_row = df.loc[next_idx]
                receiver = next_row["playerName"]
                if pd.notna(receiver) and receiver != passer:
                    edge_counts[(passer, receiver)] += 1

        # Build nodes
        nodes = []
        for player, pos in player_positions.items():
            if pos["count"] > 0:
                nodes.append({
                    "player": player,
                    "avgX": round(pos["x_sum"] / pos["count"], 1),
                    "avgY": round(pos["y_sum"] / pos["count"], 1),
                    "passCount": pos["count"],
                })

        # Build edges (only keep edges with >= 3 passes for clarity)
        edges = []
        for (passer, receiver), count in sorted(edge_counts.items(), key=lambda x: -x[1]):
            if count >= 3:
                edges.append({
                    "from": passer,
                    "to": receiver,
                    "count": count,
                })

        networks[t] = {
            "maxMinute": max_minute,
            "nodes": nodes,
            "edges": edges
        }

    return {"homeTeam": home, "awayTeam": away, "networks": networks}


# ══════════════════════════════════════════════════════════════════════════════
#  5. PPDA (Passes Per Defensive Action)
# ══════════════════════════════════════════════════════════════════════════════

def get_ppda(csv_path: str) -> dict:
    """
    PPDA measures pressing intensity.
    For each team, PPDA = opponent passes in opponent's own half / team's
    defensive actions in opponent's own half.
    Lower PPDA = more aggressive press.
    Calculated per half for tactical comparison.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)

    def _calc_ppda(pressing_team: str, opponent: str, period: str | None = None) -> float:
        subset = df if period is None else df[df["period"] == period]

        # Opponent's passes in their own defensive half (x < 50 for the opponent)
        opp_passes = subset[
            (subset["team"] == opponent)
            & (subset["type"] == "Pass")
            & (subset["x"] < 60)  # opponent's defensive 60% of the pitch
        ]

        # Pressing team's defensive actions in that same region
        # We need to flip coordinates: if opponent plays at x < 60, pressing team
        # acts at x > 40 (100 - 60)
        def_actions = subset[
            (subset["team"] == pressing_team)
            & (subset["type"].isin(DEFENSIVE_ACTIONS))
            & (subset["x"] > 40)  # high up the pitch for the pressing team
        ]

        n_def = len(def_actions)
        if n_def == 0:
            return 0.0

        return round(len(opp_passes) / n_def, 2)

    return {
        "homeTeam": home,
        "awayTeam": away,
        "home": {
            "overall": _calc_ppda(home, away),
            "firstHalf": _calc_ppda(home, away, "FirstHalf"),
            "secondHalf": _calc_ppda(home, away, "SecondHalf"),
        },
        "away": {
            "overall": _calc_ppda(away, home),
            "firstHalf": _calc_ppda(away, home, "FirstHalf"),
            "secondHalf": _calc_ppda(away, home, "SecondHalf"),
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  6. TERRITORY HEATMAP
# ══════════════════════════════════════════════════════════════════════════════

def get_territory_heatmap(csv_path: str, grid_size: int = 12) -> dict:
    """
    Touch density heatmap per team.
    Returns a grid_size x grid_size matrix of touch counts for each team,
    normalised to 0-1 for colour-mapping on the frontend.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)

    def _heatmap(team: str) -> list[list[float]]:
        touches = df[(df["team"] == team) & df["x"].notna() & df["y"].notna()]
        grid = np.zeros((grid_size, grid_size))

        for _, row in touches.iterrows():
            xi = min(int(row["x"] / 100 * grid_size), grid_size - 1)
            yi = min(int(row["y"] / 100 * grid_size), grid_size - 1)
            grid[yi][xi] += 1

        # Return raw touch counts for comparative analysis
        return grid.astype(int).tolist()

    return {
        "homeTeam": home, "awayTeam": away,
        "gridSize": grid_size,
        "home": _heatmap(home),
        "away": _heatmap(away),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  7. xT MOMENTUM TIMELINE
# ══════════════════════════════════════════════════════════════════════════════

def get_xT_momentum(csv_path: str, window: int = 5) -> dict:
    """
    Rolling xT difference between home and away, plotted per minute.
    Positive = home dominance, negative = away dominance.
    Uses a sliding window for smoothing.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)

    # Build per-minute xT sums for each team
    max_min = int(df["match_minute"].max()) + 1
    home_xT = np.zeros(max_min)
    away_xT = np.zeros(max_min)

    for _, row in df[df["xT"].notna()].iterrows():
        m = int(row["match_minute"])
        xt = float(row["xT"])
        if row["team"] == home:
            home_xT[m] += xt
        elif row["team"] == away:
            away_xT[m] += xt

    # Cumulative xT
    home_cum = np.cumsum(home_xT)
    away_cum = np.cumsum(away_xT)

    # Rolling difference (home - away), smoothed
    diff = home_cum - away_cum
    kernel = np.ones(window) / window
    smoothed = np.convolve(diff, kernel, mode="same")

    timeline = []
    for m in range(max_min):
        timeline.append({
            "minute": m,
            "homeCumXt": round(float(home_cum[m]), 4),
            "awayCumXt": round(float(away_cum[m]), 4),
            "difference": round(float(smoothed[m]), 4),
        })

    return {
        "homeTeam": home, "awayTeam": away,
        "windowSize": window,
        "timeline": timeline,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  8. DEFENSIVE ACTIONS HOTSPOT
# ══════════════════════════════════════════════════════════════════════════════

def get_defensive_actions(csv_path: str) -> dict:
    """
    Location scatter of tackles, interceptions, fouls, and challenges per team.
    Allows the frontend to visualise pressing height and defensive shape.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)

    def _actions(team: str) -> list[dict]:
        subset = df[
            (df["team"] == team)
            & df["type"].isin(DEFENSIVE_ACTIONS)
            & df["x"].notna()
            & df["y"].notna()
        ]
        results = []
        for _, row in subset.iterrows():
            results.append({
                "player": row["playerName"],
                "type": row["type"],
                "outcome": row["outcomeType"],
                "minute": int(row["match_minute"]),
                "x": round(float(row["x"]), 1),
                "y": round(float(row["y"]), 1),
            })
        return results

    return {
        "homeTeam": home, "awayTeam": away,
        "home": _actions(home),
        "away": _actions(away),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  9. ZONE ENTRIES (Final Third + Zone 14)
# ══════════════════════════════════════════════════════════════════════════════

def get_zone_entries(csv_path: str) -> dict:
    """
    Successful passes and carries that enter:
    - The Final Third (endX >= 67)
    - Zone 14 (the golden square: x 72-83, y 30-70)

    Returns counts and individual entry vectors for visualisation.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)

    def _entries(team: str) -> dict:
        t = df[(df["team"] == team) & (df["outcomeType"] == "Successful")]

        # Final third entries: events starting outside final third, ending inside
        ft_entries = t[
            (t["x"] < FINAL_THIRD_X) & (t["endX"] >= FINAL_THIRD_X)
            & t["type"].isin({"Pass", "Carry"})
        ]

        # Zone 14 entries
        z14_entries = t[
            (t["endX"] >= ZONE_14_X_MIN) & (t["endX"] <= ZONE_14_X_MAX)
            & (t["endY"] >= ZONE_14_Y_MIN) & (t["endY"] <= ZONE_14_Y_MAX)
            & t["type"].isin({"Pass", "Carry"})
        ]

        def _to_vectors(subset):
            vectors = []
            for _, row in subset.iterrows():
                if pd.notna(row["x"]) and pd.notna(row["endX"]):
                    vectors.append({
                        "player": row["playerName"],
                        "type": row["type"],
                        "minute": int(row["match_minute"]),
                        "startX": round(float(row["x"]), 1),
                        "startY": round(float(row["y"]), 1),
                        "endX": round(float(row["endX"]), 1),
                        "endY": round(float(row["endY"]), 1),
                    })
            return vectors

        return {
            "finalThirdCount": len(ft_entries),
            "zone14Count": len(z14_entries),
            "finalThirdEntries": _to_vectors(ft_entries),
            "zone14Entries": _to_vectors(z14_entries),
        }

    return {
        "homeTeam": home, "awayTeam": away,
        "home": _entries(home),
        "away": _entries(away),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  10. PASSING COMBINATIONS MATRIX
# ══════════════════════════════════════════════════════════════════════════════

def get_passing_combinations(csv_path: str, top_n: int = 10) -> dict:
    """
    Top N most frequent passer→receiver combinations for each team.
    Used to render a combination heatmap matrix on the frontend.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)

    def _combos(team: str) -> list[dict]:
        team_events = df[df["team"] == team].copy()
        passes = team_events[
            (team_events["type"] == "Pass") & (team_events["outcomeType"] == "Successful")
        ]

        team_indices = team_events.index.tolist()
        edge_counts = defaultdict(int)

        for idx in passes.index:
            passer = df.loc[idx, "playerName"]
            if pd.isna(passer):
                continue

            pos_in_team = team_indices.index(idx) if idx in team_indices else -1
            if pos_in_team >= 0 and pos_in_team + 1 < len(team_indices):
                next_idx = team_indices[pos_in_team + 1]
                receiver = df.loc[next_idx, "playerName"]
                if pd.notna(receiver) and receiver != passer:
                    edge_counts[(passer, receiver)] += 1

        sorted_combos = sorted(edge_counts.items(), key=lambda x: -x[1])[:top_n]
        return [
            {"from": p, "to": r, "count": c}
            for (p, r), c in sorted_combos
        ]

    return {
        "homeTeam": home, "awayTeam": away,
        "home": _combos(home),
        "away": _combos(away),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  11. PLAYER ACTIONS (Individual Filtering)
# ══════════════════════════════════════════════════════════════════════════════

def get_player_actions(csv_path: str, player_name: str, action_type: str | None = None) -> dict:
    """
    All events for a specific player, optionally filtered by action type.
    Supported action_type values: 'pass', 'shot', 'tackle', 'carry',
    'cross', 'aerial', or None for all.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)

    player_events = df[df["playerName"] == player_name].copy()

    TYPE_MAP = {
        "pass": {"Pass"},
        "shot": SHOT_TYPES,
        "tackle": {"Tackle"},
        "carry": {"Carry"},
        "cross": None,  # special: filter by is_cross flag
        "aerial": {"Aerial"},
        "take_on": {"TakeOn"},
        "interception": {"Interception"},
        "clearance": {"Clearance"},
        "block": {"Block", "BlockedPass", "BlockedShot"},
    }

    if action_type:
        key = action_type.lower()
        if key == "cross":
            player_events = player_events[player_events["is_cross"] == True]
        elif key in TYPE_MAP:
            player_events = player_events[player_events["type"].isin(TYPE_MAP[key])]

    actions = []
    for _, row in player_events.iterrows():
        action = {
            "type": row["type"],
            "outcome": row["outcomeType"],
            "minute": int(row["match_minute"]),
            "x": round(float(row["x"]), 1) if pd.notna(row["x"]) else None,
            "y": round(float(row["y"]), 1) if pd.notna(row["y"]) else None,
            "endX": round(float(row["endX"]), 1) if pd.notna(row["endX"]) else None,
            "endY": round(float(row["endY"]), 1) if pd.notna(row["endY"]) else None,
        }
        # Include relevant boolean flags that are True
        flags = [c for c in df.columns if c.startswith("is_") and row.get(c) == True]
        if flags:
            action["flags"] = flags
        actions.append(action)

    team = player_events["team"].mode().iloc[0] if not player_events.empty else "Unknown"

    return {
        "player": player_name,
        "team": team,
        "actionType": action_type,
        "count": len(actions),
        "actions": actions,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  12. PLAYER HEATMAP
# ══════════════════════════════════════════════════════════════════════════════

def get_player_heatmap(csv_path: str, player_name: str, grid_size: int = 12) -> dict:
    """
    Touch density heatmap for a single player.
    Returns a normalised grid_size x grid_size matrix.
    """
    df = _load_match(csv_path)

    touches = df[
        (df["playerName"] == player_name)
        & df["x"].notna()
        & df["y"].notna()
    ]

    grid = np.zeros((grid_size, grid_size))
    for _, row in touches.iterrows():
        xi = min(int(row["x"] / 100 * grid_size), grid_size - 1)
        yi = min(int(row["y"] / 100 * grid_size), grid_size - 1)
        grid[yi][xi] += 1

    max_val = grid.max()
    if max_val > 0:
        grid = grid / max_val

    team = touches["team"].mode().iloc[0] if not touches.empty else "Unknown"

    return {
        "player": player_name,
        "team": team,
        "gridSize": grid_size,
        "totalTouches": int(len(touches)),
        "heatmap": np.round(grid, 3).tolist(),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  13. PLAYER PASS SONAR
# ══════════════════════════════════════════════════════════════════════════════

def get_player_pass_sonar(csv_path: str, player_name: str, n_bins: int = 16) -> dict:
    """
    Pass direction sonar: groups all of a player's successful passes into
    angular bins (0-360°) and counts volume + average distance per bin.
    0° = straight forward (toward opponent goal), 90° = right, 180° = backward.
    """
    df = _load_match(csv_path)

    passes = df[
        (df["playerName"] == player_name)
        & (df["type"] == "Pass")
        & (df["outcomeType"] == "Successful")
        & df["x"].notna() & df["y"].notna()
        & df["endX"].notna() & df["endY"].notna()
    ]

    bin_size = 360 / n_bins
    bins = [{"angle": i * bin_size, "count": 0, "avgDistance": 0, "totalDist": 0} for i in range(n_bins)]

    for _, row in passes.iterrows():
        dx = row["endX"] - row["x"]
        dy = row["endY"] - row["y"]

        # Angle: 0° = forward (positive x), clockwise
        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad)
        # Normalise to 0-360
        angle_deg = angle_deg % 360

        distance = math.sqrt(dx**2 + dy**2)
        bin_idx = int(angle_deg / bin_size) % n_bins

        bins[bin_idx]["count"] += 1
        bins[bin_idx]["totalDist"] += distance

    # Calculate averages
    for b in bins:
        if b["count"] > 0:
            b["avgDistance"] = round(b["totalDist"] / b["count"], 1)
        del b["totalDist"]

    team = passes["team"].mode().iloc[0] if not passes.empty else "Unknown"

    return {
        "player": player_name,
        "team": team,
        "totalPasses": int(len(passes)),
        "bins": bins,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  14. ADVANCED MATCH METRICS (Stock-Exchange Panel)
# ══════════════════════════════════════════════════════════════════════════════

def get_advanced_metrics(csv_path: str) -> dict:
    """
    Computes a battery of advanced tactical metrics for both teams:
    Pressing, Progression, Possession, Aggression, Creativity, Duels, Shape.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)

    def _metrics(team: str, opponent: str) -> dict:
        t = df[df["team"] == team]
        o = df[df["team"] == opponent]

        # ── PRESSING ──────────────────────────────────────────────────────
        # PPDA: opponent passes in their own half / team's defensive actions in opp half
        opp_passes_own_half = len(o[(o["type"] == "Pass") & (o["x"] < 60)])
        team_def_actions_high = len(t[
            (t["type"].isin(DEFENSIVE_ACTIONS)) & (t["x"] > 40)
        ])
        ppda = round(opp_passes_own_half / team_def_actions_high, 2) if team_def_actions_high else 0.0

        # Final Third Ball Recoveries
        final_third_recoveries = len(t[
            (t["type"] == "BallRecovery") & (t["x"] >= FINAL_THIRD_X)
        ])

        # ── PROGRESSION ───────────────────────────────────────────────────
        # prog_pass/prog_carry are float distance values; positive = progressive
        progressive_passes = int((t["prog_pass"] > 0).sum()) if "prog_pass" in t.columns else 0
        progressive_carries = int((t["prog_carry"] > 0).sum()) if "prog_carry" in t.columns else 0

        # Build-up Play Ratio: % of passes in own third (x < 33) → higher = more patient build-up
        team_passes = t[t["type"] == "Pass"]
        total_team_passes = len(team_passes)
        own_third_passes = len(team_passes[team_passes["x"] < 33])
        buildup_ratio = round((own_third_passes / total_team_passes * 100), 1) if total_team_passes else 0.0

        # ── POSSESSION ────────────────────────────────────────────────────
        # Average Passing Sequence Length
        # Count consecutive passes by the same team, then average the sequence lengths
        passes_all = df[df["type"] == "Pass"].sort_values(["period", "minute", "second"]).reset_index(drop=True)
        sequences = []
        current_team = None
        current_len = 0
        for _, row in passes_all.iterrows():
            if row["team"] == team:
                if current_team == team:
                    current_len += 1
                else:
                    if current_team == team and current_len > 0:
                        sequences.append(current_len)
                    current_team = team
                    current_len = 1
            else:
                if current_team == team and current_len > 0:
                    sequences.append(current_len)
                current_team = row["team"]
                current_len = 0
        if current_team == team and current_len > 0:
            sequences.append(current_len)

        avg_sequence = round(sum(sequences) / len(sequences), 1) if sequences else 0.0

        # ── AGGRESSION ────────────────────────────────────────────────────
        tackles = len(t[t["type"] == "Tackle"])
        fouls = len(t[t["type"] == "Foul"])
        aggression_index = round((tackles + fouls) / 2, 1)

        # ── CREATIVITY ────────────────────────────────────────────────────
        key_passes = int(t["is_key_pass"].sum()) if "is_key_pass" in t.columns else 0

        # Crossing accuracy
        crosses = t[t["is_cross"] == True] if "is_cross" in t.columns else pd.DataFrame()
        total_crosses = len(crosses)
        successful_crosses = len(crosses[crosses["outcomeType"] == "Successful"]) if total_crosses else 0
        crossing_accuracy = round((successful_crosses / total_crosses * 100), 1) if total_crosses else 0.0

        # Direct Pass Ratio: long balls + through balls as % of total passes
        long_balls = int(t["is_long_ball"].sum()) if "is_long_ball" in t.columns else 0
        through_balls = int(t["is_through_ball"].sum()) if "is_through_ball" in t.columns else 0
        direct_passes = long_balls + through_balls
        direct_ratio = round((direct_passes / total_team_passes * 100), 1) if total_team_passes else 0.0

        # ── DUELS ─────────────────────────────────────────────────────────
        aerials = t[t["type"] == "Aerial"]
        total_aerials = len(aerials)
        aerials_won = len(aerials[aerials["outcomeType"] == "Successful"])
        aerial_win_pct = round((aerials_won / total_aerials * 100), 1) if total_aerials else 0.0

        takeons = t[t["type"] == "TakeOn"]
        total_takeons = len(takeons)
        takeons_won = len(takeons[takeons["outcomeType"] == "Successful"])
        dribble_success_pct = round((takeons_won / total_takeons * 100), 1) if total_takeons else 0.0

        # ── SHAPE ─────────────────────────────────────────────────────────
        # Field Tilt: team's final-third passes / total final-third passes by both teams
        team_ft_passes = len(team_passes[team_passes["x"] >= FINAL_THIRD_X])
        opp_passes_obj = o[o["type"] == "Pass"]
        opp_ft_passes = len(opp_passes_obj[opp_passes_obj["x"] >= FINAL_THIRD_X])
        total_ft = team_ft_passes + opp_ft_passes
        field_tilt = round((team_ft_passes / total_ft * 100), 1) if total_ft else 50.0

        return {
            "pressing": {
                "ppda": ppda,
                "finalThirdRecoveries": final_third_recoveries,
            },
            "progression": {
                "progressivePasses": progressive_passes,
                "progressiveCarries": progressive_carries,
                "buildUpRatio": buildup_ratio,
            },
            "possession": {
                "avgPassSequence": avg_sequence,
            },
            "aggression": {
                "aggressionIndex": aggression_index,
            },
            "creativity": {
                "keyPasses": key_passes,
                "crossingAccuracy": crossing_accuracy,
                "directPassRatio": direct_ratio,
            },
            "duels": {
                "aerialWinPct": aerial_win_pct,
                "dribbleSuccessPct": dribble_success_pct,
            },
            "shape": {
                "fieldTilt": field_tilt,
            },
        }

    return {
        "homeTeam": home,
        "awayTeam": away,
        "home": _metrics(home, away),
        "away": _metrics(away, home),
    }
