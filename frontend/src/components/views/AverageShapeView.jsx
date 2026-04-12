import { useState } from 'react';
import './AverageShapeView.css';

export default function AverageShapeView({ data, homeTeam, awayTeam }) {
  const [activeTeam, setActiveTeam] = useState('home');
  const [hoveredPlayer, setHoveredPlayer] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  if (!data || !data.home || !data.away) {
    return <div className="view-loading">Loading Average Shape data...</div>;
  }

  const teamData = data[activeTeam];
  const teamClass = activeTeam; // 'home' or 'away'

  const handleMouseMove = (e) => {
    setMousePos({ x: e.clientX, y: e.clientY });
  };

  // Convert (0-100) raw coordinates to pitch coordinates (105x68)
  const scaleX = (val) => (val / 100) * 105;
  const scaleY = (val) => ((100 - val) / 100) * 68;

  const renderTooltip = () => {
    if (!hoveredPlayer) return null;
    return (
      <div 
        className="as-tooltip" 
        style={{ 
          left: mousePos.x + 15, 
          top: mousePos.y - 40,
          position: 'fixed'
        }}
      >
        <div className="as-tt-player">{hoveredPlayer.player}</div>
        <div className="as-tt-row">
            <span>Touches</span>
            <span className="val">{hoveredPlayer.touches}</span>
        </div>
        <div className="as-tt-row">
            <span>Passes Played</span>
            <span className="val">{hoveredPlayer.passesPlayed || 0}</span>
        </div>
        <div className="as-tt-row">
            <span>Passes Received</span>
            <span className="val">{hoveredPlayer.passesReceived || 0}</span>
        </div>
        {hoveredPlayer.isSub && <div className="as-tt-sub">Substitute</div>}
      </div>
    );
  };

  return (
    <div className="average-shape-view" onMouseMove={handleMouseMove}>
      <div className="as-header">
        <div className="as-controls">
          <div className="as-btn-group">
            <button
              className={`as-btn ${activeTeam === 'home' ? 'active home' : ''}`}
              onClick={() => setActiveTeam('home')}
            >
              {homeTeam}
            </button>
            <button
              className={`as-btn ${activeTeam === 'away' ? 'active away' : ''}`}
              onClick={() => setActiveTeam('away')}
            >
              {awayTeam}
            </button>
          </div>
        </div>
        <div className="as-legend">
           <div className="as-legend-item">
             <div className={`as-node-legend solid ${teamClass}`}></div>
             <span>Starters</span>
           </div>
           <div className="as-legend-item">
             <div className={`as-node-legend ghost ${teamClass}`}></div>
             <span>Substitutes</span>
           </div>
        </div>
      </div>

      <div className="as-body">
        <div className="as-pitch-container">
          <svg viewBox="0 0 105 68" className="as-pitch-svg" preserveAspectRatio="xMidYMid meet">
            {/* Pitch Background */}
            <rect width="105" height="68" className="as-turf" />
            
            <g className="as-lines" strokeWidth="0.3" stroke="rgba(255, 255, 255, 0.25)" fill="none">
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

            {/* Nodes */}
            {teamData.map((node, idx) => {
              const nx = scaleX(node.x);
              const ny = scaleY(node.y);
              const isSubClass = node.isSub ? 'sub' : 'starter';

              return (
                <g 
                  key={idx} 
                  className="as-node-group"
                  onMouseEnter={() => setHoveredPlayer(node)}
                  onMouseLeave={() => setHoveredPlayer(null)}
                >
                  <circle
                    cx={nx}
                    cy={ny}
                    r="2.8"
                    className={`as-node ${teamClass} ${isSubClass}`}
                  />
                  <text
                    x={nx}
                    y={ny}
                    dy="0.3em"
                    textAnchor="middle"
                    className="as-node-text"
                  >
                    {node.initials}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>
      {renderTooltip()}
    </div>
  );
}
