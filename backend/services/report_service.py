"""
report_service.py
=================
AI match report generation using Google Gemini.

Aggregates all match data, generates pitch visualizations with mplsoccer,
streams a professional analyst report via SSE, and caches to disk.
"""

import io
import json
import base64
import asyncio
from pathlib import Path
from typing import AsyncGenerator

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from mplsoccer import VerticalPitch, Pitch

from dotenv import load_dotenv
import os

from services.match_analyzer import (
    get_match_summary,
    get_starting_xi,
    get_shot_map,
    get_pass_network,
    get_ppda,
    get_average_shape,
    get_xT_momentum,
    get_defensive_actions,
    get_zone_entries,
    get_set_piece_analysis,
    get_goal_build_ups,
)
from services.gradient_scoring import get_gradient_scoring

# ── Constants ──────────────────────────────────────────────────────────────────

HOME_COLOR = "#38bdf8"
AWAY_COLOR = "#f87171"
GOAL_COLOR = "#00f485"
PITCH_BG = "#0d1117"

REPORTS_DIR = Path(__file__).parent.parent / "data" / "reports"

load_dotenv(Path(__file__).parent.parent / ".env")
_GROQ_API_KEY = os.getenv("GROQ_API_KEY")


# ── Cache ─────────────────────────────────────────────────────────────────────

def get_cache_path(csv_path: str) -> Path:
    return REPORTS_DIR / f"{Path(csv_path).stem}_report.json"


def load_cached_report(csv_path: str) -> dict | None:
    cache_path = get_cache_path(csv_path)
    if not cache_path.exists():
        return None
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_report_cache(csv_path: str, report_text: str, images: dict):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = get_cache_path(csv_path)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({"reportText": report_text, "images": images}, f)


# ── Image Helpers ─────────────────────────────────────────────────────────────

def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=PITCH_BG, edgecolor="none")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ── Shot Map ──────────────────────────────────────────────────────────────────

def generate_shot_map_image(csv_path: str) -> str:
    data = get_shot_map(csv_path)
    home = data["homeTeam"]
    away = data["awayTeam"]
    shots = data["shots"]

    home_shots = [s for s in shots if s["team"] == home]
    away_shots = [s for s in shots if s["team"] == away]

    pitch = VerticalPitch(
        pitch_type="opta",
        half=True,
        pitch_color=PITCH_BG,
        line_color="#ffffff25",
        linewidth=1,
    )
    fig, axes = pitch.draw(figsize=(14, 8), nrows=1, ncols=2)
    fig.patch.set_facecolor(PITCH_BG)

    OUTCOME_STYLES = {
        "goal":      {"color": GOAL_COLOR,   "alpha": 1.0, "edge": "#ffffff", "zorder": 6},
        "on_target": {"color": HOME_COLOR,   "alpha": 0.75, "edge": "none",   "zorder": 5},
        "off_target": {"color": "#ffffff",   "alpha": 0.3, "edge": "none",   "zorder": 4},
    }

    def _plot_shots(ax, shots_list, flip_x: bool):
        for s in shots_list:
            x = (100 - s["x"]) if flip_x else s["x"]
            y = s["y"]
            size = 250 if s["isBigChance"] else 90
            style = OUTCOME_STYLES.get(s["outcome"], OUTCOME_STYLES["off_target"])
            pitch.scatter(
                x, y, ax=ax,
                s=size, c=style["color"], alpha=style["alpha"],
                edgecolors=style["edge"], linewidths=1.5, zorder=style["zorder"],
            )

    _plot_shots(axes[0], home_shots, flip_x=False)
    _plot_shots(axes[1], away_shots, flip_x=True)

    axes[0].set_title(home, color="white", fontsize=12, fontweight="bold", pad=8)
    axes[1].set_title(away, color="white", fontsize=12, fontweight="bold", pad=8)

    legend_handles = [
        mpatches.Patch(color=GOAL_COLOR, label="Goal"),
        mpatches.Patch(color=HOME_COLOR, label="On Target"),
        mpatches.Patch(color="#ffffff50", label="Off Target"),
    ]
    fig.legend(handles=legend_handles, loc="lower center", ncol=3,
               frameon=False, fontsize=9, labelcolor="white")
    fig.suptitle("Shot Map", color="white", fontsize=14, fontweight="bold", y=1.02)

    return _fig_to_base64(fig)


