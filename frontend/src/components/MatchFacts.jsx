/**
 * MatchFacts
 * ==========
 * Scoreline hero + stat comparison bars. PL-style editorial layout.
 */

import './MatchFacts.css';
import { getTeamLogo } from '../utils/logos';

function StatBar({ label, homeVal, awayVal, format }) {
  const homeNum = typeof homeVal === 'number' ? homeVal : 0;
  const awayNum = typeof awayVal === 'number' ? awayVal : 0;
  const total = homeNum + awayNum || 1;

  return (
    <div className="stat-container">
      <div className="stat-header">
        <span className="stat-value home">{format ? format(homeVal) : homeVal}</span>
        <span className="stat-label">{label}</span>
        <span className="stat-value away">{format ? format(awayVal) : awayVal}</span>
      </div>
      <div className="stat-bar-track">
        <div className="stat-bar home-bar" style={{ width: `${(homeNum / total) * 100}%` }} />
        <div className="stat-bar away-bar" style={{ width: `${(awayNum / total) * 100}%` }} />
      </div>
    </div>
  );
}

export default function MatchFacts({ summary }) {
  if (!summary) return null;

  const { homeTeam, awayTeam, homeStats, awayStats } = summary;

  return (
    <section className="match-facts">
      {/* Scoreline Hero */}
      <div className="scoreline">
        <div className="team home-team">
          <img 
            src={getTeamLogo(homeTeam)} 
            alt={homeTeam} 
            className="team-badge home-badge" 
            onError={(e) => { 
                if (e.target.dataset.failed) return; 
                e.target.dataset.failed = true; 
                e.target.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(homeTeam)}&background=111827&color=fff&rounded=true&bold=true`; 
            }}
          />
          <span className="team-name">{homeTeam}</span>
        </div>
        <div className="score">
          <span className="score-num">{homeStats.goals}</span>
          <span className="score-sep">–</span>
          <span className="score-num">{awayStats.goals}</span>
        </div>
        <div className="team away-team">
          <span className="team-name">{awayTeam}</span>
          <img 
            src={getTeamLogo(awayTeam)} 
            alt={awayTeam} 
            className="team-badge away-badge" 
            onError={(e) => { 
                if (e.target.dataset.failed) return; 
                e.target.dataset.failed = true; 
                e.target.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(awayTeam)}&background=111827&color=fff&rounded=true&bold=true`; 
            }}
          />
        </div>
      </div>

      {/* Stat Comparison */}
      <div className="stats-grid">
        <StatBar label="Possession" homeVal={homeStats.possession} awayVal={awayStats.possession} format={(v) => `${v}%`} />
        
        {/* Attacking Metrics */}
        <StatBar label="Shots" homeVal={homeStats.shots} awayVal={awayStats.shots} />
        <StatBar label="On Target" homeVal={homeStats.shotsOnTarget} awayVal={awayStats.shotsOnTarget} />
        <StatBar label="Big Chances" homeVal={homeStats.bigChances || 0} awayVal={awayStats.bigChances || 0} />
        
        {/* Passing Metrics */}
        <StatBar label="Total Passes" homeVal={homeStats.totalPasses || 0} awayVal={awayStats.totalPasses || 0} />
        <StatBar label="Pass Accuracy (%)" homeVal={homeStats.passAccuracy || 0} awayVal={awayStats.passAccuracy || 0} format={(v) => `${v}%`} />
        
        {/* Defensive Metrics */}
        <StatBar label="Tackles" homeVal={homeStats.tackles || 0} awayVal={awayStats.tackles || 0} />
        <StatBar label="Interceptions" homeVal={homeStats.interceptions || 0} awayVal={awayStats.interceptions || 0} />
        <StatBar label="Clearances" homeVal={homeStats.clearances || 0} awayVal={awayStats.clearances || 0} />
        
        {/* General Events */}
        <StatBar label="Corners" homeVal={homeStats.corners} awayVal={awayStats.corners} />
        <StatBar label="Saves" homeVal={homeStats.saves} awayVal={awayStats.saves} />
        <StatBar label="Fouls" homeVal={homeStats.fouls} awayVal={awayStats.fouls} />
      </div>
    </section>
  );
}
