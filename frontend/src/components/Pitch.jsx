/**
 * Pitch Component
 * ================
 * Reusable SVG football pitch calibrated to the WhoScored 0-100 coordinate system.
 * Lush green grass with white markings, editorial quality.
 *
 * Props:
 *   children — SVG elements to overlay (circles, lines, rects, etc.)
 *   width    — CSS width (default: '100%')
 */

import './Pitch.css';

const PITCH_RATIO = 68 / 105; // FIFA standard aspect ratio

export default function Pitch({ children, width = '100%' }) {
  // viewBox maps to WhoScored's 0-100 x and 0-100 y
  return (
    <div className="pitch-container" style={{ width }}>
      <svg
        className="pitch-svg"
        viewBox="-2 -2 104 104"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          {/* Grass stripe pattern */}
          <pattern id="grassStripes" width="8.33" height="100" patternUnits="userSpaceOnUse">
            <rect width="4.165" height="100" fill="var(--pitch-green)" />
            <rect x="4.165" width="4.165" height="100" fill="var(--pitch-green-light)" />
          </pattern>
        </defs>

        {/* Pitch surface */}
        <rect x="0" y="0" width="100" height="100" rx="1" fill="url(#grassStripes)" />

        {/* Border */}
        <rect x="0" y="0" width="100" height="100" rx="1"
          fill="none" stroke="var(--pitch-line)" strokeWidth="0.4" />

        {/* Halfway line */}
        <line x1="50" y1="0" x2="50" y2="100"
          stroke="var(--pitch-line)" strokeWidth="0.3" />

        {/* Centre circle */}
        <circle cx="50" cy="50" r="9.15"
          fill="none" stroke="var(--pitch-line)" strokeWidth="0.3" />
        <circle cx="50" cy="50" r="0.5" fill="var(--pitch-line)" />

        {/* Left penalty area */}
        <rect x="0" y="21.1" width="17" height="57.8"
          fill="none" stroke="var(--pitch-line)" strokeWidth="0.3" />
        {/* Left 6-yard box */}
        <rect x="0" y="36.8" width="5.5" height="26.4"
          fill="none" stroke="var(--pitch-line)" strokeWidth="0.3" />
        {/* Left penalty spot */}
        <circle cx="11" cy="50" r="0.4" fill="var(--pitch-line)" />
        {/* Left penalty arc */}
        <path d="M 17 42.5 A 9.15 9.15 0 0 1 17 57.5"
          fill="none" stroke="var(--pitch-line)" strokeWidth="0.3" />
        {/* Left goal */}
        <rect x="-2" y="44.2" width="2" height="11.6"
          fill="none" stroke="var(--pitch-line)" strokeWidth="0.25" strokeDasharray="0.5,0.5" />

        {/* Right penalty area */}
        <rect x="83" y="21.1" width="17" height="57.8"
          fill="none" stroke="var(--pitch-line)" strokeWidth="0.3" />
        {/* Right 6-yard box */}
        <rect x="94.5" y="36.8" width="5.5" height="26.4"
          fill="none" stroke="var(--pitch-line)" strokeWidth="0.3" />
        {/* Right penalty spot */}
        <circle cx="89" cy="50" r="0.4" fill="var(--pitch-line)" />
        {/* Right penalty arc */}
        <path d="M 83 42.5 A 9.15 9.15 0 0 0 83 57.5"
          fill="none" stroke="var(--pitch-line)" strokeWidth="0.3" />
        {/* Right goal */}
        <rect x="100" y="44.2" width="2" height="11.6"
          fill="none" stroke="var(--pitch-line)" strokeWidth="0.25" strokeDasharray="0.5,0.5" />

        {/* Corner arcs */}
        <path d="M 0 2 A 2 2 0 0 1 2 0" fill="none" stroke="var(--pitch-line)" strokeWidth="0.25" />
        <path d="M 98 0 A 2 2 0 0 1 100 2" fill="none" stroke="var(--pitch-line)" strokeWidth="0.25" />
        <path d="M 0 98 A 2 2 0 0 0 2 100" fill="none" stroke="var(--pitch-line)" strokeWidth="0.25" />
        <path d="M 98 100 A 2 2 0 0 0 100 98" fill="none" stroke="var(--pitch-line)" strokeWidth="0.25" />

        {/* Data overlay layer */}
        <g className="pitch-data-layer">
          {children}
        </g>
      </svg>
    </div>
  );
}
