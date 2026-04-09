"""
Phase 1 Test Script
--------------------
Tests the Discovery Service by running all 4 search scenarios and printing results.
NOTE: Adds a 3-second delay between scenarios to avoid rate-limiting WhoScored.

Usage (from the backend directory, with .venv activated):
    python scripts/test_phase1.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.discovery_service import search_fixtures


def print_separator():
    print("\n" + "=" * 80 + "\n")


def print_fixtures(fixtures: list[dict], label: str):
    print(f"🔍 {label}")
    print(f"   Found {len(fixtures)} fixture(s):\n")
    if not fixtures:
        print("   ⚠️  No fixtures found for this query.")
    for i, f in enumerate(fixtures, 1):
        mc_status = "✅ MatchCentre" if f["has_matchcentre"] else "❌ No MatchCentre"
        print(f"   {i:>2}. {f['display_name']}")
        print(f"       URL: {f['whoscored_url']}")
        print(f"       Match ID: {f['match_id']} | {mc_status}")
        print(f"       Date: {f['date_str']} | Season: {f['season']} | Competition: {f['competition']}")
        print()


def test_scenario(label: str, **kwargs) -> list[dict]:
    print_separator()
    print(f"📋 {label}")
    print_separator()
    fixtures = search_fixtures(**kwargs)
    print_fixtures(fixtures, str(kwargs))
    return fixtures


if __name__ == "__main__":
    print("\n" + "🏟️  xG Match Analyzer - Phase 1 Test Suite".center(80))
    print("=" * 80)
    print("⚠️  Note: 3s delay between scenarios to avoid rate-limiting WhoScored.\n")

    all_results = {}

    # Scenario 1: Team only
    all_results["scenario_1"] = test_scenario(
        "SCENARIO 1: Team name only",
        team_name="Arsenal",
    )

    time.sleep(3)

    # Scenario 2: Team + Season
    all_results["scenario_2"] = test_scenario(
        "SCENARIO 2: Team name + Season",
        team_name="Arsenal",
        season="2025/2026",
    )

    time.sleep(3)

    # Scenario 3: Team + Competition
    all_results["scenario_3"] = test_scenario(
        "SCENARIO 3: Team name + Competition",
        team_name="Arsenal",
        competition="Premier League",
    )

    time.sleep(3)

    # Scenario 4: All filters
    all_results["scenario_4"] = test_scenario(
        "SCENARIO 4: Team name + Season + Competition (strict)",
        team_name="Arsenal",
        season="2025/2026",
        competition="Premier League",
    )

    time.sleep(3)

    # Bonus: Different team
    all_results["bonus"] = test_scenario(
        "BONUS: Different team (Real Madrid)",
        team_name="Real Madrid",
    )

    # Summary
    print_separator()
    print("📊 SUMMARY")
    print_separator()
    for key, fixtures in all_results.items():
        count = len(fixtures)
        mc_count = sum(1 for f in fixtures if f["has_matchcentre"])
        print(f"   {key}: {count} fixtures found ({mc_count} with MatchCentre data)")

    print("\n✅ Phase 1 test complete.\n")
