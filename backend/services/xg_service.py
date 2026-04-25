"""
xG Service
----------
Loads the trained XGBoost xG model and runs inference on a match CSV.
All feature engineering replicates notebook xG_model_building.ipynb exactly
so that predictions here match notebook output to floating-point precision.
"""

import pickle
import xgboost as xgb
import numpy as np
import pandas as pd
from pathlib import Path

# ── Model artefacts (loaded once at startup) ─────────────────────────────────

MODEL_DIR = Path(__file__).parent.parent / "xg-model" / "my-xG-model"

_model = xgb.XGBClassifier()
_model.load_model(MODEL_DIR / "xgb_xg_model.json")

with open(MODEL_DIR / "xg_features.pkl", "rb") as _f:
    _features: list = pickle.load(_f)

with open(MODEL_DIR / "xg_clip_values.pkl", "rb") as _f:
    _clips_raw: dict = pickle.load(_f)

# Convert numpy scalars to plain Python floats — avoids any pandas/numpy
# type coercion issues when passing to Series.clip()
_clips: dict = {k: float(v) for k, v in _clips_raw.items()}

# XGBoost was trained with early_stopping_rounds=20 and best_iteration=107.
# When loaded from pickle in a fresh process the sklearn wrapper may not use
# best_ntree_limit automatically. We pin the iteration range explicitly.
_best_iter: int = int(getattr(_model, "best_iteration", 0)) or 107

# ── Constants ─────────────────────────────────────────────────────────────────

SHOT_TYPES = ["Goal", "SavedShot", "MissedShot", "BlockedShot", "ShotOnPost"]
PENALTY_XG = 0.76


# ── Feature engineering — exact replica of notebook cells 3 & 12 ─────────────

def backfill_assist_context(df_match: pd.DataFrame) -> pd.DataFrame:
    """
    Assist info lives on the preceding PASS row, not the shot row.
    Looks back up to 5 events, finds the most recent same-team pass,
    and copies its flags onto the shot row.
    Enforces mutual exclusivity: corner > freekick > cross > throughball.

    Identical to notebook cell 3.
    """
    df = df_match.copy()
    shot_indices = df[df["type"].isin(SHOT_TYPES)].index.tolist()

    for idx in shot_indices:
        shot_team = df.loc[idx, "team"]
        window_start = max(df.index[0], idx - 5)
        preceding = df.loc[window_start : idx - 1]

        same_team_passes = preceding[
            (preceding["type"] == "Pass") & (preceding["team"] == shot_team)
        ]

        if same_team_passes.empty:
            continue

        assist_row = same_team_passes.iloc[-1]

        is_cross       = bool(assist_row.get("is_cross", False))
        is_corner      = bool(assist_row.get("is_corner", False))
        is_freekick    = bool(assist_row.get("is_freekick", False))
        is_throughball = bool(assist_row.get("is_through_ball", False))

        if is_corner:
            is_cross = False

        df.loc[idx, "is_assist_throughball"] = is_throughball
        df.loc[idx, "is_assist_freekick"]    = is_freekick    and not is_throughball
        df.loc[idx, "is_assist_corner"]      = is_corner      and not is_freekick and not is_throughball
        df.loc[idx, "is_assist_cross"]       = is_cross       and not is_corner   and not is_freekick and not is_throughball

    return df


def prepare_match_features(df_match: pd.DataFrame, clips: dict) -> pd.DataFrame:
    """
    Geometry calculation + clipping + binary feature fill.
    Identical to notebook cell 12 prepare_match_features.
    Operates in-place on the passed DataFrame (same as notebook).
    """
    df_match["x_met"] = df_match["x"] * (105 / 100)
    df_match["y_met"] = df_match["y"] * (68 / 100)

    df_match["distance"] = np.sqrt(
        (105 - df_match["x_met"]) ** 2 + (34 - df_match["y_met"]) ** 2
    )

    angle_to_post1 = np.arctan2(37.66 - df_match["y_met"], 105 - df_match["x_met"])
    angle_to_post2 = np.arctan2(30.34 - df_match["y_met"], 105 - df_match["x_met"])
    df_match["angle_deg"] = np.degrees(np.abs(angle_to_post1 - angle_to_post2))

    df_match["log_distance"] = np.log(df_match["distance"])

    # Apply SAME clipping as training (Python floats, not numpy scalars)
    df_match["log_distance"] = df_match["log_distance"].clip(
        clips["log_dist_min"], clips["log_dist_max"]
    )
    df_match["angle_deg"] = df_match["angle_deg"].clip(
        clips["angle_min"], clips["angle_max"]
    )

    # Binary features — fill NaN with 0, cast to int
    binary_cols = [
        "is_header", "is_volley", "is_left_foot", "is_right_foot",
        "is_fast_break", "is_big_chance", "is_assist_throughball",
        "is_assist_cross", "is_assist_corner", "is_assist_freekick",
    ]
    for col in binary_cols:
        if col not in df_match.columns:
            df_match[col] = 0
    df_match[binary_cols] = df_match[binary_cols].fillna(0).astype(int)

    return df_match


