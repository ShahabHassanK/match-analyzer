import pandas as pd
from services.match_analyzer import get_goal_build_ups, _load_match
import glob
csvs = glob.glob("data/*.csv")
if not csvs:
    print("No CSVs found")
else:
    csv_path = sorted(csvs, key=lambda x: x)[-1]
    print("Testing on", csv_path)
    df = _load_match(csv_path)
    goals = df[df["type"] == "Goal"]
    print("Total goals in match:", len(goals))
    for _, g in goals.iterrows():
        print("  Goal at minute:", g.get('match_minute', '?'), "by", g.get('playerName', 'Unknown'), "x:", g.get("x"), "y:", g.get("y"))
    res = get_goal_build_ups(csv_path)
    print("Sequences returned:", len(res["sequences"]))
    for seq in res["sequences"]:
        print("Sequence goal:", seq["scorer"], "minute:", seq["minute"], "len:", len(seq["events"]))
