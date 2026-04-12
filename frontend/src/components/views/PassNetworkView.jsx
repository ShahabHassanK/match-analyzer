import { useState, useMemo } from 'react';
import './PassNetworkView.css';

export default function PassNetworkView({ data, homeTeam, awayTeam }) {
  const [activeTeam, setActiveTeam] = useState('home');
  const [hoveredNode, setHoveredNode] = useState(null);

  // Safely extract network edges for useMemo dependency without violating hook rules
  const network = data?.networks?.[activeTeam === 'home' ? homeTeam : awayTeam];
  const edges = network?.edges || [];
  
  // Build active player stats if hovered
  const activeStats = useMemo(() => {
    if (!hoveredNode) return null;
    const player = hoveredNode.player;
    const passesTo = edges
      .filter(e => e.from === player)
      .sort((a, b) => b.count - a.count);
    const receivedFrom = edges
      .filter(e => e.to === player)
      .sort((a, b) => b.count - a.count);
    return {
      player,
      totalPasses: hoveredNode.passCount,
      touches: hoveredNode.touches || 0,
      passesPlayed: hoveredNode.passesPlayed || 0,
      passesReceived: hoveredNode.passesReceived || 0,
      topTargets: passesTo.slice(0, 3),
      topProviders: receivedFrom.slice(0, 3),
    };
  }, [hoveredNode, edges]);

  // Now perform early returns safely
  if (!data || !data.networks) {
    return <div className="view-loading">Loading Pass Network…</div>;
  }

  const teamName = activeTeam === 'home' ? homeTeam : awayTeam;

  if (!network) {
    return <div className="view-loading">No pass network available for {teamName}</div>;
  }

  const { nodes, maxMinute } = network;

  // Max passes for scaling node sizes
  const maxPasses = nodes.length > 0 ? Math.max(...nodes.map(n => n.passCount)) : 1;
  // Max edge passes for line thickness scaling
  const maxEdgeCount = edges.length > 0 ? Math.max(...edges.map(e => e.count)) : 1;

  // Pitch aspect ratio mapping (Pitch is 105m x 68m)
  // X: 0-100 -> 0-105
  // Y: 0-100 -> 0-68 
  const mapX = (avgX) => (avgX / 100) * 105;
  const mapY = (avgY) => ((100 - avgY) / 100) * 68;

  // Derive node size
  const getNodeRadius = (passCount) => {
    // scale roughly from 1.5 to 3.5
    return 1.5 + (passCount / maxPasses) * 2.0;
  };

  // Derive initial abbreviation
  const getInitials = (name) => {
    const parts = String(name).split(' ');
    if (parts.length === 1) return parts[0].substring(0, 3).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  };

  return (
    <div className="premium-pn">
      <div className="ppn-header">
        <div className="ppn-team-selector">
          <button
            className={`ppn-tab ${activeTeam === 'home' ? 'active home' : ''}`}
            onClick={() => setActiveTeam('home')}
          >
            {homeTeam}
          </button>
          <button
            className={`ppn-tab ${activeTeam === 'away' ? 'active away' : ''}`}
            onClick={() => setActiveTeam('away')}
          >
            {awayTeam}
          </button>
        </div>
        <div className="ppn-summary">
          <div className="ppn-sum-item">
            <span>{maxMinute}'</span> Minutes
            {maxMinute < 90 && " (First Sub)"}
          </div>
          <div className="ppn-sum-item">
            <span>{nodes.length}</span> Active Players
          </div>
        </div>
      </div>

      <div className="ppn-body">
        <div className="ppn-pitch-container">
          {/* viewBox reflects 105x68 dimensions */}
          <svg viewBox="0 0 105 68" className="ppn-pitch-svg" preserveAspectRatio="xMidYMid meet">
            {/* Pitch Background */}
            <rect width="105" height="68" className="ppn-turf" />
            
            {/* Pitch Lines */}
            <g className="ppn-lines" strokeWidth="0.3" fill="none">
              <rect x="0" y="0" width="105" height="68" />
              <line x1="52.5" y1="0" x2="52.5" y2="68" />
              <circle cx="52.5" cy="34" r="9.15" />
              <circle cx="52.5" cy="34" r="0.4" fill="var(--ppn-line-color)" />
              
              {/* Left Penalty Area */}
              <rect x="0" y="13.84" width="16.5" height="40.32" />
              <rect x="0" y="24.84" width="5.5" height="18.32" />
              <circle cx="11" cy="34" r="0.3" fill="var(--ppn-line-color)" />
              <path d="M 16.5 26.7 A 9.15 9.15 0 0 1 16.5 41.3" />

              {/* Right Penalty Area */}
              <rect x="88.5" y="13.84" width="16.5" height="40.32" />
              <rect x="99.5" y="24.84" width="5.5" height="18.32" />
              <circle cx="94" cy="34" r="0.3" fill="var(--ppn-line-color)" />
              <path d="M 88.5 41.3 A 9.15 9.15 0 0 1 88.5 26.7" />
            </g>

            {/* Edges */}
            <g className="ppn-edges">
              {edges.map((e, idx) => {
                const nodeFrom = nodes.find(n => n.player === e.from);
                const nodeTo = nodes.find(n => n.player === e.to);
                if (!nodeFrom || !nodeTo) return null;

                // Scale line width 0.1 to 1.5
                const thickness = 0.1 + (e.count / maxEdgeCount) * 1.4;
                
                // Interaction State
                let edgeStateClass = '';
                if (hoveredNode) {
                  if (e.from === hoveredNode.player || e.to === hoveredNode.player) {
                    edgeStateClass = 'active';
                  } else {
                    edgeStateClass = 'dimmed';
                  }
                }

                return (
                  <line
                    key={idx}
                    x1={mapX(nodeFrom.avgX)}
                    y1={mapY(nodeFrom.avgY)}
                    x2={mapX(nodeTo.avgX)}
                    y2={mapY(nodeTo.avgY)}
                    strokeWidth={thickness}
                    className={`ppn-edge ${edgeStateClass}`}
                  />
                );
              })}
            </g>

            {/* Nodes */}
            <g className="ppn-nodes">
              {nodes.map((node, idx) => {
                const cx = mapX(node.avgX);
                const cy = mapY(node.avgY);
                const r = getNodeRadius(node.passCount);
                
                let nodeStateClass = '';
                if (hoveredNode && hoveredNode.player !== node.player) {
                  nodeStateClass = 'dimmed';
                } else if (hoveredNode && hoveredNode.player === node.player) {
                  nodeStateClass = 'hovered';
                }

                return (
                  <g 
                    key={idx} 
                    className={`ppn-node-group ${nodeStateClass}`}
                    onMouseEnter={() => setHoveredNode(node)}
                    onMouseLeave={() => setHoveredNode(null)}
                  >
                    <circle 
                      cx={cx} 
                      cy={cy} 
                      r={r} 
                      className="ppn-node"
                      strokeWidth="0.2"
                    />
                    <text x={cx} y={cy} className="ppn-node-label">
                      {getInitials(node.player)}
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>
        </div>

        {/* Sidebar */}
        <div className="ppn-sidebar">
          {activeStats ? (
            <div className="ppn-legend">
              <h4 className="ppn-sidebar-title">Player Focus</h4>
              <div className="ppn-tt-player">{activeStats.player}</div>
              <div className="ppn-insight-row"><strong>Touches:</strong> {activeStats.touches}</div>
              <div className="ppn-insight-row"><strong>Passes Played:</strong> {activeStats.passesPlayed}</div>
              <div className="ppn-insight-row"><strong>Passes Received:</strong> {activeStats.passesReceived}</div>
              <div className="ppn-insight-row"><strong>Success Passes:</strong> {activeStats.totalPasses}</div>
              
              <h4 className="ppn-sidebar-title" style={{ marginTop: '24px' }}>Top Recipients</h4>
              <div className="ppn-insight">
                {activeStats.topTargets.length > 0 ? activeStats.topTargets.map(t => (
                  <div className="ppn-insight-row" key={t.to}>
                    <span>{t.to}</span>
                    <strong>{t.count}</strong>
                  </div>
                )) : <div className="ppn-insight-empty">No outgoing passes.</div>}
              </div>

              <h4 className="ppn-sidebar-title" style={{ marginTop: '24px' }}>Top Providers</h4>
              <div className="ppn-insight">
                {activeStats.topProviders.length > 0 ? activeStats.topProviders.map(t => (
                  <div className="ppn-insight-row" key={t.from}>
                    <span>{t.from}</span>
                    <strong>{t.count}</strong>
                  </div>
                )) : <div className="ppn-insight-empty">No incoming passes.</div>}
              </div>
            </div>
          ) : (
            <div className="ppn-legend">
              <h4 className="ppn-sidebar-title">Hover for Intelligence</h4>
              <p className="ppn-insight-empty">Hover over any player node to highlight their connections and view specific pass volumes.</p>
              <br/>
              <p className="ppn-insight-row"><strong>Thicker Lines:</strong> Frequent passing combo</p>
              <p className="ppn-insight-row"><strong>Larger Nodes:</strong> High passing volume</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
