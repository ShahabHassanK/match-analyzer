/**
 * App.jsx — Match Analyzer
 * =========================
 * Two-screen architecture:
 *   1. HomePage: Team search + URL paste + match selection → triggers scraping
 *   2. Dashboard: Full tactical analysis for a scraped/loaded match
 *
 * All backend logic is fully abstracted behind the API client.
 */

import { useState, useEffect, useCallback } from 'react';
import './App.css';

import Header from './components/Header';
import HomePage from './components/HomePage';
import Dashboard from './components/Dashboard';

export default function App() {
  // null = homepage, string = match dashboard
  const [activeMatchId, setActiveMatchId] = useState(null);

  const handleMatchSelected = useCallback((matchId) => {
    setActiveMatchId(matchId);
  }, []);

  const handleBackToHome = useCallback(() => {
    setActiveMatchId(null);
  }, []);

  return (
    <div className="app">
      <Header onLogoClick={handleBackToHome} />
      <main className="main">
        {activeMatchId ? (
          <Dashboard matchId={activeMatchId} onBack={handleBackToHome} />
        ) : (
          <HomePage onMatchSelected={handleMatchSelected} />
        )}
      </main>
      <footer className="footer">
        <span>Data source: WhoScored • Built for tactical analysis</span>
      </footer>
    </div>
  );
}
