// Shared components — ETF Advisor v3
function fmtPct(v, d) {
  if (v == null) return '—';
  return (v > 0 ? '+' : '') + v.toFixed(d != null ? d : 2) + '%';
}
function chg(v) {
  if (v == null || v === 0) return 'var(--fg-3)';
  return v > 0 ? '#A8342A' : '#2A6B4F';
}

// Star display
function Stars({ n }) {
  if (n >= 5) return <span style={{ color: '#A8342A', letterSpacing: 1 }}>★★★★★</span>;
  if (n >= 4) return <span style={{ color: '#A8342A', letterSpacing: 1 }}>★★★★<span style={{ opacity: 0.25 }}>★</span></span>;
  if (n >= 3) return <span style={{ color: '#8B6914', letterSpacing: 1 }}>★★★<span style={{ opacity: 0.25 }}>★★</span></span>;
  if (n >= 2) return <span style={{ color: '#8B6914', letterSpacing: 1 }}>★★<span style={{ opacity: 0.25 }}>★★★</span></span>;
  if (n >= 1) return <span style={{ color: 'var(--fg-3)', letterSpacing: 1 }}>★<span style={{ opacity: 0.25 }}>★★★★</span></span>;
  if (n === 0) return <span style={{ color: 'var(--fg-muted)', fontSize: 10 }}>观望</span>;
  return <span style={{ color: '#2A6B4F', letterSpacing: 1 }}>✕</span>;
}

// Recommendation indicator — professional signal bars + label
function RecIndicator({ rec, stars }) {
  const isBuy = rec === '买入';
  const isSell = rec === '卖出';
  const isWait = !isBuy && !isSell;
  const absStars = Math.abs(stars);
  const maxBars = 5;

  // Color scheme
  const activeColor = isSell ? '#2A6B4F' : isBuy ? '#A8342A' : 'var(--fg-muted)';
  const inactiveColor = 'var(--ink-10)';

  // Label style
  const labelBg = isBuy && stars >= 4 ? 'rgba(168,52,42,0.1)' : isBuy ? 'rgba(168,52,42,0.06)' : isSell ? 'rgba(42,107,79,0.08)' : 'var(--ink-05)';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
      <span style={{
        fontFamily: 'var(--font-ui)', fontSize: 11, fontWeight: 600, color: activeColor,
        padding: '2px 6px', borderRadius: 2, background: labelBg,
      }}>{rec}</span>
      {!isWait && (
        <div style={{ display: 'flex', gap: 2 }}>
          {Array.from({ length: maxBars }, (_, i) => {
            const filled = i < absStars;
            return (
              <div key={i} style={{
                width: 8, height: 8, borderRadius: 1,
                background: filled ? activeColor : inactiveColor,
                opacity: filled ? (0.5 + 0.1 * i) : 1,
              }}></div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// Compact version for cards/mobile
function RecCompact({ rec, stars }) {
  const isBuy = rec === '买入';
  const isSell = rec === '卖出';
  const activeColor = isSell ? '#2A6B4F' : isBuy ? '#A8342A' : 'var(--fg-muted)';
  const absStars = Math.abs(stars);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <span style={{ fontFamily: 'var(--font-ui)', fontSize: 11, fontWeight: 600, color: activeColor }}>{rec}</span>
      {absStars > 0 && (
        <div style={{ display: 'flex', gap: 1.5 }}>
          {Array.from({ length: absStars }, (_, i) => (
            <div key={i} style={{ width: 6, height: 6, borderRadius: 1, background: activeColor, opacity: 0.5 + 0.1 * i }}></div>
          ))}
        </div>
      )}
    </div>
  );
}

// Pool badge — shows rotation pool membership
function PoolBadge({ pool }) {
  const [show, setShow] = React.useState(false);
  if (!pool) return null;
  return (
    <span style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
      <span onClick={e => { e.stopPropagation(); setShow(!show); }}
        style={{ fontFamily: 'var(--font-ui)', fontSize: 9, color: '#A8342A', cursor: 'pointer',
          background: 'rgba(168,52,42,0.08)', padding: '1px 4px', borderRadius: 2, lineHeight: 1.2 }}>◆</span>
      {show && (
        <span onClick={e => { e.stopPropagation(); setShow(false); }}
          style={{ position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 50,
            fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-2)', whiteSpace: 'nowrap',
            background: 'var(--paper)', border: '1px solid var(--ink-20)', padding: '6px 10px',
            borderRadius: 2, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
          推荐池ETF：基于历史溢价稳定性筛选，加分
        </span>
      )}
    </span>
  );
}

// Premium bar — thin horizontal indicator
function PremBar({ v, max }) {
  const w = Math.min(100, Math.abs(v) / (max || 8) * 100);
  const c = v > 4 ? '#A8342A' : v > 2 ? '#8B6914' : '#2A6B4F';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ width: 40, height: 3, background: 'var(--ink-05)', borderRadius: 2, flexShrink: 0, overflow: 'hidden' }}>
        <div style={{ width: w + '%', height: '100%', background: c, borderRadius: 2 }}></div>
      </div>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: chg(v) }}>{fmtPct(v)}</span>
    </div>
  );
}

// Eyebrow section label
function Label({ children, right }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
      <span style={{ fontFamily: 'var(--font-ui)', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--fg-3)' }}>{children}</span>
      {right && <span style={{ fontFamily: 'var(--font-ui)', fontSize: 11, color: 'var(--fg-muted)' }}>{right}</span>}
    </div>
  );
}

// Futures ticker
function FuturesTicker({ data, compact }) {
  if (!data || !data.length) return null;
  const latest = data[data.length - 1];
  const prev = data.length > 1 ? data[0] : null;
  const items = [
    { l: 'NQ', p: latest.nq_price, c: latest.nq_change },
    { l: 'ES', p: latest.es_price, c: latest.es_change },
    { l: 'YM', p: latest.ym_price, c: latest.ym_change },
  ];
  return (
    <div style={{ display: 'flex', gap: compact ? 10 : 20, padding: compact ? '8px 0' : '10px 0', borderBottom: '1px solid var(--ink-10)', overflowX: 'auto' }}>
      {items.map(f => (
        <div key={f.l} style={{ display: 'flex', alignItems: 'baseline', gap: 5, whiteSpace: 'nowrap' }}>
          <span style={{ fontFamily: 'var(--font-ui)', fontSize: compact ? 9 : 10, color: 'var(--fg-muted)', fontWeight: 600, letterSpacing: '0.04em' }}>{f.l}</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: compact ? 12 : 13, fontWeight: 500 }}>{f.p}</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: compact ? 10 : 11, color: chg(f.c) }}>{fmtPct(f.c)}</span>
        </div>
      ))}
      <span style={{ fontFamily: 'var(--font-ui)', fontSize: compact ? 8 : 9, color: 'var(--fg-muted)', alignSelf: 'center', marginLeft: 'auto' }}>{latest.date}</span>
    </div>
  );
}