# ── Pass Network ──────────────────────────────────────────────────────────────

def generate_pass_network_image(csv_path: str, team_name: str, is_home: bool) -> str:
    data = get_pass_network(csv_path)
    network = data["networks"].get(team_name, {})
    nodes = network.get("nodes", [])
    edges = network.get("edges", [])

    pitch = Pitch(
        pitch_type="opta",
        pitch_color=PITCH_BG,
        line_color="#ffffff25",
        linewidth=1,
    )
    fig, ax = pitch.draw(figsize=(12, 8))
    fig.patch.set_facecolor(PITCH_BG)

    color = HOME_COLOR if is_home else AWAY_COLOR

    pos = {n["player"]: (n["avgX"], n["avgY"]) for n in nodes}
    if not is_home:
        pos = {p: (100 - x, y) for p, (x, y) in pos.items()}

    max_count = max((e["count"] for e in edges), default=1)
    for edge in edges:
        if edge["from"] not in pos or edge["to"] not in pos:
            continue
        x1, y1 = pos[edge["from"]]
        x2, y2 = pos[edge["to"]]
        lw = 0.5 + (edge["count"] / max_count) * 5
        ax.plot([x1, x2], [y1, y2], color=color, alpha=0.35, linewidth=lw, zorder=2)

    max_passes = max((n["passCount"] for n in nodes), default=1)
    for node in nodes:
        player = node["player"]
        if player not in pos:
            continue
        x, y = pos[player]
        size = 80 + (node["passCount"] / max_passes) * 450
        ax.scatter(x, y, s=size, c=color, alpha=0.9,
                   edgecolors="white", linewidths=1.2, zorder=4)
        label = player.split()[-1][:9]
        ax.text(x, y - 5, label, color="white", fontsize=6.5,
                ha="center", va="top", zorder=5,
                bbox=dict(boxstyle="round,pad=0.1", facecolor="#00000050", edgecolor="none"))

    ax.set_title(f"{team_name} — Pass Network", color="white",
                 fontsize=13, fontweight="bold")
    return _fig_to_base64(fig)


# ── Momentum Chart ────────────────────────────────────────────────────────────

def generate_momentum_image(csv_path: str) -> str:
    data = get_xT_momentum(csv_path)
    home = data["homeTeam"]
    away = data["awayTeam"]
    timeline = data["timeline"]

    minutes = np.array([t["minute"] for t in timeline])
    diff = np.array([t["difference"] for t in timeline])

    fig, ax = plt.subplots(figsize=(14, 5))
    fig.patch.set_facecolor(PITCH_BG)
    ax.set_facecolor(PITCH_BG)

    ax.fill_between(minutes, diff, 0,
                    where=(diff >= 0), interpolate=True,
                    color=HOME_COLOR, alpha=0.55, label=home)
    ax.fill_between(minutes, diff, 0,
                    where=(diff < 0), interpolate=True,
                    color=AWAY_COLOR, alpha=0.55, label=away)
    ax.plot(minutes, diff, color="white", linewidth=0.8, alpha=0.5)
    ax.axhline(0, color="#ffffff35", linewidth=0.8)

    if len(minutes) > 0:
        ax.axvline(45, color="#ffffff25", linewidth=1, linestyle="--")
        ylim = ax.get_ylim()
        ax.text(46, ylim[1] * 0.85, "HT", color="#ffffff50", fontsize=8)

    ax.set_xlabel("Minute", color="white", fontsize=10)
    ax.set_ylabel("Cumulative xT Difference (Home − Away)", color="white", fontsize=10)
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#ffffff20")
    ax.legend(frameon=False, fontsize=9, labelcolor="white", loc="upper left")
    ax.set_title("xT Momentum Timeline", color="white", fontsize=13, fontweight="bold")

    return _fig_to_base64(fig)


# ── Combined Image Generation ─────────────────────────────────────────────────

def generate_pitch_images(csv_path: str) -> dict:
    shot_data = get_shot_map(csv_path)
    home = shot_data["homeTeam"]
    away = shot_data["awayTeam"]
    return {
        "shotMap": generate_shot_map_image(csv_path),
        "passNetworkHome": generate_pass_network_image(csv_path, home, is_home=True),
        "passNetworkAway": generate_pass_network_image(csv_path, away, is_home=False),
        "momentum": generate_momentum_image(csv_path),
    }


