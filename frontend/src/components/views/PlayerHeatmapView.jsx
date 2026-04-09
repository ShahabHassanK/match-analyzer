/**
 * views/PlayerHeatmapView.jsx
 * ============================
 * Touch density heatmap for an individual player, overlaid on the pitch.
 */

import Pitch from '../Pitch';
import './views.css';

export default function PlayerHeatmapView({ data }) {
  if (!data) return <div className="view-loading">Select a player from the line-ups…</div>;

  const { heatmap, gridSize, player, totalTouches } = data;
  const cellW = 100 / gridSize;
  const cellH = 100 / gridSize;

  return (
    <div className="view-container">
      <div className="player-view-header">
        <span className="player-view-name">{player}</span>
        <span className="player-view-stat">{totalTouches} touches</span>
      </div>

      <Pitch>
        {heatmap.map((row, yi) =>
          row.map((val, xi) => (
            val > 0.05 ? (
              <rect key={`${yi}-${xi}`}
                x={xi * cellW}
                y={yi * cellH}
                width={cellW}
                height={cellH}
                fill="var(--color-primary)"
                fillOpacity={val * 0.75}
                rx="0.5"
              />
            ) : null
          ))
        )}
      </Pitch>
    </div>
  );
}
