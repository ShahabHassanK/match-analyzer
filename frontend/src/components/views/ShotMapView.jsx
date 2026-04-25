/**
 * views/ShotMapView.jsx
 * =====================
 * State-of-the-art Shot Map visualization (Vertical attacking UP).
 * Inspired by Opta / StatsBomb / Understat.
 *
 * Features:
 * - Vertical half-pitch orientation (industry standard).
 * - Premium dark turf styling for contrast.
 * - Logarithmic/Categorical sizing based on Big Chance constraint.
 * - Tooltip perfectly anchored to the shot (no jitter).
 */

import { useState, useMemo } from 'react';
import './ShotMapView.css';

const OUTCOMES = {
  goal:       { color: '#00F485', label: 'Goal' },
  on_target:  { color: '#38BDF8', label: 'Saved' },
  off_target: { color: '#94A3B8', label: 'Missed / Blocked' },
  own_goal:   { color: '#EF4444', label: 'Own Goal' }
};

export default function ShotMapView({ data, homeTeam, awayTeam }) {
  const [activeTeam, setActiveTeam] = useState('home');
  const [hoveredShot, setHoveredShot] = useState(null);

  const teamName = activeTeam === 'home' ? homeTeam : awayTeam;

  // Sort shots chronological
  const teamShots = useMemo(() => {
    if (!data || !data.shots) return [];
    return data.shots
      .filter(s => s.team === teamName)
      .sort((a, b) => a.minute - b.minute);
  }, [data, teamName]);

  if (!data) return <div className="view-loading">Loading shot map…</div>;

  const goals = teamShots.filter(s => s.outcome === 'goal').length;
  const onTarget = teamShots.filter(s => s.outcome === 'on_target').length;
  const offTarget = teamShots.filter(s => s.outcome === 'off_target').length;

  // Coordinate Mapping for Vertical Half-Pitch
  // WhoScored attack right: x is 0(own)->100(opp), y is 0(right)->100(left) or vice versa.
  // We map taking x: 50->100 to svgY: 100->0.
  // And y: 0->100 to svgX: 0->100.
  const mapY = (x) => Math.max(0, Math.min(100, (100 - x) * 2));
  const mapX = (y) => 100 - y; // WhoScored Y is essentially pitch width, inverted for broadcast view, inverted for broadcast view

  // Distance calculator (rough metres from center of goal)
  const scaleX = (val) => (val / 100) * 105;
  const scaleY = (val) => ((100 - val) / 100) * 68; // 68m width
  const calcDist = (sx, sy) => {
    const dx = (sx - 50) * 0.68; // 68m width
    const dy = sy * 1.05; // 105m length
    return Math.sqrt(dx*dx + dy*dy).toFixed(1);
  };

  return (
    <div className="premium-shotmap">
      {/* Top Bar Navigation */}
      <div className="psm-header">
        <div className="psm-team-selector">
          <button
            className={`psm-tab ${activeTeam === 'home' ? 'active home' : ''}`}
            onClick={() => setActiveTeam('home')}
          >
            {homeTeam}
          </button>
          <button
            className={`psm-tab ${activeTeam === 'away' ? 'active away' : ''}`}
            onClick={() => setActiveTeam('away')}
          >
            {awayTeam}
          </button>
        </div>
        <div className="psm-summary">
          <div className="psm-sum-item"><span>{teamShots.length}</span> Shots</div>
          <div className="psm-sum-item"><span>{goals}</span> Goals</div>
          <div className="psm-sum-item"><span>{onTarget}</span> On Target</div>
        </div>
      </div>

      <div className="psm-body">
        
        {/* Left Side: Pitch Visualization */}
        <div className="psm-pitch-container">
          <svg viewBox="0 0 100 100" className="psm-pitch-svg" preserveAspectRatio="xMidYMid meet">
            {/* Pitch Background */}
            <rect width="100" height="100" className="psm-turf" />
            
            {/* Pitch Lines */}
            <g className="psm-lines">
              {/* Box Outline */}
              <rect x="0" y="0" width="100" height="100" strokeWidth="0.5" fill="none" />
              {/* Halfway Line (bottom edge) */}
              <line x1="0" y1="100" x2="100" y2="100" strokeWidth="0.5" />
              {/* Centre Circle (Bottom) */}
              <circle cx="50" cy="100" r="9.15" strokeWidth="0.5" fill="none" />
              {/* Penalty Area */}
              <rect x="21.1" y="0" width="57.8" height="34" strokeWidth="0.5" fill="none" />
              {/* 6 Yard Box */}
              <rect x="36.8" y="0" width="26.4" height="11" strokeWidth="0.5" fill="none" />
              {/* Goal */}
              <rect x="44.2" y="-2" width="11.6" height="2" strokeWidth="0.8" fill="none" />
              {/* Penalty Spot */}
              <circle cx="50" cy="22" r="0.4" fill="var(--psm-line-color)" />
              {/* D Arc */}
              <path d="M 36.8 34 A 9.15 9.15 0 0 0 63.2 34" strokeWidth="0.5" fill="none" />
            </g>

            {/* Shots rendering */}
            {teamShots.map((shot, i) => {
              const cx = mapX(shot.y);
              const cy = mapY(shot.x);
              // Larger circle for Big Chance
              const r = shot.outcome === 'goal' ? (shot.isBigChance ? 3.5 : 2.5) : (shot.isBigChance ? 2.5 : 1.5);
              const color = OUTCOMES[shot.outcome].color;
              const isHovered = hoveredShot === shot;

              return (
                <g key={i} 
                   className={`psm-shot-node ${isHovered ? 'hovered' : ''}`}
                   onMouseEnter={() => setHoveredShot(shot)}
                   onMouseLeave={() => setHoveredShot(null)}
                   style={{ cursor: 'pointer' }}>
                  {/* Glow effect for goals */}
                  {shot.outcome === 'goal' && (
                    <circle cx={cx} cy={cy} r={r + 1.5} fill={color} opacity="0.3" 
                      className={isHovered ? 'pulse' : ''} />
                  )}
                  {/* Outer ring for big chance non-goals */}
                  {shot.isBigChance && shot.outcome !== 'goal' && (
                    <circle cx={cx} cy={cy} r={r + 1} stroke={color} strokeWidth="0.3" fill="none" opacity="0.6" />
                  )}
                  {/* Main dot */}
                  <circle 
                    cx={cx} 
                    cy={cy} 
                    r={r} 
                    fill={color} 
                    stroke="rgba(0,0,0,0.5)" 
                    strokeWidth="0.3" 
                    opacity={isHovered ? "1" : "0.85"} 
                  />
                  {/* Extra distinction for goals (a star or dot inside) */}
                  {shot.outcome === 'goal' && (
                    <circle cx={cx} cy={cy} r={r * 0.3} fill="#fff" pointerEvents="none" />
                  )}
                </g>
              );
            })}
          </svg>

          {/* HTML Overlay Tooltip anchored to active shot percentage */}
          {hoveredShot && (() => {
            const tx = mapX(hoveredShot.y);
            const ty = mapY(hoveredShot.x);
            let tooltipClass = "psm-tooltip";
            
            // Boundary detection
            if (ty < 20) tooltipClass += " flip-down";
            if (tx < 20) tooltipClass += " shift-right";
            else if (tx > 80) tooltipClass += " shift-left";

            return (
              <div className={tooltipClass} 
                   style={{
                     left: `${tx}%`,
                     top: `${ty}%`,
                   }}>
              <div className="psm-tooltip-inner">
                <div className="psm-tt-header">
                  <span className="psm-tt-player">{hoveredShot.player}</span>
                  <span className="psm-tt-minute">{hoveredShot.minute}'</span>
                </div>
                <div className="psm-tt-body">
                  <span className="psm-tt-badge" style={{ backgroundColor: OUTCOMES[hoveredShot.outcome].color, color: hoveredShot.outcome === 'goal' ? '#000' : '#fff' }}>
                    {OUTCOMES[hoveredShot.outcome].label}
                  </span>
                  <span className="psm-tt-dist">
                    {calcDist(mapX(hoveredShot.y), mapY(hoveredShot.x))}m
                  </span>
                </div>
                <div className="psm-tt-footer">
                  {hoveredShot.isBigChance ? <span className="psm-pill warning">Big Chance</span> : null}
                  <span className={`psm-pill ${hoveredShot.bodyPart === 'Header' ? 'info' : 'text'}`}>
                    {hoveredShot.bodyPart || (hoveredShot.isHeader ? 'Header' : 'Foot')}
                  </span>
                  {hoveredShot.origin && hoveredShot.origin !== 'Open Play' && (
                    <span className="psm-pill set-piece">{hoveredShot.origin}</span>
                  )}
                </div>
              </div>
            </div>
            );
          })()}
        </div>

        {/* Right Side: Timeline and Legend */}
        <div className="psm-sidebar">
          <div className="psm-legend">
            <h4 className="psm-sidebar-title">Shot Quality & Outcome</h4>
            <div className="psm-legend-items">
              <div className="psm-legend-row"><span className="psm-dot goal" /> Goal</div>
              <div className="psm-legend-row"><span className="psm-dot target" /> On Target (Saved)</div>
              <div className="psm-legend-row"><span className="psm-dot miss" /> Missed / Blocked</div>
            </div>
            <div className="psm-legend-items sizes">
              <div className="psm-legend-row size-row"><span className="psm-dot-size big" /> Big Chance</div>
              <div className="psm-legend-row size-row"><span className="psm-dot-size normal" /> Normal Chance</div>
            </div>
          </div>

          <div className="psm-timeline-wrapper">
            <h4 className="psm-sidebar-title">Chronological Shots</h4>
            <div className="psm-timeline-list">
              {teamShots.map((shot, i) => (
                <div 
                  key={i}
                  className={`psm-tl-item ${hoveredShot === shot ? 'active' : ''}`}
                  onMouseEnter={() => setHoveredShot(shot)}
                  onMouseLeave={() => setHoveredShot(null)}
                >
                  <div className="psm-tl-min">{shot.minute}'</div>
                  <div className="psm-tl-content">
                    <span className="psm-tl-icon" style={{ background: OUTCOMES[shot.outcome].color }}>
                      {shot.outcome === 'goal' ? '⚽' : ''}
                    </span>
                    <span className="psm-tl-name">{shot.player}</span>
                    {shot.isBigChance && <span className="psm-tl-bc">BC</span>}
                  </div>
                </div>
              ))}
              {teamShots.length === 0 && <div className="psm-tl-empty">No shots recorded.</div>}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
