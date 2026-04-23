/**
 * Dashboard
 * =========
 * Main match analysis container. Loads core match data (summary + starting XI),
 * manages view switching, and passes data down to visualisation components.
 */

import { useState, useEffect, useCallback } from 'react';
import './Dashboard.css';

import MatchFacts from './MatchFacts';
import StartingXI from './StartingXI';
import AdvancedMetrics from './AdvancedMetrics';
import GradientScoring from './GradientScoring';
import ShotMapView from './views/ShotMapView';
import PassNetworkView from './views/PassNetworkView';
import DefensiveActionsView from './views/DefensiveActionsView';
import ZoneEntriesView from './views/ZoneEntriesView';
import SetPiecesView from './views/SetPiecesView';
import AverageShapeView from './views/AverageShapeView';
import MomentumView from './views/MomentumView';
import PlayerActionsView from './views/PlayerActionsView';
import GoalReplaysView from './views/GoalReplaysView';
import AIGuide from './AIGuide';

import {
  fetchSummary,
  fetchStartingXI,
  fetchShots,
  fetchPassNetwork,
  fetchPPDA,
  fetchMomentum,
  fetchDefensiveActions,
  fetchZoneEntries,
  fetchSetPieces,
  fetchAverageShape,
  fetchGoalBuildUps,
  fetchPlayerActions,
} from '../services/api';


const TEAM_VIEWS = [
  { id: 'momentum',     label: 'Match Momentum' },
  { id: 'shots',        label: 'Shot Map' },
  { id: 'passNetwork',  label: 'Pass Network' },
  { id: 'defensive',    label: 'Defensive Actions' },
  { id: 'zoneEntries',  label: 'Creative Play' },
  { id: 'setPieces',    label: 'Set Pieces' },
  { id: 'averageShape', label: 'Tactical Shape' },
];

const PERIOD_LABELS = { full: 'Full Match', FirstHalf: '1st Half', SecondHalf: '2nd Half' };

const PLAYER_VIEWS = [
  { id: 'playerActions',   label: 'Actions',    icon: '👟' },
];


