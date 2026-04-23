import { useState, useMemo, useRef } from 'react';
import './MomentumView.css';

const ANNOTATION_COLORS = {
  goal:         '#00F485',
  redCard:      '#ef4444',
  substitution: '#94a3b8',
};

export default function MomentumView({ data }) {
  const [hoverMinute, setHoverMinute] = useState(null);
  const [hoveredAnnotation, setHoveredAnnotation] = useState(null);
  const [annotationPos, setAnnotationPos] = useState({ x: 0, y: 0 });
  const svgRef = useRef(null);

  // Validate data
  if (!data || !data.timeline || data.timeline.length === 0) {
    return <div className="view-loading">No momentum data available.</div>;
  }

  const { homeTeam, awayTeam, timeline, annotations = [] } = data;
  const maxMinute = Math.max(...timeline.map(t => t.minute));
  
  // Find min/max values for Y-axis scaling
  let minDiff = 0;
  let maxDiff = 0;
  timeline.forEach(t => {
    if (t.difference > maxDiff) maxDiff = t.difference;
    if (t.difference < minDiff) minDiff = t.difference;
  });

  // Calculate scales (SVG dimensions: 1000x300)
  const SVG_WIDTH = 1000;
  const SVG_HEIGHT = 300;
  
  // Add some vertical padding (10%) to min/max
  const range = maxDiff - minDiff || 1; // prevent div by 0
  const yPadding = range * 0.1;
  const plotMin = minDiff - yPadding;
  const plotMax = maxDiff + yPadding;
  const plotRange = plotMax - plotMin;

  const getX = (minute) => (minute / maxMinute) * SVG_WIDTH;
  
  // In SVG, y=0 is at the top. 
  // Positive difference (home dominance) goes UP (smaller Y).
  // Negative difference (away dominance) goes DOWN (larger Y).
  const getY = (val) => SVG_HEIGHT - ((val - plotMin) / plotRange) * SVG_HEIGHT;

  const zeroY = getY(0);

  // Generate SVG path for the continuous area
  const pathData = useMemo(() => {
    if (timeline.length === 0) return '';
    
    // Start at (0, zeroY)
    let d = `M ${getX(timeline[0].minute)},${zeroY} `;
    
    // Line to each point
    timeline.forEach(t => {
      d += `L ${getX(t.minute)},${getY(t.difference)} `;
    });
    
    // Line to end zero, then close back to start zero
    d += `L ${getX(timeline[timeline.length - 1].minute)},${zeroY} Z`;
    
    return d;
  }, [timeline, plotMin, plotRange, zeroY]);

  // Handle interaction for dynamic tooltip
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  const handleMouseMove = (e) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const boundedX = Math.max(0, Math.min(x, rect.width));
    
    // Math bug fix: Use screen width (rect.width) to calculate the minute natively, not SVG viewBox width
    const calculatedMinute = Math.round((boundedX / rect.width) * maxMinute);
    setHoverMinute(calculatedMinute);
    
    // Position tooltip natively on screen with safe bounds
    let tipX = e.clientX + 20;
    
    // The tooltip width is ~220px. If it goes off the right edge of the screen, flip it left safely.
    if (tipX + 240 > window.innerWidth) {
      tipX = e.clientX - 260; 
    }
    
    // Ensure it doesn't go off the left edge if flipped too aggressively
    if (tipX < 0) tipX = 20;

    setTooltipPos({ x: tipX, y: e.clientY + 20 });
  };

  const handleMouseLeave = () => setHoverMinute(null);

  // Find active minute based on hover
  const hoverData = hoverMinute !== null ? timeline.find(t => t.minute === hoverMinute) || timeline[timeline.length - 1] : null;

  // Calculate the gradient percentage where Y=0 happens
  const zeroPercent = Math.max(0, Math.min(100, (zeroY / SVG_HEIGHT) * 100));

  return (
    <div className="momentum-view">
      <div className="mo-main-panel">
        <div className="mo-header">
          <h3 className="mo-title">Match Momentum (Rolling xT)</h3>
          <p className="mo-subtitle">
            Visualising periods of dominance based on Expected Threat generated over a 5-minute rolling window.
          </p>
        </div>

        <div className="mo-legend">
          <div className="mo-legend-item">
            <div className="mo-legend-color home"></div>
            <span>{homeTeam} Dominance</span>
          </div>
          <div className="mo-legend-item">
            <div className="mo-legend-color away"></div>
            <span>{awayTeam} Dominance</span>
          </div>
        </div>

        <div className="mo-chart-container">
          {/* Y-Axis Labels */}
          <div className="mo-y-axis">
            <span className="mo-y-label top">+{plotMax.toFixed(2)}</span>
            <span className="mo-y-label middle" style={{ top: `${zeroPercent}%` }}>0.00</span>
            <span className="mo-y-label bottom">{plotMin.toFixed(2)}</span>
          </div>

          <div className="mo-svg-wrapper">
            <svg 
              ref={svgRef}
              viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`} 
              className="mo-svg"
              onMouseMove={handleMouseMove}
              onMouseLeave={handleMouseLeave}
              preserveAspectRatio="none"
            >
              <defs>
                <linearGradient id="momentumGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--mo-color-home)" stopOpacity="0.8" />
                  <stop offset={`${zeroPercent}%`} stopColor="var(--mo-color-home)" stopOpacity="0.1" />
                  <stop offset={`${zeroPercent}%`} stopColor="var(--mo-color-away)" stopOpacity="0.1" />
                  <stop offset="100%" stopColor="var(--mo-color-away)" stopOpacity="0.8" />
                </linearGradient>
              </defs>

              {/* Zero Line */}
              <line 
                x1="0" y1={zeroY} 
                x2={SVG_WIDTH} y2={zeroY} 
                className="mo-zero-line" 
              />

              {/* Area Chart */}
              <path 
                d={pathData} 
                fill="url(#momentumGradient)" 
                className="mo-area" 
              />

              {/* Line Chart Outline */}
              <path 
                d={pathData.replace(/Z$/, '').replace(/M.*?L/, 'M')} 
                fill="none" 
                className="mo-line" 
              />

              {/* Annotation Markers */}
              {annotations.map((ann, i) => {
                const ax = getX(ann.minute);
                const color = ANNOTATION_COLORS[ann.type] || '#94a3b8';
                const isGoal = ann.type === 'goal';
                return (
                  <g
                    key={i}
                    className="mo-annotation"
                    onMouseEnter={(e) => {
                      setHoveredAnnotation(ann);
                      setAnnotationPos({ x: e.clientX + 12, y: e.clientY - 10 });
                    }}
                    onMouseLeave={() => setHoveredAnnotation(null)}
                    style={{ cursor: 'pointer' }}
                  >
                    <line
                      x1={ax} y1="0" x2={ax} y2={SVG_HEIGHT}
                      stroke={color}
                      strokeWidth={isGoal ? 2 : 1}
                      strokeDasharray={isGoal ? 'none' : '4 3'}
                      opacity="0.7"
                    />
                    {isGoal && (
                      <circle cx={ax} cy={zeroY} r="5" fill={color} opacity="0.9" />
                    )}
                  </g>
                );
              })}

              {/* Hover Marker */}
              {hoverMinute !== null && hoverData && (
                <g className="mo-hover-group">
                  <line
                    x1={getX(hoverData.minute)} y1="0"
                    x2={getX(hoverData.minute)} y2={SVG_HEIGHT}
                    className="mo-hover-line"
                  />
                  <circle
                    cx={getX(hoverData.minute)}
                    cy={getY(hoverData.difference)}
                    r="6"
                    className={`mo-hover-point ${hoverData.difference >= 0 ? 'home' : 'away'}`}
                  />
                </g>
              )}
            </svg>

          {/* X-Axis Labels (Minutes) */}
          <div className="mo-x-axis">
            <span className="mo-x-label">0'</span>
            <span className="mo-x-label" style={{ left: '50%', transform: 'translateX(-50%)' }}>45'</span>
            <span className="mo-x-label" style={{ right: 0 }}>{maxMinute}'</span>
          </div>
        </div>

        </div>
      </div>

      {/* Sidebar for Top Players */}
      {data.topPlayers && data.topPlayers.length > 0 && (
        <div className="mo-sidebar">
          <h4 className="mo-sidebar-title">Top Threat Creators</h4>
          <div className="mo-top-players">
            {data.topPlayers.map((player, idx) => (
              <div key={idx} className="mo-player-card">
                <div className="mo-player-rank">{idx + 1}</div>
                <div className="mo-player-info">
                  <div className="mo-player-name">{player.name}</div>
                  <div className="mo-player-xt">+{player.xT.toFixed(2)} xT</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Dynamic Tooltip fixed on screen */}
      {hoverData && (
        <div 
          className="mo-tooltip" 
          style={{ position: 'fixed', left: tooltipPos.x, top: tooltipPos.y, zIndex: 1000 }}
        >
          <div className="mo-tt-time">Minute {hoverData.minute}'</div>
          <div className="mo-tt-row">
            <span className="mo-tt-label">{homeTeam} xT:</span>
            <span className="mo-tt-val home">{hoverData.homeCumXt.toFixed(2)}</span>
          </div>
          <div className="mo-tt-row">
            <span className="mo-tt-label">{awayTeam} xT:</span>
            <span className="mo-tt-val away">{hoverData.awayCumXt.toFixed(2)}</span>
          </div>
          <div className="mo-tt-divider"></div>
          <div className="mo-tt-row total">
            <span className="mo-tt-label">Advantage:</span>
            <span className={`mo-tt-val ${hoverData.difference >= 0 ? 'home' : 'away'}`}>
              {hoverData.difference >= 0 ? homeTeam : awayTeam} ({Math.abs(hoverData.difference).toFixed(2)})
            </span>
          </div>
        </div>
      )}

      {/* Annotation Tooltip */}
      {hoveredAnnotation && (
        <div
          className="mo-tooltip"
          style={{ position: 'fixed', left: annotationPos.x, top: annotationPos.y, zIndex: 1001 }}
        >
          <div className="mo-tt-time">
            {hoveredAnnotation.type === 'goal' && (hoveredAnnotation.isOwnGoal ? 'Own Goal' : 'GOAL')}
            {hoveredAnnotation.type === 'redCard' && 'Red Card'}
            {hoveredAnnotation.type === 'substitution' && 'Substitution'}
            {' — '}{hoveredAnnotation.minute}'
          </div>
          <div className="mo-tt-row">
            <span className="mo-tt-label">Team:</span>
            <span className="mo-tt-val">{hoveredAnnotation.team}</span>
          </div>
          {hoveredAnnotation.type === 'substitution' ? (
            <>
              <div className="mo-tt-row">
                <span className="mo-tt-label">On:</span>
                <span className="mo-tt-val" style={{ color: '#4ade80' }}>{hoveredAnnotation.playerOn}</span>
              </div>
              <div className="mo-tt-row">
                <span className="mo-tt-label">Off:</span>
                <span className="mo-tt-val" style={{ color: '#f87171' }}>{hoveredAnnotation.playerOff}</span>
              </div>
            </>
          ) : (
            <div className="mo-tt-row">
              <span className="mo-tt-label">Player:</span>
              <span className="mo-tt-val">{hoveredAnnotation.player}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
