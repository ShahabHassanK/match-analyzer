import { useState } from 'react';
import './SubstitutionImpactView.css';

const METRICS = [
  { key: 'xTRate',        label: 'xT/min',    decimals: 3 },
  { key: 'shotsP15',      label: 'Shots/15m', decimals: 1 },
  { key: 'progPassesP15', label: 'Prog/15m',  decimals: 1 },
];

function DeltaCell({ before, after, metricKey, decimals }) {
  if (!after) return <td className="si-cell si-na">—</td>;
  const bVal = before[metricKey] ?? 0;
  const aVal = after[metricKey] ?? 0;
  const delta = aVal - bVal;
  const pct = bVal !== 0 ? (delta / bVal) * 100 : null;
  const positive = delta >= 0;
  return (
    <td className={`si-cell ${positive ? 'si-pos' : 'si-neg'}`}>
      <span className="si-after">{aVal.toFixed(decimals)}</span>
      <span className="si-delta">
        {positive ? '+' : ''}{delta.toFixed(decimals)}
        {pct !== null && ` (${positive ? '+' : ''}${pct.toFixed(0)}%)`}
      </span>
    </td>
  );
}

export default function SubstitutionImpactView({ data, homeTeam, awayTeam }) {
  const [activeTeam, setActiveTeam] = useState('home');

  if (!data || !data.substitutions) {
    return <div className="view-loading">No substitution data available.</div>;
  }

  const { substitutions, minMinutesThreshold } = data;
  const teamFilter = activeTeam === 'home' ? homeTeam : awayTeam;
  const teamSubs = substitutions.filter(s => s.team === teamFilter);

  return (
    <div className="si-view">
      <div className="si-header">
        <div className="si-title-block">
          <h3 className="si-title">Substitution Impact</h3>
          <p className="si-subtitle">
            Team metrics 15 minutes before vs. after each substitution.
            Requires ≥{minMinutesThreshold} minutes of post-sub data to show comparison.
          </p>
        </div>

        <div className="si-team-toggle">
          <button
            className={`si-btn ${activeTeam === 'home' ? 'active home' : ''}`}
            onClick={() => setActiveTeam('home')}
          >
            {homeTeam}
          </button>
          <button
            className={`si-btn ${activeTeam === 'away' ? 'active away' : ''}`}
            onClick={() => setActiveTeam('away')}
          >
            {awayTeam}
          </button>
        </div>
      </div>

      {teamSubs.length === 0 ? (
        <div className="si-empty">No substitutions recorded for {teamFilter}.</div>
      ) : (
        <div className="si-table-wrapper">
          <table className="si-table">
            <thead>
              <tr>
                <th>Min</th>
                <th>On → Off</th>
                {METRICS.map(m => (
                  <th key={m.key}>
                    {m.label}
                    <div className="si-th-sub">before → after</div>
                  </th>
                ))}
                <th>Goals ±</th>
                <th>Data</th>
              </tr>
            </thead>
            <tbody>
              {teamSubs.map((sub, i) => (
                <tr key={i} className={!sub.sufficientData ? 'si-row-limited' : ''}>
                  <td className="si-cell si-minute">{sub.minute}'</td>
                  <td className="si-cell si-players">
                    <div className="si-player-on">{sub.playerOn}</div>
                    <div className="si-player-off">{sub.playerOff}</div>
                  </td>

                  {METRICS.map(m => (
                    sub.sufficientData ? (
                      <DeltaCell
                        key={m.key}
                        before={sub.before}
                        after={sub.after}
                        metricKey={m.key}
                        decimals={m.decimals}
                      />
                    ) : (
                      <td key={m.key} className="si-cell si-before-only">
                        {sub.before[m.key]?.toFixed(m.decimals) ?? '—'}
                      </td>
                    )
                  ))}

                  {/* Goals column */}
                  {sub.sufficientData ? (
                    <td className="si-cell">
                      <span className="si-goals-before">{sub.before.goals} before</span>
                      <span className="si-goals-after">{sub.after?.goals ?? 0} after</span>
                    </td>
                  ) : (
                    <td className="si-cell si-before-only">{sub.before.goals} before</td>
                  )}

                  <td className="si-cell si-data-badge">
                    {sub.sufficientData ? (
                      <span className="si-badge valid">{sub.minutesAfter}m</span>
                    ) : (
                      <span className="si-badge limited">{sub.minutesAfter}m ⚠</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="si-footnote">
        <span className="si-dot si-pos-dot" /> Improvement after sub &nbsp;
        <span className="si-dot si-neg-dot" /> Decline after sub &nbsp;
        <span className="si-badge limited" style={{ verticalAlign: 'middle' }}>⚠</span> Fewer than {minMinutesThreshold} min played — before-only shown
      </div>
    </div>
  );
}
