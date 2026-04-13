import { useState, useEffect, useRef, useMemo } from 'react';
import './GoalReplaysView.css';

export default function GoalReplaysView({ data }) {
  const [selectedGoalIdx, setSelectedGoalIdx] = useState(0);
  const [step, setStep] = useState(0); // 0 means before the first event starts
  const [isPlaying, setIsPlaying] = useState(false);
  const [ballPos, setBallPos] = useState({ x: 50, y: 50, gliding: false });
  
  const timerRef = useRef(null);

  const sequences = data?.sequences || [];
  const activeSequence = sequences[selectedGoalIdx];
  const events = activeSequence?.events || [];
  const homeTeam = data?.homeTeam;

  // Reset when goal changes
  useEffect(() => {
    handleReset();
  }, [selectedGoalIdx]);

  // Main playback loop
  useEffect(() => {
    if (!isPlaying) {
      if (timerRef.current) clearTimeout(timerRef.current);
      return;
    }

    if (step < events.length) {
      const evt = events[step];

      // 1. Snap ball to the player's feet
      setBallPos({ ...posToPercent(evt.x, evt.y, evt.team, evt.period), gliding: false });

      // 2. A tiny delay to allow the DOM to digest the snap, then trigger the glide
      const glideTimer = setTimeout(() => {
        setBallPos({ ...posToPercent(evt.endX, evt.endY, evt.team, evt.period), gliding: true });
        
        // 3. Advance to the next step after the glide duration (800ms) + a pause (200ms)
        timerRef.current = setTimeout(() => {
          setStep(s => s + 1);
        }, 1000);
      }, 50);

      return () => {
        clearTimeout(glideTimer);
        clearTimeout(timerRef.current);
      };
    } else {
      // Reached the end
      setIsPlaying(false);
    }
  }, [isPlaying, step, events]);

  if (!sequences || sequences.length === 0) {
    return <div className="no-data">No open play goals capable of being sequenced were found.</div>;
  }

  const handlePlayPause = () => {
    if (step >= events.length) {
      handleReset();
      // small delay to let reset take effect
      setTimeout(() => setIsPlaying(true), 100);
    } else {
      setIsPlaying(!isPlaying);
    }
  };

  const handleReset = () => {
    setIsPlaying(false);
    if (timerRef.current) clearTimeout(timerRef.current);
    setStep(0);
    if (events.length > 0) {
      setBallPos({ ...posToPercent(events[0].x, events[0].y, events[0].team, events[0].period), gliding: false });
    }
  };

  // Horizontal Pitch mapping. Screen X is Length, Screen Y is Width.
  function posToPercent(evtX, evtY, teamArg, periodArg) {
    const isHome = teamArg === homeTeam;
    // By convention, assume Home team attacks RIGHT in FirstHalf, and LEFT in SecondHalf.
    // Ensure "SecondHalf" exact text match from WhoScored data (or handle minute if period is missing).
    const isSecondHalf = periodArg === "SecondHalf";
    
    let attacksRight = isHome;
    if (isSecondHalf) {
      attacksRight = !attacksRight; // Switch sides
    }
    
    // WhoScored data always has X=100 as the goal they are attacking.
    if (attacksRight) {
      // Attacking Right visually. X=100 maps to 100%. Left Wing (Y=100) maps to Top (Y=0) or Bottom (Y=100)?
      return { x: evtX, y: 100 - evtY }; // 100-evtY keeps standard TV wings.
    } else {
      // Attacking Left visually. X=100 maps to 0%.
      return { x: 100 - evtX, y: evtY };
    }
  }

  function getInitials(name) {
    if (!name) return "";
    const parts = name.split(" ");
    if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  return (
    <div className="goal-replay-container">
      {/* Controls */}
      <div className="goal-selector">
        <label>Select Goal:</label>
        <select 
          value={selectedGoalIdx} 
          onChange={e => setSelectedGoalIdx(Number(e.target.value))}
        >
          {sequences.map((seq, idx) => (
            <option key={idx} value={idx}>
              {seq.minute}' - {seq.scorer} ({seq.team}) [{seq.events.length} actions]
            </option>
          ))}
        </select>
        
        <div className="playback-controls">
          <button onClick={handleReset}>⏮ Reset</button>
          <button className="play-btn" onClick={handlePlayPause}>
            {isPlaying ? '⏸ Pause' : step >= events.length ? '🔄 Replay' : '▶ Play'}
          </button>
        </div>
      </div>

      {/* Pitch Area */}
      <div className="pitch-container">
        {/* Draw Pitch Lines via standard SVG */}
        <svg className="drawing-layer" viewBox="0 0 100 100" preserveAspectRatio="none">
          {/* Pitch Markings */}
          <rect width="100" height="100" fill="#111827" />
          <path d="M 50 0 L 50 100 M 0 20.3 L 15.7 20.3 L 15.7 79.7 L 0 79.7 M 100 20.3 L 84.3 20.3 L 84.3 79.7 L 100 79.7 M 0 36.8 L 5.7 36.8 L 5.7 63.2 L 0 63.2 M 100 36.8 L 94.3 36.8 L 94.3 63.2 L 100 63.2" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="0.3" />
          {/* Center Circle: rx=9.15/105*100=8.71, ry=9.15/68*100=13.45 */}
          <ellipse cx="50" cy="50" rx="8.71" ry="13.45" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="0.3" />
          <ellipse cx="10.5" cy="50" rx="0.3" ry="0.5" fill="rgba(255,255,255,0.2)" />
          <ellipse cx="89.5" cy="50" rx="0.3" ry="0.5" fill="rgba(255,255,255,0.2)" />
          {/* D-Arcs */}
          <path d="M 15.7 37.6 A 8.71 13.45 0 0 1 15.7 62.4" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="0.3" />
          <path d="M 84.3 37.6 A 8.71 13.45 0 0 0 84.3 62.4" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="0.3" />
          
          {/* Draw historical traces (from events before current step) */}
          {events.slice(0, step).map((evt, idx) => {
            const p1 = posToPercent(evt.x, evt.y, evt.team, evt.period);
            const p2 = posToPercent(evt.endX, evt.endY, evt.team, evt.period);
            return (
              <g key={`history-${idx}`}>
                <line 
                  x1={p1.x} y1={p1.y} 
                  x2={p2.x} y2={p2.y} 
                  stroke={evt.team === activeSequence.team ? "rgba(16, 185, 129, 0.5)" : "rgba(239, 68, 68, 0.5)"} 
                  strokeWidth="0.4"
                  className="historical-line"
                />
              </g>
            );
          })}
          
          {/* Draw the actively animating line */}
          {isPlaying && step < events.length && (() => {
            const evt = events[step];
            const p1 = posToPercent(evt.x, evt.y, evt.team, evt.period);
            const p2 = posToPercent(evt.endX, evt.endY, evt.team, evt.period);
            return (
              <line
                x1={p1.x} y1={p1.y}
                x2={p2.x} y2={p2.y}
                stroke="rgba(16, 185, 129, 0.9)"
                strokeWidth="0.6"
                className="animating-line"
              />
            );
          })()}

          {/* If the goal is complete, highlight the final shot line */}
          {step >= events.length && events.length > 0 && events[events.length-1].isGoal && (() => {
            const last = events[events.length-1];
            const p1 = posToPercent(last.x, last.y, last.team, last.period);
            const p2 = posToPercent(last.endX, last.endY, last.team, last.period);
            return (
              <line
                x1={p1.x} y1={p1.y}
                x2={p2.x} y2={p2.y}
                stroke="#10b981"
                strokeWidth="0.8"
              />
            );
          })()}
        </svg>

        {/* DOM HTML Overlays for Markers and Ball */}
        
        {/* Render markers for all players involved up to the CURRENT step */}
        {events.slice(0, step + 1).map((evt, idx) => {
          const pt = posToPercent(evt.x, evt.y, evt.team, evt.period);
          const isHomeEvt = evt.team === homeTeam;
          return (
            <div 
              key={`marker-${idx}`} 
              className="event-marker" 
              style={{ left: `${pt.x}%`, top: `${pt.y}%` }}
            >
              <div className={`marker-dot ${isHomeEvt ? 'home' : 'away'}`}>
                {getInitials(evt.player)}
              </div>
              <div className="marker-label">
                {evt.player}
              </div>
            </div>
          );
        })}

        {/* Render the goalscorer marker at the end of the shot if complete */}
        {step >= events.length && events.length > 0 && events[events.length-1].isGoal && (() => {
            const last = events[events.length-1];
            const pt = posToPercent(last.endX, last.endY, last.team, last.period);
            const isHomeEvt = last.team === homeTeam;
            return (
              <div 
                className="event-marker pulse" 
                style={{ left: `${pt.x}%`, top: `${pt.y}%` }}
              >
                <div className={`marker-dot goal ${isHomeEvt ? 'home' : 'away'}`} style={{background: '#10b981', color: '#fff', borderColor: '#10b981', boxShadow: '0 0 10px #10b981'}}>⚽</div>
                <div className="marker-label" style={{color: '#10b981', fontWeight: 'bold' }}>GOAL!</div>
              </div>
            );
        })()}

        {/* The Animated Ball */}
        <div 
          className={`football ${ballPos.gliding ? 'gliding' : ''}`}
          style={{ 
            left: `${ballPos.x}%`, 
            top: `${ballPos.y}%` 
          }} 
        >
          ⚽
        </div>
        
      </div>
    </div>
  );
}