# ── Data Aggregation ──────────────────────────────────────────────────────────

def _shots_summary(shots: list, team: str) -> dict:
    ts = [s for s in shots if s["team"] == team]
    goals = [s for s in ts if s["outcome"] == "goal"]
    origins: dict[str, int] = {}
    for s in ts:
        o = s.get("origin", "Open Play")
        origins[o] = origins.get(o, 0) + 1
    return {
        "total": len(ts),
        "goals": len(goals),
        "on_target": len([s for s in ts if s["outcome"] == "on_target"]),
        "off_target": len([s for s in ts if s["outcome"] == "off_target"]),
        "big_chances": len([s for s in ts if s["isBigChance"]]),
        "in_box": len([s for s in ts if s["x"] > 83 and 21 < s["y"] < 79]),
        "six_yard": len([s for s in ts if s["x"] > 94]),
        "outside_box": len([s for s in ts if s["x"] <= 83]),
        "origins": origins,
        "scorers": [f"{s['player']} ({s['minute']}')" for s in goals],
    }


def _momentum_phases(timeline: list) -> str:
    phases = []
    current = None
    streak = 0
    start_min = 0
    for point in timeline:
        dom = "home" if point["difference"] > 0.05 else (
            "away" if point["difference"] < -0.05 else "neutral"
        )
        if dom == current:
            streak += 1
        else:
            if current and current != "neutral" and streak >= 5:
                phases.append(f"{current.capitalize()} controlled mins {start_min}–{point['minute']} ({streak} min)")
            current = dom
            streak = 1
            start_min = point["minute"]
    return "; ".join(phases[:5]) if phases else "Closely contested throughout"


def _goal_narratives(sequences: list) -> str:
    if not sequences:
        return "No goals recorded in this match."
    lines = []
    for seq in sequences:
        lines.append(f"Goal — {seq['scorer']} ({seq['team']}, {seq['minute']}')")
        for e in seq["events"]:
            lines.append(f"  {e['minute']}' {e['player']}: {e['type']} ({e['outcome']})")
        lines.append("")
    return "\n".join(lines)


def aggregate_match_data(csv_path: str) -> dict:
    summary = get_match_summary(csv_path)
    xi = get_starting_xi(csv_path)
    shots_raw = get_shot_map(csv_path)
    pass_net = get_pass_network(csv_path)
    ppda = get_ppda(csv_path)
    momentum = get_xT_momentum(csv_path)
    def_act = get_defensive_actions(csv_path)
    zone_ent = get_zone_entries(csv_path)
    set_pcs = get_set_piece_analysis(csv_path)
    buildups = get_goal_build_ups(csv_path)
    gradient = get_gradient_scoring(csv_path)

    home = summary["homeTeam"]
    away = summary["awayTeam"]
    hs = summary["homeStats"]
    aws = summary["awayStats"]

    h_shots = _shots_summary(shots_raw["shots"], home)
    a_shots = _shots_summary(shots_raw["shots"], away)

    h_net = pass_net["networks"].get(home, {})
    a_net = pass_net["networks"].get(away, {})

    def _top_edges(net, n=5):
        return [f"{e['from']} → {e['to']} ({e['count']})"
                for e in sorted(net.get("edges", []), key=lambda x: -x["count"])[:n]]

    def _top_nodes(net, n=5):
        return [f"{n['player']} ({n['passCount']} passes)"
                for n in sorted(net.get("nodes", []), key=lambda x: -x["passCount"])[:n]]

    tl = momentum["timeline"]
    home_xt_total = round(tl[-1]["homeCumXt"], 2) if tl else 0
    away_xt_total = round(tl[-1]["awayCumXt"], 2) if tl else 0

    home_def = def_act.get("home", [])
    away_def = def_act.get("away", [])
    h_ze = zone_ent.get("home", {})
    a_ze = zone_ent.get("away", {})
    h_sp = set_pcs.get("home", {}).get("summary", {})
    a_sp = set_pcs.get("away", {}).get("summary", {})
    h_grad = gradient.get("homegradient", {})
    a_grad = gradient.get("awaygradient", {})

    return {
        "homeTeam": home,
        "awayTeam": away,
        "scoreline": f"{home} {hs['goals']} – {aws['goals']} {away}",
        "summary": {"home": hs, "away": aws},
        "xi": {
            "home": xi.get("homeXI", []),
            "away": xi.get("awayXI", []),
            "homeSubs": xi.get("homeSubs", []),
            "awaySubs": xi.get("awaySubs", []),
        },
        "shots": {"home": h_shots, "away": a_shots},
        "passNetwork": {
            "home": {
                "topConnections": _top_edges(h_net),
                "keyPlayers": _top_nodes(h_net),
                "maxMinute": h_net.get("maxMinute", 90),
            },
            "away": {
                "topConnections": _top_edges(a_net),
                "keyPlayers": _top_nodes(a_net),
                "maxMinute": a_net.get("maxMinute", 90),
            },
        },
        "ppda": {"home": ppda["home"], "away": ppda["away"]},
        "momentum": {
            "homeTotal_xT": home_xt_total,
            "awayTotal_xT": away_xt_total,
            "phases": _momentum_phases(tl),
            "topPlayers": momentum.get("topPlayers", []),
        },
        "defensiveActions": {
            "homeTotalActions": len(home_def),
            "awayTotalActions": len(away_def),
            "homeHighPress": len([a for a in home_def if a["x"] > 60]),
            "awayHighPress": len([a for a in away_def if a["x"] < 40]),
        },
        "zoneEntries": {
            "home": {
                "finalThird": h_ze.get("finalThirdCount", 0),
                "zone14": h_ze.get("zone14Count", 0),
                "throughBalls": h_ze.get("throughBallCount", 0),
                "boxEntries": h_ze.get("boxCount", 0),
                "boxTouches": h_ze.get("boxTouchesCount", 0),
            },
            "away": {
                "finalThird": a_ze.get("finalThirdCount", 0),
                "zone14": a_ze.get("zone14Count", 0),
                "throughBalls": a_ze.get("throughBallCount", 0),
                "boxEntries": a_ze.get("boxCount", 0),
                "boxTouches": a_ze.get("boxTouchesCount", 0),
            },
        },
        "setPieces": {"home": h_sp, "away": a_sp},
        "goalBuildUps": _goal_narratives(buildups.get("sequences", [])),
        "gradient": {"home": h_grad, "away": a_grad},
    }


