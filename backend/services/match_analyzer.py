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


def _get_player_match_stats(df: pd.DataFrame) -> dict:
    """
    Calculate match-wide player involvement:
    - total touches (any event with position and playerName)
    - successful passes played
    - successful passes received
    """
    stats = {}
    
    # Passes stats
    passes = df[(df["type"] == "Pass") & (df["outcomeType"] == "Successful")]
    for player, count in passes["playerName"].value_counts().items():
        if player not in stats: stats[player] = {"touches": 0, "passesPlayed": 0, "passesReceived": 0}
        stats[player]["passesPlayed"] = int(count)
        
    # Received stats (sequential)
    for team in df["team"].unique():
        t_events = df[df["team"] == team]
        indices = t_events.index.tolist()
        for i, idx in enumerate(indices):
            row = df.loc[idx]
            if row["type"] == "Pass" and row["outcomeType"] == "Successful":
                if i + 1 < len(indices):
                    next_row = df.loc[indices[i+1]]
                    receiver = next_row["playerName"]
                    if pd.notna(receiver) and receiver != row["playerName"]:
                        if receiver not in stats: stats[receiver] = {"touches": 0, "passesPlayed": 0, "passesReceived": 0}
                        stats[receiver]["passesReceived"] += 1

    # Touches (all unique events with location)
    touches = df[df["playerName"].notna() & df["x"].notna() & df["y"].notna()]
    for player, count in touches["playerName"].value_counts().items():
        if player not in stats: stats[player] = {"touches": 0, "passesPlayed": 0, "passesReceived": 0}
        stats[player]["touches"] = int(count)

    return stats


# ══════════════════════════════════════════════════════════════════════════════
#  1. MATCH SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

