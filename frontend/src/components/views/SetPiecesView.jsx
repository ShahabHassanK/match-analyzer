/**
 * views/SetPiecesView.jsx
 * ======================
 * Set piece analysis view — Corners and Free Kicks.
 * 
 * Features:
 * - Team selector (Home / Away)
 * - Sub-tabs: Corners / Free Kicks
 * - Pitch delivery arrows color-coded by outcome
 * - First contact & shot result per delivery
 * - Summary stats panel
 */

import { useState, useMemo } from 'react';
import './SetPiecesView.css';

const OUTCOME_COLORS = {
  goal: '#00F485',
  shot: '#f59e0b',
  firstContact: '#38BDF8',
  lostContact: '#94A3B8',
};

export default function SetPiecesView({ data, homeTeam, awayTeam }) {
  const [activeTeam, setActiveTeam] = useState('home');
  const [activeType, setActiveType] = useState('corners');
  const [hoveredDelivery, setHoveredDelivery] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  const isDataValid = data && data.home && data.away;
  const teamName = activeTeam === 'home' ? homeTeam : awayTeam;
  const teamClass = activeTeam === 'home' ? 'home' : 'away';
  const teamData = isDataValid ? (activeTeam === 'home' ? data.home : data.away) : null;

  // Get the deliveries for the active type
  const deliveries = useMemo(() => {
    if (!teamData) return [];
    return activeType === 'corners' ? (teamData.corners || []) : (teamData.freeKicks || []);
  }, [teamData, activeType]);

  const summary = teamData?.summary || {};

  // Stats for active type
  const activeStats = useMemo(() => {
    if (!deliveries.length) return { total: 0, firstContact: 0, resultedInShot: 0, goals: 0 };
    return {
      total: deliveries.length,
      firstContact: deliveries.filter(d => d.firstContact).length,
      resultedInShot: deliveries.filter(d => d.resultedInShot).length,
      goals: deliveries.filter(d => d.shotOutcome === 'Goal').length,
    };
  }, [deliveries]);

  // Coordinate mapping
  const scaleX = (val) => (val / 100) * 105;
  const scaleY = (val) => (val / 100) * 68;

  const getDeliveryColor = (delivery) => {
    if (delivery.shotOutcome === 'Goal') return OUTCOME_COLORS.goal;
    if (delivery.resultedInShot) return OUTCOME_COLORS.shot;
    if (delivery.firstContact) return OUTCOME_COLORS.firstContact;
    return OUTCOME_COLORS.lostContact;
  };

  const handleMouseMove = (e) => setMousePos({ x: e.clientX, y: e.clientY });

  if (!isDataValid) {
    return <div className="view-loading">Loading Set Pieces…</div>;
  }

  return (
    <div className="setpiece-view" onMouseMove={handleMouseMove}>
      {/* Header */}
      <div className="sp-header">
        <div className="sp-filters">
          {/* Team Toggle */}
          <div className="sp-btn-group">
            <button
              className={`sp-btn ${activeTeam === 'home' ? 'active home' : ''}`}
              onClick={() => setActiveTeam('home')}
            >
              {homeTeam}
            </button>
            <button
              className={`sp-btn ${activeTeam === 'away' ? 'active away' : ''}`}
              onClick={() => setActiveTeam('away')}
            >
              {awayTeam}
            </button>
          </div>
          {/* Type Toggle */}
          <div className="sp-btn-group">
            <button
              className={`sp-btn ${activeType === 'corners' ? 'active' : ''}`}
              onClick={() => setActiveType('corners')}
            >
              Corners
            </button>
            <button
              className={`sp-btn ${activeType === 'freeKicks' ? 'active' : ''}`}
              onClick={() => setActiveType('freeKicks')}
            >
              Free Kicks
            </button>
          </div>
        </div>

        <div className="sp-header-stats">
          <div className="sp-stat-pill">{activeStats.total} <span>Deliveries</span></div>
          <div className="sp-stat-pill accent">{activeStats.firstContact} <span>1st Contact</span></div>
          <div className="sp-stat-pill shot">{activeStats.resultedInShot} <span>Led to Shot</span></div>
          {activeStats.goals > 0 && (
            <div className="sp-stat-pill goal">{activeStats.goals} <span>Goals</span></div>
          )}
        </div>
      </div>

      <div className="sp-body">
        {/* Pitch */}
        <div className="sp-pitch-container">
          <svg viewBox="0 0 105 68" className="sp-pitch-svg" preserveAspectRatio="xMidYMid meet">
            <defs>
              <marker id="sp-arrow-goal" viewBox="0 0 10 10" refX="7" refY="5"
                markerWidth="4" markerHeight="4" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill={OUTCOME_COLORS.goal} />
              </marker>
              <marker id="sp-arrow-shot" viewBox="0 0 10 10" refX="7" refY="5"
                markerWidth="4" markerHeight="4" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill={OUTCOME_COLORS.shot} />
              </marker>
              <marker id="sp-arrow-first" viewBox="0 0 10 10" refX="7" refY="5"
                markerWidth="4" markerHeight="4" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill={OUTCOME_COLORS.firstContact} />
              </marker>
              <marker id="sp-arrow-lost" viewBox="0 0 10 10" refX="7" refY="5"
                markerWidth="4" markerHeight="4" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill={OUTCOME_COLORS.lostContact} />
              </marker>
            </defs>

            <rect width="105" height="68" className="sp-turf" />

            {/* Pitch Lines */}
            <g className="sp-lines" strokeWidth="0.3" fill="none">
              <rect x="0" y="0" width="105" height="68" />
              <line x1="52.5" y1="0" x2="52.5" y2="68" />
              <circle cx="52.5" cy="34" r="9.15" />
              <rect x="0" y="13.84" width="16.5" height="40.32" />
              <rect x="0" y="24.84" width="5.5" height="18.32" />
              <circle cx="11" cy="34" r="0.3" fill="var(--sp-line-color)" />
              <path d="M 16.5 26.7 A 9.15 9.15 0 0 1 16.5 41.3" />
              <rect x="88.5" y="13.84" width="16.5" height="40.32" />
              <rect x="99.5" y="24.84" width="5.5" height="18.32" />
              <circle cx="94" cy="34" r="0.3" fill="var(--sp-line-color)" />
              <path d="M 88.5 41.3 A 9.15 9.15 0 0 1 88.5 26.7" />
            </g>

            {/* Delivery Arrows */}
            <g className="sp-deliveries">
              {deliveries.map((d, idx) => {
                const sx = scaleX(d.startX);
                const sy = scaleY(d.startY);
                const ex = scaleX(d.endX);
                const ey = scaleY(d.endY);
                const color = getDeliveryColor(d);
                const markerId = d.shotOutcome === 'Goal' ? 'sp-arrow-goal'
                  : d.resultedInShot ? 'sp-arrow-shot'
                  : d.firstContact ? 'sp-arrow-first'
                  : 'sp-arrow-lost';

                const isHovered = hoveredDelivery === d;

                return (
                  <g key={idx}>
                    <line
                      x1={sx} y1={sy} x2={ex} y2={ey}
                      stroke={color}
                      strokeWidth={isHovered ? "0.9" : "0.5"}
                      strokeOpacity={hoveredDelivery && !isHovered ? 0.2 : 0.8}
                      markerEnd={`url(#${markerId})`}
                      className="sp-delivery-line"
                      onMouseEnter={() => setHoveredDelivery(d)}
                      onMouseLeave={() => setHoveredDelivery(null)}
                    />
                    {/* Start dot */}
                    <circle cx={sx} cy={sy} r="1"
                      fill={color}
                      opacity={hoveredDelivery && !isHovered ? 0.2 : 0.9}
                      pointerEvents="none"
                    />
                    {/* End dot */}
                    <circle cx={ex} cy={ey} r="1.2"
                      fill={color}
                      opacity={hoveredDelivery && !isHovered ? 0.15 : 0.6}
                      stroke={color}
                      strokeWidth="0.3"
                      pointerEvents="none"
                    />
                    {/* Goal marker */}
                    {d.shotOutcome === 'Goal' && (
                      <circle cx={ex} cy={ey} r="2.5"
                        fill="none" stroke={OUTCOME_COLORS.goal}
                        strokeWidth="0.4" strokeDasharray="1,0.8"
                        opacity={hoveredDelivery && !isHovered ? 0.2 : 0.7}
                        pointerEvents="none"
                      />
                    )}
                  </g>
                );
              })}
            </g>
          </svg>

          {/* Tooltip */}
          {hoveredDelivery && (
            <div className="sp-tooltip"
              style={{ left: mousePos.x + 15, top: mousePos.y - 40, position: 'fixed', pointerEvents: 'none' }}
            >
              <div className="sp-tt-player">{hoveredDelivery.player}</div>
              <div className="sp-tt-row">
                <span>Minute</span>
                <span className="val">{hoveredDelivery.minute}'</span>
              </div>
              <div className="sp-tt-row">
                <span>1st Contact</span>
                <span className={`val ${hoveredDelivery.firstContact ? 'yes' : 'no'}`}>
                  {hoveredDelivery.firstContact ? 'Won' : 'Lost'}
                </span>
              </div>
              <div className="sp-tt-row">
                <span>Led to Shot</span>
                <span className={`val ${hoveredDelivery.resultedInShot ? 'yes' : 'no'}`}>
                  {hoveredDelivery.resultedInShot
                    ? (hoveredDelivery.shotOutcome === 'Goal' ? '⚽ Goal' : 'Yes')
                    : 'No'}
                </span>
              </div>
              <div className="sp-tt-row">
                <span>Delivery</span>
                <span className="val">{hoveredDelivery.outcome}</span>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar: Summary Stats */}
        <div className="sp-sidebar">
          {/* Legend */}
          <div className="sp-legend-block">
            <h4 className="sp-sidebar-title">Delivery Outcome</h4>
            <div className="sp-legend-items">
              <div className="sp-legend-row">
                <span className="sp-legend-dot" style={{ background: OUTCOME_COLORS.goal }} />
                Led to Goal
              </div>
              <div className="sp-legend-row">
                <span className="sp-legend-dot" style={{ background: OUTCOME_COLORS.shot }} />
                Led to Shot
              </div>
              <div className="sp-legend-row">
                <span className="sp-legend-dot" style={{ background: OUTCOME_COLORS.firstContact }} />
                1st Contact Won
              </div>
              <div className="sp-legend-row">
                <span className="sp-legend-dot" style={{ background: OUTCOME_COLORS.lostContact }} />
                1st Contact Lost
              </div>
            </div>
          </div>

          {/* Summary Stats */}
          <div className="sp-summary-block">
            <h4 className="sp-sidebar-title">Set Piece Summary</h4>

            <div className="sp-summary-grid">
              <div className="sp-sg-item">
                <div className="sp-sg-label">Total Set Pieces</div>
                <div className="sp-sg-val">{summary.totalSetPieces ?? 0}</div>
              </div>
              <div className="sp-sg-item">
                <div className="sp-sg-label">Led to Shot</div>
                <div className="sp-sg-val">{summary.ledToShot ?? 0}</div>
              </div>
              <div className="sp-sg-item">
                <div className="sp-sg-label">Led to Big Chance</div>
                <div className="sp-sg-val highlight">{summary.ledToBigChance ?? 0}</div>
              </div>
              <div className="sp-sg-item">
                <div className="sp-sg-label">Led to Goal</div>
                <div className="sp-sg-val highlight">{summary.ledToGoal ?? 0}</div>
              </div>
              <div className="sp-sg-item">
                <div className="sp-sg-label">SP Assists</div>
                <div className="sp-sg-val">{summary.setPieceAssists ?? 0}</div>
              </div>
            </div>

            <div className="sp-divider" />

            <div className="sp-summary-grid">
              <div className="sp-sg-item">
                <div className="sp-sg-label">Penalty Goals</div>
                <div className="sp-sg-val">{summary.penaltyGoals ?? 0}</div>
              </div>
              <div className="sp-sg-item">
                <div className="sp-sg-label">1st Contacts Won</div>
                <div className="sp-sg-val">{summary.firstContactsWon ?? 0}</div>
              </div>
            </div>

            <div className="sp-divider" />

            {/* First Contact Rates */}
            <div className="sp-contact-section">
              <div className="sp-contact-row">
                <span className="sp-contact-label">Corner 1st Contact</span>
                <div className="sp-bar-wrapper">
                  <div className={`sp-bar-fill ${teamClass}`}
                    style={{ width: `${summary.cornerFirstContactPct ?? 0}%` }} />
                </div>
                <span className="sp-contact-pct">{summary.cornerFirstContactPct ?? 0}%</span>
              </div>
              <div className="sp-contact-info">
                {summary.cornerFirstContacts ?? 0} / {summary.totalCorners ?? 0} corners
              </div>

              <div className="sp-contact-row" style={{ marginTop: '12px' }}>
                <span className="sp-contact-label">FK 1st Contact</span>
                <div className="sp-bar-wrapper">
                  <div className={`sp-bar-fill ${teamClass}`}
                    style={{ width: `${summary.fkFirstContactPct ?? 0}%` }} />
                </div>
                <span className="sp-contact-pct">{summary.fkFirstContactPct ?? 0}%</span>
              </div>
              <div className="sp-contact-info">
                {summary.fkFirstContacts ?? 0} / {summary.totalFreeKicks ?? 0} free kicks
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