# ── Prompt ─────────────────────────────────────────────────────────────────────

def build_prompt(data: dict) -> str:
    home = data["homeTeam"]
    away = data["awayTeam"]
    hs = data["summary"]["home"]
    aws = data["summary"]["away"]
    hsh = data["shots"]["home"]
    ash = data["shots"]["away"]
    hpn = data["passNetwork"]["home"]
    apn = data["passNetwork"]["away"]
    hze = data["zoneEntries"]["home"]
    aze = data["zoneEntries"]["away"]
    hsp = data["setPieces"]["home"]
    asp = data["setPieces"]["away"]
    hg = data["gradient"]["home"]
    ag = data["gradient"]["away"]

    home_xi = ", ".join(data["xi"]["home"]) or "Not available"
    away_xi = ", ".join(data["xi"]["away"]) or "Not available"
    home_subs = ", ".join(data["xi"]["homeSubs"]) or "None"
    away_subs = ", ".join(data["xi"]["awaySubs"]) or "None"

    xt_players = "; ".join(
        f"{p['name']} ({p['xT']} xT)" for p in data["momentum"]["topPlayers"]
    ) or "None"

    return f"""You are a football analyst writing a match report for a general audience. Using only the data below, write a clear and insightful report that explains what actually happened in this match — how each team played, which team dominated in which areas, and why the result was what it was.

Rules:
- Only use numbers from the data provided. Never invent statistics.
- When you mention a metric (like PPDA or xT), explain it briefly in plain English in the same sentence.
- Use actual player names from the data. Never say "a midfielder" or "the striker."
- Write in natural, readable prose. No jargon without explanation.
- Be direct: say which team was better in each area and why.

---
MATCH DATA

Result: {data['scoreline']}

{home} XI: {home_xi}
{home} Subs: {home_subs}

{away} XI: {away_xi}
{away} Subs: {away_subs}

Core Stats:
| Metric | {home} | {away} |
|---|---|---|
| Goals | {hs['goals']} | {aws['goals']} |
| Shots | {hs['shots']} | {aws['shots']} |
| Shots on Target | {hs['shotsOnTarget']} | {aws['shotsOnTarget']} |
| Possession % | {hs['possession']} | {aws['possession']} |
| Pass Accuracy % | {hs['passAccuracy']} | {aws['passAccuracy']} |
| Total Passes | {hs['totalPasses']} | {aws['totalPasses']} |
| Big Chances | {hs['bigChances']} | {aws['bigChances']} |
| Corners | {hs['corners']} | {aws['corners']} |
| Fouls | {hs['fouls']} | {aws['fouls']} |
| Yellow Cards | {hs['yellowCards']} | {aws['yellowCards']} |
| Red Cards | {hs['redCards']} | {aws['redCards']} |
| Tackles | {hs['tackles']} | {aws['tackles']} |
| Interceptions | {hs['interceptions']} | {aws['interceptions']} |
| Clearances | {hs['clearances']} | {aws['clearances']} |
| Saves | {hs['saves']} | {aws['saves']} |

Shots:
{home}: {hsh['total']} shots, {hsh['on_target']} on target, {hsh['big_chances']} big chances, {hsh['in_box']} inside box, {hsh['outside_box']} outside box, {hsh['six_yard']} six-yard. Origins: {hsh['origins']}. Scorers: {", ".join(hsh['scorers']) or "None"}
{away}: {ash['total']} shots, {ash['on_target']} on target, {ash['big_chances']} big chances, {ash['in_box']} inside box, {ash['outside_box']} outside box, {ash['six_yard']} six-yard. Origins: {ash['origins']}. Scorers: {", ".join(ash['scorers']) or "None"}

Pressing — PPDA (Passes Allowed Per Defensive Action; lower = more intense pressing):
{home}: overall {data['ppda']['home']['overall']}, 1st half {data['ppda']['home']['firstHalf']}, 2nd half {data['ppda']['home']['secondHalf']}
{away}: overall {data['ppda']['away']['overall']}, 1st half {data['ppda']['away']['firstHalf']}, 2nd half {data['ppda']['away']['secondHalf']}

Defensive Actions:
{home}: {data['defensiveActions']['homeTotalActions']} total, {data['defensiveActions']['homeHighPress']} in opposition half
{away}: {data['defensiveActions']['awayTotalActions']} total, {data['defensiveActions']['awayHighPress']} in opposition half

Zone Penetration:
| | {home} | {away} |
|---|---|---|
| Final Third Entries | {hze['finalThird']} | {aze['finalThird']} |
| Zone 14 Entries | {hze['zone14']} | {aze['zone14']} |
| Through Balls | {hze['throughBalls']} | {aze['throughBalls']} |
| Box Entries | {hze['boxEntries']} | {aze['boxEntries']} |
| Box Touches | {hze['boxTouches']} | {aze['boxTouches']} |

Pass Networks (key players and connections in build-up play):
{home}: top connections — {"; ".join(hpn['topConnections']) or "None"} | central players — {"; ".join(hpn['keyPlayers']) or "None"}
{away}: top connections — {"; ".join(apn['topConnections']) or "None"} | central players — {"; ".join(apn['keyPlayers']) or "None"}

Set Pieces:
{home}: {hsp.get('totalCorners', 0)} corners, {hsp.get('cornerLedToShot', 0)} led to shot, {hsp.get('cornerFirstContactPct', 0)}% first contact won; {hsp.get('totalFreeKicks', 0)} free kicks, {hsp.get('fkLedToShot', 0)} led to shot; {hsp.get('ledToGoal', 0)} set piece goals
{away}: {asp.get('totalCorners', 0)} corners, {asp.get('cornerLedToShot', 0)} led to shot, {asp.get('cornerFirstContactPct', 0)}% first contact won; {asp.get('totalFreeKicks', 0)} free kicks, {asp.get('fkLedToShot', 0)} led to shot; {asp.get('ledToGoal', 0)} set piece goals

xT — Expected Threat (a measure of how much danger each action created, based on where it moved the ball):
{home} total xT: {data['momentum']['homeTotal_xT']}
{away} total xT: {data['momentum']['awayTotal_xT']}
Match phases (which team led xT by period): {data['momentum']['phases']}
Top creators: {xt_players}

Goal Sequences:
{data['goalBuildUps']}

Performance Scores (42-variable model, 0–100 scale):
{home} — Attack: {hg.get('attack', {}).get('score', 0)} | Defense: {hg.get('defense', {}).get('score', 0)} | Possession: {hg.get('passing', {}).get('score', 0)}
  Attack detail: {hg.get('attack', {}).get('breakdown', {})}
  Defense detail: {hg.get('defense', {}).get('breakdown', {})}
  Possession detail: {hg.get('passing', {}).get('breakdown', {})}

{away} — Attack: {ag.get('attack', {}).get('score', 0)} | Defense: {ag.get('defense', {}).get('score', 0)} | Possession: {ag.get('passing', {}).get('score', 0)}
  Attack detail: {ag.get('attack', {}).get('breakdown', {})}
  Defense detail: {ag.get('defense', {}).get('breakdown', {})}
  Possession detail: {ag.get('passing', {}).get('breakdown', {})}

---
Write the report using these sections in order. Use ## for each heading.

## Match Overview
2–3 paragraphs. Cover the result, the overall flow of the match, which team was in control and when, and the decisive moments. Mention goal scorers by name and reference the build-up sequences.

## How the Goals Happened
For each goal in the data, write a short paragraph describing the move — where it started, who carried it forward, the key pass or action, and how it was finished. Stick strictly to the sequence data.

## Possession and Build-up
Who controlled the ball and how effectively? Explain what the pass accuracy and total passes tell us. Identify the key players driving build-up from the pass network data. Was one team's passing more direct? Did a team dominate the ball without converting it into danger?

## Attacking Performance
Compare both teams' attacking output. Use shots, on-target shots, big chances, box entries, zone 14 entries, and xT totals. Which team created more, and which created better quality chances? Name the key attackers and what they contributed.

## Pressing and Defensive Shape
Explain what PPDA means, then compare both teams' pressing intensity across both halves. Which team disrupted the other more? Cover defensive actions, tackles, interceptions, and clearances. Highlight any significant shift between halves.

## Set Pieces
How did both teams use their set piece opportunities? Were corners or free kicks converted into genuine danger? Name any patterns or standout stats.

## Key Performers
For each team, name 2–3 players who stood out based on the data — mention their specific numbers (xT, pass connections, defensive actions, goals). Keep it factual.

## Verdict
3–4 sentences. Was the result a fair reflection of the match? Which team deserved more credit? Name the standout player and give a one-line summary of each team's performance.
"""


