import { useState, useMemo } from 'react';
import './ZoneEntriesView.css';

export default function ZoneEntriesView({ data, homeTeam, awayTeam }) {
  const [activeTeam, setActiveTeam] = useState('home');
  const [activeZone, setActiveZone] = useState('finalThird');
  const [hoveredVector, setHoveredVector] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  // Safe data extraction so hooks don't crash before early return
  const isDataValid = data && data.home && data.away;
  const teamData = isDataValid ? (activeTeam === 'home' ? data.home : data.away) : {};
  const teamClass = activeTeam === 'home' ? 'home' : 'away';
  const teamName = activeTeam === 'home' ? homeTeam : awayTeam;

  const vectors = teamData[`${activeZone}Entries`] || [];
  const entryCount = teamData[`${activeZone}Count`] || 0;

  // ── Calculate Top 3 Players ──────────────────────────────────────────────
  const topPlayers = useMemo(() => {
    const counts = {};
    vectors.forEach(v => {
      counts[v.player] = (counts[v.player] || 0) + 1;
    });
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3);
  }, [vectors]);

  // Geometry Translation
  const scaleX = (val) => (val / 100) * 105;
  const scaleY = (val) => (val / 100) * 68;

  const handleMouseMove = (e) => {
    setMousePos({ x: e.clientX, y: e.clientY });
  };

  if (!isDataValid) {
    return <div className="view-loading">Loading Zone Entries…</div>;
  }

  return (
    <div className="zone-view" onMouseMove={handleMouseMove}>
      <div className="zv-header">
        <div className="zv-filters">
          <div className="zv-btn-group">
            <button
              className={`zv-btn ${activeTeam === 'home' ? `active home` : ''}`}
              onClick={() => setActiveTeam('home')}
            >
              {homeTeam}
            </button>
            <button
              className={`zv-btn ${activeTeam === 'away' ? `active away` : ''}`}
              onClick={() => setActiveTeam('away')}
            >
              {awayTeam}
            </button>
          </div>
          <div className="zv-btn-group" style={{ marginTop: '0' }}>
            <button
              className={`zv-btn ${activeZone === 'finalThird' ? 'active' : ''}`}
              onClick={() => setActiveZone('finalThird')}
            >
              Final Third
            </button>
            <button
              className={`zv-btn ${activeZone === 'zone14' ? 'active' : ''}`}
              onClick={() => setActiveZone('zone14')}
            >
              Zone 14
            </button>
          </div>
        </div>

        <div className="zv-summary-container">
            <div className="zv-summary">
            <div className={`zv-stat ${teamClass}`}>{entryCount}</div>
            <div className="zv-stat-label">Successful Entries</div>
            </div>
        </div>
      </div>

      <div className="zv-body" style={{ display: 'flex', gap: '24px', alignItems: 'flex-start' }}>
        
        {/* Top Players Panel Overlaid on the pitch container (left side) */}
        <div className="zv-top-players">
           <h4 className="zv-top-title">Top Penetrators ({activeZone === 'zone14' ? 'Z14' : 'Final 1/3'})</h4>
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
             <p className="zv-empty">No entries logged.</p>
           )}
           
           {/* Legend */}
           <div className="zv-legend">
              <div className="zv-legend-item">
                  <div className={`zv-legend-line solid ${teamClass}`}></div>
                  <span>Pass</span>
              </div>
              <div className="zv-legend-item">
                  <div className={`zv-legend-line dashed ${teamClass}`}></div>
                  <span>Carry (Dribble)</span>
              </div>
           </div>
        </div>

        {hoveredVector && (
          <div 
            className="zv-tooltip"
            style={{ 
              left: mousePos.x + 15, 
              top: mousePos.y - 40,
              position: 'fixed' 
            }}
          >
            <div className="zv-tt-player">{hoveredVector.player}</div>
            <div className="zv-tt-row">
              <span>Action</span>
              <span className="val">{hoveredVector.type}</span>
            </div>
            <div className="zv-tt-row">
              <span>Minute</span>
              <span className="val">{hoveredVector.minute}'</span>
            </div>
            {hoveredVector.type === 'Carry' && (
              <div className="zv-tt-dim">(Dribbling progression)</div>
            )}
            {hoveredVector.type === 'Pass' && (
              <div className="zv-tt-dim">(Passing progression)</div>
            )}
          </div>
        )}

        <div className="zv-pitch-container" style={{ flex: '1', minWidth: '65%' }}>
          <svg viewBox="0 0 105 68" className="zv-pitch-svg" preserveAspectRatio="xMidYMid meet">
            <defs>
              <marker
                id={`arrow-${teamClass}-pass`}
                viewBox="0 0 10 10"
                refX="7"
                refY="5"
                markerWidth="3.5"
                markerHeight="3.5"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" className={`zv-arrowhead pass ${teamClass}`} />
              </marker>
              
              <marker
                id={`arrow-${teamClass}-carry`}
                viewBox="0 0 10 10"
                refX="7"
                refY="5"
                markerWidth="4"
                markerHeight="4"
                orient="auto-start-reverse"
              >
                {/* Carries get a slightly distinct arrowhead */}
                <path d="M 0 1 L 10 5 L 0 9 z" className={`zv-arrowhead carry ${teamClass}`} />
              </marker>
            </defs>

            <rect width="105" height="68" className="zv-turf" />
            
            <g className="zv-target-zone active">
              {activeZone === 'finalThird' && (
                <rect x="67" y="0" width="38" height="68" />
              )}
              {activeZone === 'zone14' && (
                <rect x={(72 / 100) * 105} y={(30 / 100) * 68} width={(11 / 100) * 105} height={(40 / 100) * 68} />
              )}
            </g>

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

            <g className="zv-vectors">
              {vectors.map((vec, idx) => {
                const sx = scaleX(vec.startX);
                const sy = scaleY(vec.startY);
                const ex = scaleX(vec.endX);
                const ey = scaleY(vec.endY);
                
                const isCarry = vec.type === 'Carry';
                // Distinct stroke pattern: long dash for carry vs solid pass
                const strokeDash = isCarry ? '1.5, 1.2' : 'none';
                const opacity = isCarry ? 0.95 : 0.75;
                const strokeW = isCarry ? "0.6" : "0.45";
                const marker = isCarry ? `url(#arrow-${teamClass}-carry)` : `url(#arrow-${teamClass}-pass)`;

                return (
                  <line
                    key={idx}
                    x1={sx}
                    y1={sy}
                    x2={ex}
                    y2={ey}
                    className={`zv-vector ${teamClass}`}
                    strokeWidth={strokeW}
                    strokeDasharray={strokeDash}
                    strokeOpacity={opacity}
                    markerEnd={marker}
                    fill="none"
                    onMouseEnter={() => setHoveredVector(vec)}
                    onMouseLeave={() => setHoveredVector(null)}
                  />
                );
              })}
            </g>
          </svg>
        </div>
      </div>
    </div>
  );
}
