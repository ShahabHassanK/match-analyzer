import { useState, useMemo } from 'react';
import './ZoneEntriesView.css';

const ZONE_CONFIG = {
  finalThird:  { label: 'Final Third', key: 'finalThird',  countKey: 'finalThirdCount',  hasFilter: true,  isTouch: false },
  zone14:      { label: 'Zone 14',     key: 'zone14',       countKey: 'zone14Count',       hasFilter: true,  isTouch: false },
  box:         { label: 'Box Entries', key: 'box',          countKey: 'boxCount',           hasFilter: true,  isTouch: false },
  throughBall: { label: 'Through Balls', key: 'throughBall', countKey: 'throughBallCount', hasFilter: false, isTouch: false },
  boxTouches:  { label: 'Box Touches',  key: 'boxTouches',  countKey: 'boxTouchesCount',   hasFilter: false, isTouch: true  },
};

export default function ZoneEntriesView({ data, homeTeam, awayTeam }) {
  const [activeTeam, setActiveTeam] = useState('home');
  const [activeZone, setActiveZone] = useState('finalThird');
  const [entryFilter, setEntryFilter] = useState('all'); // 'all' | 'pass' | 'carry'
  const [hoveredItem, setHoveredItem] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  const isDataValid = data && data.home && data.away;
  const teamData = isDataValid ? (activeTeam === 'home' ? data.home : data.away) : {};
  const teamClass = activeTeam === 'home' ? 'home' : 'away';
  const teamName = activeTeam === 'home' ? homeTeam : awayTeam;
  const config = ZONE_CONFIG[activeZone];

  // Get raw entries/touches for active tab
  const rawVectors = config.isTouch ? [] : (teamData[`${config.key}Entries`] || []);
  const rawTouches = config.isTouch ? (teamData['boxTouches'] || []) : [];
  const totalCount = teamData[config.countKey] || 0;

  // Apply pass/carry filter for vector tabs
  const vectors = useMemo(() => {
    if (config.isTouch) return [];
    if (activeZone === 'throughBall') return rawVectors;
    if (entryFilter === 'pass') return rawVectors.filter(v => v.type === 'Pass');
    if (entryFilter === 'carry') return rawVectors.filter(v => v.type === 'Carry');
    return rawVectors;
  }, [rawVectors, entryFilter, activeZone, config.isTouch]);

  const isThroughBallTab = activeZone === 'throughBall';
  const successfulVectors = isThroughBallTab ? vectors.filter(v => v.outcome === 'Successful') : vectors;
  const displayCount = isThroughBallTab ? successfulVectors.length : (config.isTouch ? rawTouches.length : vectors.length);

  // Top Players
  const topPlayers = useMemo(() => {
    const source = config.isTouch ? rawTouches : successfulVectors;
    const counts = {};
    source.forEach(v => {
      const p = v.player || 'Unknown';
      counts[p] = (counts[p] || 0) + 1;
    });
    return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 3);
  }, [successfulVectors, rawTouches, config.isTouch]);

  // Geometry helpers
  const scaleX = (val) => (val / 100) * 105;
  const scaleY = (val) => ((100 - val) / 100) * 68;

  const handleMouseMove = (e) => setMousePos({ x: e.clientX, y: e.clientY });

  // Reset filter when switching zones
  const handleZoneChange = (zone) => {
    setActiveZone(zone);
    setEntryFilter('all');
  };

  if (!isDataValid) {
    return <div className="view-loading">Loading Creative Play…</div>;
  }

  // Summary label
  const summaryLabel = isThroughBallTab
    ? `Successful (${totalCount > 0 ? Math.round((successfulVectors.length / totalCount) * 100) : 0}% success)`
    : config.isTouch
    ? 'Successful Box Touches'
    : entryFilter !== 'all'
    ? `${entryFilter === 'pass' ? 'Passes' : 'Carries'} (${displayCount} of ${totalCount})`
    : 'Successful Entries';

  return (
    <div className="zone-view" onMouseMove={handleMouseMove}>
      <div className="zv-header">
        <div className="zv-filters">

          {/* Team Toggle */}
          <div className="zv-btn-group">
            <button
              className={`zv-btn ${activeTeam === 'home' ? 'active home' : ''}`}
              onClick={() => setActiveTeam('home')}
            >
              {homeTeam}
            </button>
            <button
              className={`zv-btn ${activeTeam === 'away' ? 'active away' : ''}`}
              onClick={() => setActiveTeam('away')}
            >
              {awayTeam}
            </button>
          </div>

          {/* Zone Toggle */}
          <div className="zv-btn-group">
            {Object.entries(ZONE_CONFIG).map(([id, cfg]) => (
              <button
                key={id}
                className={`zv-btn ${activeZone === id ? 'active' : ''}`}
                onClick={() => handleZoneChange(id)}
              >
                {cfg.label}
              </button>
            ))}
          </div>

          {/* Pass / Carry Filter — only show on vector tabs that support it */}
          {config.hasFilter && (
            <div className="zv-btn-group zv-filter-group">
              {['all', 'pass', 'carry'].map(f => (
                <button
                  key={f}
                  className={`zv-btn zv-filter-btn ${entryFilter === f ? `active ${teamClass}` : ''}`}
                  onClick={() => setEntryFilter(f)}
                >
                  {f === 'all' ? 'All' : f === 'pass' ? '→ Passes' : '⚡ Carries'}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Summary Count */}
        <div className="zv-summary-container">
          <div className="zv-summary">
            <div className={`zv-stat ${teamClass}`}>{displayCount}</div>
            <div className="zv-stat-label">{summaryLabel}</div>
          </div>
        </div>
      </div>

      <div className="zv-body" style={{ display: 'flex', gap: '24px', alignItems: 'flex-start' }}>

        {/* Sidebar: Top Players + Legend */}
        <div className="zv-top-players">
          <h4 className="zv-top-title">
            {config.isTouch ? 'Top Box Touchers (Successful)' : isThroughBallTab ? 'Top (Through Balls)' : `Top Penetrators (${config.label})`}
          </h4>
          {topPlayers.length > 0 ? (
            <ul className="zv-player-list">
              {topPlayers.map(([player, count], idx) => (
                <li key={idx}>
                  <span className="rank">{idx + 1}</span>
                  <span className="name">{player}</span>
                  <span className={`count ${teamClass}`}>{count}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="zv-empty">No data logged.</p>
          )}

          {/* Legend */}
          <div className="zv-legend">
            {config.isTouch ? (
              <>
                <div className="zv-legend-item">
                  <div className={`zv-legend-dot ${teamClass}`} />
                  <span>Touch in Box</span>
                </div>
              </>
            ) : isThroughBallTab ? (
              <>
                <div className="zv-legend-item">
                  <div className={`zv-legend-line solid ${teamClass}`} />
                  <span>Successful Pass</span>
                </div>
                <div className="zv-legend-item">
                  <div className="zv-legend-line dashed" style={{ borderTopColor: '#ef4444' }} />
                  <span>Unsuccessful</span>
                </div>
              </>
            ) : (
              <>
                {(entryFilter === 'all' || entryFilter === 'pass') && (
                  <div className="zv-legend-item">
                    <div className={`zv-legend-line solid ${teamClass}`} />
                    <span>Pass</span>
                  </div>
                )}
                {(entryFilter === 'all' || entryFilter === 'carry') && (
                  <div className="zv-legend-item">
                    <div className={`zv-legend-line dashed ${teamClass}`} />
                    <span>Carry (Dribble)</span>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Tooltip */}
        {hoveredItem && (
          <div
            className="zv-tooltip"
            style={{ left: mousePos.x + 15, top: mousePos.y - 40, position: 'fixed' }}
          >
            <div className="zv-tt-player">{hoveredItem.player}</div>
            <div className="zv-tt-row">
              <span>Action</span>
              <span className="val">{hoveredItem.type}</span>
            </div>
            <div className="zv-tt-row">
              <span>Minute</span>
              <span className="val">{hoveredItem.minute}'</span>
            </div>
            <div className="zv-tt-row">
              <span>Outcome</span>
              <span className="val" style={{ color: hoveredItem.outcome === 'Successful' ? 'inherit' : '#ef4444' }}>
                {hoveredItem.outcome}
              </span>
            </div>
            {hoveredItem.type === 'Carry' && (
              <div className="zv-tt-dim">(Dribbling progression)</div>
            )}
          </div>
        )}

        {/* Pitch */}
        <div className="zv-pitch-container" style={{ flex: '1', minWidth: '65%' }}>
          <svg viewBox="0 0 105 68" className="zv-pitch-svg" preserveAspectRatio="xMidYMid meet">
            <defs>
              <marker id={`arrow-${teamClass}-pass`} viewBox="0 0 10 10" refX="7" refY="5" markerWidth="3.5" markerHeight="3.5" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" className={`zv-arrowhead pass ${teamClass}`} />
              </marker>
              <marker id={`arrow-${teamClass}-carry`} viewBox="0 0 10 10" refX="7" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">
                <path d="M 0 1 L 10 5 L 0 9 z" className={`zv-arrowhead carry ${teamClass}`} />
              </marker>
              <marker id="arrow-unsuccessful-pass" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="3.5" markerHeight="3.5" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" opacity="0.6" />
              </marker>
              <filter id="touch-glow">
                <feGaussianBlur stdDeviation="0.8" result="blur" />
                <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
            </defs>

            {/* Pitch surface */}
            <rect width="105" height="68" className="zv-turf" />

            {/* Target zone highlight */}
            <g className="zv-target-zone active">
              {activeZone === 'finalThird' && (
                <rect x="67" y="0" width="38" height="68" />
              )}
              {activeZone === 'zone14' && (
                <rect x={(72 / 100) * 105} y={(30 / 100) * 68} width={(11 / 100) * 105} height={(40 / 100) * 68} />
              )}
              {(activeZone === 'box' || activeZone === 'boxTouches') && (
                <rect x="88.5" y="13.84" width="16.5" height="40.32" />
              )}
            </g>

            {/* Pitch lines */}
            <g className="zv-lines" strokeWidth="0.3" fill="none">
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

            {/* ── Vector arrows (all tabs except boxTouches) ── */}
            {!config.isTouch && (
              <g className="zv-vectors">
                {vectors.map((vec, idx) => {
                  const sx = scaleX(vec.startX);
                  const sy = scaleY(vec.startY);
                  const ex = scaleX(vec.endX);
                  const ey = scaleY(vec.endY);
                  const isCarry = vec.type === 'Carry';
                  const isUnsuccessful = vec.outcome !== 'Successful';
                  const strokeDash = isCarry ? '1.5, 1.2' : (isUnsuccessful ? '2, 1.5' : 'none');
                  const opacity = isUnsuccessful ? 0.6 : (isCarry ? 0.95 : 0.75);
                  const strokeW = isCarry ? '0.6' : '0.45';
                  let marker = `url(#arrow-${teamClass}-pass)`;
                  if (isUnsuccessful) marker = 'url(#arrow-unsuccessful-pass)';
                  else if (isCarry) marker = `url(#arrow-${teamClass}-carry)`;
                  const strokeColor = isUnsuccessful ? '#ef4444' : undefined;
                  return (
                    <line
                      key={idx}
                      x1={sx} y1={sy} x2={ex} y2={ey}
                      className={`zv-vector ${isUnsuccessful ? '' : teamClass}`}
                      stroke={strokeColor}
                      strokeWidth={strokeW}
                      strokeDasharray={strokeDash}
                      strokeOpacity={opacity}
                      markerEnd={marker}
                      fill="none"
                      onMouseEnter={() => setHoveredItem(vec)}
                      onMouseLeave={() => setHoveredItem(null)}
                    />
                  );
                })}
              </g>
            )}

            {/* ── Touch dots (boxTouches tab) ── */}
            {config.isTouch && (
              <g className="zv-touches">
                {rawTouches.map((touch, idx) => {
                  const cx = scaleX(touch.x);
                  const cy = scaleY(touch.y);
                  const isGoal = touch.type === 'Goal';
                  const isShot = ['SavedShot', 'MissedShots', 'ShotOnPost', 'BlockedShot', 'AttemptSaved'].includes(touch.type);
                  return (
                    <circle
                      key={idx}
                      cx={cx}
                      cy={cy}
                      r={isGoal ? 1.6 : isShot ? 1.4 : 1.1}
                      className={`zv-touch-dot ${teamClass} ${isGoal ? 'goal' : isShot ? 'shot' : ''}`}
                      filter={isGoal ? 'url(#touch-glow)' : undefined}
                      onMouseEnter={() => setHoveredItem(touch)}
                      onMouseLeave={() => setHoveredItem(null)}
                    />
                  );
                })}
              </g>
            )}
          </svg>
        </div>
      </div>
    </div>
  );
}
