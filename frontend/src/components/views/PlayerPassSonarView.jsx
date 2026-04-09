/**
 * views/PlayerPassSonarView.jsx
 * ==============================
 * Circular pass direction sonar — polar chart showing pass volume per angle bin.
 */

import './views.css';

export default function PlayerPassSonarView({ data }) {
  if (!data) return <div className="view-loading">Select a player from the line-ups…</div>;

  const { bins, player, totalPasses } = data;
  const maxCount = Math.max(...bins.map(b => b.count), 1);

  // SVG centre and radius
  const CX = 150;
  const CY = 150;
  const R_MAX = 110;
  const R_MIN = 20;

  const segments = bins.map((bin, i) => {
    const angleStart = (bin.angle - 360 / bins.length / 2) * (Math.PI / 180) - Math.PI / 2;
    const angleEnd = (bin.angle + 360 / bins.length / 2) * (Math.PI / 180) - Math.PI / 2;
    const r = R_MIN + ((bin.count / maxCount) * (R_MAX - R_MIN));

    const x1Inner = CX + R_MIN * Math.cos(angleStart);
    const y1Inner = CY + R_MIN * Math.sin(angleStart);
    const x1Outer = CX + r * Math.cos(angleStart);
    const y1Outer = CY + r * Math.sin(angleStart);
    const x2Outer = CX + r * Math.cos(angleEnd);
    const y2Outer = CY + r * Math.sin(angleEnd);
    const x2Inner = CX + R_MIN * Math.cos(angleEnd);
    const y2Inner = CY + R_MIN * Math.sin(angleEnd);

    const largeArc = 360 / bins.length > 180 ? 1 : 0;

    const path = [
      `M ${x1Inner} ${y1Inner}`,
      `L ${x1Outer} ${y1Outer}`,
      `A ${r} ${r} 0 ${largeArc} 1 ${x2Outer} ${y2Outer}`,
      `L ${x2Inner} ${y2Inner}`,
      `A ${R_MIN} ${R_MIN} 0 ${largeArc} 0 ${x1Inner} ${y1Inner}`,
      'Z',
    ].join(' ');

    const opacity = bin.count > 0 ? 0.3 + (bin.count / maxCount) * 0.55 : 0.05;

    return (
      <path key={i} d={path}
        fill="var(--color-primary)"
        fillOpacity={opacity}
        stroke="var(--color-primary)"
        strokeWidth="0.5"
        strokeOpacity="0.5"
      >
        <title>{`${bin.angle}° — ${bin.count} passes`}</title>
      </path>
    );
  });

  return (
    <div className="view-container">
      <div className="player-view-header">
        <span className="player-view-name">{player}</span>
        <span className="player-view-stat">{totalPasses} successful passes</span>
      </div>

      <div className="sonar-wrapper">
        <svg viewBox="0 0 300 300" className="sonar-svg">
          {/* Background rings */}
          {[0.25, 0.5, 0.75, 1].map(pct => (
            <circle key={pct}
              cx={CX} cy={CY}
              r={R_MIN + pct * (R_MAX - R_MIN)}
              fill="none"
              stroke="var(--border-light)"
              strokeWidth="0.5"
            />
          ))}

          {/* Direction labels */}
          <text x={CX} y={CY - R_MAX - 6} textAnchor="middle" fontSize="10" fill="var(--text-secondary)" fontWeight="600">FWD →</text>
          <text x={CX} y={CY + R_MAX + 14} textAnchor="middle" fontSize="10" fill="var(--text-secondary)" fontWeight="600">← BACK</text>
          <text x={CX + R_MAX + 8} y={CY + 4} textAnchor="start" fontSize="10" fill="var(--text-secondary)" fontWeight="600">R</text>
          <text x={CX - R_MAX - 8} y={CY + 4} textAnchor="end" fontSize="10" fill="var(--text-secondary)" fontWeight="600">L</text>

          {segments}

          {/* Centre dot */}
          <circle cx={CX} cy={CY} r={R_MIN} fill="var(--bg-card)" stroke="var(--border-medium)" strokeWidth="0.5" />
          <circle cx={CX} cy={CY} r="3" fill="var(--color-primary)" />
        </svg>
      </div>
    </div>
  );
}