def get_match_summary(csv_path: str, period: str | None = None) -> dict:
    """
    Basic match facts: scoreline, shots, shots on target, saves, fouls, cards,
    corners, and possession estimate.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)
    if period and period in ("FirstHalf", "SecondHalf"):
        df = df[df["period"] == period]

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

def get_shot_map(csv_path: str, period: str | None = None) -> dict:
    """
    All shots with location and outcome category.
    Outcome colours: Goal (green), On Target/Saved (amber), Missed/Blocked (red).
    Enhanced with shot origin context (body part, set piece origin).
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)
    if period and period in ("FirstHalf", "SecondHalf"):
        df = df[df["period"] == period]
    shots = df[df["type"].isin(SHOT_TYPES)].copy()

    def _outcome_category(row) -> str:
        if row["type"] == "Goal":
            return "goal"
        elif row["type"] == "SavedShot":
            return "on_target"
        else:
            return "off_target"

    def _shot_body_part(row) -> str:
        if row.get("is_header"):
            return "Header"
        elif row.get("is_left_foot"):
            return "Left Foot"
        elif row.get("is_right_foot"):
            return "Right Foot"
        return "Foot"

    def _shot_origin(row, idx) -> str:
        """Determine the set piece origin of a shot."""
        if row.get("is_penalty"):
            return "Penalty"
        # Direct corner shot (the shot itself is a corner)
        if row.get("is_corner"):
            return "Corner Shot"
        # Direct free kick shot (the shot itself is a free kick)
        if row.get("is_freekick"):
            return "Free Kick"
        # Check if previous event from same team is a corner or free kick
        same_team_prev = df[
            (df.index < idx)
            & (df["team"] == row["team"])
            & (df["period"] == row["period"])
        ]
        if not same_team_prev.empty:
            prev = same_team_prev.iloc[-1]
            if prev.get("is_corner"):
                return "From Corner"
            if prev.get("is_freekick"):
                return "From Free Kick"
        return "Open Play"

    results = []
    for idx, row in shots.iterrows():
        results.append({
            "player": row["playerName"],
            "team": row["team"],
            "minute": int(row["match_minute"]),
            "x": round(float(row["x"]), 1),
            "y": round(float(row["y"]), 1),
            "outcome": _outcome_category(row),
            "isBigChance": bool(row.get("is_big_chance", False)),
            "isHeader": bool(row.get("is_header", False)),
            "bodyPart": _shot_body_part(row),
            "origin": _shot_origin(row, idx),
            "goalMouthY": round(float(row["goal_mouth_y"]), 1) if pd.notna(row.get("goal_mouth_y")) else None,
            "goalMouthZ": round(float(row["goal_mouth_z"]), 1) if pd.notna(row.get("goal_mouth_z")) else None,
        })

    return {
        "homeTeam": home, "awayTeam": away,
        "shots": results,
        "playerStats": _get_player_match_stats(df),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  4. PASS NETWORK
# ══════════════════════════════════════════════════════════════════════════════

def get_pass_network(csv_path: str, team: str | None = None, period: str | None = None) -> dict:
    """
    Passing network: average position of each player + weighted edges between
    passers and receivers.

    We infer the receiver by looking at the *next* event in chronological order:
    if it's from the same team and has a playerName, that player received the ball.
    Only successful passes are counted.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)
    if period and period in ("FirstHalf", "SecondHalf"):
        df = df[df["period"] == period]
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
        passes_played_counts = defaultdict(int)
        passes_received_counts = defaultdict(int)
        touches_counts = defaultdict(int)

        # Pre-calculate touches for the specific context
        for _, row in team_events.iterrows():
            if pd.notna(row["playerName"]):
                touches_counts[row["playerName"]] += 1

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
                    passes_played_counts[passer] += 1
                    passes_received_counts[receiver] += 1

        # Build nodes
        nodes = []
        for player, pos in player_positions.items():
            if pos["count"] > 0:
                nodes.append({
                    "player": player,
                    "avgX": round(pos["x_sum"] / pos["count"], 1),
                    "avgY": round(pos["y_sum"] / pos["count"], 1),
                    "passCount": pos["count"],
                    "touches": touches_counts[player],
                    "passesPlayed": passes_played_counts[player],
                    "passesReceived": passes_received_counts[player],
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

    return {
        "homeTeam": home, "awayTeam": away, 
        "networks": networks,
        "playerStats": _get_player_match_stats(df),
    }


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
#  6B. AVERAGE IN-POSSESSION SHAPE
# ══════════════════════════════════════════════════════════════════════════════

def get_average_shape(csv_path: str, period: str | None = None) -> dict:
    """
    Average in-possession shape per player.
    Excludes set pieces and kick-offs to reflect strict open-play structure.
    Calculates average X,Y for each player during ball interactions.
    Identifies substitutes to render them differently.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)
    if period and period in ("FirstHalf", "SecondHalf"):
        df = df[df["period"] == period]

    def _get_initials(name):
        parts = str(name).split()
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    # Determine substitutes (players subbed ON)
    subs_on = set(df[df["type"] == "SubstitutionOn"]["playerName"].unique())

    # Strict open play filter
    open_play = df[
        (~df["is_corner"].fillna(False).astype(bool))
        & (~df["is_freekick"].fillna(False).astype(bool))
        & (~df["type"].isin({"GoalKick", "Start", "End"}))
        & (~df["is_penalty"].fillna(False).astype(bool))
    ]

    def _shape(team: str) -> list[dict]:
        # Events where team has possession and we have location
        team_touches = open_play[(open_play["team"] == team) & open_play["x"].notna() & open_play["y"].notna()]
        
        # Calculate passes played and received using the full un-filtered sequential df for accurate next-event tracking
        team_events_full = df[df["team"] == team]
        team_event_indices = team_events_full.index.tolist()
        
        passes_played_counts = defaultdict(int)
        passes_received_counts = defaultdict(int)
        
        for i, idx in enumerate(team_event_indices):
            row = df.loc[idx]
            if row["type"] == "Pass" and row["outcomeType"] == "Successful":
                passer = row["playerName"]
                if pd.notna(passer):
                    passes_played_counts[passer] += 1
                
                # Receiver is the player in the next consecutive event for the team
                if i + 1 < len(team_event_indices):
                    next_idx = team_event_indices[i + 1]
                    next_row = df.loc[next_idx]
                    receiver = next_row["playerName"]
                    if pd.notna(receiver) and receiver != passer:
                        passes_received_counts[receiver] += 1

        results = []
        for player, group in team_touches.groupby("playerName"):
            count = len(group)
            if count < 3:  # Too few touches to establish a shape
                continue
                
            avg_x = group["x"].mean()
            avg_y = group["y"].mean()

            results.append({
                "player": player,
                "initials": _get_initials(player),
                "x": round(float(avg_x), 1),
                "y": round(float(avg_y), 1),
                "touches": count,
                "passesPlayed": passes_played_counts[player],
                "passesReceived": passes_received_counts[player],
                "isSub": player in subs_on
            })
            
        # Sort by touches mostly to layer them predictably
        results.sort(key=lambda x: x["touches"], reverse=True)
        return results

    return {
        "homeTeam": home, "awayTeam": away,
        "home": _shape(home),
        "away": _shape(away)
    }


# ══════════════════════════════════════════════════════════════════════════════
#  7. xT MOMENTUM TIMELINE
# ══════════════════════════════════════════════════════════════════════════════

