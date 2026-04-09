/**
 * views/PlayerActionsView.jsx
 * ============================
 * Filtered player actions rendered as vectors/points on the pitch.
 * Dropdown to select action type.
 */

import { useState, useEffect } from 'react';
import Pitch from '../Pitch';
import { fetchPlayerActions } from '../../services/api';
import './views.css';

const ACTION_TYPES = [
  { value: '', label: 'All Actions' },
  { value: 'pass', label: 'Passes' },
  { value: 'shot', label: 'Shots' },
  { value: 'carry', label: 'Carries' },
  { value: 'cross', label: 'Crosses' },
  { value: 'tackle', label: 'Tackles' },
  { value: 'interception', label: 'Interceptions' },
  { value: 'aerial', label: 'Aerials' },
  { value: 'take_on', label: 'Take-Ons' },
];

const OUTCOME_COLOR = {
  Successful: 'var(--color-goal)',
  Unsuccessful: 'var(--color-off-target)',
};

export default function PlayerActionsView({ matchId, playerName }) {
  const [actionType, setActionType] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!matchId || !playerName) return;
    setLoading(true);
    fetchPlayerActions(matchId, playerName, actionType || undefined)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [matchId, playerName, actionType]);

  if (!playerName) return <div className="view-loading">Select a player from the line-ups…</div>;
  if (loading) return <div className="view-loading">Loading actions…</div>;
  if (!data) return null;

  return (
    <div className="view-container">
      <div className="player-view-header">
        <span className="player-view-name">{data.player}</span>
        <span className="player-view-stat">{data.count} actions</span>
      </div>

      <div className="view-controls">
        <select className="view-select" value={actionType} onChange={e => setActionType(e.target.value)}>
          {ACTION_TYPES.map(t => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </div>

      <Pitch>
        {data.actions.map((action, i) => {
          if (action.x == null || action.y == null) return null;
          const color = OUTCOME_COLOR[action.outcome] || '#999';
          const hasEnd = action.endX != null && action.endY != null;

          return (
            <g key={i}>
              {hasEnd && (
                <line
                  x1={action.x} y1={action.y}
                  x2={action.endX} y2={action.endY}
                  stroke={color} strokeWidth="0.4" opacity="0.5"
                />
              )}
              <circle cx={action.x} cy={action.y} r="1.2"
                fill={color} fillOpacity="0.8" stroke="white" strokeWidth="0.25"
              >
                <title>{`${action.type} (${action.minute}') — ${action.outcome}`}</title>
              </circle>
            </g>
          );
        })}
      </Pitch>
    </div>
  );
}
