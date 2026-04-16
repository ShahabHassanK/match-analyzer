import { useState, useEffect } from 'react';
import { fetchGradientScoring } from '../services/api';
import './GradientScoring.css';

export default function GradientScoring({ matchId, homeTeam, awayTeam }) {
  const [isOpen, setIsOpen] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedSection, setExpandedSection] = useState(null); // 'attack', 'defense', or 'passing'

  useEffect(() => {
    if (isOpen && !data) {
      setLoading(true);
      fetchGradientScoring(matchId)
        .then(setData)
        .catch(err => setError(err.message))
        .finally(() => setLoading(false));
    }
  }, [isOpen, matchId, data]);

  if (!isOpen) {
    return (
      <div className="gradient-scoring-wrap">
        <button className="gradient-toggle-btn" onClick={() => setIsOpen(true)}>
          Gradient Scoring Breakdown
        </button>
      </div>
    );
  }

  const toggleSection = (section) => {
    setExpandedSection(prev => prev === section ? null : section);
  };

  const renderBar = (homeScore, awayScore, maxScore = 100) => {
    const homePct = (homeScore / maxScore) * 100;
    const awayPct = (awayScore / maxScore) * 100;
    
    return (
      <div className="gs-bar-container">
        <div className="gs-bar-bg">
          <div className="gs-bar home-bar" style={{ width: `${homePct}%` }} />
        </div>
        <div className="gs-bar-bg away-bg">
          <div className="gs-bar away-bar" style={{ width: `${awayPct}%` }} />
        </div>
      </div>
    );
  };

  const renderBreakdownItem = (label, homeVal, awayVal, maxScore) => {
    return (
      <div className="gs-breakdown-row" key={label}>
        <span className="gs-val home-val">{homeVal.toFixed(1)}</span>
        <div className="gs-breakdown-center">
          <span className="gs-breakdown-label">{label}</span>
          {renderBar(homeVal, awayVal, maxScore)}
        </div>
        <span className="gs-val away-val">{awayVal.toFixed(1)}</span>
      </div>
    );
  };

  return (
    <div className="gradient-scoring-container">
      <div className="gs-header">
        <h3>Gradient Performance Matrix</h3>
        <button className="gs-close-btn" onClick={() => setIsOpen(false)}>CLOSE</button>
      </div>

      {loading && <div className="gs-loading">Analyzing 42 performance vectors...</div>}
      {error && <div className="gs-error">{error}</div>}

      {data && data.homegradient && (
        <div className="gs-content">
          <div className="gs-teams">
            <span className="gs-team-name home-team">{homeTeam}</span>
            <span className="gs-team-name away-team">{awayTeam}</span>
          </div>

          {/* ATTACK */}
          <div className="gs-section">
            <div className="gs-section-header" onClick={() => toggleSection('attack')}>
              <span className="gs-score home-score">{data.homegradient.attack.score.toFixed(1)}</span>
              <div className="gs-section-title">
                <h4>Attacking Score</h4>
                {renderBar(data.homegradient.attack.score, data.awaygradient.attack.score, 100)}
              </div>
              <span className="gs-score away-score">{data.awaygradient.attack.score.toFixed(1)}</span>
            </div>
            
            {expandedSection === 'attack' && (
              <div className="gs-breakdown">
                {Object.keys(data.homegradient.attack.breakdown).map(key => (
                  renderBreakdownItem(
                    key, 
                    data.homegradient.attack.breakdown[key], 
                    data.awaygradient.attack.breakdown[key], 
                    25 // Rough max for sub-categories
                  )
                ))}
                <div className="gs-raw-stats">
                  {Object.keys(data.homegradient.attack.stats).map(key => (
                    <div className="gs-raw-row" key={key}>
                      <span>{data.homegradient.attack.stats[key]}</span>
                      <small>{key}</small>
                      <span>{data.awaygradient.attack.stats[key]}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* DEFENSE */}
          <div className="gs-section">
            <div className="gs-section-header" onClick={() => toggleSection('defense')}>
              <span className="gs-score home-score">{data.homegradient.defense.score.toFixed(1)}</span>
              <div className="gs-section-title">
                <h4>Defensive Score</h4>
                {renderBar(data.homegradient.defense.score, data.awaygradient.defense.score, 100)}
              </div>
              <span className="gs-score away-score">{data.awaygradient.defense.score.toFixed(1)}</span>
            </div>
            
            {expandedSection === 'defense' && (
              <div className="gs-breakdown">
                {Object.keys(data.homegradient.defense.breakdown).map(key => (
                  renderBreakdownItem(
                    key, 
                    data.homegradient.defense.breakdown[key], 
                    data.awaygradient.defense.breakdown[key], 
                    25
                  )
                ))}
                <div className="gs-raw-stats">
                  {Object.keys(data.homegradient.defense.stats).map(key => (
                    <div className="gs-raw-row" key={key}>
                      <span>{data.homegradient.defense.stats[key]}</span>
                      <small>{key}</small>
                      <span>{data.awaygradient.defense.stats[key]}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* PASSING */}
          <div className="gs-section">
            <div className="gs-section-header" onClick={() => toggleSection('passing')}>
              <span className="gs-score home-score">{data.homegradient.passing.score.toFixed(1)}</span>
              <div className="gs-section-title">
                <h4>Possession Score</h4>
                {renderBar(data.homegradient.passing.score, data.awaygradient.passing.score, 100)}
              </div>
              <span className="gs-score away-score">{data.awaygradient.passing.score.toFixed(1)}</span>
            </div>
            
            {expandedSection === 'passing' && (
              <div className="gs-breakdown">
                {Object.keys(data.homegradient.passing.breakdown).map(key => (
                  renderBreakdownItem(
                    key, 
                    data.homegradient.passing.breakdown[key], 
                    data.awaygradient.passing.breakdown[key], 
                    25
                  )
                ))}
                <div className="gs-raw-stats">
                  {Object.keys(data.homegradient.passing.stats).map(key => (
                    <div className="gs-raw-row" key={key}>
                      <span>{data.homegradient.passing.stats[key]}</span>
                      <small>{key}</small>
                      <span>{data.awaygradient.passing.stats[key]}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

        </div>
      )}
    </div>
  );
}