def get_xT_momentum(csv_path: str, window: int = 5, period: str | None = None) -> dict:
    """
    Rolling xT difference between home and away, plotted per minute.
    Positive = home dominance, negative = away dominance.
    Uses a sliding window for smoothing.
    Includes match event annotations: goals, red cards, substitutions.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)
    if period and period in ("FirstHalf", "SecondHalf"):
        df = df[df["period"] == period]

    # Build per-minute xT sums for each team
    max_min = int(df["minute"].max()) + 1
    home_xT = np.zeros(max_min)
    away_xT = np.zeros(max_min)
    player_xt = defaultdict(float)

    for _, row in df[df["xT"].notna()].iterrows():
        m = int(row["minute"])
        xt = float(row["xT"])
        player_name = str(row["playerName"])
        if pd.notna(row["playerName"]):
            player_xt[player_name] += xt

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

    # Top 3 threat creators
    top_players = [
        {"name": p, "xT": round(v, 2)}
        for p, v in sorted(player_xt.items(), key=lambda x: x[1], reverse=True)
        if v > 0
    ][:3]

    # Build match event annotations
    annotations = []

    for _, g in df[df["type"] == "Goal"].iterrows():
        annotations.append({
            "minute": int(g["minute"]),
            "type": "goal",
            "team": g["team"],
            "player": g.get("playerName", ""),
            "isOwnGoal": bool(g.get("is_own_goal", False)),
        })

    red_mask = df["is_red_card"] == True
    if "is_second_yellow" in df.columns:
        red_mask = red_mask | (df["is_second_yellow"] == True)
    for _, r in df[red_mask].iterrows():
        annotations.append({
            "minute": int(r["minute"]),
            "type": "redCard",
            "team": r["team"],
            "player": r.get("playerName", ""),
        })

    sub_on_events = df[df["type"] == "SubstitutionOn"]
    sub_off_events = df[df["type"] == "SubstitutionOff"]
    for _, s in sub_on_events.iterrows():
        off_match = sub_off_events[
            (sub_off_events["team"] == s["team"]) & (sub_off_events["minute"] == s["minute"])
        ]
        player_off = off_match.iloc[0]["playerName"] if not off_match.empty else ""
        annotations.append({
            "minute": int(s["minute"]),
            "type": "substitution",
            "team": s["team"],
            "playerOn": s.get("playerName", ""),
            "playerOff": player_off,
        })

    annotations.sort(key=lambda a: a["minute"])

    return {
        "homeTeam": home, "awayTeam": away,
        "windowSize": window,
        "timeline": timeline,
        "topPlayers": top_players,
        "annotations": annotations,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  8. DEFENSIVE ACTIONS HOTSPOT
# ══════════════════════════════════════════════════════════════════════════════

def get_defensive_actions(csv_path: str, period: str | None = None) -> dict:
    """
    Location scatter of tackles, interceptions, fouls, challenges, and ball
    recoveries per team.  Allows the frontend to visualise pressing height,
    defensive shape, and high-turnover pressing chains.

    Each action is tagged with:
    - isSetPiece   — whether it occurred during a set-piece sequence
    - leadsToShot  — whether a same-team shot followed within 15 seconds
    - shot*        — location / outcome of the resulting shot (if any)

    Also returns duelsByZone: success rates for tackles, challenges, and aerials
    broken down by defensive/middle/attacking thirds.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)
    if period and period in ("FirstHalf", "SecondHalf"):
        df = df[df["period"] == period]

    PRESSING_ACTIONS = DEFENSIVE_ACTIONS | {"BallRecovery"}

    def _is_set_piece_action(idx: int) -> bool:
        """Check if a defensive action occurred during a set piece sequence.
        Look at the previous 3 events from the opposing team for a corner/FK delivery."""
        row = df.loc[idx]
        opp_team = away if row["team"] == home else home
        prev_events = df[
            (df.index < idx)
            & (df["period"] == row["period"])
        ].tail(4)
        for _, prev in prev_events.iterrows():
            if prev.get("is_corner") or prev.get("is_freekick"):
                return True
            if prev.get("type") == "GoalKick":
                return True
        return False

    def _find_shot_after(idx: int, team: str, max_seconds: int = 15) -> dict | None:
        """Look ahead from *idx* for a same-team shot within *max_seconds*."""
        row = df.loc[idx]
        action_time = float(row["minute"]) * 60 + float(row.get("second", 0) or 0)
        action_period = row["period"]

        subsequent = df[
            (df.index > idx)
            & (df["period"] == action_period)
        ]

        for s_idx, s_row in subsequent.iterrows():
            event_time = float(s_row["minute"]) * 60 + float(s_row.get("second", 0) or 0)
            if event_time - action_time > max_seconds:
                break
            if s_row["team"] == team and s_row["type"] in SHOT_TYPES:
                return {
                    "shotPlayer": s_row.get("playerName", ""),
                    "shotMinute": int(s_row["match_minute"]),
                    "shotX": round(float(s_row["x"]), 1) if pd.notna(s_row.get("x")) else None,
                    "shotY": round(float(s_row["y"]), 1) if pd.notna(s_row.get("y")) else None,
                    "shotOutcome": "Goal" if s_row["type"] == "Goal" else s_row["outcomeType"],
                }
            # If the opponent gains possession, the pressing chain is broken
            if s_row["team"] != team and s_row["type"] in {"Pass", "Carry", "TakeOn"}:
                break

        return None

    def _actions(team: str) -> list[dict]:
        subset = df[
            (df["team"] == team)
            & df["type"].isin(PRESSING_ACTIONS)
            & df["x"].notna()
            & df["y"].notna()
        ]
        results = []
        for idx, row in subset.iterrows():
            shot_info = _find_shot_after(idx, team)
            action_data = {
                "player": row["playerName"],
                "type": row["type"],
                "outcome": row["outcomeType"],
                "minute": int(row["match_minute"]),
                "x": round(float(row["x"]), 1),
                "y": round(float(row["y"]), 1),
                "isSetPiece": _is_set_piece_action(idx),
                "leadsToShot": shot_info is not None,
            }
            if shot_info:
                action_data.update(shot_info)
            results.append(action_data)
        return results

    def _duels_by_zone(team: str) -> dict:
        t = df[df["team"] == team]
        duel_types = {
            "Tackle": t[t["type"] == "Tackle"],
            "Challenge": t[t["type"] == "Challenge"],
            "Aerial": t[t["type"] == "Aerial"],
        }
        zones = [
            ("defensiveThird", 0, 33.3, "Defensive Third"),
            ("middleThird", 33.3, 66.6, "Middle Third"),
            ("attackingThird", 66.6, 100, "Attacking Third"),
        ]
        result = []
        for zone_key, x_min, x_max, zone_label in zones:
            zone_data = {"zone": zone_key, "label": zone_label}
            for duel_type, duel_df in duel_types.items():
                zone_duels = duel_df[
                    duel_df["x"].notna()
                    & (duel_df["x"] >= x_min) & (duel_df["x"] < x_max)
                ]
                total = len(zone_duels)
                won = len(zone_duels[zone_duels["outcomeType"] == "Successful"])
                zone_data[duel_type.lower()] = {
                    "total": total,
                    "won": won,
                    "pct": round(won / total * 100, 1) if total else 0,
                }
            result.append(zone_data)
        return result

    return {
        "homeTeam": home, "awayTeam": away,
        "home": _actions(home),
        "away": _actions(away),
        "homeDuelsByZone": _duels_by_zone(home),
        "awayDuelsByZone": _duels_by_zone(away),
        "playerStats": _get_player_match_stats(df),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  9. ZONE ENTRIES (Final Third + Zone 14)
# ══════════════════════════════════════════════════════════════════════════════

def get_zone_entries(csv_path: str, period: str | None = None) -> dict:
    """
    Successful passes and carries that enter:
    - The Final Third (endX >= 67)
    - Zone 14 (the golden square: x 72-83, y 30-70)

    Only open-play entries — excludes corners, free kicks, and goal kicks.
    Returns counts and individual entry vectors for visualisation.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)
    if period and period in ("FirstHalf", "SecondHalf"):
        df = df[df["period"] == period]

    def _entries(team: str) -> dict:
        t_all = df[df["team"] == team]
        t = t_all[t_all["outcomeType"] == "Successful"]

        # Exclude set pieces: corners, free kicks, goal kicks
        open_play = t[
            (~t["is_corner"].fillna(False).astype(bool))
            & (~t["is_freekick"].fillna(False).astype(bool))
            & (t["type"] != "GoalKick")
        ]

        # Final third entries: events starting outside final third, ending inside
        ft_entries = open_play[
            (open_play["x"] < FINAL_THIRD_X) & (open_play["endX"] >= FINAL_THIRD_X)
            & open_play["type"].isin({"Pass", "Carry"})
        ]

        # Zone 14 entries
        z14_entries = open_play[
            (open_play["endX"] >= ZONE_14_X_MIN) & (open_play["endX"] <= ZONE_14_X_MAX)
            & (open_play["endY"] >= ZONE_14_Y_MIN) & (open_play["endY"] <= ZONE_14_Y_MAX)
            & open_play["type"].isin({"Pass", "Carry"})
        ]

        # Through Balls (Progressive only, both successful & unsuccessful)
        tb_entries = t_all[
            (t_all["is_through_ball"].fillna(False).astype(bool))
            & (t_all["endX"] > t_all["x"])  # progressive filter
        ]

        # Box Entries: passes/carries ending inside the penalty box from outside it (open play)
        open_play_all_teams = df[
            (~df["is_corner"].fillna(False).astype(bool))
            & (~df["is_freekick"].fillna(False).astype(bool))
            & (df["type"] != "GoalKick")
            & (df["team"] == team)
        ]
        box_pass_entries = open_play_all_teams[
            (open_play_all_teams["is_box_entry_pass"].fillna(False).astype(bool))
            & (open_play_all_teams["outcomeType"] == "Successful")
        ]
        box_carry_entries = open_play_all_teams[
            (open_play_all_teams["is_box_entry_carry"].fillna(False).astype(bool))
            & (open_play_all_teams["type"] == "Carry")
        ]
        box_entries = pd.concat([box_pass_entries, box_carry_entries]).sort_values(["period", "match_minute"])

        # Touches in the Opposition Box: successful on-ball events where is_touch_in_box == True
        # Goals and shots are included regardless of outcome label (SavedShot etc. are successful attacks)
        SHOT_TYPES_SET = {"SavedShot", "MissedShots", "Goal", "ShotOnPost", "BlockedShot", "AttemptSaved", "Attempt"}
        t_all_team = df[df["team"] == team]
        box_touches_df = t_all_team[
            (t_all_team["is_touch_in_box"].fillna(False).astype(bool))
            & pd.notna(t_all_team["x"])
            & pd.notna(t_all_team["y"])
            & (
                (t_all_team["outcomeType"] == "Successful")
                | (t_all_team["type"].isin(SHOT_TYPES_SET))  # shots always count
            )
        ]

        def _to_vectors(subset):
            vectors = []
            for _, row in subset.iterrows():
                if pd.notna(row["x"]) and pd.notna(row["endX"]):
                    vectors.append({
                        "player": row["playerName"],
                        "type": row["type"],
                        "minute": int(row["match_minute"]),
                        "outcome": row["outcomeType"],
                        "startX": round(float(row["x"]), 1),
                        "startY": round(float(row["y"]), 1),
                        "endX": round(float(row["endX"]), 1),
                        "endY": round(float(row["endY"]), 1),
                    })
            return vectors

        def _to_touches(subset):
            touches = []
            for _, row in subset.iterrows():
                try:
                    touches.append({
                        "player": str(row.get("playerName", "Unknown")),
                        "type": str(row.get("type", "")),
                        "minute": int(row["match_minute"]),
                        "outcome": str(row.get("outcomeType", "")),
                        "x": round(float(row["x"]), 1),
                        "y": round(float(row["y"]), 1),
                    })
                except (TypeError, ValueError):
                    continue
            return touches

        return {
            "finalThirdCount": len(ft_entries),
            "zone14Count": len(z14_entries),
            "throughBallCount": len(tb_entries),
            "boxCount": len(box_entries),
            "boxTouchesCount": len(box_touches_df),
            "finalThirdEntries": _to_vectors(ft_entries),
            "zone14Entries": _to_vectors(z14_entries),
            "throughBallEntries": _to_vectors(tb_entries),
            "boxEntries": _to_vectors(box_entries),
            "boxTouches": _to_touches(box_touches_df),
        }

    return {
        "homeTeam": home, "awayTeam": away,
        "home": _entries(home),
        "away": _entries(away),
        "playerStats": _get_player_match_stats(df),
    }



# ══════════════════════════════════════════════════════════════════════════════
#  11. PLAYER ACTIONS (Individual Filtering)
# ══════════════════════════════════════════════════════════════════════════════

def get_player_actions(csv_path: str, player_name: str, action_type: str | None = None, period: str | None = None) -> dict:
    """
    All events for a specific player, optionally filtered by action type.
    Supported action_type values: 'pass', 'shot', 'tackle', 'carry',
    'cross', 'aerial', or None for all.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)
    if period and period in ("FirstHalf", "SecondHalf"):
        df = df[df["period"] == period]

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


