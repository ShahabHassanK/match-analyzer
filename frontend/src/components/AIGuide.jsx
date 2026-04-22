import { useState, useRef, useCallback, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { explainFeature } from '../services/api';
import './AIGuide.css';

const LABELS = {
  shots:          'Shot Map',
  passNetwork:    'Pass Network',
  momentum:       'Match Momentum',
  defensive:      'Defensive Actions',
  zoneEntries:    'Creative Play',
  setPieces:      'Set Pieces',
  averageShape:   'Tactical Shape',
  gradientScoring:'Gradient Scoring',
  advancedMetrics:'Advanced Metrics',
};

export default function AIGuide({ matchId, feature }) {
  const [isOpen, setIsOpen]   = useState(false);
  const [text, setText]       = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);
  const readerRef             = useRef(null);

  const abort = () => {
    if (readerRef.current) {
      readerRef.current.cancel().catch(() => {});
      readerRef.current = null;
    }
  };

  const close = useCallback(() => {
    abort();
    setIsOpen(false);
  }, []);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e) => { if (e.key === 'Escape') close(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, close]);

  const handleToggle = useCallback(async () => {
    if (isOpen) { close(); return; }

    setIsOpen(true);
    setLoading(true);
    setText('');
    setError(null);

    let response;
    try {
      response = await explainFeature(matchId, feature);
      if (!response.ok) throw new Error(`Server error ${response.status}`);
    } catch (e) {
      setError(e.message);
      setLoading(false);
      return;
    }

    const reader = response.body.getReader();
    readerRef.current = reader;
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() ?? '';
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith('data:')) continue;
          let event;
          try { event = JSON.parse(line.slice(5).trim()); } catch { continue; }
          if (event.type === 'chunk') {
            setLoading(false);
            setText(prev => prev + event.text);
          } else if (event.type === 'done') {
            setLoading(false);
          } else if (event.type === 'error') {
            setError(event.message);
            setLoading(false);
          }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') setError(e.message);
      setLoading(false);
    }

    readerRef.current = null;
  }, [matchId, feature, isOpen, close]);

  const label = LABELS[feature] || feature;

  const drawer = isOpen ? (
    <>
      <div className="aig-backdrop" onClick={close} />
      <div className="aig-drawer">
        <div className="aig-panel-header">
          <span className="aig-panel-title">✦ {label}</span>
          <button className="aig-panel-close" onClick={close}>✕</button>
        </div>
        <div className="aig-panel-body">
          {loading && (
            <div className="aig-dots">
              <span /><span /><span />
            </div>
          )}
          {error && <p className="aig-error">{error}</p>}
          {text && <p className="aig-text">{text}</p>}
        </div>
      </div>
    </>
  ) : null;

  return (
    <div className="aig-wrap">
      <button
        className={`aig-btn ${isOpen ? 'aig-btn--active' : ''}`}
        onClick={handleToggle}
        title={`AI Guide: ${label}`}
      >
        ✦ AI Guide
      </button>
      {createPortal(drawer, document.body)}
    </div>
  );
}
