/**
 * AdvancedMetrics
 * ===============
 * Stock-exchange / Bloomberg terminal-style data panel showing advanced
 * tactical metrics for both teams side-by-side.
 */

import { useState, useEffect } from 'react';
import { fetchAdvancedMetrics } from '../services/api';
import './AdvancedMetrics.css';

const METRIC_CATEGORIES = [
  {
    id: 'pressing',
    label: 'Pressing',
    metrics: [
      { key: 'ppda', label: 'PPDA', suffix: '', decimals: 2, lowerBetter: true },
      { key: 'finalThirdRecoveries', label: 'Final Third Recoveries', suffix: '', decimals: 0, lowerBetter: false },
    ],
  },
  {
    id: 'progression',
    label: 'Progression',
    metrics: [
      { key: 'progressivePasses', label: 'Progressive Passes', suffix: '', decimals: 0, lowerBetter: false },
      { key: 'progressiveCarries', label: 'Progressive Carries', suffix: '', decimals: 0, lowerBetter: false },
      { key: 'buildUpRatio', label: 'Build-up Ratio', suffix: '%', decimals: 1, lowerBetter: false },
    ],
  },
  {
    id: 'possession',
    label: 'Possession',
    metrics: [
      { key: 'avgPassSequence', label: 'Avg Pass Sequence', suffix: '', decimals: 1, lowerBetter: false },
    ],
  },
  {
    id: 'aggression',
    label: 'Aggression',
    metrics: [
      { key: 'aggressionIndex', label: 'Aggression Index', suffix: '', decimals: 1, lowerBetter: false },
    ],
  },
  {
    id: 'creativity',
    label: 'Creativity',
    metrics: [
      { key: 'keyPasses', label: 'Key Passes', suffix: '', decimals: 0, lowerBetter: false },
      { key: 'crossingAccuracy', label: 'Crossing Accuracy', suffix: '%', decimals: 1, lowerBetter: false },
      { key: 'directPassRatio', label: 'Direct Pass Ratio', suffix: '%', decimals: 1, lowerBetter: false },
    ],
  },
  {
    id: 'duels',
    label: 'Duels',
    metrics: [
      { key: 'aerialWinPct', label: 'Aerial Win Rate', suffix: '%', decimals: 1, lowerBetter: false },
      { key: 'dribbleSuccessPct', label: 'Dribble Success', suffix: '%', decimals: 1, lowerBetter: false },
    ],
  },
  {
    id: 'shape',
    label: 'Shape',
    metrics: [
      { key: 'fieldTilt', label: 'Field Tilt', suffix: '%', decimals: 1, lowerBetter: false },
    ],
  },
];


function MetricRow({ metric, homeVal, awayVal }) {
  const { label, suffix, decimals, lowerBetter } = metric;

  const hv = typeof homeVal === 'number' ? homeVal : 0;
  const av = typeof awayVal === 'number' ? awayVal : 0;

  let homeWins, awayWins;
  if (lowerBetter) {
    homeWins = hv < av && hv > 0;
    awayWins = av < hv && av > 0;
  } else {
    homeWins = hv > av;
    awayWins = av > hv;
  }

  const tied = hv === av;
  const total = hv + av || 1;
  const homeWidth = Math.round((hv / total) * 100);
  const awayWidth = 100 - homeWidth;

  return (
    <div className="am-row">
      <div className={`am-val home ${homeWins ? 'leading' : ''}`}>
        {!tied && (
          <span className={`am-arrow ${homeWins ? 'up' : 'down'}`}>
            {homeWins ? '▲' : '▼'}
          </span>
        )}
        {hv.toFixed(decimals)}{suffix}
      </div>
      <div className="am-center">
        <span className="am-label">{label}</span>
        <div className="am-bar-track">
          <div className="am-bar home-bar" style={{ width: `${homeWidth}%` }} />
          <div className="am-bar away-bar" style={{ width: `${awayWidth}%` }} />
        </div>
      </div>
      <div className={`am-val away ${awayWins ? 'leading' : ''}`}>
        {av.toFixed(decimals)}{suffix}
        {!tied && (
          <span className={`am-arrow ${awayWins ? 'up' : 'down'}`}>
            {awayWins ? '▲' : '▼'}
          </span>
        )}
      </div>
    </div>
  );
}


export default function AdvancedMetrics({ matchId, homeTeam, awayTeam }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!matchId || !visible) return;
    if (data) return; // already loaded
    setLoading(true);
    setError(null);
    fetchAdvancedMetrics(matchId)
      .then(d => setData(d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [matchId, visible]);

  // Toggle button when collapsed
  if (!visible) {
    return (
      <div className="am-toggle-wrap">
        <button className="am-toggle-btn" onClick={() => setVisible(true)}>
          View Advanced Metrics
        </button>
      </div>
    );
  }

  return (
    <div className="am-panel">
      <div className="am-header">
        <div className="am-title-block">
          <h3 className="am-title">Advanced Metrics</h3>
          <span className="am-badge">DATA TERMINAL</span>
        </div>
        <div className="am-header-right">
          <div className="am-teams-header">
            <span className="am-team-name home">{homeTeam}</span>
            <span className="am-vs">VS</span>
            <span className="am-team-name away">{awayTeam}</span>
          </div>
          <button className="am-close-btn" onClick={() => setVisible(false)}>
            Close
          </button>
        </div>
      </div>

      {loading && (
        <div className="am-loading">
          <div className="am-spinner" />
          Computing advanced metrics…
        </div>
      )}

      {error && (
        <div className="am-error">Failed to load metrics: {error}</div>
      )}

      {data && (
        <div className="am-grid">
          {METRIC_CATEGORIES.map(cat => (
            <div key={cat.id} className="am-category">
              <div className="am-cat-header">
                <span className="am-cat-label">{cat.label}</span>
              </div>
              <div className="am-cat-body">
                {cat.metrics.map(m => (
                  <MetricRow
                    key={m.key}
                    metric={m}
                    homeVal={data.home[cat.id]?.[m.key]}
                    awayVal={data.away[cat.id]?.[m.key]}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
