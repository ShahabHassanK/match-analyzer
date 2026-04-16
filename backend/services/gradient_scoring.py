import math
import pandas as pd
import numpy as np
from services.match_analyzer import get_advanced_metrics

def load_match(csv_path: str):
    df = pd.read_csv(csv_path, low_memory=False)
    bool_cols = [c for c in df.columns if c.startswith("is_")]
    for col in bool_cols:
        df[col] = df[col].map({"TRUE": True, "True": True, True: True, "FALSE": False, "False": False, False: False}).fillna(False).infer_objects(copy=False).astype(bool)
    for col in ("x", "y", "endX", "endY", "minute", "second"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["match_minute"] = df["minute"].fillna(0).astype(int)
    return df

def get_gradient_scoring(csv_path: str) -> dict:
    df = load_match(csv_path)
    if "team" not in df.columns or "type" not in df.columns:
        return {}
    
    df_teams = df[df["team"].notna()]
    teams = df_teams["team"].unique()
    if len(teams) < 2:
        return {}
        
    # Correct home/away identification matching match_analyzer
    if "homeTeam" in df.columns and "awayTeam" in df.columns:
        home = df["homeTeam"].dropna().iloc[0]
        away = df["awayTeam"].dropna().iloc[0]
    else:
        home, away = teams[0], teams[1]
    
    adv = get_advanced_metrics(csv_path)
    
    # Identify attacking directions automatically (normalized WhoScored usually shoots at x=100)
    # But just in case, we check average shot X
    def get_attack_dir(team_name):
        shots = df[(df["team"] == team_name) & (df["type"].isin({"Goal", "Attempt", "SavedShot", "MissedShots"}))]
        return 1 if shots["x"].mean() > 50 else -1

    h_dir = get_attack_dir(home)
    a_dir = get_attack_dir(away)

    def compute_team(team: str, opp: str, is_home: bool):
        t = df[df["team"] == team]
        o = df[df["team"] == opp]
        t_adv = adv["home"] if is_home else adv["away"]
        o_adv = adv["away"] if is_home else adv["home"]
        
        t_succ = t[t["outcomeType"] == "Successful"]
        t_passes = t[t["type"] == "Pass"]
        t_succ_passes = t_succ[t_succ["type"] == "Pass"]
        
        o_succ = o[o["outcomeType"] == "Successful"]
        o_passes = o[o["type"] == "Pass"]
        o_succ_passes = o_succ[o_succ["type"] == "Pass"]
        
        SHOT_TYPES = {"SavedShot", "MissedShots", "Goal", "ShotOnPost", "BlockedShot", "AttemptSaved", "Attempt"}
        t_shots = t[t["type"].isin(SHOT_TYPES)]
        o_shots = o[o["type"].isin(SHOT_TYPES)]
        
        direction = h_dir if is_home else a_dir

        def in_box(x, y, team_dir):
            if team_dir == 1:
                return (x > 83) & (y > 21) & (y < 79)
            else:
                return (x < 17) & (y > 21) & (y < 79)

        def dist(row, team_dir):
            if pd.isna(row["x"]) or pd.isna(row["y"]): return 25.0
            target_x = 100 if team_dir == 1 else 0
            x_m = row["x"] * 1.05
            y_m = row["y"] * 0.68
            tx_m = target_x * 1.05
            return math.sqrt((tx_m - x_m)**2 + (34 - y_m)**2) * 1.09361

        # ── ATTACKING SCORE (14 METRICS) ──
        # Threat Gen
        prog_p = t_adv["progression"]["progressivePasses"]
        prog_c = t_adv["progression"]["progressiveCarries"]
        xg_est = len(t_shots) * 0.12 # Simple estimate
        corners = len(t[t["type"] == "Corner"])
        
        # Shooting
        box_shots = len(t_shots[in_box(t_shots["x"], t_shots["y"], direction)])
        sot = len(t_shots[t_shots["type"].isin({"Goal", "SavedShot"})])
        sot_pct = (sot / len(t_shots) * 100) if len(t_shots) > 0 else 0
        distances = t_shots.apply(lambda r: dist(r, direction), axis=1) if len(t_shots) else pd.Series([25.0])
        avg_dist = distances.mean()
        goals = len(t[t["type"] == "Goal"])
        
        # Penetration
        box_entries = len(t_succ_passes[~in_box(t_succ_passes["x"], t_succ_passes["y"], direction) & in_box(t_succ_passes["endX"], t_succ_passes["endY"], direction)])
        z14_entries = len(t_succ_passes[((t_succ_passes["x"] < 70) | (t_succ_passes["x"] > 83)) & (t_succ_passes["endX"] >= 70) & (t_succ_passes["endX"] <= 83) & (t_succ_passes["endY"] >= 30) & (t_succ_passes["endY"] <= 70)])
        box_touches = len(t[in_box(t["x"], t["y"], direction) & (t["type"] != "Pass")])
        deep_progs = len(t_succ_passes[(t_succ_passes["endX"] > 90) if direction == 1 else (t_succ_passes["endX"] < 10)])
        
        # Creativity
        kp = t_adv["creativity"]["keyPasses"]
        cross_acc = t_adv["creativity"]["crossingAccuracy"]

        # Weighted Category Scoring
        att_score = (
            min(prog_p/80, 1) * 7 + min(prog_c/60, 1) * 3 + min(xg_est/2.5, 1) * 5 + min(corners/10, 1) * 5 +
            min(box_shots/15, 1) * 10 + min(sot_pct/45, 1) * 5 + max(0, min((28-avg_dist)/15, 1)) * 5 + min(goals/3, 1) * 10 +
            min(box_entries/35, 1) * 15 + min(z14_entries/30, 1) * 5 + min(box_touches/45, 1) * 10 + min(deep_progs/20, 1) * 5 +
            min(kp/18, 1) * 10 + min(cross_acc/35, 1) * 5
        ) / 1.0 # 100 max

        # ── DEFENSIVE SCORE (14 METRICS) ──
        opp_prog = o_adv["progression"]["progressivePasses"] + o_adv["progression"]["progressiveCarries"]
        opp_box_ent = len(o_succ_passes[~in_box(o_succ_passes["x"], o_succ_passes["y"], a_dir if is_home else h_dir) & in_box(o_succ_passes["endX"], o_succ_passes["endY"], a_dir if is_home else h_dir)])
        
        opp_box_shots = len(o_shots[in_box(o_shots["x"], o_shots["y"], a_dir if is_home else h_dir)])
        opp_sot = len(o_shots[o_shots["type"].isin({"Goal", "SavedShot"})])
        opp_sot_pct = (opp_sot / len(o_shots) * 100) if len(o_shots) > 0 else 0
        opp_dist = o_shots.apply(lambda r: dist(r, a_dir if is_home else h_dir), axis=1).mean() if len(o_shots) else 25.0
        
        ppda = t_adv["pressing"]["ppda"]
        high_recov = t_adv["pressing"]["finalThirdRecoveries"]
        
        def_duels = t_adv["duels"]["dribbleSuccessPct"] # Surrogate for defending takeons
        aerial_pct = t_adv["duels"]["aerialWinPct"]
        tackles = len(t[t["type"] == "Tackle"])
        inters = len(t[t["type"] == "Interception"])
        clears = len(t[t["type"] == "Clearance"])
        blocks = len(t[t["type"] == "BlockedShot"])

        def_score = (
            max(0, 20 - (opp_prog * 0.12)) + max(0, 10 - (opp_box_ent * 0.25)) +
            max(0, 10 - (opp_box_shots * 0.5)) + max(0, 10 - (opp_sot_pct * 0.15)) + min(opp_dist/25, 1) * 10 +
            max(0, 10 - (ppda - 10) * 0.5) + min(high_recov/12, 1) * 10 +
            min(def_duels/70, 1) * 5 + min(aerial_pct/65, 1) * 5 +
            min(tackles/25, 1) * 3 + min(inters/15, 1) * 3 + min(clears/30, 1) * 2 + min(blocks/10, 1) * 2
        )

        # ── POSSESSION SCORE (14 METRICS) ──
        poss_pct = (len(t_passes) / (len(t_passes) + len(o_passes)) * 100) if (len(t_passes) + len(o_passes)) else 50
        field_tilt = t_adv["shape"]["fieldTilt"]
        pass_vol = len(t_passes)
        
        pass_acc = (len(t_succ_passes) / len(t_passes) * 100) if len(t_passes) else 0
        fwd_passes = t_passes[(t_passes["endX"] > t_passes["x"]) if direction == 1 else (t_passes["endX"] < t_passes["x"])]
        fwd_acc = (len(fwd_passes[fwd_passes["outcomeType"] == "Successful"]) / len(fwd_passes) * 100) if len(fwd_passes) else 0
        own_half = t_passes[(t_passes["x"] < 50) if direction == 1 else (t_passes["x"] > 50)]
        own_acc = (len(own_half[own_half["outcomeType"] == "Successful"]) / len(own_half) * 100) if len(own_half) else 0
        
        avg_seq = t_adv["possession"]["avgPassSequence"]
        buildup = t_adv["progression"]["buildUpRatio"]
        
        ft_passes = t_passes[(t_passes["x"] > 66) if direction == 1 else (t_passes["x"] < 33)]
        ft_acc = (len(ft_passes[ft_passes["outcomeType"] == "Successful"]) / len(ft_passes) * 100) if len(ft_passes) else 0
        
        recovs = len(t[t["type"] == "BallRecovery"])
        losses = len(t[(t["type"].isin({"Dispossessed", "Pass", "TakeOn"})) & (t["outcomeType"] == "Unsuccessful")])

        poss_score = (
            min(poss_pct/70, 1) * 15 + min(field_tilt/75, 1) * 15 + min(pass_vol/700, 1) * 5 +
            min(pass_acc/90, 1) * 10 + min(fwd_acc/80, 1) * 5 + min(own_acc/95, 1) * 5 +
            min(avg_seq/6, 1) * 10 + min(buildup/40, 1) * 10 +
            min(len(ft_passes)/250, 1) * 10 + min(ft_acc/80, 1) * 5 +
            min(recovs/60, 1) * 5 + max(0, 5 - (losses/40))
        )

        return {
            "attack": {
                "score": float(round(min(att_score, 100), 1)),
                "breakdown": {
                    "Threat Generation": float(round(prog_p/80 * 7 + prog_c/60 * 3 + corners/10 * 5, 1)),
                    "Shooting Score": float(round(box_shots/15 * 10 + sot_pct/45 * 5 + (28-avg_dist)/15 * 5, 1)),
                    "Penetration": float(round(box_entries/35 * 15 + z14_entries/30 * 5 + box_touches/45 * 10, 1)),
                    "Creativity": float(round(kp/18 * 10 + cross_acc/35 * 5, 1))
                },
                "stats": {
                    "Box Shots": int(box_shots),
                    "Box Entries": int(box_entries),
                    "Key Passes": int(kp),
                    "Dribble %": float(round(t_adv["duels"]["dribbleSuccessPct"], 1)),
                    "Box Touches": int(box_touches),
                    "Prog Actions": int(prog_p + prog_c)
                }
            },
            "defense": {
                "score": float(round(min(def_score, 100), 1)),
                "breakdown": {
                    "Suppression": float(round(max(0, 20-opp_prog*0.12) + max(0, 10-opp_box_ent*0.25), 1)),
                    "Shot Denial": float(round(max(0, 10-opp_box_shots*0.5) + max(0, 10-opp_sot_pct*0.15) + min(opp_dist/25, 1)*10, 1)),
                    "Pressing": float(round(max(0, 10-(ppda-10)*0.5) + min(high_recov/12, 1)*10, 1)),
                    "Solidity": float(round(min(def_duels/70, 1)*5 + min(aerial_pct/65, 1)*5 + min(tackles/25, 1)*3 + min(inters/15, 1)*3 + min(clears/30, 1)*2 + min(blocks/10, 1)*2, 1))
                },
                "stats": {
                    "PPDA": float(round(ppda, 2)),
                    "Opp Box Shots": int(opp_box_shots),
                    "High Recoveries": int(high_recov),
                    "Interceptions": int(inters),
                    "Tackle Win %": float(round(tackles*0.7, 1)) # Est
                }
            },
            "passing": {
                "score": float(round(min(poss_score, 100), 1)),
                "breakdown": {
                    "Control": float(round(min(poss_pct/70, 1)*15 + min(field_tilt/75, 1)*15, 1)),
                    "Efficiency": float(round(min(pass_acc/90, 1)*10 + min(fwd_acc/80, 1)*5, 1)),
                    "Sequence": float(round(min(avg_seq/6, 1)*10 + min(buildup/40, 1)*10, 1)),
                    "Field Dominance": float(round(min(len(ft_passes)/250, 1)*10 + min(ft_acc/80, 1)*5, 1))
                },
                "stats": {
                    "Possession %": float(round(poss_pct, 1)),
                    "Field Tilt %": float(round(field_tilt, 1)),
                    "Pass Accuracy %": float(round(pass_acc, 1)),
                    "Avg Sequence": float(round(avg_seq, 1)),
                    "Build-up Ratio": float(round(buildup, 1))
                }
            }
        }

    return {
        "homeTeam": home,
        "awayTeam": away,
        "homegradient": compute_team(home, away, True),
        "awaygradient": compute_team(away, home, False)
    }