# ══════════════════════════════════════════════════════════════════════════════
#  15. SET PIECE ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def get_set_piece_analysis(csv_path: str, period: str | None = None) -> dict:
    """
    Comprehensive set piece analysis: corners and free kicks.

    For each delivery:
    - Start and end coordinates (delivery arrows)
    - Whether the team won first contact
    - Whether the delivery resulted in a shot on goal (within next 4 same-team events)

    Summary stats:
    - Set piece shots/goals vs open play shots/goals
    - Penalty goals vs non-penalty goals
    - First contact rates for corners and free kicks

    Also includes cornerZones: landing zone clusters for corner deliveries.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)
    if period and period in ("FirstHalf", "SecondHalf"):
        df = df[df["period"] == period]

    def _analyze_team(team: str) -> dict:
        t_all = df.copy().reset_index(drop=True)

        # ── Corner deliveries ─────────────────────────────────────────
        corner_mask = (
            (t_all["team"] == team)
            & (t_all["is_corner"].fillna(False).astype(bool))
            & t_all["x"].notna()
            & t_all["y"].notna()
        )
        corners = []
        for idx in t_all[corner_mask].index:
            row = t_all.loc[idx]
            delivery = _build_delivery(t_all, row, idx, team)
            corners.append(delivery)

        # ── Free kick deliveries ──────────────────────────────────────
        fk_mask = (
            (t_all["team"] == team)
            & (t_all["is_freekick"].fillna(False).astype(bool))
            & t_all["x"].notna()
            & t_all["y"].notna()
        )
        free_kicks = []
        for idx in t_all[fk_mask].index:
            row = t_all.loc[idx]
            delivery = _build_delivery(t_all, row, idx, team)
            free_kicks.append(delivery)

        # ── Corner landing zone clusters ──────────────────────────────────
        _CORNER_ZONE_LABELS = {
            "sixYardBox": "Six-Yard Box",
            "nearPost": "Near Post",
            "farPost": "Far Post",
            "penaltyArea": "Penalty Area",
            "widePenaltyBox": "Wide Penalty Box",
            "edgeOfBox": "Edge of Box",
            "cleared": "Cleared / Short",
        }

        def _classify_corner_zone(ex: float, ey: float) -> str:
            if ex >= 94:
                if 37 <= ey <= 63:
                    return "sixYardBox"
                return "nearPost" if ey < 50 else "farPost"
            if ex >= 83:
                return "penaltyArea" if 33 <= ey <= 67 else "widePenaltyBox"
            if ex >= 67:
                return "edgeOfBox"
            return "cleared"

        corner_zone_agg: dict[str, dict] = {}
        for c in corners:
            zone = _classify_corner_zone(c["endX"], c["endY"])
            if zone not in corner_zone_agg:
                corner_zone_agg[zone] = {"count": 0, "shots": 0, "goals": 0}
            corner_zone_agg[zone]["count"] += 1
            if c["resultedInShot"]:
                corner_zone_agg[zone]["shots"] += 1
            if c["shotOutcome"] == "Goal":
                corner_zone_agg[zone]["goals"] += 1

        corner_zones = sorted([
            {
                "zone": z,
                "label": _CORNER_ZONE_LABELS.get(z, z),
                "count": v["count"],
                "shots": v["shots"],
                "goals": v["goals"],
                "shotPct": round(v["shots"] / v["count"] * 100, 1) if v["count"] else 0,
            }
            for z, v in corner_zone_agg.items()
        ], key=lambda x: x["count"], reverse=True)

        # ── Summary stats (derived from delivery data — same forward-looking logic) ──
        all_deliveries = corners + free_kicks
        total_set_pieces = len(all_deliveries)
        led_to_shot = sum(1 for d in all_deliveries if d["resultedInShot"])
        led_to_goal = sum(1 for d in all_deliveries if d["shotOutcome"] == "Goal")
        led_to_big_chance = sum(1 for d in all_deliveries if d.get("resultedInBigChance"))
        first_contacts_won = sum(1 for d in all_deliveries if d["firstContact"])

        # Assists from set pieces (corners and free kicks)
        assist_corners = len(t_all[
            (t_all["team"] == team)
            & (t_all["is_assist_corner"].fillna(False).astype(bool))
        ]) if "is_assist_corner" in t_all.columns else 0
        assist_fks = len(t_all[
            (t_all["team"] == team)
            & (t_all["is_assist_freekick"].fillna(False).astype(bool))
        ]) if "is_assist_freekick" in t_all.columns else 0

        # Penalty goals (separate from set piece breakdown)
        penalty_goals = len(t_all[
            (t_all["team"] == team)
            & (t_all["type"] == "Goal")
            & (t_all["is_penalty"].fillna(False).astype(bool))
        ])

        # Corner-specific
        corner_first_contacts = sum(1 for c in corners if c["firstContact"])
        corner_led_to_shot = sum(1 for c in corners if c["resultedInShot"])

        # FK-specific
        fk_first_contacts = sum(1 for f in free_kicks if f["firstContact"])
        fk_led_to_shot = sum(1 for f in free_kicks if f["resultedInShot"])

        summary = {
            "totalSetPieces": total_set_pieces,
            "ledToShot": led_to_shot,
            "ledToBigChance": led_to_big_chance,
            "ledToGoal": led_to_goal,
            "firstContactsWon": first_contacts_won,
            "firstContactPct": round(first_contacts_won / total_set_pieces * 100, 1) if total_set_pieces else 0,
            "setPieceAssists": assist_corners + assist_fks,
            "assistCorners": assist_corners,
            "assistFreeKicks": assist_fks,
            "penaltyGoals": penalty_goals,
            "totalCorners": len(corners),
            "cornerFirstContacts": corner_first_contacts,
            "cornerFirstContactPct": round(corner_first_contacts / len(corners) * 100, 1) if corners else 0,
            "cornerLedToShot": corner_led_to_shot,
            "totalFreeKicks": len(free_kicks),
            "fkFirstContacts": fk_first_contacts,
            "fkFirstContactPct": round(fk_first_contacts / len(free_kicks) * 100, 1) if free_kicks else 0,
            "fkLedToShot": fk_led_to_shot,
        }

        return {
            "corners": corners,
            "freeKicks": free_kicks,
            "cornerZones": corner_zones,
            "summary": summary,
        }

    return {
        "homeTeam": home,
        "awayTeam": away,
        "home": _analyze_team(home),
        "away": _analyze_team(away),
        "playerStats": _get_player_match_stats(df),
    }


def _build_delivery(df: pd.DataFrame, row: pd.Series, idx: int, team: str) -> dict:
    """
    Build a single set piece delivery dict with first contact and shot outcome.
    """
    end_x = row["endX"] if pd.notna(row.get("endX")) else row["x"]
    end_y = row["endY"] if pd.notna(row.get("endY")) else row["y"]

    # Look at next events to determine first contact and shot result
    subsequent = df[(df.index > idx) & (df["period"] == row["period"])].head(5)

    first_contact = False
    resulted_in_shot = False
    resulted_in_big_chance = False
    shot_outcome = None

    if not subsequent.empty:
        next_event = subsequent.iloc[0]
        first_contact = next_event.get("team") == team

        # Check next 4 same-team events for a shot
        same_team_subsequent = subsequent[subsequent["team"] == team].head(4)
        for _, evt in same_team_subsequent.iterrows():
            if evt["type"] in SHOT_TYPES:
                resulted_in_shot = True
                shot_outcome = "Goal" if evt["type"] == "Goal" else "Shot"
                if evt.get("is_big_chance"):
                    resulted_in_big_chance = True
                break

    return {
        "player": row.get("playerName", ""),
        "minute": int(row.get("match_minute", 0)),
        "startX": round(float(row["x"]), 1),
        "startY": round(float(row["y"]), 1),
        "endX": round(float(end_x), 1),
        "endY": round(float(end_y), 1),
        "firstContact": first_contact,
        "resultedInShot": resulted_in_shot,
        "resultedInBigChance": resulted_in_big_chance,
        "shotOutcome": shot_outcome,
        "outcome": row.get("outcomeType", ""),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  18. GOAL BUILD UPS (2D ANIMATION)
# ══════════════════════════════════════════════════════════════════════════════

def get_goal_build_ups(csv_path: str, period: str | None = None) -> dict:
    """
    Extracts pass/carry sequences leading to a Goal for 2D animation.
    Traces backwards from the goal event as long as the ball remains with the scoring team.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)
    if period and period in ("FirstHalf", "SecondHalf"):
        df = df[df["period"] == period]

    goal_events = df[df["type"] == "Goal"]
    sequences = []
    
    for _, goal in goal_events.iterrows():
        goal_idx = goal.name
        team = goal["team"]
        if goal.get("is_own_goal"):
            team = home if team == away else away
        
        prev_events = df[(df.index <= goal_idx) & (df["period"] == goal["period"])].copy()
        sequence_items = []
        last_time = float(goal["minute"]) * 60 + float(goal.get("second", 0) or 0)
        
        for i in range(len(prev_events) - 1, -1, -1):
            evt = prev_events.iloc[i]
            
            # Opponent actions that signify a change of possession
            if evt["team"] != team:
                if evt["type"] in {"Pass", "Carry", "TakeOn", "BallRecovery", "Clearance", "GoalKick"}:
                    if evt["outcomeType"] == "Successful":
                        break
                    
            if evt["team"] == team:
                curr_time = float(evt["minute"]) * 60 + float(evt.get("second", 0) or 0)
                if last_time - curr_time > 20: 
                    # 20 second gap without an event -> break sequence
                    break
                
                # Only collect actionable on-ball events with coordinates
                if pd.notna(evt["x"]) and pd.notna(evt["y"]) and evt["type"] not in {"Start", "End", "SubstitutionOff", "SubstitutionOn"}:
                    if evt["type"] == "Goal":
                        ey_val = evt.get("goal_mouth_y")
                        ex = 100
                        ey = float(ey_val) if pd.notna(ey_val) else 50
                    else:
                        ex = evt.get("endX", evt["x"])
                        ey = evt.get("endY", evt["y"])
                    
                    if pd.isna(ex): ex = evt["x"]
                    if pd.isna(ey): ey = evt["y"]

                    sequence_items.append({
                        "id": int(evt.name),
                        "type": evt["type"],
                        "minute": int(evt["match_minute"]),
                        "second": int(evt.get("second", 0) or 0),
                        "player": str(evt.get("playerName", "Unknown")),
                        "team": str(evt["team"]),
                        "period": str(evt.get("period", "FirstHalf")),
                        "x": round(float(evt["x"]), 1),
                        "y": round(float(evt["y"]), 1),
                        "endX": round(float(ex), 1),
                        "endY": round(float(ey), 1),
                        "outcome": evt.get("outcomeType", ""),
                        "isGoal": evt["type"] == "Goal",
                    })
                    last_time = curr_time

        # Built backwards, so reverse for playback
        sequence_items.reverse()
        if len(sequence_items) > 0:
            sequences.append({
                "goalId": int(goal_idx),
                "team": team,
                "scorer": goal.get("playerName", "Unknown"),
                "minute": int(goal["match_minute"]),
                "events": sequence_items
            })
            
    return {
        "homeTeam": home,
        "awayTeam": away,
        "sequences": sequences
    }


