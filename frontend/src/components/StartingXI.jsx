/**
 * StartingXI
 * ==========
 * Side-by-side player list for both teams.
 * Clicking a player triggers onSelectPlayer callback.
 */

import './StartingXI.css';

export default function StartingXI({ xi, selectedPlayer, onSelectPlayer }) {
  if (!xi) return null;
  const { homeTeam, awayTeam, homeXI, awayXI, homeSubs, awaySubs } = xi;

  return (
    <section className="starting-xi">
      <h2 className="xi-heading">Line-ups</h2>
      <div className="xi-columns">
        {/* Home */}
        <div className="xi-column">
          <div className="xi-team-header home">
            <span className="xi-team-dot home-dot" />
            <span className="xi-team-name">{homeTeam}</span>
          </div>
          <ul className="xi-list">
            {homeXI.map((player, i) => (
              <li key={player}>
                <button
                  className={`xi-player ${selectedPlayer === player ? 'active' : ''}`}
                  onClick={() => onSelectPlayer(selectedPlayer === player ? null : player)}
                >
                  <span className="xi-number">{i + 1}</span>
                  <span className="xi-name">{player}</span>
                  {selectedPlayer === player && <span className="xi-active-dot" />}
                </button>
              </li>
            ))}
          </ul>
          
          {homeSubs && homeSubs.length > 0 && (
            <>
              <div className="xi-team-header home" style={{ marginTop: '24px', borderTop: '1px solid var(--border-light)', paddingTop: '12px' }}>
                <span className="xi-team-name" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Substitutes</span>
              </div>
              <ul className="xi-list">
                {homeSubs.map((player, i) => (
                  <li key={player}>
                    <button
                      className={`xi-player ${selectedPlayer === player ? 'active' : ''}`}
                      onClick={() => onSelectPlayer(selectedPlayer === player ? null : player)}
                    >
                      <span className="xi-number sub-number">-</span>
                      <span className="xi-name">{player}</span>
                      {selectedPlayer === player && <span className="xi-active-dot" />}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>

        {/* Away */}
        <div className="xi-column">
          <div className="xi-team-header away">
            <span className="xi-team-dot away-dot" />
            <span className="xi-team-name">{awayTeam}</span>
          </div>
          <ul className="xi-list">
            {awayXI.map((player, i) => (
              <li key={player}>
                <button
                  className={`xi-player ${selectedPlayer === player ? 'active' : ''}`}
                  onClick={() => onSelectPlayer(selectedPlayer === player ? null : player)}
                >
                  <span className="xi-number">{i + 1}</span>
                  <span className="xi-name">{player}</span>
                  {selectedPlayer === player && <span className="xi-active-dot" />}
                </button>
              </li>
            ))}
          </ul>

          {awaySubs && awaySubs.length > 0 && (
            <>
              <div className="xi-team-header away" style={{ marginTop: '24px', borderTop: '1px solid var(--border-light)', paddingTop: '12px' }}>
                <span className="xi-team-name" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Substitutes</span>
              </div>
              <ul className="xi-list">
                {awaySubs.map((player, i) => (
                  <li key={player}>
                    <button
                      className={`xi-player ${selectedPlayer === player ? 'active' : ''}`}
                      onClick={() => onSelectPlayer(selectedPlayer === player ? null : player)}
                    >
                      <span className="xi-number sub-number">-</span>
                      <span className="xi-name">{player}</span>
                      {selectedPlayer === player && <span className="xi-active-dot" />}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
