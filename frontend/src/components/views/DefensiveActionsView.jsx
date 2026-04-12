import { useState, useMemo } from 'react';
import './DefensiveActionsView.css';

const ORIGINAL_DEF_ACTIONS = new Set(['Tackle', 'Interception', 'Foul', 'Challenge', 'BlockedPass']);

export default function DefensiveActionsView({ data, homeTeam, awayTeam }) {
  const [activeTeam, setActiveTeam] = useState('home');
  const [activeTab, setActiveTab] = useState('all'); // 'all' or 'pressing'
  const [hoveredAction, setHoveredAction] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  const isDataValid = data && data.home && data.away;
  const allTeamData = isDataValid ? (activeTeam === 'home' ? data.home : data.away) : [];
  const teamClass = activeTeam === 'home' ? 'home' : 'away';

  const isPressing = activeTab === 'pressing';

  // Filter: "All Actions" shows original defensive actions only (no BallRecovery)
  const teamData = useMemo(() => {
    return allTeamData.filter(a => ORIGINAL_DEF_ACTIONS.has(a.type));
  }, [allTeamData]);

  // ── Pressing Tab Data ───────────────────────────────────────────────────
  const pressingData = useMemo(() => {
    if (!allTeamData.length) return { actions: [], highRecoveries: 0, ledToShot: 0, topPressers: [] };

    // Only BallRecovery in opponent half (x > 50), exclude set pieces
    const highRecoveries = allTeamData.filter(a => a.type === 'BallRecovery' && a.x > 50 && !a.isSetPiece);
    const ledToShot = highRecoveries.filter(a => a.leadsToShot);

    // Top pressers: players with most high recoveries
    const playerCounts = {};
    highRecoveries.forEach(a => {
      if (!playerCounts[a.player]) playerCounts[a.player] = { total: 0, shots: 0 };
      playerCounts[a.player].total++;
      if (a.leadsToShot) playerCounts[a.player].shots++;
    });
    const topPressers = Object.entries(playerCounts)
      .map(([player, c]) => ({ player, total: c.total, shots: c.shots }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 5);

    return {
      actions: highRecoveries,
      highRecoveries: highRecoveries.length,
      ledToShot: ledToShot.length,
      topPressers,
    };
  }, [allTeamData]);

  // ── All Actions Tab Stats ───────────────────────────────────────────────
  const { medianX, thirds, totalValid } = useMemo(() => {
    if (!teamData.length) return { medianX: null, thirds: { def: 0, mid: 0, att: 0 }, totalValid: 0 };

    const validActions = teamData.filter(a => a.outcome !== 'Unsuccessful');
    
    const openPlayActions = validActions.filter(a => !a.isSetPiece);
    const xCoords = openPlayActions.map(a => a.x).sort((a, b) => a - b);
    let median = null;
    if (xCoords.length > 0) {
      const mid = Math.floor(xCoords.length / 2);
      median = xCoords.length % 2 !== 0 ? xCoords[mid] : (xCoords[mid - 1] + xCoords[mid]) / 2.0;
    }

    const thirdsCount = { def: 0, mid: 0, att: 0 };
    validActions.forEach(a => {
        if (a.x < 33.3) thirdsCount.def++;
        else if (a.x < 66.6) thirdsCount.mid++;
        else thirdsCount.att++;
    });

    return { medianX: median, thirds: thirdsCount, totalValid: validActions.length };
  }, [teamData]);

  // ── Display data based on active tab ────────────────────────────────────
  const displayActions = isPressing ? pressingData.actions : teamData;

  // Transformation Helpers
  const scaleX = (val) => (val / 100) * 105;
  const scaleY = (val) => ((100 - val) / 100) * 68;

  const renderShape = (action, idx) => {
    const cx = scaleX(action.x);
    const cy = scaleY(action.y);
    const isUnsuccessful = action.outcome === 'Unsuccessful';

    let markerClass = `dv-marker ${teamClass}`;
    if (isPressing) {
      markerClass += action.leadsToShot ? ' turnover-glow' : ' press-normal';
    } else {
      markerClass += isUnsuccessful ? ' unsuccessful' : '';
    }

    const handleEnter = () => setHoveredAction(action);
    const handleLeave = () => setHoveredAction(null);

    if (isPressing) {
      // Pressing tab: all markers are squares (BallRecovery only)
      return (
        <rect
          key={`action-${idx}`}
          x={cx - 1.6} y={cy - 1.6}
          width="3.2" height="3.2"
          rx="0.5"
          className={markerClass}
          onMouseEnter={handleEnter} onMouseLeave={handleLeave}
        />
      );
    }

    // All Actions tab: shape per type
    switch (action.type) {
        case 'Interception':
            return (
                <polygon 
                    key={`action-${idx}`}
                    points={`${cx},${cy-2.5} ${cx-2},${cy+2} ${cx+2},${cy+2}`} 
                    className={markerClass}
                    onMouseEnter={handleEnter} onMouseLeave={handleLeave}
                />
            );
        case 'Foul':
            return (
                <path 
                    key={`action-${idx}`}
                    d={`M ${cx-1.5} ${cy-1.5} L ${cx+1.5} ${cy+1.5} M ${cx-1.5} ${cy+1.5} L ${cx+1.5} ${cy-1.5}`} 
                    className={markerClass} 
                    strokeWidth="1"
                    stroke={isUnsuccessful ? 'var(--text-muted)' : `var(--color-${teamClass})`}
                    fill="none"
                    onMouseEnter={handleEnter} onMouseLeave={handleLeave}
                />
            );
        default: // Tackles & Challenges
            return (
                <circle 
                    key={`action-${idx}`}
                    cx={cx} cy={cy} r="1.8" 
                    className={markerClass}
                    onMouseEnter={handleEnter} onMouseLeave={handleLeave}
                />
            );
    }
  };

  const handleMouseMove = (e) => setMousePos({ x: e.clientX, y: e.clientY });

  if (!isDataValid) {
    return <div className="view-loading">Loading Defensive Actions…</div>;
  }

  return (
    <div className="defensive-view" onMouseMove={handleMouseMove}>
      <div className="dv-header">
        <div className="dv-filters">
          {/* Team Selector */}
          <div className="dv-btn-group">
            <button
              className={`dv-btn ${activeTeam === 'home' ? `active home` : ''}`}
              onClick={() => setActiveTeam('home')}
            >
              {homeTeam}
            </button>
            <button
              className={`dv-btn ${activeTeam === 'away' ? `active away` : ''}`}
              onClick={() => setActiveTeam('away')}
            >
              {awayTeam}
            </button>
          </div>

          {/* Sub-tab Selector (below team names) */}
          <div className="dv-btn-group">
            <button
              className={`dv-btn ${activeTab === 'all' ? 'active' : ''}`}
              onClick={() => setActiveTab('all')}
            >
              All Actions
            </button>
            <button
              className={`dv-btn ${activeTab === 'pressing' ? 'active' : ''}`}
              onClick={() => setActiveTab('pressing')}
            >
              Pressing
            </button>
          </div>
        </div>
      </div>

      <div className="dv-body">
        
        {/* Pitch Area */}
        <div className="dv-pitch-container">
          <svg viewBox="0 0 105 68" className="dv-pitch-svg" preserveAspectRatio="xMidYMid meet">
            <rect width="105" height="68" className="dv-turf" />

            {/* Base Pitch Lines */}
            <g className="dv-lines" strokeWidth="0.3" fill="none">
               <rect x="0" y="0" width="105" height="68" />
               <line x1="52.5" y1="0" x2="52.5" y2="68" />
               <circle cx="52.5" cy="34" r="9.15" />
               
               <rect x="0" y="13.84" width="16.5" height="40.32" />
               <rect x="0" y="24.84" width="5.5" height="18.32" />
               <circle cx="11" cy="34" r="0.3" />
               <path d="M 16.5 26.7 A 9.15 9.15 0 0 1 16.5 41.3" />

               <rect x="88.5" y="13.84" width="16.5" height="40.32" />
               <rect x="99.5" y="24.84" width="5.5" height="18.32" />
               <circle cx="94" cy="34" r="0.3" />
               <path d="M 88.5 41.3 A 9.15 9.15 0 0 1 88.5 26.7" />
            </g>

            {/* Pressing Zone Highlight (opponent half) */}
            {isPressing && (
              <rect x="52.5" y="0" width="52.5" height="68" className="dv-press-zone" />
            )}

            {/* Median Pressing Line (All Actions tab only) */}
            {!isPressing && medianX !== null && (
                <line 
                  x1={scaleX(medianX)} y1="0" 
                  x2={scaleX(medianX)} y2="68" 
                  className={`dv-median-line ${teamClass}`} 
                />
            )}

            {/* Shot Connection Line (Pressing tab, on hover) */}
            {isPressing && hoveredAction && hoveredAction.leadsToShot && hoveredAction.shotX != null && (
              <line
                x1={scaleX(hoveredAction.x)}
                y1={scaleY(hoveredAction.y)}
                x2={scaleX(hoveredAction.shotX)}
                y2={scaleY(hoveredAction.shotY)}
                className={`dv-shot-chain ${teamClass}`}
              />
            )}

            {/* Shot Target Marker (on hover) */}
            {isPressing && hoveredAction && hoveredAction.leadsToShot && hoveredAction.shotX != null && (
              <g>
                <circle
                  cx={scaleX(hoveredAction.shotX)}
                  cy={scaleY(hoveredAction.shotY)}
                  r="2.5"
                  className="dv-shot-target"
                />
                <text
                  x={scaleX(hoveredAction.shotX)}
                  y={scaleY(hoveredAction.shotY) - 4}
                  className="dv-shot-label"
                  textAnchor="middle"
                >
                  {hoveredAction.shotOutcome === 'Goal' ? '⚽' : '🎯'}
                </text>
              </g>
            )}

            {/* Action Group */}
            <g className="dv-actions">
              {displayActions.map(renderShape)}
            </g>
          </svg>

          {hoveredAction && (
          <div 
            className="dv-tooltip"
            style={{ 
              left: mousePos.x + 15, 
              top: mousePos.y - 40,
              position: 'fixed',
              pointerEvents: 'none'
            }}
          >
            <div className="dv-tt-player">{hoveredAction.player}</div>
            <div className="dv-tt-row">
              <span>Action</span>
              <span className="val">{hoveredAction.type}</span>
            </div>
            <div className="dv-tt-row">
              <span>Outcome</span>
              <span className="val" style={{ color: hoveredAction.outcome === 'Unsuccessful' ? 'var(--color-off-target)' : 'var(--color-on-target)'}}>{hoveredAction.outcome}</span>
            </div>
            <div className="dv-tt-row">
              <span>Minute</span>
              <span className="val">{hoveredAction.minute}'</span>
            </div>
            {isPressing && hoveredAction.leadsToShot && (
              <div className="dv-tt-shot-chain">
                <div className="dv-tt-chain-label">→ Led to Shot</div>
                <div className="dv-tt-row">
                  <span>Shooter</span>
                  <span className="val">{hoveredAction.shotPlayer}</span>
                </div>
                <div className="dv-tt-row">
                  <span>Result</span>
                  <span className="val" style={{ color: hoveredAction.shotOutcome === 'Goal' ? 'var(--color-on-target)' : 'var(--text-primary)' }}>
                    {hoveredAction.shotOutcome}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
        </div>

        {/* Sidebar Analytics */}
        <div className="dv-sidebar">

          {/* ── Pressing Sidebar ── */}
          {isPressing ? (
            <>
              <div className="dv-stat-block">
                <div className="dv-stat-title">High Recoveries</div>
                <div className={`dv-stat-big ${teamClass}`}>{pressingData.highRecoveries}</div>
                <div className="dv-tt-dim">Ball recoveries in opponent's half</div>
              </div>

              <div className="dv-stat-block">
                <div className="dv-stat-title">Led to Shot</div>
                <div className={`dv-stat-big ${teamClass}`}>{pressingData.ledToShot}</div>
                <div className="dv-tt-dim">High recoveries followed by a shot within 15s</div>
              </div>

              <div className="dv-stat-block">
                <div className="dv-stat-title">Top Pressers</div>
                {pressingData.topPressers.length > 0 ? (
                  <ul className="dv-presser-list">
                    {pressingData.topPressers.map((p, idx) => (
                      <li key={idx} className="dv-presser-item">
                        <span className="dv-presser-rank">{idx + 1}</span>
                        <span className="dv-presser-name">{p.player}</span>
                        <span className="dv-presser-stats">
                          <span className="dv-presser-total">{p.total}</span>
                          {p.shots > 0 && <span className="dv-presser-shots">({p.shots} → shot)</span>}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="dv-tt-dim">No high recoveries recorded.</div>
                )}
              </div>

              <div className="dv-legend">
                <div className="dv-legend-item">
                  <div className="dv-legend-shape">
                    <svg viewBox="0 0 24 24" width="24" height="24">
                      <rect x="5" y="5" width="14" height="14" rx="2" fill="#f97316" stroke="var(--bg-page)" strokeWidth="2" />
                    </svg>
                  </div>
                  <span>Led to Shot (High Turnover)</span>
                </div>
                <div className="dv-legend-item">
                  <div className="dv-legend-shape">
                    <svg viewBox="0 0 24 24" width="24" height="24">
                      <rect x="5" y="5" width="14" height="14" rx="2" fill={`var(--color-${teamClass})`} stroke="var(--bg-page)" strokeWidth="2" opacity="0.6" />
                    </svg>
                  </div>
                  <span>Ball Recovery (No Shot)</span>
                </div>
                <div className="dv-legend-item" style={{ marginTop: '8px' }}>
                  <div className="dv-legend-shape">
                    <svg viewBox="0 0 24 24" width="24" height="24">
                      <rect x="0" y="0" width="24" height="24" fill="rgba(249,115,22,0.08)" rx="4" />
                    </svg>
                  </div>
                  <span>Opponent Half (Press Zone)</span>
                </div>
              </div>
            </>
          ) : (
            /* ── All Actions Sidebar ── */
            <>
              <div className="dv-stat-block">
                <div className="dv-stat-title">Average Pressing Height</div>
                <div className="dv-stat-big">{medianX ? medianX.toFixed(1) : '--'}<span className="dv-stat-unit">m</span></div>
                <div className="dv-tt-dim">Median X-coordinate of disruptions</div>
              </div>

              <div className="dv-stat-block">
                <div className="dv-stat-title">Actions by Third</div>
                <ul className="dv-thirds-list">
                    <li>
                        <div className="dv-thirds-item">
                            <span>Attacking 1/3 (High Press)</span>
                            <span>{totalValid ? Math.round((thirds.att / totalValid)*100) : 0}%</span>
                        </div>
                        <div className="dv-thirds-bar-bg">
                            <div className={`dv-thirds-bar-fill ${teamClass}`} style={{ width: `${totalValid ? (thirds.att / totalValid)*100 : 0}%`}}></div>
                        </div>
                    </li>
                    <li>
                        <div className="dv-thirds-item">
                            <span>Middle 1/3</span>
                            <span>{totalValid ? Math.round((thirds.mid / totalValid)*100) : 0}%</span>
                        </div>
                        <div className="dv-thirds-bar-bg">
                            <div className={`dv-thirds-bar-fill ${teamClass}`} style={{ width: `${totalValid ? (thirds.mid / totalValid)*100 : 0}%`}}></div>
                        </div>
                    </li>
                    <li>
                        <div className="dv-thirds-item">
                            <span>Defensive 1/3 (Low Block)</span>
                            <span>{totalValid ? Math.round((thirds.def / totalValid)*100) : 0}%</span>
                        </div>
                        <div className="dv-thirds-bar-bg">
                            <div className={`dv-thirds-bar-fill ${teamClass}`} style={{ width: `${totalValid ? (thirds.def / totalValid)*100 : 0}%`}}></div>
                        </div>
                    </li>
                </ul>
              </div>

              <div className="dv-legend">
                <div className="dv-legend-item">
                    <div className="dv-legend-shape">
                        <svg viewBox="0 0 24 24" width="24" height="24">
                            <circle cx="12" cy="12" r="9" fill={`var(--color-${teamClass})`} stroke="var(--bg-page)" strokeWidth="2" />
                        </svg>
                    </div>
                    <span>Tackle / Challenge</span>
                </div>
                <div className="dv-legend-item">
                    <div className="dv-legend-shape">
                        <svg viewBox="0 0 24 24" width="24" height="24">
                            <polygon points="12,3 4,20 20,20" fill={`var(--color-${teamClass})`} stroke="var(--bg-page)" strokeWidth="2" />
                        </svg>
                    </div>
                    <span>Interception</span>
                </div>
                <div className="dv-legend-item">
                    <div className="dv-legend-shape">
                        <svg viewBox="0 0 24 24" width="24" height="24">
                            <path d="M 5 5 L 19 19 M 5 19 L 19 5" stroke={`var(--color-${teamClass})`} strokeWidth="4" strokeLinecap="round" />
                        </svg>
                    </div>
                    <span>Foul</span>
                </div>
                <div className="dv-legend-item" style={{ marginTop: '8px' }}>
                    <div className="dv-legend-shape">
                        <svg viewBox="0 0 24 24" width="24" height="24">
                            <circle cx="12" cy="12" r="9" fill="var(--text-muted)" opacity="0.4" />
                        </svg>
                    </div>
                    <span>Unsuccessful Action</span>
                </div>
                <div className="dv-legend-item">
                    <div className="dv-legend-shape" style={{ width: '24px' }}>
                        <svg viewBox="0 0 24 24" width="24" height="24">
                            <line x1="12" y1="0" x2="12" y2="24" stroke={`var(--color-${teamClass})`} strokeDasharray="4,3" strokeWidth="3" strokeLinecap="round" />
                        </svg>
                    </div>
                    <span>Average Pressing Line</span>
                </div>
              </div>
            </>
          )}
        </div>

      </div>
    </div>
  );
}