# ══════════════════════════════════════════════════════════════════════════════
#  19. SUBSTITUTION IMPACT ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def get_substitution_impact(csv_path: str, min_minutes_after: int = 10) -> dict:
    """
    For each substitution, compares team metrics in the 15-minute window before
    and after the substitution event.

    Metrics compared: xT rate (per minute), shots per 15 min, progressive passes
    per 15 min, and goals scored in the window.

    Substitutions with fewer than min_minutes_after minutes remaining are flagged
    as having insufficient data for post-sub comparison.
    """
    df = _load_match(csv_path)
    home, away = _team_names(df)

    max_minute = int(df["minute"].max())

    def _window_metrics(team: str, start_min: int, end_min: int) -> dict:
        duration = end_min - start_min
        if duration <= 0:
            return {"xTRate": 0, "shotsP15": 0, "progPassesP15": 0, "goals": 0, "minutes": 0}
        w = df[(df["team"] == team) & (df["minute"] >= start_min) & (df["minute"] < end_min)]
        xT_rate = round(float(w["xT"].fillna(0).sum()) / duration, 4)
        shots = len(w[w["type"].isin(SHOT_TYPES)])
        prog_passes = int((w["prog_pass"] > 0).sum()) if "prog_pass" in w.columns else 0
        goals = len(w[(w["type"] == "Goal") & (~w["is_own_goal"].fillna(False))])
        return {
            "xTRate": xT_rate,
            "shotsP15": round(shots / duration * 15, 1),
            "progPassesP15": round(prog_passes / duration * 15, 1),
            "goals": goals,
            "minutes": duration,
        }

    sub_on_events = df[df["type"] == "SubstitutionOn"].copy()
    sub_off_events = df[df["type"] == "SubstitutionOff"]

    # Track which SubstitutionOff events have been matched to avoid double-pairing
    matched_off_indices: set[int] = set()

    substitutions = []
    for _, s in sub_on_events.iterrows():
        minute = int(s["minute"])
        team = s["team"]
        player_on = s.get("playerName", "Unknown")

        # Pair with an unmatched SubstitutionOff for the same team at the same minute
        candidates = sub_off_events[
            (sub_off_events["team"] == team)
            & (sub_off_events["minute"] == s["minute"])
            & (~sub_off_events.index.isin(matched_off_indices))
        ]
        if not candidates.empty:
            off_idx = candidates.index[0]
            matched_off_indices.add(off_idx)
            player_off = candidates.loc[off_idx, "playerName"]
        else:
            player_off = "Unknown"

        minutes_after = max_minute - minute
        sufficient_data = minutes_after >= min_minutes_after

        before_start = max(0, minute - 15)
        after_end = min(max_minute + 1, minute + 16)

        before = _window_metrics(team, before_start, minute)
        after = _window_metrics(team, minute, after_end) if sufficient_data else None

        substitutions.append({
            "minute": minute,
            "team": team,
            "playerOn": player_on,
            "playerOff": player_off,
            "minutesAfter": minutes_after,
            "sufficientData": sufficient_data,
            "before": before,
            "after": after,
        })

    substitutions.sort(key=lambda s: (s["team"] != home, s["minute"]))

    return {
        "homeTeam": home,
        "awayTeam": away,
        "minMinutesThreshold": min_minutes_after,
        "substitutions": substitutions,
    }
