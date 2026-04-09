import './Header.css';

export default function Header({ onLogoClick }) {
  return (
    <header className="header">
      <div className="header-inner container">
        <button className="header-brand" onClick={onLogoClick}>
          <svg className="header-logo" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 2 C14.5 6, 18 8, 22 12 C18 16, 14.5 18, 12 22 C9.5 18, 6 16, 2 12 C6 8, 9.5 6, 12 2Z" />
          </svg>
          <h1 className="header-title">Match Analyzer</h1>
        </button>
        <span className="header-badge">Beta</span>
      </div>
    </header>
  );
}