// Table cell styles
const TH = {
  padding: '8px 6px', borderBottom: '1px solid var(--ink-20)',
  fontFamily: 'var(--font-ui)', fontSize: 10, fontWeight: 600,
  textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--fg-3)',
  textAlign: 'center', whiteSpace: 'nowrap', background: 'var(--paper)',
};
const TD = {
  padding: '8px 6px', borderBottom: '1px solid var(--ink-10)',
  textAlign: 'center', verticalAlign: 'middle', whiteSpace: 'nowrap',
};
const TDL = { ...TD, textAlign: 'left' };
const TDM = { ...TD, fontFamily: 'var(--font-mono)', fontSize: 12 };

// Refresh button — subtle, matches page style
function RefreshBtn({ compact }) {
  const [spinning, setSpin] = React.useState(false);
  const handleClick = (e) => {
    e.stopPropagation();
    setSpin(true);
    location.reload();
  };
  const size = compact ? 14 : 16;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="var(--fg-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
      onClick={handleClick}
      style={{ cursor: 'pointer', opacity: 0.5, transition: 'opacity 150ms',
        animation: spinning ? 'spin 0.6s linear infinite' : 'none' }}
      onMouseEnter={e => e.currentTarget.style.opacity = 1}
      onMouseLeave={e => e.currentTarget.style.opacity = 0.5}>
      <path d="M21 2v6h-6" />
      <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
      <path d="M3 22v-6h6" />
      <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
    </svg>
  );
}

window.fmtPct = fmtPct;
window.chg = chg;
window.Stars = Stars;
window.RecIndicator = RecIndicator;
window.RecCompact = RecCompact;
window.PremBar = PremBar;
window.Label = Label;
window.FuturesTicker = FuturesTicker;
window.RefreshBtn = RefreshBtn;
window.PoolBadge = PoolBadge;
window.TH = TH; window.TD = TD; window.TDL = TDL; window.TDM = TDM;
