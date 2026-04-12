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
import ShotMapView from './views/ShotMapView';
import PassNetworkView from './views/PassNetworkView';
import DefensiveActionsView from './views/DefensiveActionsView';
import ZoneEntriesView from './views/ZoneEntriesView';
import SetPiecesView from './views/SetPiecesView';
import AverageShapeView from './views/AverageShapeView';
import PlayerHeatmapView from './views/PlayerHeatmapView';
import PlayerPassSonarView from './views/PlayerPassSonarView';
import PlayerActionsView from './views/PlayerActionsView';

import {
  fetchSummary,
  fetchStartingXI,
  fetchShots,
  fetchPassNetwork,
  fetchPPDA,
  fetchTerritory,
  fetchMomentum,
  fetchDefensiveActions,
  fetchZoneEntries,
  fetchSetPieces,
  fetchAverageShape,
  fetchPlayerHeatmap,
  fetchPlayerPassSonar,
} from '../services/api';


const TEAM_VIEWS = [
  { id: 'shots',       label: 'Shot Map' },
  { id: 'passNetwork', label: 'Pass Network' },
  { id: 'defensive',   label: 'Defensive Actions' },
  { id: 'zoneEntries', label: 'Zone Entries' },
  { id: 'setPieces',   label: 'Set Pieces' },
  { id: 'averageShape',label: 'Tactical Shape' },
];

const PLAYER_VIEWS = [
  { id: 'playerHeatmap',   label: 'Heatmap',    icon: '🔥' },
  { id: 'playerActions',   label: 'Actions',    icon: '👟' },
  { id: 'playerPassSonar', label: 'Pass Sonar', icon: '📡' },
];


export default function Dashboard({ matchId, onBack }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Core data
  const [summary, setSummary] = useState(null);
  const [xi, setXI] = useState(null);

  // View state
  const [activeView, setActiveView] = useState('shots');
  const [selectedPlayer, setSelectedPlayer] = useState(null);

  // Lazy-loaded view data cache
  const [viewData, setViewData] = useState({});

  // ── Load core data ──────────────────────────────────────────────────────
  useEffect(() => {
    setLoading(true);
    setError(null);
    setViewData({});
    setSelectedPlayer(null);
    setActiveView('shots');

    Promise.all([fetchSummary(matchId), fetchStartingXI(matchId)])
      .then(([sum, startXI]) => {
        setSummary(sum);
        setXI(startXI);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [matchId]);

  // ── Lazy view data fetching ─────────────────────────────────────────────
  useEffect(() => {
    if (!matchId || !summary) return;
    const cacheKey = selectedPlayer ? `${activeView}_${selectedPlayer}` : activeView;
    if (viewData[cacheKey]) return;

    const fetchers = {
      shots: () => fetchShots(matchId),
      passNetwork: () => fetchPassNetwork(matchId),
      momentum: () => fetchMomentum(matchId),
      territory: () => fetchTerritory(matchId),
      defensive: () => fetchDefensiveActions(matchId),
      zoneEntries: () => fetchZoneEntries(matchId),
      setPieces: () => fetchSetPieces(matchId),
      averageShape: () => fetchAverageShape(matchId),
      playerHeatmap: () => selectedPlayer ? fetchPlayerHeatmap(matchId, selectedPlayer) : null,
      playerPassSonar: () => selectedPlayer ? fetchPlayerPassSonar(matchId, selectedPlayer) : null,
    };

    const fetcher = fetchers[activeView];
    if (!fetcher) return;
    const promise = fetcher();
    if (!promise) return;

    promise
      .then(data => setViewData(prev => ({ ...prev, [cacheKey]: data })))
      .catch(console.error);
  }, [matchId, activeView, selectedPlayer, summary]);

  // ── Player selection ────────────────────────────────────────────────────
  const handleSelectPlayer = useCallback((player) => {
    if (player) {
      setSelectedPlayer(player);
      if (!PLAYER_VIEWS.find(v => v.id === activeView)) {
        setActiveView('playerHeatmap');
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
  function renderView() {
    const data = viewData[activeView];
    
    if (activeView === 'shots') {
      return <ShotMapView data={data} homeTeam={homeTeam} awayTeam={awayTeam} />;
    }
    if (activeView === 'passNetwork') {
      return <PassNetworkView data={data} homeTeam={homeTeam} awayTeam={awayTeam} />;
    }
    if (activeView === 'zoneEntries') {
      return <ZoneEntriesView data={data} homeTeam={homeTeam} awayTeam={awayTeam} />;
    }
    if (activeView === 'defensive') {
      return <DefensiveActionsView data={data} homeTeam={homeTeam} awayTeam={awayTeam} />;
    }
    if (activeView === 'setPieces') {
      return <SetPiecesView data={data} homeTeam={homeTeam} awayTeam={awayTeam} />;
    }
    if (activeView === 'averageShape') {
      return <AverageShapeView data={data} homeTeam={homeTeam} awayTeam={awayTeam} />;
    }
    
    return <div className="dash-error container"><p>Visualisation not built yet.</p></div>;
  }

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

      {/* Advanced Metrics Terminal */}
      <AdvancedMetrics matchId={matchId} homeTeam={homeTeam} awayTeam={awayTeam} />

      {/* Single View Panel */}
      <section className="view-panel">
        <div className="view-selector-header">
          <span className="view-selector-label">Visualisation:</span>
          <select 
            className="view-dropdown" 
            value={activeView} 
            onChange={(e) => setActiveView(e.target.value)}
          >
            {TEAM_VIEWS.map(v => (
              <option key={v.id} value={v.id}>{v.label}</option>
            ))}
          </select>
        </div>
        <div className="view-content">
          {renderView()}
        </div>
      </section>
    </div>
  );
}
