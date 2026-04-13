/**
 * HomePage
 * ========
 * The entry point of the application.
 * Three ways to load a match:
 *   1. Search by team name (with autocomplete) → browse fixtures → select one → scrape
 *   2. Paste a WhoScored URL directly → scrape
 *   3. Pick from already-scraped matches in backend/data/
 */

import { useState, useEffect, useRef } from 'react';
import './HomePage.css';
import { searchFixtures, scrapeMatch, fetchMatches, fetchTeams } from '../services/api';

export default function HomePage({ onMatchSelected }) {
  // Search state
  const [teamQuery, setTeamQuery] = useState('');
  const [fixtures, setFixtures] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState('');

  // Autocomplete state
  const [knownTeams, setKnownTeams] = useState([]);
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const autocompleteRef = useRef(null);

  // URL paste state
  const [pasteUrl, setPasteUrl] = useState('');

  const [scraping, setScraping] = useState(false);
  const [scrapingStatus, setScrapingStatus] = useState('');
  const [scrapingError, setScrapingError] = useState(false); // New state to track if we're in an error state

  // Previously scraped matches
  const [existingMatches, setExistingMatches] = useState([]);

  // Load existing matches & available teams on mount
  useEffect(() => {
    fetchMatches()
      .then(data => setExistingMatches(data.matches || []))
      .catch(() => {});
    
    fetchTeams()
      .then(data => setKnownTeams(data.teams || []))
      .catch(() => {});
  }, []);

  // Handle click outside for autocomplete
  useEffect(() => {
    function handleClickOutside(event) {
      if (autocompleteRef.current && !autocompleteRef.current.contains(event.target)) {
        setShowAutocomplete(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [autocompleteRef]);

  // ── Search ──────────────────────────────────────────────────────────────
  const handleSearch = async (e) => {
    e?.preventDefault();
    if (!teamQuery.trim()) return;

    setShowAutocomplete(false);
    setSearchLoading(true);
    setSearchError('');
    setFixtures([]);

    try {
      const result = await searchFixtures(teamQuery.trim());
      setFixtures(result.fixtures || []);
      if (!result.fixtures?.length) {
        setSearchError('No fixtures found. Try a different team name.');
      }
    } catch (err) {
      setSearchError(err.message);
    } finally {
      setSearchLoading(false);
    }
  };

  const handleSelectTeam = (team) => {
    setTeamQuery(team);
    setShowAutocomplete(false);
    // Optionally trigger search immediately
    setTimeout(() => {
      setTeamQuery(team);
      searchSpecificTeam(team);
    }, 0);
  };

  const searchSpecificTeam = async (teamName) => {
    setSearchLoading(true);
    setSearchError('');
    setFixtures([]);

    try {
      const result = await searchFixtures(teamName);
      setFixtures(result.fixtures || []);
      if (!result.fixtures?.length) {
        setSearchError('No fixtures found. Try a different team name.');
      }
    } catch (err) {
      setSearchError(err.message);
    } finally {
      setSearchLoading(false);
    }
  }

  // ── Scrape ──────────────────────────────────────────────────────────────
  const doScrape = async (url) => {
    setScraping(true);
    setScrapingError(false);
    setScrapingStatus('Connecting to WhoScored…');

    try {
      setScrapingStatus('Scraping match events… This may take roughly 20-30 seconds.');
      const result = await scrapeMatch(url);
      setScrapingStatus(`✅ Scraped ${result.event_count} events. Loading dashboard…`);

      setTimeout(() => {
        setScraping(false); // Clear overlay before navigating
        onMatchSelected(result.match_id);
      }, 800);
    } catch (err) {
      setScrapingError(true);
      setScrapingStatus(`❌ ${err.message}`);
      // Do not setScraping(false) here, so the user can read the error message.
    }
  };


  const handleScrapeFromUrl = (e) => {
    e.preventDefault();
    if (!pasteUrl.trim()) return;
    doScrape(pasteUrl.trim());
  };

  const handleFixtureClick = (fixture) => {
    doScrape(fixture.whoscored_url);
  };

  const filteredTeams = knownTeams.filter(t => 
    t.toLowerCase().includes(teamQuery.toLowerCase())
  );

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="home-wrapper">
      <div className="home-page container">
      <section className="home-hero">
        <h2 className="hero-title">Match Analyzer</h2>
        <p className="hero-subtitle">
          Deconstruct the tactical matrix. Reveal truth hidden in elite match data.
        </p>
      </section>

      <div className="home-grid">
        {/* ── Left: Team Search ─────────────────────────────────────────── */}
        <section className="home-card">
          <h3 className="card-title">
            Search by Team
          </h3>
          <form className="search-form" onSubmit={handleSearch}>
            <div className="autocomplete-wrapper" ref={autocompleteRef}>
              <input
                type="text"
                className="search-input"
                placeholder="e.g. Real Madrid"
                value={teamQuery}
                onFocus={() => setShowAutocomplete(true)}
                onChange={e => {
                  setTeamQuery(e.target.value);
                  setShowAutocomplete(true);
                }}
                disabled={scraping}
                autoComplete="off"
              />
              {showAutocomplete && teamQuery && filteredTeams.length > 0 && (
                <ul className="autocomplete-list">
                  {filteredTeams.map((team, idx) => (
                    <li 
                      key={idx} 
                      className="autocomplete-item"
                      onClick={() => handleSelectTeam(team)}
                    >
                      {team}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <button type="submit" className="btn btn-primary" disabled={searchLoading || scraping || !teamQuery.trim()}>
              {searchLoading ? 'Searching…' : 'Search Recent Fixtures'}
            </button>
          </form>

          {searchError && <p className="search-error">{searchError}</p>}

          {fixtures.length > 0 && (
            <div className="fixture-list">
              <div className="fixture-list-header">
                <span>{fixtures.length} recent fixtures found</span>
              </div>
              {fixtures.map((f, i) => (
                <button
                  key={f.match_id || i}
                  className="fixture-row"
                  onClick={() => handleFixtureClick(f)}
                  disabled={scraping}
                >
                  <div className="fixture-teams">
                    <span className="fixture-home">{f.home_team}</span>
                    <span className="fixture-vs">vs</span>
                    <span className="fixture-away">{f.away_team}</span>
                  </div>
                  <div className="fixture-meta">
                    <span className="fixture-comp">{f.competition}</span>
                    <span className="fixture-date">{f.date_str}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>

        {/* ── Right: URL Paste ────────────────────────────────────────── */}
        <div className="home-right">
          <section className="home-card">
            <h3 className="card-title">
              Paste WhoScored URL
            </h3>
            <form className="url-form" onSubmit={handleScrapeFromUrl}>
              <input
                type="url"
                className="search-input"
                placeholder="https://www.whoscored.com/Matches/..."
                value={pasteUrl}
                onChange={e => setPasteUrl(e.target.value)}
                disabled={scraping}
              />
              <button type="submit" className="btn btn-primary" disabled={!pasteUrl.trim() || scraping}>
                {scraping ? 'Scraping…' : 'Load Match Dashboard'}
              </button>
            </form>
          </section>
        </div>
      </div>

      {/* ── Full-width: Saved Matches ─────────────────────────────────── */}
      {existingMatches.length > 0 && (
        <section className="home-card saved-matches-card">
          <h3 className="card-title">
            Saved Database Matches
            <span className="match-count">{existingMatches.length}</span>
          </h3>
          <div className="existing-list">
            {existingMatches.map(m => (
              <button
                key={m.id}
                className="existing-row"
                onClick={() => onMatchSelected(m.id)}
                disabled={scraping}
              >
                <span className="existing-name">{m.displayName}</span>
                <span className="existing-meta">{m.scrapedAt || ''}</span>
                <span className="existing-arrow">→</span>
              </button>
            ))}
          </div>
        </section>
      )}

      {scraping && (
        <div className="scraping-overlay">
          <div className="scraping-modal">
            {!scrapingError && <div className="scraping-spinner" />}
            <p className="scraping-text">{scrapingStatus}</p>
            {scrapingError && (
              <button 
                className="btn btn-primary" 
                style={{ marginTop: '16px' }}
                onClick={() => {
                  setScraping(false);
                  setScrapingError(false);
                }}
              >
                Close
              </button>
            )}
          </div>
        </div>
      )}
    </div>
    </div>
  );
}
