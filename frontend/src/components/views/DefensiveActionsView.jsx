import { useState, useMemo } from 'react';
import './DefensiveActionsView.css';

export default function DefensiveActionsView({ data, homeTeam, awayTeam }) {
  const [activeTeam, setActiveTeam] = useState('home');
  const [hoveredAction, setHoveredAction] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  const isDataValid = data && data.home && data.away;
  const teamData = isDataValid ? (activeTeam === 'home' ? data.home : data.away) : [];
  const teamClass = activeTeam === 'home' ? 'home' : 'away';

  // Calculate geometry & aggregated stats
  const { medianX, thirds, totalValid } = useMemo(() => {
    if (!teamData.length) return { medianX: null, thirds: { def: 0, mid: 0, att: 0 }, totalValid: 0 };

    const validActions = teamData.filter(a => a.outcome !== 'Unsuccessful');
    
    // 1. Median Pressing Line — open play only (exclude set piece defensive actions)
    const openPlayActions = validActions.filter(a => !a.isSetPiece);
    const xCoords = openPlayActions.map(a => a.x).sort((a, b) => a - b);
    let median = null;
    if (xCoords.length > 0) {
      const mid = Math.floor(xCoords.length / 2);
      median = xCoords.length % 2 !== 0 ? xCoords[mid] : (xCoords[mid - 1] + xCoords[mid]) / 2.0;
    }

    // 2. Pitch Thirds Distribution Calculation (uses ALL valid actions)
    const thirdsCount = { def: 0, mid: 0, att: 0 };
    validActions.forEach(a => {
        if (a.x < 33.3) thirdsCount.def++;
        else if (a.x < 66.6) thirdsCount.mid++;
        else thirdsCount.att++;
    });

    return { medianX: median, thirds: thirdsCount, totalValid: validActions.length };
  }, [teamData]);


  // Transformation Helpers
  const scaleX = (val) => (val / 100) * 105;
  const scaleY = (val) => (val / 100) * 68;
  const renderShape = (action, idx) => {
    const cx = scaleX(action.x);
    const cy = scaleY(action.y);
    const isUnsuccessful = action.outcome === 'Unsuccessful';
    const className = `dv-marker ${teamClass} ${isUnsuccessful ? 'unsuccessful' : ''}`;

    const handleEnter = () => setHoveredAction(action);
    const handleLeave = () => setHoveredAction(null);

    // Shape Dictionary based on action type
    switch (action.type) {
        case 'Interception':
            return (
                <polygon 
                    key={`action-${idx}`}
                    points={`${cx},${cy-2.5} ${cx-2},${cy+2} ${cx+2},${cy+2}`} 
                    className={className}
                    onMouseEnter={handleEnter} onMouseLeave={handleLeave}
                />
            );
        case 'Foul':
            return (
                <path 
                    key={`action-${idx}`}
                    d={`M ${cx-1.5} ${cy-1.5} L ${cx+1.5} ${cy+1.5} M ${cx-1.5} ${cy+1.5} L ${cx+1.5} ${cy-1.5}`} 
                    className={className} 
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
                    className={className}
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

            {/* Median Pressing Line */}
            {medianX !== null && (
                <line 
                  x1={scaleX(medianX)} y1="0" 
                  x2={scaleX(medianX)} y2="68" 
                  className={`dv-median-line ${teamClass}`} 
                />
            )}

            {/* Action Group */}
            <g className="dv-actions">
              {teamData.map(renderShape)}
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
          </div>
        )}
        </div>

        {/* Sidebar Analytics */}
        <div className="dv-sidebar">
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
        </div>

      </div>
    </div>
  );
}
