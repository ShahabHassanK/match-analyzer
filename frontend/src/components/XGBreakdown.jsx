import { useState, useEffect, useRef, useMemo } from 'react';
import './XGBreakdown.css';
import { fetchXGBreakdown } from '../services/api';

// ── Helpers ──────────────────────────────────────────────────────────────────

function outcomeIcon(outcome) {
  if (outcome === 'Goal')    return '⚽';
  if (outcome === 'Saved')   return '🧤';
  if (outcome === 'Missed')  return '✗';
  if (outcome === 'Blocked') return '🛡';
  if (outcome === 'Post')    return '🏅';
  return outcome;
}

function xgColor(xg) {
  // Low → slate, mid → amber, high → green
  if (xg >= 0.3) return '#4ade80';
  if (xg >= 0.15) return '#fbbf24';
  return '#94a3b8';
}

// ── SVG Timeline ─────────────────────────────────────────────────────────────

const MARGIN = { top: 20, right: 24, bottom: 38, left: 48 };
const SVG_W = 800;
const SVG_H = 260;
const PLOT_W = SVG_W - MARGIN.left - MARGIN.right;
const PLOT_H = SVG_H - MARGIN.top - MARGIN.bottom;

function XGTimeline({ timeline, homeTeam, awayTeam }) {
  const svgRef = useRef(null);
  const [hoverInfo, setHoverInfo] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  const maxMinute = useMemo(
    () => Math.max(90, ...timeline.map(t => t.minute)),
    [timeline]
  );
  const maxCumXG = useMemo(
    () => Math.max(0.5, ...timeline.map(t => Math.max(t.cumHome, t.cumAway))),
    [timeline]
  );

  const xScale = (min) => MARGIN.left + (min / maxMinute) * PLOT_W;
  const yScale = (val) => MARGIN.top + PLOT_H - (val / maxCumXG) * PLOT_H;

  // Build step-function SVG path for one team
  function buildStepPath(team) {
    const events = timeline.filter(t => t.team === team);
    if (events.length === 0) return `M ${xScale(0)} ${yScale(0)} L ${xScale(maxMinute)} ${yScale(0)}`;

    let d = `M ${xScale(0)} ${yScale(0)}`;
    let prevCum = 0;

    for (const ev of events) {
      const cum = team === 'home' ? ev.cumHome : ev.cumAway;
      d += ` L ${xScale(ev.minute)} ${yScale(prevCum)}`; // horizontal to shot minute
      d += ` L ${xScale(ev.minute)} ${yScale(cum)}`;     // vertical step up
      prevCum = cum;
    }
    // Extend to end of match
    d += ` L ${xScale(maxMinute)} ${yScale(prevCum)}`;
    return d;
  }

  // Build filled area path (step path + close back to baseline)
  function buildAreaPath(team) {
    const step = buildStepPath(team);
    return `${step} L ${xScale(maxMinute)} ${yScale(0)} L ${xScale(0)} ${yScale(0)} Z`;
  }

  const goals = useMemo(() => timeline.filter(t => t.isGoal), [timeline]);

  // Y-axis ticks at 0.5 intervals
  const yTicks = useMemo(() => {
    const ticks = [];
    for (let v = 0; v <= maxCumXG + 0.01; v += 0.5) {
      ticks.push(parseFloat(v.toFixed(1)));
    }
    return ticks;
  }, [maxCumXG]);

  const handleMouseMove = (e) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const relX = e.clientX - rect.left - (MARGIN.left / SVG_W) * rect.width;
    const plotWidth = rect.width * (PLOT_W / SVG_W);
    const fraction = Math.max(0, Math.min(1, relX / plotWidth));
    const minute = Math.round(fraction * maxMinute);

    // Find the state of cumulative xG at this minute
    let cumHome = 0, cumAway = 0;
    for (const ev of timeline) {
      if (ev.minute > minute) break;
      cumHome = ev.cumHome;
      cumAway = ev.cumAway;
    }

    let tipX = e.clientX + 16;
    if (tipX + 200 > window.innerWidth) tipX = e.clientX - 216;
    setHoverInfo({ minute, cumHome, cumAway });
    setTooltipPos({ x: tipX, y: e.clientY + 12 });
  };

  return (
    <div className="xg-chart-wrap">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${SVG_W} ${SVG_H}`}
        className="xg-svg"
        preserveAspectRatio="none"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoverInfo(null)}
      >
        <defs>
          <linearGradient id="xgHomeGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.04" />
          </linearGradient>
          <linearGradient id="xgAwayGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#f97316" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#f97316" stopOpacity="0.04" />
          </linearGradient>
        </defs>

        {/* Y-axis grid lines + labels */}
        {yTicks.map(v => (
          <g key={v}>
            <line
              x1={MARGIN.left} y1={yScale(v)}
              x2={MARGIN.left + PLOT_W} y2={yScale(v)}
              stroke="#e2e8f0" strokeWidth="1" strokeDasharray="4 3"
            />
            <text
              x={MARGIN.left - 6} y={yScale(v) + 4}
              textAnchor="end" fontSize="11" fill="#94a3b8"
            >
              {v.toFixed(1)}
            </text>
          </g>
        ))}

        {/* X-axis labels */}
        <text x={xScale(0)} y={SVG_H - 6} textAnchor="middle" fontSize="11" fill="#94a3b8">0'</text>
        <text x={xScale(45)} y={SVG_H - 6} textAnchor="middle" fontSize="11" fill="#94a3b8">45'</text>
        <text x={xScale(maxMinute)} y={SVG_H - 6} textAnchor="end" fontSize="11" fill="#94a3b8">{maxMinute}'</text>

        {/* Half-time line */}
        <line
          x1={xScale(45)} y1={MARGIN.top}
          x2={xScale(45)} y2={MARGIN.top + PLOT_H}
          stroke="#cbd5e1" strokeWidth="1" strokeDasharray="5 4"
        />

        {/* Filled areas */}
        <path d={buildAreaPath('home')} fill="url(#xgHomeGrad)" />
        <path d={buildAreaPath('away')} fill="url(#xgAwayGrad)" />

        {/* Step-function lines */}
        <path d={buildStepPath('home')} fill="none" stroke="#3b82f6" strokeWidth="2.5" strokeLinejoin="round" />
        <path d={buildStepPath('away')} fill="none" stroke="#f97316" strokeWidth="2.5" strokeLinejoin="round" />

        {/* Goal markers */}
        {goals.map((g, i) => {
          const gx = xScale(g.minute);
          const cum = g.team === 'home' ? g.cumHome : g.cumAway;
          const gy = yScale(cum);
          const color = g.team === 'home' ? '#3b82f6' : '#f97316';
          return (
            <g key={i}>
              <line
                x1={gx} y1={MARGIN.top}
                x2={gx} y2={MARGIN.top + PLOT_H}
                stroke={color} strokeWidth="1.5" strokeDasharray="4 3" opacity="0.6"
              />
              <circle cx={gx} cy={gy} r="5" fill={color} stroke="#ffffff" strokeWidth="1.5" />
            </g>
          );
        })}

        {/* Hover vertical line */}
        {hoverInfo && (
          <line
            x1={xScale(hoverInfo.minute)} y1={MARGIN.top}
            x2={xScale(hoverInfo.minute)} y2={MARGIN.top + PLOT_H}
            stroke="#94a3b8" strokeWidth="1" strokeDasharray="3 2" opacity="0.5"
          />
        )}
      </svg>

      <div className="xg-chart-legend">
        <span className="xg-legend-dot" style={{ background: '#3b82f6' }} />{homeTeam}
        <span className="xg-legend-dot" style={{ background: '#f97316', marginLeft: '1.5rem' }} />{awayTeam}
        <span className="xg-legend-goal">● Goal marker</span>
      </div>

      {hoverInfo && (
        <div
          className="xg-chart-tooltip"
          style={{ position: 'fixed', left: hoverInfo ? tooltipPos.x : -9999, top: tooltipPos.y }}
        >
          <div className="xg-tt-min">{hoverInfo.minute}'</div>
          <div className="xg-tt-row">
            <span className="xg-tt-dot" style={{ background: '#3b82f6' }} />
            <span>{homeTeam}</span>
            <span className="xg-tt-val">{hoverInfo.cumHome.toFixed(2)} xG</span>
          </div>
          <div className="xg-tt-row">
            <span className="xg-tt-dot" style={{ background: '#f97316' }} />
            <span>{awayTeam}</span>
            <span className="xg-tt-val">{hoverInfo.cumAway.toFixed(2)} xG</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Summary Cards ─────────────────────────────────────────────────────────────

function SummaryCard({ teamName, stats, perf, color }) {
  const badgeClass =
    perf.label === 'Overperformed' ? 'xg-badge xg-badge-over' :
    perf.label === 'Underperformed' ? 'xg-badge xg-badge-under' :
    'xg-badge xg-badge-expected';

  const diffSign = perf.xGDiff > 0 ? '+' : '';

  return (
    <div className="xg-summary-card" style={{ borderTopColor: color }}>
      <div className="xg-card-team" style={{ color }}>{teamName}</div>
      <div className="xg-card-main">
        <span className="xg-card-xg">{stats.xG.toFixed(2)}</span>
        <span className="xg-card-xglabel">xG</span>
      </div>
      <div className="xg-card-row">
        <span className="xg-card-label">npxG</span>
        <span className="xg-card-value">{stats.npxG.toFixed(2)}</span>
      </div>
      <div className="xg-card-row">
        <span className="xg-card-label">Goals</span>
        <span className="xg-card-value">{stats.goals}</span>
      </div>
      <div className="xg-card-row">
        <span className="xg-card-label">Shots</span>
        <span className="xg-card-value">{stats.shots}</span>
      </div>
      <div className={badgeClass}>
        {perf.label} ({diffSign}{perf.xGDiff.toFixed(2)})
      </div>
    </div>
  );
}

// ── Shot Table ────────────────────────────────────────────────────────────────

function ShotTable({ shots, homeTeam, awayTeam }) {
  return (
    <div className="xg-table-wrap">
      <table className="xg-table">
        <thead>
          <tr>
            <th>Min</th>
            <th>Player</th>
            <th>Team</th>
            <th>xG</th>
            <th>Outcome</th>
            <th>Body Part</th>
            <th>Origin</th>
          </tr>
        </thead>
        <tbody>
          {shots.map((s, i) => (
            <tr
              key={i}
              className={
                s.isGoal ? 'xg-row-goal' :
                s.isPenalty ? 'xg-row-pen' :
                ''
              }
            >
              <td className="xg-td-min">{s.minute}'</td>
              <td className="xg-td-player">{s.player}</td>
              <td className="xg-td-team">
                <span
                  className="xg-team-pill"
                  style={{ background: s.team === 'home' ? '#dbeafe' : '#ffedd5', color: s.team === 'home' ? '#1d4ed8' : '#c2410c' }}
                >
                  {s.team === 'home' ? homeTeam : awayTeam}
                </span>
              </td>
              <td className="xg-td-xg" style={{ color: xgColor(s.xG) }}>
                {s.isPenalty ? <span title="Fixed penalty xG">{s.xG.toFixed(3)} <span className="xg-pen-tag">P</span></span> : s.xG.toFixed(3)}
              </td>
              <td className="xg-td-outcome">
                <span className={`xg-outcome xg-outcome-${s.outcome.toLowerCase()}`}>
                  {outcomeIcon(s.outcome)} {s.outcome}
                </span>
              </td>
              <td>{s.bodyPart}</td>
              <td>{s.origin}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function XGBreakdown({ matchId, homeTeam, awayTeam, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [shotFilter, setShotFilter] = useState('all');

  useEffect(() => {
    setLoading(true);
    setError(null);
    setData(null);
    fetchXGBreakdown(matchId)
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [matchId]);

  if (loading) {
    return (
      <div className="xg-panel xg-panel-loading">
        <div className="scraping-spinner" />
        <p>Running xG model…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="xg-panel xg-panel-error">
        <p>Failed to load xG breakdown: {error}</p>
      </div>
    );
  }

  if (!data) return null;

  const resolvedHome = data.homeTeam || homeTeam;
  const resolvedAway = data.awayTeam || awayTeam;

  return (
    <div className="xg-panel">
      <div className="xg-panel-header">
        <h2 className="xg-panel-title">xG Breakdown</h2>
        <p className="xg-panel-sub">Expected Goals — trained XGBoost model, full match</p>
      </div>

      {/* Section A: Summary */}
      <div className="xg-summary-row">
        <SummaryCard
          teamName={resolvedHome}
          stats={data.summary.home}
          perf={data.performance.home}
          color="#3b82f6"
        />
        <div className="xg-summary-vs">
          <div className="xg-vs-label">VS</div>
          <div className="xg-vs-score">
            {data.summary.home.goals} – {data.summary.away.goals}
          </div>
          <div className="xg-vs-xg">
            {data.summary.home.xG.toFixed(2)} – {data.summary.away.xG.toFixed(2)} xG
          </div>
        </div>
        <SummaryCard
          teamName={resolvedAway}
          stats={data.summary.away}
          perf={data.performance.away}
          color="#f97316"
        />
      </div>

      {/* Section B: Timeline */}
      <div className="xg-section">
        <h3 className="xg-section-title">Cumulative xG Timeline</h3>
        {data.timeline.length > 0 ? (
          <XGTimeline
            timeline={data.timeline}
            homeTeam={resolvedHome}
            awayTeam={resolvedAway}
          />
        ) : (
          <p className="xg-empty">No shot data available.</p>
        )}
      </div>

      {/* Section C: Shot table */}
      <div className="xg-section">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <h3 className="xg-section-title" style={{ margin: 0 }}>Shot-by-Shot Breakdown</h3>
          <div style={{ display: 'flex', gap: '0.4rem', marginLeft: 'auto' }}>
            {[
              { key: 'all',  label: 'All',        bg: shotFilter === 'all'  ? '#1e293b' : '#f1f5f9', color: shotFilter === 'all'  ? '#fff' : '#64748b' },
              { key: 'home', label: resolvedHome,  bg: shotFilter === 'home' ? '#3b82f6' : '#dbeafe', color: shotFilter === 'home' ? '#fff' : '#1d4ed8' },
              { key: 'away', label: resolvedAway,  bg: shotFilter === 'away' ? '#f97316' : '#ffedd5', color: shotFilter === 'away' ? '#fff' : '#c2410c' },
            ].map(({ key, label, bg, color }) => (
              <button
                key={key}
                onClick={() => setShotFilter(key)}
                style={{ padding: '0.25rem 0.75rem', borderRadius: '999px', border: 'none', cursor: 'pointer', fontSize: '0.78rem', fontWeight: 600, background: bg, color, transition: 'all 0.15s' }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        {data.shots.length > 0 ? (
          <ShotTable
            shots={data.shots.filter(s => shotFilter === 'all' || s.team === shotFilter)}
            homeTeam={resolvedHome}
            awayTeam={resolvedAway}
          />
        ) : (
          <p className="xg-empty">No shots recorded.</p>
        )}
      </div>
    </div>
  );
}
