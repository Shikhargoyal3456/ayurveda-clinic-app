import React from 'react';

/**
 * DosageTimingBadge
 * Parses prescription frequency notation (like 1-0-1, 1-1-1, 1-0-0, 0-0-1, BD, TDS, OD)
 * and visually breaks it down into 3 times of the day:
 * Position 1 = Morning (☀️)
 * Position 2 = Afternoon (🌤️)
 * Position 3 = Night (🌙)
 * where 1 (or >0) = Taken / Active, and 0 = Not taken / Skip.
 */
export default function DosageTimingBadge({ frequency = '1-0-1', compact = false }) {
  const raw = String(frequency || '').trim();

  // Normalize Latin medical abbreviations to 3-slot pattern
  let pattern = raw;
  const upper = raw.toUpperCase();
  if (upper === 'BD' || upper === 'BID' || upper.includes('TWICE DAILY') || upper.includes('TWICE A DAY')) pattern = '1-0-1';
  else if (upper === 'TDS' || upper === 'TID' || upper.includes('THREE TIMES DAILY') || upper.includes('THRICE')) pattern = '1-1-1';
  else if (upper === 'OD' || upper.includes('ONCE DAILY') || upper.includes('ONCE A DAY')) pattern = '1-0-0';
  else if (upper === 'HS' || upper.includes('BEDTIME') || upper.includes('AT NIGHT')) pattern = '0-0-1';
  else if (upper.includes('AFTER MEALS') || upper.includes('AFTER FOOD') || upper.includes('AFTER LUNCH AND DINNER')) pattern = '1-0-1';

  // Check if matches X-Y-Z pattern (e.g. 1-0-1, 1-1-1, 1/2-0-1/2, or 1-0-1 [Morning: 1, ...])
  const match = pattern.match(/([0-9/]+)\s*[-–—]\s*([0-9/]+)\s*[-–—]\s*([0-9/]+)/);

  if (!match) {
    // Fallback for non-standard frequencies (like SOS, Weekly, Once daily)
    return (
      <span style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: '6px',
        background: 'rgba(6, 182, 212, 0.14)',
        color: '#06B6D4',
        fontWeight: '600',
        fontSize: '0.78rem'
      }}>
        {raw || '1-0-1'}
      </span>
    );
  }

  const mVal = match[1];
  const aVal = match[2];
  const nVal = match[3];
  const displayPattern = `${mVal}-${aVal}-${nVal}`;
  const mActive = mVal !== '0' && mVal !== '' && mVal !== '-';
  const aActive = aVal !== '0' && aVal !== '' && aVal !== '-';
  const nActive = nVal !== '0' && nVal !== '' && nVal !== '-';

  // Derive human explanation
  let scheduleLabel = '';
  if (mActive && !aActive && nActive) scheduleLabel = 'Twice Daily (Morning & Night)';
  else if (mActive && aActive && nActive) scheduleLabel = '3 Times Daily (Morning, Afternoon, Night)';
  else if (mActive && !aActive && !nActive) scheduleLabel = 'Once Daily (Morning Only)';
  else if (!mActive && !aActive && nActive) scheduleLabel = 'Once Daily (Night / Bedtime)';
  else if (!mActive && aActive && !nActive) scheduleLabel = 'Once Daily (Afternoon Only)';
  else if (mActive && aActive && !nActive) scheduleLabel = 'Twice Daily (Morning & Afternoon)';
  else if (!mActive && aActive && nActive) scheduleLabel = 'Twice Daily (Afternoon & Night)';
  else scheduleLabel = `${pattern} Schedule`;

  if (compact) {
    return (
      <div 
        title={`${displayPattern}: ${scheduleLabel} — Morning: ${mActive ? mVal : 'Skip'}, Afternoon: ${aActive ? aVal : 'Skip'}, Night: ${nActive ? nVal : 'Skip'}`}
        style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}
      >
        <span style={{
          padding: '2px 6px',
          borderRadius: '4px',
          background: 'rgba(6, 182, 212, 0.15)',
          color: '#06B6D4',
          fontWeight: '800',
          fontSize: '0.78rem',
          marginRight: '3px'
        }}>
          {displayPattern}
        </span>
        <span style={{
          padding: '1px 5px',
          borderRadius: '4px',
          fontSize: '0.7rem',
          fontWeight: mActive ? '700' : '500',
          background: mActive ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.04)',
          color: mActive ? '#10B981' : '#64748B',
          border: mActive ? '1px solid rgba(16, 185, 129, 0.35)' : '1px solid rgba(255, 255, 255, 0.05)'
        }}>
          ☀️ {mVal}
        </span>
        <span style={{
          padding: '1px 5px',
          borderRadius: '4px',
          fontSize: '0.7rem',
          fontWeight: aActive ? '700' : '500',
          background: aActive ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.04)',
          color: aActive ? '#10B981' : '#64748B',
          border: aActive ? '1px solid rgba(16, 185, 129, 0.35)' : '1px solid rgba(255, 255, 255, 0.05)'
        }}>
          🌤️ {aVal}
        </span>
        <span style={{
          padding: '1px 5px',
          borderRadius: '4px',
          fontSize: '0.7rem',
          fontWeight: nActive ? '700' : '500',
          background: nActive ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.04)',
          color: nActive ? '#10B981' : '#64748B',
          border: nActive ? '1px solid rgba(16, 185, 129, 0.35)' : '1px solid rgba(255, 255, 255, 0.05)'
        }}>
          🌙 {nVal}
        </span>
      </div>
    );
  }

  return (
    <div style={{ display: 'inline-flex', flexDirection: 'column', gap: '4px' }}>
      {/* Pattern Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span style={{
          padding: '2px 8px',
          borderRadius: '6px',
          background: 'rgba(6, 182, 212, 0.16)',
          color: '#06B6D4',
          fontWeight: '800',
          fontSize: '0.8rem',
          letterSpacing: '0.04em'
        }}>
          {displayPattern}
        </span>
        <span style={{ fontSize: '0.72rem', color: '#94A3B8', fontWeight: '600' }}>
          {scheduleLabel}
        </span>
      </div>

      {/* 3 Times Breakdown: Morning | Afternoon | Night */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap' }}>
        {/* Morning Slot */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '3px',
          padding: '2px 6px',
          borderRadius: '5px',
          fontSize: '0.72rem',
          fontWeight: mActive ? '700' : '500',
          background: mActive ? 'rgba(16, 185, 129, 0.18)' : 'rgba(255, 255, 255, 0.03)',
          color: mActive ? '#10B981' : '#64748B',
          border: mActive ? '1px solid rgba(16, 185, 129, 0.35)' : '1px solid rgba(255, 255, 255, 0.06)'
        }}>
          <span>☀️ Morning:</span>
          <span style={{
            padding: '1px 5px',
            borderRadius: '4px',
            background: mActive ? '#10B981' : '#334155',
            color: mActive ? '#0B1512' : '#94A3B8',
            fontWeight: '800',
            fontSize: '0.68rem'
          }}>
            {mActive ? `${mVal} (Take)` : '0 (Skip)'}
          </span>
        </div>

        {/* Afternoon Slot */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '3px',
          padding: '2px 6px',
          borderRadius: '5px',
          fontSize: '0.72rem',
          fontWeight: aActive ? '700' : '500',
          background: aActive ? 'rgba(16, 185, 129, 0.18)' : 'rgba(255, 255, 255, 0.03)',
          color: aActive ? '#10B981' : '#64748B',
          border: aActive ? '1px solid rgba(16, 185, 129, 0.35)' : '1px solid rgba(255, 255, 255, 0.06)'
        }}>
          <span>🌤️ Afternoon:</span>
          <span style={{
            padding: '1px 5px',
            borderRadius: '4px',
            background: aActive ? '#10B981' : '#334155',
            color: aActive ? '#0B1512' : '#94A3B8',
            fontWeight: '800',
            fontSize: '0.68rem'
          }}>
            {aActive ? `${aVal} (Take)` : '0 (Skip)'}
          </span>
        </div>

        {/* Night Slot */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '3px',
          padding: '2px 6px',
          borderRadius: '5px',
          fontSize: '0.72rem',
          fontWeight: nActive ? '700' : '500',
          background: nActive ? 'rgba(16, 185, 129, 0.18)' : 'rgba(255, 255, 255, 0.03)',
          color: nActive ? '#10B981' : '#64748B',
          border: nActive ? '1px solid rgba(16, 185, 129, 0.35)' : '1px solid rgba(255, 255, 255, 0.06)'
        }}>
          <span>🌙 Night:</span>
          <span style={{
            padding: '1px 5px',
            borderRadius: '4px',
            background: nActive ? '#10B981' : '#334155',
            color: nActive ? '#0B1512' : '#94A3B8',
            fontWeight: '800',
            fontSize: '0.68rem'
          }}>
            {nActive ? `${nVal} (Take)` : '0 (Skip)'}
          </span>
        </div>
      </div>
    </div>
  );
}