export default function Dashboard({ matchId, onBack }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Core data
  const [summary, setSummary] = useState(null);
  const [xi, setXI] = useState(null);

  // View state
  const [activeView, setActiveView] = useState('');
  const [selectedPlayer, setSelectedPlayer] = useState(null);
  const [activePeriod, setActivePeriod] = useState('full');

  // Lazy-loaded view data cache — keyed by `${view}_${period}` or `${view}_${player}_${period}`
  const [viewData, setViewData] = useState({});

  // ── Load core match data (XI only — doesn't change by period) ───────────
  useEffect(() => {
    setLoading(true);
    setError(null);
    setViewData({});
    setSelectedPlayer(null);
    setActiveView('');
    setActivePeriod('full');

    fetchStartingXI(matchId)
      .then(startXI => setXI(startXI))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [matchId]);

  // ── Reload summary when matchId or period changes ───────────────────────
  useEffect(() => {
    if (!matchId) return;
    const period = activePeriod === 'full' ? null : activePeriod;
    fetchSummary(matchId, period)
      .then(sum => setSummary(sum))
      .catch(console.error);
  }, [matchId, activePeriod]);

  // ── Lazy view data fetching ─────────────────────────────────────────────
  useEffect(() => {
    if (!matchId || !xi) return;

    const period = activePeriod === 'full' ? null : activePeriod;
    const baseCacheKey = selectedPlayer ? `${activeView}_${selectedPlayer}` : activeView;
    const cacheKey = `${baseCacheKey}_${activePeriod}`;
    if (viewData[cacheKey]) return;

    const p = period;

    const fetchers = {
      shots:         () => fetchShots(matchId, p),
      passNetwork:   () => fetchPassNetwork(matchId, undefined, p),
      momentum:      () => fetchMomentum(matchId, 5, p),
      defensive:     () => fetchDefensiveActions(matchId, p),
      zoneEntries:   () => fetchZoneEntries(matchId, p),
      setPieces:     () => fetchSetPieces(matchId, p),
      averageShape:  () => fetchAverageShape(matchId, p),
      goalReplays:   () => fetchGoalBuildUps(matchId, p),
      playerActions: selectedPlayer ? () => fetchPlayerActions(matchId, selectedPlayer, undefined, p) : null,
    };

    const fetcher = fetchers[activeView];
    if (!fetcher) return;

    fetcher()
      .then(data => setViewData(prev => ({ ...prev, [cacheKey]: data })))
      .catch(console.error);
  }, [matchId, activeView, selectedPlayer, activePeriod, xi]);

  // ── Player selection ────────────────────────────────────────────────────
  const handleSelectPlayer = useCallback((player) => {
    if (player) {
      setSelectedPlayer(player);
      if (!PLAYER_VIEWS.find(v => v.id === activeView)) {
        setActiveView('playerActions');
      }
    } else {
      setSelectedPlayer(null);
      if (!TEAM_VIEWS.find(v => v.id === activeView)) {
        setActiveView('shots');
      }
    }
  }, [activeView]);

  // ── Derived ─────────────────────────────────────────────────────────────
  const homeTeam = summary?.homeTeam || '';
  const awayTeam = summary?.awayTeam || '';

  // ── Render view ─────────────────────────────────────────────────────────
  const renderView = () => {
    const baseCacheKey = selectedPlayer ? `${activeView}_${selectedPlayer}` : activeView;
    const cacheKey = `${baseCacheKey}_${activePeriod}`;
    const data = viewData[cacheKey];
    if (!data) return <div className="view-loading">Loading specific view data…</div>;

    if (activeView === 'momentum') return <MomentumView data={data} />;
    if (activeView === 'shots') return <ShotMapView data={data} homeTeam={homeTeam} awayTeam={awayTeam} />;
    if (activeView === 'passNetwork') return <PassNetworkView data={data} homeTeam={homeTeam} awayTeam={awayTeam} />;
    if (activeView === 'zoneEntries') return <ZoneEntriesView data={data} homeTeam={homeTeam} awayTeam={awayTeam} />;
    if (activeView === 'defensive') return <DefensiveActionsView data={data} homeTeam={homeTeam} awayTeam={awayTeam} />;
    if (activeView === 'setPieces') return <SetPiecesView data={data} homeTeam={homeTeam} awayTeam={awayTeam} />;
    if (activeView === 'averageShape') return <AverageShapeView data={data} homeTeam={homeTeam} awayTeam={awayTeam} />;
    if (activeView === 'goalReplays') return <GoalReplaysView data={data} />;

    if (activeView === 'playerActions') return <PlayerActionsView data={data} />;

    return (
      <div className="empty-view-placeholder" style={{ padding: '4rem 2rem', textAlign: 'center', color: '#64748b', fontSize: '1.1rem', backgroundColor: '#0f172a', borderRadius: '8px', border: '1px dashed #334155' }}>
        <p>Please select a visualization from the dropdown menu above to begin analysis.</p>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="dash-loading">
        <div className="scraping-spinner" />
        <p>Loading match data…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dash-error container">
        <p>{error}</p>
        <button className="btn btn-primary" onClick={onBack}>← Back to Home</button>
      </div>
    );
  }

  return (
    <div className="dashboard container">
      {/* Back button */}
      <button className="dash-back" onClick={onBack}>← Back to matches</button>

      {/* Top: Match Facts + Starting XI */}
      <div className="dash-top">
        <div className="dash-facts">
          <MatchFacts summary={summary} />
        </div>
        <div className="dash-xi">
          <StartingXI
            xi={xi}
            selectedPlayer={selectedPlayer}
            onSelectPlayer={handleSelectPlayer}
          />
        </div>
      </div>

      {/* Advanced Metrics Terminal & Goal Replays Buttons */}
      <div className="dash-actions" style={{ display: 'flex', gap: '1rem', justifyContent: 'center', alignItems: 'flex-start' }}>
        <div className="am-toggle-wrap" style={{ marginTop: '32px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
          <GradientScoring matchId={matchId} homeTeam={homeTeam} awayTeam={awayTeam} />
          <AIGuide matchId={matchId} feature="gradientScoring" />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
          <AdvancedMetrics matchId={matchId} homeTeam={homeTeam} awayTeam={awayTeam} />
          <AIGuide matchId={matchId} feature="advancedMetrics" />
        </div>
        <div className="am-toggle-wrap" style={{ marginTop: '32px' }}>
          <button
            className="am-toggle-btn"
            onClick={() => setActiveView(activeView === 'goalReplays' ? '' : 'goalReplays')}
            style={{
              background: activeView === 'goalReplays' ? '#1e293b' : undefined,
              borderColor: activeView === 'goalReplays' ? '#60a5fa' : undefined,
              color: activeView === 'goalReplays' ? '#ffffff' : undefined,
            }}
          >
            {activeView === 'goalReplays' ? 'Close 2D Goal Replay' : '2D Goal Replay'}
          </button>
        </div>
      </div>

      {/* Period Filter */}
      <div className="period-selector">
        {Object.entries(PERIOD_LABELS).map(([key, label]) => (
          <button
            key={key}
            className={`period-btn${activePeriod === key ? ' active' : ''}`}
            onClick={() => setActivePeriod(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Single View Panel */}
      <section className="view-panel">
        {activeView !== 'goalReplays' && (
          <div className="view-selector-header">
            <span className="view-selector-label">Visualisation:</span>
            <select
              className="view-dropdown"
              value={activeView}
              onChange={(e) => setActiveView(e.target.value)}
            >
              <option value="" disabled>Select visualization...</option>
              {TEAM_VIEWS.map(v => (
                <option key={v.id} value={v.id}>{v.label}</option>
              ))}
            </select>
            {activeView && TEAM_VIEWS.find(v => v.id === activeView) && (
              <AIGuide matchId={matchId} feature={activeView} />
            )}
          </div>
        )}
        <div className="view-content">
          {renderView()}
        </div>
      </section>
    </div>
  );
}
