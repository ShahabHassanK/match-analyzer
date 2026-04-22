"""explain_service.py — per-feature contextual AI explanations via Groq."""

import json
import asyncio
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
import os

from services.match_analyzer import (
    get_match_summary,
    get_shot_map,
    get_pass_network,
    get_ppda,
    get_xT_momentum,
    get_defensive_actions,
    get_zone_entries,
    get_set_piece_analysis,
)
from services.gradient_scoring import get_gradient_scoring

load_dotenv(Path(__file__).parent.parent / ".env")
_GROQ_API_KEY = os.getenv("GROQ_API_KEY")
_MODEL = "llama-3.3-70b-versatile"


def _build_prompt(feature: str, csv_path: str) -> str:
    summary = get_match_summary(csv_path)
    home = summary["homeTeam"]
    away = summary["awayTeam"]
    hs = summary["homeStats"]
    aws = summary["awayStats"]
    score = f"{home} {hs['goals']} - {aws['goals']} {away}"

    # ── Shot Map ──────────────────────────────────────────────────────────────
    if feature == "shots":
        shots_data = get_shot_map(csv_path)
        all_shots = shots_data["shots"]

        h_shots = [s for s in all_shots if s["team"] == home]
        a_shots = [s for s in all_shots if s["team"] == away]

        h_goals   = [s for s in h_shots if s["outcome"] == "goal"]
        h_on_tgt  = [s for s in h_shots if s["outcome"] == "on_target"]
        h_bc      = [s for s in h_shots if s["isBigChance"]]
        h_in_box  = [s for s in h_shots if s["x"] >= 83]
        h_scorers = list(dict.fromkeys(s["player"] for s in h_goals))

        a_goals   = [s for s in a_shots if s["outcome"] == "goal"]
        a_on_tgt  = [s for s in a_shots if s["outcome"] == "on_target"]
        a_bc      = [s for s in a_shots if s["isBigChance"]]
        a_in_box  = [s for s in a_shots if s["x"] >= 83]
        a_scorers = list(dict.fromkeys(s["player"] for s in a_goals))

        return f"""Football analyst. Explain this shot map in 2 paragraphs, around 130 words total.

§1 (2 sentences): Each dot is a shot plotted at the location it was taken — colour shows outcome (green=goal, amber=saved/on target, grey=missed or blocked) and larger dots indicate bigger chances. The closer to goal and more central the cluster, the better the quality of chances created.

§2 (4-5 sentences): Analyse {score} using the data below. Who created more danger and from better areas? Were the big chances taken? Name the scorers and flag anything surprising about the shot locations or volume.

{home}: {len(h_shots)} shots, {len(h_on_tgt)} on target, {len(h_goals)} goals, {len(h_bc)} big chances, {len(h_in_box)} in box. Scorers: {', '.join(h_scorers) or 'none'}
{away}: {len(a_shots)} shots, {len(a_on_tgt)} on target, {len(a_goals)} goals, {len(a_bc)} big chances, {len(a_in_box)} in box. Scorers: {', '.join(a_scorers) or 'none'}"""

    # ── Pass Network ──────────────────────────────────────────────────────────
    elif feature == "passNetwork":
        pn = get_pass_network(csv_path)
        networks = pn["networks"]

        def _summarise_network(team):
            net = networks.get(team, {})
            nodes = sorted(net.get("nodes", []), key=lambda n: n["passCount"], reverse=True)
            edges = sorted(net.get("edges", []), key=lambda e: e["count"], reverse=True)
            key_players = [n["player"] for n in nodes[:4]]
            top_connections = [f"{e['from']} → {e['to']} ({e['count']})" for e in edges[:3]]
            return key_players, top_connections

        h_players, h_connections = _summarise_network(home)
        a_players, a_connections = _summarise_network(away)

        return f"""Football analyst. Explain this pass network in 2 paragraphs, around 130 words total.

§1 (2 sentences): Each node represents a player — its size reflects pass involvement and its position shows where they typically operated on the pitch. Lines between players show how often they combined, with thicker lines meaning a stronger partnership; the overall shape reveals whether a team built through the middle, used wide outlets, or relied on one key connector.

§2 (4-5 sentences): Analyse {score} using the data below. Who were the central figures in each team's build-up? Were the busiest connections central or wide? What does the network structure tell us about each team's style?

{home}: Key players — {'; '.join(h_players) or 'none'} | Top links — {'; '.join(h_connections) or 'none'}
{away}: Key players — {'; '.join(a_players) or 'none'} | Top links — {'; '.join(a_connections) or 'none'}"""

    # ── Match Momentum ────────────────────────────────────────────────────────
    elif feature == "momentum":
        mom = get_xT_momentum(csv_path)
        timeline = mom.get("timeline", [])
        top_players = mom.get("topPlayers", [])

        home_total = round(timeline[-1]["homeCumXt"], 2) if timeline else 0
        away_total = round(timeline[-1]["awayCumXt"], 2) if timeline else 0

        # Find the minute where the leader changed (biggest swing)
        peak_home_lead = 0
        peak_away_lead = 0
        for t in timeline:
            diff = t["difference"]
            if diff > peak_home_lead:
                peak_home_lead = diff
            if diff < peak_away_lead:
                peak_away_lead = diff

        top_str = "; ".join(f"{p['name']} ({p['xT']} xT)" for p in top_players[:3]) or "none"

        return f"""Football analyst. Explain this match momentum chart in 2 paragraphs, around 130 words total.

§1 (2 sentences): xT (Expected Threat) assigns a danger score to every pass and carry based on how much it improved the team's chance of scoring — it captures threatening intent, not just end results. The chart plots the running xT difference minute-by-minute: when the line rises {home} were dominating, when it falls {away} were; sharp swings mark when control shifted.

§2 (4-5 sentences): Analyse {score} using the data below. Who generated more threat overall? When were the key momentum shifts? Do the xT totals align with the result or tell a different story? Name the top creators.

{home} total xT: {home_total} | {away} total xT: {away_total}
Peak {home} lead: {round(peak_home_lead, 2)} | Peak {away} lead: {round(abs(peak_away_lead), 2)}
Top creators: {top_str}"""

    # ── Defensive Actions ─────────────────────────────────────────────────────
    elif feature == "defensive":
        ppda = get_ppda(csv_path)
        da = get_defensive_actions(csv_path)

        h_actions = da.get("home", [])
        a_actions = da.get("away", [])

        h_total      = len(h_actions)
        h_high_press = len([a for a in h_actions if a.get("x", 0) > 50])
        a_total      = len(a_actions)
        a_high_press = len([a for a in a_actions if a.get("x", 0) > 50])

        h_ppda = ppda["home"]
        a_ppda = ppda["away"]

        return f"""Football analyst. Explain this defensive actions map in 2 paragraphs, around 130 words total.

§1 (2 sentences): Each dot is a defensive action — tackle, interception, foul, or ball recovery — plotted at the exact location it occurred on the pitch; clusters high up the field mean a high press, clusters deep mean a low block or reactive defending. PPDA (Passes Allowed Per Defensive Action) quantifies pressing intensity: a lower number means the team pressed earlier and more aggressively, giving the opponent fewer passes before winning the ball back.

§2 (4-5 sentences): Analyse {score} using the data below. Which team pressed more and where on the pitch? Did either team change their defensive approach between halves? What do the raw action counts tell us?

PPDA — {home}: {h_ppda['overall']} overall (H1: {h_ppda['firstHalf']}, H2: {h_ppda['secondHalf']}) | {away}: {a_ppda['overall']} overall (H1: {a_ppda['firstHalf']}, H2: {a_ppda['secondHalf']})
Actions — {home}: {h_total} total, {h_high_press} in opp. half | {away}: {a_total} total, {a_high_press} in opp. half
Tackles: {home} {hs['tackles']} | {away} {aws['tackles']} | Interceptions: {home} {hs['interceptions']} | {away} {aws['interceptions']}"""

    # ── Creative Play / Zone Entries ──────────────────────────────────────────
    elif feature == "zoneEntries":
        ze = get_zone_entries(csv_path)
        h = ze["home"]
        a = ze["away"]

        return f"""Football analyst. Explain this creative play / zone entries map in 2 paragraphs, around 130 words total.

§1 (2 sentences): Arrows show successful passes and carries that moved the ball into dangerous territory — the final third (attacking 33% of the pitch), Zone 14 (the central channel just outside the penalty box, the most creative space in football), and direct box entries. More entries, especially into Zone 14 and the box, indicate sustained attacking intent rather than just possession.

§2 (4-5 sentences): Analyse {score} using the data below. Which team penetrated more effectively and through which zones? Did one team dominate box access? Were through balls a feature? Does the volume of entries match the actual goalscoring output?

{home}: final third {h.get('finalThirdCount', 0)}, Zone 14 {h.get('zone14Count', 0)}, through balls {h.get('throughBallCount', 0)}, box entries {h.get('boxCount', 0)}, box touches {h.get('boxTouchesCount', 0)}
{away}: final third {a.get('finalThirdCount', 0)}, Zone 14 {a.get('zone14Count', 0)}, through balls {a.get('throughBallCount', 0)}, box entries {a.get('boxCount', 0)}, box touches {a.get('boxTouchesCount', 0)}"""

    # ── Set Pieces ────────────────────────────────────────────────────────────
    elif feature == "setPieces":
        sp = get_set_piece_analysis(csv_path)
        hs_sp  = sp["home"]["summary"]
        aws_sp = sp["away"]["summary"]

        return f"""Football analyst. Explain this set pieces analysis panel in 2 paragraphs, around 130 words total.

§1 (2 sentences): Delivery arrows show where each corner and free kick was played from and where it landed — stats track first contact won (an indicator of delivery quality and aerial dominance), how many deliveries created a shot, and whether any directly led to a goal. Set pieces account for roughly 30% of goals in top-level football, so understanding which team used them better often explains a result.

§2 (4-5 sentences): Analyse {score} using the data below. Were set pieces a significant factor? Which team won more and used them more dangerously? Did aerial dominance (first contact %) match the expected threat? Any set piece goals?

{home}: {hs_sp.get('totalCorners', 0)} corners ({hs_sp.get('cornerLedToShot', 0)} → shot, {hs_sp.get('cornerFirstContactPct', 0)}% 1st contact), {hs_sp.get('totalFreeKicks', 0)} FKs ({hs_sp.get('fkLedToShot', 0)} → shot), {hs_sp.get('ledToGoal', 0)} goals from set pieces
{away}: {aws_sp.get('totalCorners', 0)} corners ({aws_sp.get('cornerLedToShot', 0)} → shot, {aws_sp.get('cornerFirstContactPct', 0)}% 1st contact), {aws_sp.get('totalFreeKicks', 0)} FKs ({aws_sp.get('fkLedToShot', 0)} → shot), {aws_sp.get('ledToGoal', 0)} goals from set pieces"""

    # ── Tactical Shape ────────────────────────────────────────────────────────
    elif feature == "averageShape":
        return f"""Football analyst. Explain this tactical shape / average positions visualization in 2 paragraphs, around 130 words total.

§1 (2 sentences): Each dot represents a player plotted at the average position they occupied with the ball during the match — the overall pattern reveals the team's in-possession formation, how high or deep the defensive line sat, whether wingers stayed wide or tucked in, and how compact or stretched the team's shape was. It's a snapshot of the tactical blueprint each manager set up, filtered to on-ball moments only.

§2 (4-5 sentences): Using {score} as context, guide the viewer on what to look for in this specific match. Does the possession dominance show in the shape? Where do the two formations differ most? What should the viewer specifically look at when comparing the two teams' dots?

{home}: {hs['possession']}% possession, {hs['totalPasses']} passes, {hs['passAccuracy']}% accuracy
{away}: {aws['possession']}% possession, {aws['totalPasses']} passes, {aws['passAccuracy']}% accuracy"""

    # ── Gradient Scoring ──────────────────────────────────────────────────────
    elif feature == "gradientScoring":
        gs = get_gradient_scoring(csv_path)
        hg = gs.get("homegradient", {})
        ag = gs.get("awaygradient", {})
        h_atk = hg.get("attack", {})
        h_def = hg.get("defense", {})
        h_pos = hg.get("passing", {})
        a_atk = ag.get("attack", {})
        a_def = ag.get("defense", {})
        a_pos = ag.get("passing", {})

        h_atk_bd = h_atk.get("breakdown", {})
        a_atk_bd = a_atk.get("breakdown", {})
        h_def_bd = h_def.get("breakdown", {})
        a_def_bd = a_def.get("breakdown", {})
        h_pos_bd = h_pos.get("breakdown", {})
        a_pos_bd = a_pos.get("breakdown", {})

        return f"""Football analyst. Explain this gradient scoring breakdown in 2 paragraphs, around 130 words total.

§1 (2 sentences): Explain what gradient scoring is — a model scoring each team across 42 variables in 3 areas (attack, defense, possession) out of 100. Each area has sub-scores revealing where a team specifically excelled or struggled.

§2 (4-5 sentences): Analyse {score} using the scores below. Which team performed better overall and in which areas? Do the scores align with the result or suggest it flattered/flattered the wrong team? Mention the most interesting sub-score gap.

{home} — Attack: {h_atk.get('score',0)}/100 {h_atk_bd} | Defense: {h_def.get('score',0)}/100 {h_def_bd} | Possession: {h_pos.get('score',0)}/100 {h_pos_bd}
{away} — Attack: {a_atk.get('score',0)}/100 {a_atk_bd} | Defense: {a_def.get('score',0)}/100 {a_def_bd} | Possession: {a_pos.get('score',0)}/100 {a_pos_bd}"""

    # ── Advanced Metrics ──────────────────────────────────────────────────────
    elif feature == "advancedMetrics":
        ppda = get_ppda(csv_path)
        h_ppda = ppda["home"]
        a_ppda = ppda["away"]

        return f"""Football analyst. Explain this advanced metrics panel in 2 paragraphs, around 130 words total.

§1 (2 sentences): Advanced metrics go beyond goals and shots — they cover pressing intensity (PPDA: lower = more aggressive, higher = more passive), passing quality and volume, defensive output, and big chance creation to reveal how each team actually played rather than just what ended up on the scoresheet. Together they paint a fuller picture of tactical dominance and efficiency.

§2 (4-5 sentences): Analyse {score} using the data below. Pick the 2-3 most telling numbers and explain what they reveal. Which team controlled the game on these deeper metrics? Does it align with the result or suggest the scoreline flattered one side?

Possession: {home} {hs['possession']}% | {away} {aws['possession']}%
Pass accuracy: {home} {hs['passAccuracy']}% | {away} {aws['passAccuracy']}%
PPDA (lower = more intense press): {home} {h_ppda['overall']} | {away} {a_ppda['overall']}
Tackles: {home} {hs['tackles']} | {away} {aws['tackles']} | Interceptions: {home} {hs['interceptions']} | {away} {aws['interceptions']}
Big chances: {home} {hs['bigChances']} | {away} {aws['bigChances']}"""

    else:
        return f"In about 100 words, explain what '{feature}' means in football analytics. Keep it plain and engaging."


async def stream_explanation(csv_path: str, feature: str) -> AsyncGenerator[str, None]:
    from groq import AsyncGroq

    if not _GROQ_API_KEY:
        yield f"data: {json.dumps({'type': 'error', 'message': 'GROQ_API_KEY not configured in backend/.env'})}\n\n"
        return

    try:
        prompt = _build_prompt(feature, csv_path)
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': f'Could not load match data: {str(e)}'})}\n\n"
        return

    client = AsyncGroq(api_key=_GROQ_API_KEY)
    try:
        stream = await client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=320,
            temperature=0.6,
            stream=True,
        )
        async for chunk in stream:
            text = chunk.choices[0].delta.content
            if text:
                yield f"data: {json.dumps({'type': 'chunk', 'text': text})}\n\n"
                await asyncio.sleep(0)
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        return

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