def _predict_xg(feature_df: pd.DataFrame) -> np.ndarray:
    """
    Run predict_proba with an explicit iteration_range so that the model
    always uses best_iteration trees — matching notebook behaviour even when
    loaded from pickle in a fresh Python process.
    """
    try:
        return _model.predict_proba(
            feature_df,
            iteration_range=(0, _best_iter + 1),
        )[:, 1]
    except TypeError:
        # Fallback for XGBoost versions that don't support iteration_range
        return _model.predict_proba(feature_df)[:, 1]


# ── Main public function ──────────────────────────────────────────────────────

def get_xg_breakdown(csv_path: str) -> dict:
    """
    Load a match CSV, run the xG model, return a structured breakdown.

    Prediction logic mirrors notebook predict_match_xg exactly:
      1. Read CSV
      2. backfill_assist_context on FULL event stream
      3. Filter SHOT_TYPES
      4. Exclude own goals
      5. Exclude penalties (kept separately with fixed xG = 0.76)
      6. x >= 50 spatial filter
      7. prepare_match_features (geometry + clipping + binary fill)
      8. model.predict_proba with explicit best_iteration
    """
    df = pd.read_csv(csv_path)

    # Extract team metadata
    home_team = df["homeTeam"].dropna().iloc[0] if "homeTeam" in df.columns else "Home"
    away_team = df["awayTeam"].dropna().iloc[0] if "awayTeam" in df.columns else "Away"

    # ── Step 1: backfill assist context on FULL stream ────────────────────────
    df = backfill_assist_context(df)

    # ── Step 2: filter to shot events ────────────────────────────────────────
    shots_raw = df[df["type"].isin(SHOT_TYPES)].copy()

    # ── Step 3: separate own goals (shown but xG = 0, credited to benefiting team)
    if "is_own_goal" in shots_raw.columns:
        og_mask = shots_raw["is_own_goal"].fillna(False).astype(bool)
    else:
        og_mask = pd.Series(False, index=shots_raw.index)

    own_goal_shots = shots_raw[og_mask].copy()
    shots_raw = shots_raw[~og_mask]

    def _flip_team(name: str) -> str:
        return away_team if name == home_team else home_team

    if not own_goal_shots.empty:
        own_goal_shots["team"] = own_goal_shots["team"].map(_flip_team)
    own_goal_shots["xG"] = 0.0

    # ── Step 4: keep penalty shots aside (fixed xG) ───────────────────────────
    if "is_penalty" in shots_raw.columns:
        pen_mask = shots_raw["is_penalty"].fillna(False).astype(bool)
    else:
        pen_mask = pd.Series(False, index=shots_raw.index)

    penalty_shots = shots_raw[pen_mask].copy()
    model_shots   = shots_raw[~pen_mask].copy()

    # ── Step 5: spatial filter — attacking half only ───────────────────────────
    model_shots = model_shots[model_shots["x"] >= 50].copy()

    # ── Step 6: feature engineering ───────────────────────────────────────────
    if not model_shots.empty:
        model_shots = prepare_match_features(model_shots, _clips)
        model_shots["xG"] = _predict_xg(model_shots[_features]).astype(float)
    else:
        model_shots["xG"] = pd.Series(dtype=float)

    # ── Step 7: penalty shots get fixed xG ────────────────────────────────────
    penalty_shots = penalty_shots.copy()
    penalty_shots["xG"] = float(PENALTY_XG)

    # ── Step 8: combine and sort by minute (then second if available) ──────────
    model_shots["isOwnGoal"] = False
    penalty_shots["isOwnGoal"] = False
    own_goal_shots["isOwnGoal"] = True
    all_shots = pd.concat([model_shots, penalty_shots, own_goal_shots], ignore_index=True)

    sort_cols = ["minute", "second"] if "second" in all_shots.columns else ["minute"]
    all_shots = all_shots.sort_values(sort_cols, na_position="last").reset_index(drop=True)

    # ── Build response ────────────────────────────────────────────────────────

    def team_label(name: str) -> str:
        return "home" if name == home_team else "away"

    def body_part(row) -> str:
        if bool(row.get("is_header", False)):  return "Header"
        if bool(row.get("is_left_foot", False)): return "Left Foot"
        if bool(row.get("is_right_foot", False)): return "Right Foot"
        return "Unknown"

    def shot_origin(row) -> str:
        if bool(row.get("isOwnGoal", False)):            return "Own Goal"
        if bool(row.get("is_penalty", False)):           return "Penalty"
        if bool(row.get("is_assist_corner", False)):     return "Corner"
        if bool(row.get("is_assist_freekick", False)):   return "Free Kick"
        if bool(row.get("is_assist_cross", False)):      return "Cross"
        if bool(row.get("is_assist_throughball", False)): return "Through Ball"
        return "Open Play"

    def outcome_label(row) -> str:
        if bool(row.get("isOwnGoal", False)):  return "Own Goal"
        t = row.get("type", "")
        if t == "Goal":        return "Goal"
        if t == "SavedShot":   return "Saved"
        if t == "MissedShot":  return "Missed"
        if t == "BlockedShot": return "Blocked"
        if t == "ShotOnPost":  return "Post"
        return str(t)

    # Cumulative xG timeline
    timeline = []
    cum_home = cum_away = 0.0

    for _, row in all_shots.iterrows():
        xg_val  = float(row["xG"])
        t_label = team_label(str(row.get("team", "")))
        if t_label == "home":
            cum_home += xg_val
        else:
            cum_away += xg_val

        timeline.append({
            "minute":    int(row.get("minute", 0)),
            "team":      t_label,
            "player":    str(row.get("playerName", "Unknown")),
            "xG":        round(xg_val, 3),
            "cumHome":   round(cum_home, 3),
            "cumAway":   round(cum_away, 3),
            "isGoal":    bool(row.get("type", "") == "Goal"),
            "isPenalty": bool(row.get("is_penalty", False)),
            "isOwnGoal": bool(row.get("isOwnGoal", False)),
            "outcome":   outcome_label(row),
        })

    # Shot list
    shots_list = []
    for _, row in all_shots.iterrows():
        shots_list.append({
            "minute":    int(row.get("minute", 0)),
            "player":    str(row.get("playerName", "Unknown")),
            "team":      team_label(str(row.get("team", ""))),
            "x":         float(row.get("x", 0)),
            "y":         float(row.get("y", 0)),
            "xG":        round(float(row["xG"]), 3),
            "isGoal":    bool(row.get("type", "") == "Goal"),
            "isPenalty": bool(row.get("is_penalty", False)),
            "isOwnGoal": bool(row.get("isOwnGoal", False)),
            "isHeader":  bool(row.get("is_header", False)),
            "bodyPart":  body_part(row),
            "origin":    shot_origin(row),
            "outcome":   outcome_label(row),
        })

    # Team summaries
    def team_summary(team_name: str) -> dict:
        t = all_shots[all_shots["team"] == team_name]
        non_og = t[~t["isOwnGoal"].astype(bool)]
        total_xg = float(non_og["xG"].sum())
        if "is_penalty" in non_og.columns:
            pen_xg = float(non_og[non_og["is_penalty"].fillna(False).astype(bool)]["xG"].sum())
        else:
            pen_xg = 0.0
        return {
            "xG":    round(total_xg, 3),
            "npxG":  round(max(0.0, total_xg - pen_xg), 3),
            "goals": int((t["type"] == "Goal").sum()),
            "shots": int(len(non_og)),
        }

    home_s = team_summary(home_team)
    away_s = team_summary(away_team)

    def perf(goals: int, xg: float) -> dict:
        diff = round(goals - xg, 3)
        label = ("Expected" if abs(diff) < 0.2
                 else "Overperformed" if diff > 0
                 else "Underperformed")
        return {"xGDiff": diff, "label": label}

    return {
        "homeTeam": home_team,
        "awayTeam": away_team,
        "summary":  {"home": home_s, "away": away_s},
        "timeline": timeline,
        "shots":    shots_list,
        "performance": {
            "home": perf(home_s["goals"], home_s["xG"]),
            "away": perf(away_s["goals"], away_s["xG"]),
        },
        # Debug info — can be removed once results are verified
        "_debug": {
            "best_iter_used":   _best_iter,
            "model_shot_count": len(model_shots),
            "penalty_count":    len(penalty_shots),
            "clip_values":      _clips,
        },
    }
