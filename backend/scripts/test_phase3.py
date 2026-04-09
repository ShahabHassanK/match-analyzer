"""
test_phase3.py
==============
Validates every match_analyzer function against the Arsenal vs Liverpool CSV.
Run: python scripts/test_phase3.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.match_analyzer import (
    get_match_summary,
    get_starting_xi,
    get_shot_map,
    get_pass_network,
    get_ppda,
    get_territory_heatmap,
    get_xT_momentum,
    get_defensive_actions,
    get_zone_entries,
    get_passing_combinations,
    get_player_actions,
    get_player_heatmap,
    get_player_pass_sonar,
)

CSV = os.path.join(os.path.dirname(__file__), "..", "data", "whoscored_Arsenal_vs_Liverpool_all_events.csv")

PASS_COUNT = 0
FAIL_COUNT = 0


def check(name, condition, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"  [PASS] {name}")
    else:
        FAIL_COUNT += 1
        print(f"  [FAIL] {name} -- {detail}")


def test_match_summary():
    print("\n--- 1. Match Summary ---")
    result = get_match_summary(CSV)
    check("Has homeTeam", result["homeTeam"] == "Arsenal")
    check("Has awayTeam", result["awayTeam"] == "Liverpool")
    check("Home shots > 0", result["homeStats"]["shots"] > 0, f"got {result['homeStats']['shots']}")
    check("Away shots > 0", result["awayStats"]["shots"] > 0, f"got {result['awayStats']['shots']}")
    check("Possession sums ~100", abs(result["homeStats"]["possession"] + result["awayStats"]["possession"] - 100) < 1)
    print(f"  Score: Arsenal {result['homeStats']['goals']} - {result['awayStats']['goals']} Liverpool")
    print(f"  Shots: {result['homeStats']['shots']} - {result['awayStats']['shots']}")
    print(f"  Possession: {result['homeStats']['possession']}% - {result['awayStats']['possession']}%")


def test_starting_xi():
    print("\n--- 2. Starting XI ---")
    result = get_starting_xi(CSV)
    check("Home XI has players", len(result["homeXI"]) >= 11, f"got {len(result['homeXI'])}")
    check("Away XI has players", len(result["awayXI"]) >= 11, f"got {len(result['awayXI'])}")
    print(f"  Arsenal XI ({len(result['homeXI'])}): {', '.join(result['homeXI'][:5])}...")
    print(f"  Liverpool XI ({len(result['awayXI'])}): {', '.join(result['awayXI'][:5])}...")


def test_shot_map():
    print("\n--- 3. Shot Map ---")
    result = get_shot_map(CSV)
    shots = result["shots"]
    check("Has shots", len(shots) > 0, f"got {len(shots)}")
    outcomes = set(s["outcome"] for s in shots)
    check("Has multiple outcome types", len(outcomes) >= 2, f"got {outcomes}")
    for s in shots[:3]:
        print(f"  [{s['minute']}'] {s['player']:20s} | {s['team']:10s} | {s['outcome']:10s} | ({s['x']}, {s['y']})")


def test_pass_network():
    print("\n--- 4. Pass Network ---")
    result = get_pass_network(CSV)
    for team_name, net in result["networks"].items():
        check(f"{team_name} has nodes", len(net["nodes"]) > 0, f"got {len(net['nodes'])}")
        check(f"{team_name} has edges", len(net["edges"]) > 0, f"got {len(net['edges'])}")
        top_edge = net["edges"][0] if net["edges"] else {}
        print(f"  {team_name}: {len(net['nodes'])} nodes, {len(net['edges'])} edges. Top: {top_edge.get('from','')} -> {top_edge.get('to','')} ({top_edge.get('count',0)})")


def test_ppda():
    print("\n--- 5. PPDA ---")
    result = get_ppda(CSV)
    check("Home PPDA > 0", result["home"]["overall"] > 0, f"got {result['home']['overall']}")
    check("Away PPDA > 0", result["away"]["overall"] > 0, f"got {result['away']['overall']}")
    print(f"  Arsenal PPDA: {result['home']['overall']} (1H: {result['home']['firstHalf']}, 2H: {result['home']['secondHalf']})")
    print(f"  Liverpool PPDA: {result['away']['overall']} (1H: {result['away']['firstHalf']}, 2H: {result['away']['secondHalf']})")


def test_territory():
    print("\n--- 6. Territory Heatmap ---")
    result = get_territory_heatmap(CSV)
    check("Grid is 12x12", len(result["home"]) == 12 and len(result["home"][0]) == 12)
    check("Values normalised 0-1", max(max(row) for row in result["home"]) <= 1.0)
    print(f"  Grid size: {result['gridSize']}x{result['gridSize']}")


def test_momentum():
    print("\n--- 7. xT Momentum ---")
    result = get_xT_momentum(CSV)
    timeline = result["timeline"]
    check("Timeline has entries", len(timeline) > 0, f"got {len(timeline)}")
    check("Covers 90+ minutes", timeline[-1]["minute"] >= 90, f"last minute: {timeline[-1]['minute']}")
    # Find peak dominance
    peak = max(timeline, key=lambda t: abs(t["difference"]))
    print(f"  Timeline: {len(timeline)} minutes. Peak dominance at minute {peak['minute']}: {peak['difference']:.4f}")


def test_defensive_actions():
    print("\n--- 8. Defensive Actions ---")
    result = get_defensive_actions(CSV)
    check("Home has actions", len(result["home"]) > 0, f"got {len(result['home'])}")
    check("Away has actions", len(result["away"]) > 0, f"got {len(result['away'])}")
    print(f"  Arsenal: {len(result['home'])} defensive actions")
    print(f"  Liverpool: {len(result['away'])} defensive actions")


def test_zone_entries():
    print("\n--- 9. Zone Entries ---")
    result = get_zone_entries(CSV)
    check("Home has FT entries", result["home"]["finalThirdCount"] > 0)
    check("Away has FT entries", result["away"]["finalThirdCount"] > 0)
    print(f"  Arsenal: {result['home']['finalThirdCount']} final third, {result['home']['zone14Count']} Zone 14")
    print(f"  Liverpool: {result['away']['finalThirdCount']} final third, {result['away']['zone14Count']} Zone 14")


def test_passing_combos():
    print("\n--- 10. Passing Combinations ---")
    result = get_passing_combinations(CSV)
    check("Home has combos", len(result["home"]) > 0)
    check("Away has combos", len(result["away"]) > 0)
    for combo in result["home"][:3]:
        print(f"  Arsenal: {combo['from']} -> {combo['to']} ({combo['count']})")


def test_player_actions():
    print("\n--- 11. Player Actions ---")
    result = get_player_actions(CSV, "Bukayo Saka")
    check("Found Saka actions", result["count"] > 0, f"got {result['count']}")
    print(f"  Saka total actions: {result['count']}")

    passes = get_player_actions(CSV, "Bukayo Saka", "pass")
    print(f"  Saka passes: {passes['count']}")

    shots = get_player_actions(CSV, "Bukayo Saka", "shot")
    print(f"  Saka shots: {shots['count']}")


def test_player_heatmap():
    print("\n--- 12. Player Heatmap ---")
    result = get_player_heatmap(CSV, "Bukayo Saka")
    check("Has heatmap grid", len(result["heatmap"]) == 12)
    check("Has touches", result["totalTouches"] > 0, f"got {result['totalTouches']}")
    print(f"  Saka: {result['totalTouches']} touches")


def test_player_pass_sonar():
    print("\n--- 13. Player Pass Sonar ---")
    result = get_player_pass_sonar(CSV, "Bukayo Saka")
    check("Has 16 bins", len(result["bins"]) == 16)
    check("Has passes", result["totalPasses"] > 0, f"got {result['totalPasses']}")
    top_bin = max(result["bins"], key=lambda b: b["count"])
    print(f"  Saka: {result['totalPasses']} passes. Dominant direction: {top_bin['angle']} deg ({top_bin['count']} passes)")


# ─── Run All ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  PHASE 3 - MATCH ANALYZER VALIDATION")
    print("=" * 60)

    test_match_summary()
    test_starting_xi()
    test_shot_map()
    test_pass_network()
    test_ppda()
    test_territory()
    test_momentum()
    test_defensive_actions()
    test_zone_entries()
    test_passing_combos()
    test_player_actions()
    test_player_heatmap()
    test_player_pass_sonar()

    print("\n" + "=" * 60)
    print(f"  RESULTS: {PASS_COUNT} passed, {FAIL_COUNT} failed")
    print("=" * 60)