# ── SSE Streaming ─────────────────────────────────────────────────────────────

async def stream_report(csv_path: str) -> AsyncGenerator[str, None]:
    from groq import AsyncGroq

    if not _GROQ_API_KEY:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Groq API key not configured. Add GROQ_API_KEY to backend/.env'})}\n\n"
        return

    yield f"data: {json.dumps({'type': 'status', 'message': 'Aggregating match data...'})}\n\n"
    await asyncio.sleep(0)

    try:
        match_data = aggregate_match_data(csv_path)
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': f'Data aggregation failed: {str(e)}'})}\n\n"
        return

    yield f"data: {json.dumps({'type': 'status', 'message': 'Generating report...'})}\n\n"
    await asyncio.sleep(0)

    prompt = build_prompt(match_data)
    model_names = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    client = AsyncGroq(api_key=_GROQ_API_KEY)
    last_error = ""
    images = {}

    for model_name in model_names:
        for attempt in range(3):
            try:
                full_text = ""
                stream = await client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=8192,
                    temperature=0.7,
                    stream=True,
                )
                async for chunk in stream:
                    text = chunk.choices[0].delta.content
                    if text:
                        full_text += text
                        yield f"data: {json.dumps({'type': 'chunk', 'text': text})}\n\n"
                        await asyncio.sleep(0)

                save_report_cache(csv_path, full_text, images)
                yield f"data: {json.dumps({'type': 'done', 'cached': False})}\n\n"
                return

            except Exception as e:
                last_error = str(e)
                print(f"[report] {model_name} attempt {attempt} error: {last_error}")
                is_rate_limit = "429" in last_error or "rate" in last_error.lower()

                if is_rate_limit and attempt < 2:
                    wait = 2 ** attempt
                    yield f"data: {json.dumps({'type': 'status', 'message': f'Rate limit — retrying in {wait}s...'})}\n\n"
                    await asyncio.sleep(wait)
                    continue

                if not is_rate_limit:
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Groq error ({model_name}): {last_error}'})}\n\n"
                    return

                break

    yield f"data: {json.dumps({'type': 'error', 'message': f'Report generation failed: {last_error}'})}\n\n"
