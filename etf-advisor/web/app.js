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
function Stars({
  n
}) {
  if (n >= 5) return /*#__PURE__*/React.createElement("span", {
    style: {
      color: '#A8342A',
      letterSpacing: 1
    }
  }, "\u2605\u2605\u2605\u2605\u2605");
  if (n >= 4) return /*#__PURE__*/React.createElement("span", {
    style: {
      color: '#A8342A',
      letterSpacing: 1
    }
  }, "\u2605\u2605\u2605\u2605", /*#__PURE__*/React.createElement("span", {
    style: {
      opacity: 0.25
    }
  }, "\u2605"));
  if (n >= 3) return /*#__PURE__*/React.createElement("span", {
    style: {
      color: '#8B6914',
      letterSpacing: 1
    }
  }, "\u2605\u2605\u2605", /*#__PURE__*/React.createElement("span", {
    style: {
      opacity: 0.25
    }
  }, "\u2605\u2605"));
  if (n >= 2) return /*#__PURE__*/React.createElement("span", {
    style: {
      color: '#8B6914',
      letterSpacing: 1
    }
  }, "\u2605\u2605", /*#__PURE__*/React.createElement("span", {
    style: {
      opacity: 0.25
    }
  }, "\u2605\u2605\u2605"));
  if (n >= 1) return /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--fg-3)',
      letterSpacing: 1
    }
  }, "\u2605", /*#__PURE__*/React.createElement("span", {
    style: {
      opacity: 0.25
    }
  }, "\u2605\u2605\u2605\u2605"));
  if (n === 0) return /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--fg-muted)',
      fontSize: 10
    }
  }, "\u89C2\u671B");
  return /*#__PURE__*/React.createElement("span", {
    style: {
      color: '#2A6B4F',
      letterSpacing: 1
    }
  }, "\u2715");
}

// Recommendation indicator — professional signal bars + label
function RecIndicator({
  rec,
  stars
}) {
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
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 3
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 11,
      fontWeight: 600,
      color: activeColor,
      padding: '2px 6px',
      borderRadius: 2,
      background: labelBg
    }
  }, rec), !isWait && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 2
    }
  }, Array.from({
    length: maxBars
  }, (_, i) => {
    const filled = i < absStars;
    return /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        width: 8,
        height: 8,
        borderRadius: 1,
        background: filled ? activeColor : inactiveColor,
        opacity: filled ? 0.5 + 0.1 * i : 1
      }
    });
  })));
}

// Compact version for cards/mobile
function RecCompact({
  rec,
  stars
}) {
  const isBuy = rec === '买入';
  const isSell = rec === '卖出';
  const activeColor = isSell ? '#2A6B4F' : isBuy ? '#A8342A' : 'var(--fg-muted)';
  const absStars = Math.abs(stars);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 11,
      fontWeight: 600,
      color: activeColor
    }
  }, rec), absStars > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 1.5
    }
  }, Array.from({
    length: absStars
  }, (_, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      width: 6,
      height: 6,
      borderRadius: 1,
      background: activeColor,
      opacity: 0.5 + 0.1 * i
    }
  }))));
}

// Pool badge — shows rotation pool membership
function PoolBadge({
  pool
}) {
  const [show, setShow] = React.useState(false);
  if (!pool) return null;
  return /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'relative',
      display: 'inline-flex',
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    onClick: e => {
      e.stopPropagation();
      setShow(!show);
    },
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 9,
      color: '#A8342A',
      cursor: 'pointer',
      background: 'rgba(168,52,42,0.08)',
      padding: '1px 4px',
      borderRadius: 2,
      lineHeight: 1.2
    }
  }, "\u25C6"), show && /*#__PURE__*/React.createElement("span", {
    onClick: e => {
      e.stopPropagation();
      setShow(false);
    },
    style: {
      position: 'absolute',
      top: '100%',
      left: 0,
      marginTop: 4,
      zIndex: 50,
      fontFamily: 'var(--font-ui)',
      fontSize: 10,
      color: 'var(--fg-2)',
      whiteSpace: 'nowrap',
      background: 'var(--paper)',
      border: '1px solid var(--ink-20)',
      padding: '6px 10px',
      borderRadius: 2,
      boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
    }
  }, "\u63A8\u8350\u6C60ETF\uFF1A\u57FA\u4E8E\u5386\u53F2\u6EA2\u4EF7\u7A33\u5B9A\u6027\u7B5B\u9009\uFF0C\u52A0\u5206"));
}

// Premium bar — thin horizontal indicator
function PremBar({
  v,
  max
}) {
  const w = Math.min(100, Math.abs(v) / (max || 8) * 100);
  const c = v > 4 ? '#A8342A' : v > 2 ? '#8B6914' : '#2A6B4F';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 40,
      height: 3,
      background: 'var(--ink-05)',
      borderRadius: 2,
      flexShrink: 0,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: w + '%',
      height: '100%',
      background: c,
      borderRadius: 2
    }
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 12,
      color: chg(v)
    }
  }, fmtPct(v)));
}

// Eyebrow section label
function Label({
  children,
  right
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'baseline',
      marginBottom: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 10,
      fontWeight: 600,
      textTransform: 'uppercase',
      letterSpacing: '0.08em',
      color: 'var(--fg-3)'
    }
  }, children), right && /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 11,
      color: 'var(--fg-muted)'
    }
  }, right));
}

// Futures ticker
function FuturesTicker({
  data,
  compact
}) {
  if (!data || !data.length) return null;
  const latest = data[data.length - 1];
  const prev = data.length > 1 ? data[0] : null;
  const items = [{
    l: 'NQ',
    p: latest.nq_price,
    c: latest.nq_change
  }, {
    l: 'ES',
    p: latest.es_price,
    c: latest.es_change
  }, {
    l: 'YM',
    p: latest.ym_price,
    c: latest.ym_change
  }];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: compact ? 10 : 20,
      padding: compact ? '8px 0' : '10px 0',
      borderBottom: '1px solid var(--ink-10)',
      overflowX: 'auto'
    }
  }, items.map(f => /*#__PURE__*/React.createElement("div", {
    key: f.l,
    style: {
      display: 'flex',
      alignItems: 'baseline',
      gap: 5,
      whiteSpace: 'nowrap'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: compact ? 9 : 10,
      color: 'var(--fg-muted)',
      fontWeight: 600,
      letterSpacing: '0.04em'
    }
  }, f.l), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: compact ? 12 : 13,
      fontWeight: 500
    }
  }, f.p), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: compact ? 10 : 11,
      color: chg(f.c)
    }
  }, fmtPct(f.c)))), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: compact ? 8 : 9,
      color: 'var(--fg-muted)',
      alignSelf: 'center',
      marginLeft: 'auto'
    }
  }, latest.date));
}

// Table cell styles
const TH = {
  padding: '8px 6px',
  borderBottom: '1px solid var(--ink-20)',
  fontFamily: 'var(--font-ui)',
  fontSize: 10,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  color: 'var(--fg-3)',
  textAlign: 'center',
  whiteSpace: 'nowrap',
  background: 'var(--paper)'
};
const TD = {
  padding: '8px 6px',
  borderBottom: '1px solid var(--ink-10)',
  textAlign: 'center',
  verticalAlign: 'middle',
  whiteSpace: 'nowrap'
};
const TDL = {
  ...TD,
  textAlign: 'left'
};
const TDM = {
  ...TD,
  fontFamily: 'var(--font-mono)',
  fontSize: 12
};

// Refresh button — subtle, matches page style
function RefreshBtn({
  compact
}) {
  const [spinning, setSpin] = React.useState(false);
  const handleClick = e => {
    e.stopPropagation();
    setSpin(true);
    location.reload();
  };
  const size = compact ? 14 : 16;
  return /*#__PURE__*/React.createElement("svg", {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "var(--fg-muted)",
    strokeWidth: "1.5",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    onClick: handleClick,
    style: {
      cursor: 'pointer',
      opacity: 0.5,
      transition: 'opacity 150ms',
      animation: spinning ? 'spin 0.6s linear infinite' : 'none'
    },
    onMouseEnter: e => e.currentTarget.style.opacity = 1,
    onMouseLeave: e => e.currentTarget.style.opacity = 0.5
  }, /*#__PURE__*/React.createElement("path", {
    d: "M21 2v6h-6"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M3 12a9 9 0 0 1 15-6.7L21 8"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M3 22v-6h6"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M21 12a9 9 0 0 1-15 6.7L3 16"
  }));
}

// Fund detail modal
function FundDetailModal({
  etf,
  section,
  onClose
}) {
  if (!etf) return null;
  const fc = section?.futures_correction;
  const r = fc ? 1 + (fc.ratio_pct || 0) / 100 : 1;
  const estNav = etf.nav * r;
  const holdings = etf.holdings || [];
  const rows = [['价格', etf.price.toFixed(3), null], ['净值', etf.nav.toFixed(3), null], ['估算净值', estNav.toFixed(3), chg(fc?.ratio_pct)], ['涨幅', fmtPct(etf.change), chg(etf.change)], ['估算溢价', fmtPct(etf.display_premium), chg(etf.display_premium)], ['3M超额(均值)', fmtPct(etf.excess_3m) + ' (' + fmtPct(etf.avg_3m) + ')', chg(etf.excess_3m)], ['6M超额(均值)', fmtPct(etf.excess_6m) + ' (' + fmtPct(etf.avg_6m) + ')', chg(etf.excess_6m)], ['1Y超额(均值)', fmtPct(etf.excess_1y) + ' (' + fmtPct(etf.avg_1y) + ')', chg(etf.excess_1y)], ['综合超额', fmtPct(etf.composite), chg(etf.composite)], ['年净值涨幅', fmtPct(etf.nav_return_1y), chg(etf.nav_return_1y)], ['年价格涨幅', fmtPct(etf.price_return_1y), chg(etf.price_return_1y)], ['>7%天数', String(etf.days_gt7), etf.days_gt7 > 30 ? '#A8342A' : null], ['分值', etf.score.toFixed(2), null]];
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClose,
    style: {
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0,0,0,0.4)',
      zIndex: 200,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    style: {
      background: 'var(--paper)',
      borderRadius: 8,
      padding: '20px 24px',
      width: 420,
      maxWidth: '100%',
      maxHeight: '85vh',
      overflowY: 'auto'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: 12
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-display-cjk)',
      fontSize: 18,
      fontWeight: 700
    }
  }, etf.name), /*#__PURE__*/React.createElement(PoolBadge, {
    pool: etf.rotation_pool
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 11,
      color: 'var(--fg-muted)'
    }
  }, etf.code, " \xB7 ", section?.index_name)), /*#__PURE__*/React.createElement(RecIndicator, {
    rec: etf.recommendation,
    stars: etf.stars
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      gap: 10,
      marginBottom: 16
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 28,
      fontWeight: 500
    }
  }, etf.price.toFixed(3)), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 14,
      color: chg(etf.change)
    }
  }, fmtPct(etf.change))), rows.map(([l, v, c]) => /*#__PURE__*/React.createElement("div", {
    key: l,
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      padding: '5px 0',
      borderBottom: '1px solid var(--ink-10)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 12,
      color: 'var(--fg-3)'
    }
  }, l), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 12,
      color: c || 'var(--ink)'
    }
  }, v))), holdings.length > 0 && (() => {
    const totalWeight = holdings.reduce((sum, h) => sum + (h.weight || 0), 0);
    return /*#__PURE__*/React.createElement("div", {
      style: {
        marginTop: 16
      }
    }, totalWeight < 60 && /*#__PURE__*/React.createElement("div", {
      style: {
        padding: '8px 12px',
        background: 'rgba(168,52,42,0.08)',
        border: '1px solid rgba(168,52,42,0.2)',
        borderRadius: 4,
        marginBottom: 12
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-ui)',
        fontSize: 11,
        color: '#A8342A'
      }
    }, "⚠️ \u6301\u4ED3\u8986\u76D6\u7387\u4EC5 ", totalWeight.toFixed(0), "%\uFF0C\u4F30\u7B97\u51C0\u503C\u53EF\u80FD\u8BEF\u5DEE\u8F83\u5927")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 11,
      fontWeight: 600,
      color: 'var(--fg-3)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      marginBottom: 6
    }
  }, "\u6301\u4ED3\u660E\u7EC6"), /*#__PURE__*/React.createElement("table", {
    style: {
      width: '100%',
      borderCollapse: 'collapse'
    }
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
    style: {
      ...TH,
      textAlign: 'left',
      fontSize: 9
    }
  }, "\u4EE3\u7801"), /*#__PURE__*/React.createElement("th", {
    style: {
      ...TH,
      fontSize: 9
    }
  }, "\u6743\u91CD"), /*#__PURE__*/React.createElement("th", {
    style: {
      ...TH,
      fontSize: 9
    }
  }, "\u4EF7\u683C"), /*#__PURE__*/React.createElement("th", {
    style: {
      ...TH,
      fontSize: 9
    }
  }, "\u6DA8\u8DCC"))), /*#__PURE__*/React.createElement("tbody", null, holdings.map(h => /*#__PURE__*/React.createElement("tr", {
    key: h.ticker
  }, /*#__PURE__*/React.createElement("td", {
    style: {
      ...TDL,
      fontSize: 11
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontWeight: 500
    }
  }, h.ticker), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: 'var(--fg-muted)'
    }
  }, h.name)), /*#__PURE__*/React.createElement("td", {
    style: {
      ...TDM,
      fontSize: 11
    }
  }, h.weight?.toFixed(1), "%"), /*#__PURE__*/React.createElement("td", {
    style: {
      ...TDM,
      fontSize: 11
    }
  }, h.price?.toFixed(2) || '—'), /*#__PURE__*/React.createElement("td", {
    style: {
      ...TDM,
      fontSize: 11,
      color: chg(h.change_pct)
    }
  }, h.change_pct != null ? fmtPct(h.change_pct) : '—'))))));
  })(), /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: 'center',
      marginTop: 16
    }
  }, /*#__PURE__*/React.createElement("span", {
    onClick: onClose,
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 12,
      color: 'var(--fg-muted)',
      cursor: 'pointer'
    }
  }, "\u5173\u95ED"))));
}

// Arbitrage badge for LOF
function ArbitrageBadge({
  arb,
  limit
}) {
  if (!arb) return null;
  const isRedeem = arb === 'redeem';
  const color = isRedeem ? '#2A6B4F' : '#A8342A';
  const bg = isRedeem ? 'rgba(42,107,79,0.08)' : 'rgba(168,52,42,0.08)';
  const text = isRedeem ? '赎回套利' : '申购套利' + (limit ? ' · 限' + limit : '');
  return /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 10,
      fontWeight: 600,
      color,
      background: bg,
      padding: '2px 6px',
      borderRadius: 2,
      whiteSpace: 'nowrap'
    }
  }, text);
}
window.ArbitrageBadge = ArbitrageBadge;
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
window.FundDetailModal = FundDetailModal;
window.TH = TH;
window.TD = TD;
window.TDL = TDL;
window.TDM = TDM;

// PC layout — tab-based: Overview + Premium Analysis
const {
  useState: useS,
  useMemo: useM,
  useEffect: useE,
  useCallback: useC
} = React;

/* ── PC Header with Nav ── */
function PCNav({
  tab,
  setTab
}) {
  const [scrolled, setScrolled] = useS(false);
  useE(() => {
    const fn = () => setScrolled(window.scrollY > 12);
    window.addEventListener('scroll', fn);
    return () => window.removeEventListener('scroll', fn);
  }, []);
  const tabs = [{
    k: 'overview',
    l: '总览'
  }, {
    k: 'premium',
    l: '溢价分析'
  }, {
    k: 'rotation',
    l: '纳指轮动'
  }];
  return /*#__PURE__*/React.createElement("header", {
    style: {
      position: 'sticky',
      top: 0,
      zIndex: 20,
      background: 'var(--paper)',
      borderBottom: scrolled ? '1px solid var(--ink-20)' : '1px solid transparent',
      transition: 'border-color 240ms var(--ease-gentle)',
      height: 52
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 1200,
      margin: '0 auto',
      padding: '0 32px',
      height: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-display-cjk)',
      fontWeight: 700,
      fontSize: 20,
      color: 'var(--ink)',
      letterSpacing: '-0.02em'
    }
  }, "\u5343\u91CC\u77E5\u6295"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 10,
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      color: 'var(--fg-muted)'
    }
  }, "ETF Advisor")), /*#__PURE__*/React.createElement("nav", {
    style: {
      display: 'flex',
      gap: 24
    }
  }, tabs.map(t => /*#__PURE__*/React.createElement("a", {
    key: t.k,
    href: "#",
    onClick: e => {
      e.preventDefault();
      setTab(t.k);
    },
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 13,
      textDecoration: 'none',
      color: tab === t.k ? 'var(--ink)' : 'var(--fg-3)',
      borderBottom: tab === t.k ? '1px solid var(--ink)' : '1px solid transparent',
      paddingBottom: 2,
      letterSpacing: '0.01em'
    }
  }, t.l)))));
}

/* ══════════════════════════════════════════
   Overview — light summary, fewer columns
   ══════════════════════════════════════════ */
function PCOverview({
  setTab,
  setIdx
}) {
  if (!REPORT.sections.length) return null;
  const [selFund, setSelFund] = useS(null);
  const alwaysShow = ['NASDAQ', 'SP500'];
  const topPicks = REPORT.sections.map(s => ({
    section: s,
    etf: s.etfs[0]
  })).filter(({
    section: s,
    etf: e
  }) => alwaysShow.includes(s.index_type) || e && e.stars >= 3);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 1200,
      margin: '0 auto',
      padding: '32px 32px 64px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 11,
      color: 'var(--fg-muted)'
    }
  }, REPORT.data_freshness), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 11,
      color: 'var(--fg-muted)'
    }
  }, "\u66F4\u65B0 ", REPORT.generated_at), /*#__PURE__*/React.createElement(RefreshBtn, null))), /*#__PURE__*/React.createElement(FuturesTicker, {
    data: REPORT.futures
  }), /*#__PURE__*/React.createElement(Label, {
    right: /*#__PURE__*/React.createElement("a", {
      href: "#",
      onClick: e => {
        e.preventDefault();
        setTab('premium');
      },
      style: {
        color: 'var(--fg-3)',
        textDecoration: 'none',
        borderBottom: '1px solid var(--ink-20)',
        fontFamily: 'var(--font-ui)',
        fontSize: 12
      }
    }, "\u8BE6\u7EC6\u5206\u6790 \u2192")
  }, "\u4ECA\u65E5\u5404\u6307\u6570\u63A8\u8350"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: `repeat(${REPORT.sections.length}, 1fr)`,
      gap: 1,
      background: 'var(--ink-10)',
      border: '1px solid var(--ink-10)',
      marginBottom: 40
    }
  }, topPicks.map(({
    section: s,
    etf: e
  }) => /*#__PURE__*/React.createElement("div", {
    key: s.index_type,
    onClick: () => {
      setIdx(s.index_type);
      setTab('premium');
    },
    style: {
      background: 'var(--paper)',
      padding: '18px',
      cursor: 'pointer'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'baseline'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 10,
      fontWeight: 600,
      color: 'var(--fg-muted)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, s.index_name), s.futures_cumulative != null && /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 10,
      color: chg(s.futures_cumulative)
    }
  }, "\u4FEE\u6B63 ", fmtPct(s.futures_cumulative))), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-display-cjk)',
      fontSize: 14,
      fontWeight: 500,
      marginTop: 8
    }
  }, e.name), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 10,
      color: 'var(--fg-muted)',
      marginTop: 1
    }
  }, e.code), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      gap: 8,
      marginTop: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 20,
      fontWeight: 500
    }
  }, e.price.toFixed(3)), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 12,
      color: chg(e.change)
    }
  }, fmtPct(e.change))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      marginTop: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 10,
      color: 'var(--fg-3)'
    }
  }, "\u6EA2\u4EF7"), /*#__PURE__*/React.createElement(PremBar, {
    v: e.display_premium,
    max: 8
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 8
    }
  }, /*#__PURE__*/React.createElement(RecCompact, {
    rec: e.recommendation,
    stars: e.stars
  }))))), /*#__PURE__*/React.createElement(Label, null, "\u5168\u90E8 ETF \u6309\u5206\u503C\u6392\u5E8F"), (() => {
    const allETFs = REPORT.sections.flatMap(s => s.etfs.map(e => ({
      ...e,
      indexName: s.index_name
    })));
    allETFs.sort((a, b) => b.score - a.score);
    return /*#__PURE__*/React.createElement("table", {
      style: {
        width: '100%',
        borderCollapse: 'collapse'
      }
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      style: {
        ...TH,
        textAlign: 'left'
      }
    }, "ETF"), /*#__PURE__*/React.createElement("th", {
      style: TH
    }, "\u6307\u6570"), /*#__PURE__*/React.createElement("th", {
      style: TH
    }, "\u4EF7\u683C"), /*#__PURE__*/React.createElement("th", {
      style: TH
    }, "\u6DA8\u5E45"), /*#__PURE__*/React.createElement("th", {
      style: TH
    }, "\u4F30\u7B97\u6EA2\u4EF7"), /*#__PURE__*/React.createElement("th", {
      style: TH
    }, "\u5E74\u51C0\u503C\u6DA8\u5E45"), /*#__PURE__*/React.createElement("th", {
      style: TH
    }, "\u5206\u503C"), /*#__PURE__*/React.createElement("th", {
      style: TH
    }, "\u63A8\u8350"))), /*#__PURE__*/React.createElement("tbody", null, allETFs.map(e => {
      const isTop = e.stars >= 4;
      const isSell = e.stars < 0;
      const rowBg = isTop ? 'rgba(168,52,42,0.04)' : isSell ? 'rgba(42,107,79,0.04)' : 'transparent';
      return /*#__PURE__*/React.createElement("tr", {
        key: e.code,
        style: {
          background: rowBg
        },
        onMouseEnter: ev => ev.currentTarget.style.background = 'var(--ink-05)',
        onMouseLeave: ev => ev.currentTarget.style.background = rowBg
      }, /*#__PURE__*/React.createElement("td", {
        style: TDL,
        onClick: () => {
          const s = REPORT.sections.find(s => s.index_name === e.indexName);
          if (s) {
            setIdx(s.index_type);
            setTab('premium');
          }
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          cursor: 'pointer'
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          fontFamily: 'var(--font-display-cjk)',
          fontSize: 13,
          fontWeight: 500,
          borderBottom: '1px dashed var(--ink-20)'
        }
      }, e.name), /*#__PURE__*/React.createElement(PoolBadge, {
        pool: e.rotation_pool
      })), /*#__PURE__*/React.createElement("div", {
        style: {
          fontFamily: 'var(--font-ui)',
          fontSize: 10,
          color: 'var(--fg-muted)'
        }
      }, e.code)), /*#__PURE__*/React.createElement("td", {
        style: {
          ...TD,
          fontFamily: 'var(--font-ui)',
          fontSize: 11
        }
      }, e.indexName), /*#__PURE__*/React.createElement("td", {
        style: {
          ...TDM,
          fontWeight: 500
        }
      }, e.price.toFixed(3)), /*#__PURE__*/React.createElement("td", {
        style: {
          ...TDM,
          color: chg(e.change)
        }
      }, fmtPct(e.change)), /*#__PURE__*/React.createElement("td", {
        style: {
          ...TDM,
          color: chg(e.display_premium),
          fontWeight: 500
        }
      }, fmtPct(e.display_premium)), /*#__PURE__*/React.createElement("td", {
        style: {
          ...TDM,
          fontSize: 11,
          color: chg(e.nav_return_1y)
        }
      }, fmtPct(e.nav_return_1y)), /*#__PURE__*/React.createElement("td", {
        style: {
          ...TDM,
          fontSize: 13,
          fontWeight: 700
        }
      }, e.score.toFixed(2)), /*#__PURE__*/React.createElement("td", {
        style: TD
      }, /*#__PURE__*/React.createElement(RecIndicator, {
        rec: e.recommendation,
        stars: e.stars
      })));
    })));
  })());
}

/* ══════════════════════════════════════════
   Premium Analysis — full detail per index
   ══════════════════════════════════════════ */
function PCPremium({
  activeIdx,
  setActiveIdx
}) {
  if (!REPORT.sections.length) return null;
  const [selFund, setSelFund] = useS(null);
  const section = REPORT.sections.find(s => s.index_type === activeIdx) || REPORT.sections[0];

  // 基金详情页（全页面）
  if (selFund) {
    const fc = section.futures_correction;
    const r = fc ? 1 + (fc.ratio_pct || 0) / 100 : 1;
    const estNav = selFund.nav * r;
    const holdings = selFund.holdings || [];
    const metrics = [['净值', selFund.nav.toFixed(3), null], ['估算净值', estNav.toFixed(3), chg(fc?.ratio_pct)], ['涨幅', fmtPct(selFund.change), chg(selFund.change)], ['估算溢价', fmtPct(selFund.display_premium), chg(selFund.display_premium)], ['3M均溢价', fmtPct(selFund.avg_3m), null], ['6M均溢价', fmtPct(selFund.avg_6m), null], ['1Y均溢价', fmtPct(selFund.avg_1y), null], ['溢价>7%天数', String(selFund.days_gt7), selFund.days_gt7 > 30 ? '#A8342A' : null], ['年净值涨幅', fmtPct(selFund.nav_return_1y), chg(selFund.nav_return_1y)], ['年价格涨幅', fmtPct(selFund.price_return_1y), chg(selFund.price_return_1y)], ['分值', selFund.score.toFixed(2), null]];
    if (selFund.subscription_status) {
      const subMap = {
        closed: '暂停申购',
        limited: '限大额' + (selFund.subscription_limit ? ' ' + selFund.subscription_limit : ''),
        open: '开放申购'
      };
      metrics.push(['申购状态', subMap[selFund.subscription_status] || selFund.subscription_status, null]);
    }
    return /*#__PURE__*/React.createElement("div", {
      style: {
        maxWidth: 1200,
        margin: '0 auto',
        padding: '32px 32px 64px'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        marginBottom: 20
      }
    }, /*#__PURE__*/React.createElement("a", {
      href: "#",
      onClick: e => {
        e.preventDefault();
        setSelFund(null);
      },
      style: {
        fontFamily: 'var(--font-ui)',
        fontSize: 13,
        color: 'var(--fg-3)',
        textDecoration: 'none'
      }
    }, "\u2190 \u8FD4\u56DE\u6EA2\u4EF7\u5206\u6790"), selFund.arbitrage && /*#__PURE__*/React.createElement("span", {
      style: {
        marginLeft: 12
      }
    }, /*#__PURE__*/React.createElement(ArbitrageBadge, {
      arb: selFund.arbitrage,
      limit: selFund.subscription_limit
    }))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 40
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        minWidth: 300
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        marginBottom: 20
      }
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 8
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-display-cjk)',
        fontSize: 24,
        fontWeight: 700
      }
    }, selFund.name), /*#__PURE__*/React.createElement(PoolBadge, {
      pool: selFund.rotation_pool
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 12,
        color: 'var(--fg-muted)',
        marginTop: 4
      }
    }, selFund.code, " \xB7 ", section.index_name)), /*#__PURE__*/React.createElement(RecIndicator, {
      rec: selFund.recommendation,
      stars: selFund.stars
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'baseline',
        gap: 12,
        marginBottom: 24
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 36,
        fontWeight: 500
      }
    }, selFund.price.toFixed(3)), /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 16,
        color: chg(selFund.change)
      }
    }, fmtPct(selFund.change))), /*#__PURE__*/React.createElement("table", {
      style: {
        width: '100%',
        borderCollapse: 'collapse'
      }
    }, /*#__PURE__*/React.createElement("tbody", null, metrics.map(([l, v, c]) => /*#__PURE__*/React.createElement("tr", {
      key: l
    }, /*#__PURE__*/React.createElement("td", {
      style: {
        padding: '6px 0',
        borderBottom: '1px solid var(--ink-10)',
        fontFamily: 'var(--font-ui)',
        fontSize: 13,
        color: 'var(--fg-3)',
        width: '40%'
      }
    }, l), /*#__PURE__*/React.createElement("td", {
      style: {
        padding: '6px 0',
        borderBottom: '1px solid var(--ink-10)',
        fontFamily: 'var(--font-mono)',
        fontSize: 13,
        color: c || 'var(--ink)',
        textAlign: 'right'
      }
    }, v)))))), holdings.length > 0 && /*#__PURE__*/React.createElement("div", {
      style: {
        width: 340
      }
    }, /*#__PURE__*/React.createElement(Label, null, "\u6301\u4ED3\u660E\u7EC6 (", holdings.length, ")"), /*#__PURE__*/React.createElement("table", {
      style: {
        width: '100%',
        borderCollapse: 'collapse'
      }
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      style: {
        ...TH,
        textAlign: 'left'
      }
    }, "\u4EE3\u7801"), /*#__PURE__*/React.createElement("th", {
      style: TH
    }, "\u6743\u91CD"), /*#__PURE__*/React.createElement("th", {
      style: TH
    }, "\u4EF7\u683C"), /*#__PURE__*/React.createElement("th", {
      style: TH
    }, "\u6DA8\u8DCC"))), /*#__PURE__*/React.createElement("tbody", null, holdings.map(h => /*#__PURE__*/React.createElement("tr", {
      key: h.ticker
    }, /*#__PURE__*/React.createElement("td", {
      style: TDL
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 12,
        fontWeight: 500
      }
    }, h.ticker), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'var(--font-ui)',
        fontSize: 10,
        color: 'var(--fg-muted)'
      }
    }, h.name)), /*#__PURE__*/React.createElement("td", {
      style: {
        ...TDM,
        fontSize: 12
      }
    }, h.weight?.toFixed(1), "%"), /*#__PURE__*/React.createElement("td", {
      style: {
        ...TDM,
        fontSize: 12
      }
    }, h.price?.toFixed(2) || '—'), /*#__PURE__*/React.createElement("td", {
      style: {
        ...TDM,
        fontSize: 12,
        color: chg(h.change_pct)
      }
    }, h.change_pct != null ? fmtPct(h.change_pct) : '—'))))))));
  }
  const etfs = section.etfs;
  const fc = section.futures_correction;
  const top = etfs[0];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 1200,
      margin: '0 auto',
      padding: '32px 32px 64px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 11,
      color: 'var(--fg-muted)'
    }
  }, REPORT.data_freshness), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 11,
      color: 'var(--fg-muted)'
    }
  }, "\u66F4\u65B0 ", REPORT.generated_at), /*#__PURE__*/React.createElement(RefreshBtn, null))), /*#__PURE__*/React.createElement(FuturesTicker, {
    data: REPORT.futures
  }), /*#__PURE__*/React.createElement("h1", {
    style: {
      fontFamily: 'var(--font-display-cjk)',
      fontWeight: 700,
      fontSize: 28,
      margin: '24px 0 4px',
      letterSpacing: '-0.02em'
    }
  }, "\u6EA2\u4EF7\u5206\u6790\u62A5\u544A"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6,
      marginBottom: 20,
      flexWrap: 'wrap'
    }
  }, REPORT.sections.map(s => {
    const active = activeIdx === s.index_type;
    return /*#__PURE__*/React.createElement("span", {
      key: s.index_type,
      onClick: () => setActiveIdx(s.index_type),
      style: {
        fontFamily: 'var(--font-ui)',
        fontSize: 12,
        padding: '5px 14px',
        borderRadius: 999,
        cursor: 'pointer',
        border: active ? '1px solid var(--ink)' : '1px solid var(--ink-20)',
        background: active ? 'var(--ink)' : 'transparent',
        color: active ? 'var(--paper)' : 'var(--fg-2)',
        transition: 'all 120ms',
        whiteSpace: 'nowrap'
      }
    }, s.index_name, " (", s.etfs.length, ")");
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'baseline',
      marginBottom: 4
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      fontFamily: 'var(--font-ui)',
      fontSize: 12,
      color: 'var(--fg-2)'
    }
  }, "\u63A8\u8350\u6301\u6709", /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-display-cjk)',
      fontWeight: 500
    }
  }, top.name), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 11,
      color: 'var(--fg-muted)'
    }
  }, "(", top.code, ")"), /*#__PURE__*/React.createElement(RecCompact, {
    rec: top.recommendation,
    stars: top.stars
  })), fc && /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 11,
      color: 'var(--fg-muted)'
    }
  }, section.nav_date && /*#__PURE__*/React.createElement("span", null, "\u51C0\u503C ", section.nav_date.slice(5), " \xB7 "), fc.symbol, ": ", fc.current_futures_price?.toFixed(0), " / ", fc.nav_date_close?.toFixed(0), " = ", /*#__PURE__*/React.createElement("span", {
    style: {
      fontWeight: 500,
      color: chg(fc.ratio_pct)
    }
  }, fmtPct(fc.ratio_pct)))), /*#__PURE__*/React.createElement("div", {
    style: {
      overflowX: 'auto',
      marginTop: 12
    }
  }, /*#__PURE__*/React.createElement("table", {
    style: {
      width: '100%',
      borderCollapse: 'collapse'
    }
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
    style: {
      ...TH,
      textAlign: 'left'
    }
  }, "\u4EE3\u7801"), /*#__PURE__*/React.createElement("th", {
    style: TH
  }, "\u4EF7\u683C"), /*#__PURE__*/React.createElement("th", {
    style: TH
  }, "\u51C0\u503C"), /*#__PURE__*/React.createElement("th", {
    style: TH
  }, "\u4F30\u7B97\u51C0\u503C"), /*#__PURE__*/React.createElement("th", {
    style: TH
  }, "\u6DA8\u5E45"), /*#__PURE__*/React.createElement("th", {
    style: TH
  }, "\u4F30\u7B97\u6EA2\u4EF7"), /*#__PURE__*/React.createElement("th", {
    style: TH
  }, "3M\u5747\u6EA2\u4EF7"), /*#__PURE__*/React.createElement("th", {
    style: TH
  }, "6M\u5747\u6EA2\u4EF7"), /*#__PURE__*/React.createElement("th", {
    style: TH
  }, "1Y\u5747\u6EA2\u4EF7"), /*#__PURE__*/React.createElement("th", {
    style: TH
  }, "\u6EA2\u4EF7", '>', "7%\u5929"), /*#__PURE__*/React.createElement("th", {
    style: TH
  }, "\u5E74\u51C0\u503C\u6DA8\u5E45"), /*#__PURE__*/React.createElement("th", {
    style: TH
  }, "\u5E74\u4EF7\u683C\u6DA8\u5E45"), /*#__PURE__*/React.createElement("th", {
    style: TH
  }, "\u5206\u503C"), /*#__PURE__*/React.createElement("th", {
    style: TH
  }, "\u63A8\u8350"))), /*#__PURE__*/React.createElement("tbody", null, etfs.map(e => {
    const isTop = e.stars >= 4;
    const isSell = e.stars < 0;
    const rowBg = isTop ? 'rgba(168,52,42,0.04)' : isSell ? 'rgba(42,107,79,0.04)' : 'transparent';
    return /*#__PURE__*/React.createElement("tr", {
      key: e.code,
      style: {
        background: rowBg
      },
      onMouseEnter: ev => ev.currentTarget.style.background = 'var(--ink-05)',
      onMouseLeave: ev => ev.currentTarget.style.background = rowBg
    }, /*#__PURE__*/React.createElement("td", {
      style: TDL,
      onClick: () => setSelFund(e)
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        cursor: 'pointer'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-display-cjk)',
        fontSize: 12,
        fontWeight: 500,
        borderBottom: '1px dashed var(--ink-20)'
      }
    }, e.name), /*#__PURE__*/React.createElement(PoolBadge, {
      pool: e.rotation_pool
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        color: 'var(--fg-muted)'
      }
    }, e.code)), /*#__PURE__*/React.createElement("td", {
      style: {
        ...TDM,
        fontWeight: 500
      }
    }, e.price.toFixed(3)), /*#__PURE__*/React.createElement("td", {
      style: {
        ...TDM,
        color: 'var(--fg-3)'
      }
    }, e.nav.toFixed(3)), /*#__PURE__*/React.createElement("td", {
      style: TDM
    }, (() => {
      const r = fc ? 1 + fc.ratio_pct / 100 : 1;
      const est = e.nav * r;
      return /*#__PURE__*/React.createElement("span", {
        style: {
          fontWeight: 500
        }
      }, est.toFixed(3));
    })()), /*#__PURE__*/React.createElement("td", {
      style: {
        ...TDM,
        color: chg(e.change)
      }
    }, fmtPct(e.change)), /*#__PURE__*/React.createElement("td", {
      style: {
        ...TDM,
        color: chg(e.display_premium),
        fontWeight: 500
      }
    }, fmtPct(e.display_premium)), /*#__PURE__*/React.createElement("td", {
      style: TDM
    }, fmtPct(e.avg_3m)), /*#__PURE__*/React.createElement("td", {
      style: TDM
    }, fmtPct(e.avg_6m)), /*#__PURE__*/React.createElement("td", {
      style: TDM
    }, fmtPct(e.avg_1y)), /*#__PURE__*/React.createElement("td", {
      style: {
        ...TDM,
        fontSize: 11,
        color: e.days_gt7 > 30 ? '#A8342A' : 'var(--fg-3)'
      }
    }, e.days_gt7), /*#__PURE__*/React.createElement("td", {
      style: {
        ...TDM,
        fontSize: 11,
        color: chg(e.nav_return_1y)
      }
    }, fmtPct(e.nav_return_1y)), /*#__PURE__*/React.createElement("td", {
      style: {
        ...TDM,
        fontSize: 11,
        color: chg(e.price_return_1y)
      }
    }, fmtPct(e.price_return_1y)), /*#__PURE__*/React.createElement("td", {
      style: {
        ...TDM,
        fontSize: 13,
        fontWeight: 700
      }
    }, e.score.toFixed(2)), /*#__PURE__*/React.createElement("td", {
      style: TD
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 3
      }
    }, /*#__PURE__*/React.createElement(RecIndicator, {
      rec: e.recommendation,
      stars: e.stars
    }), /*#__PURE__*/React.createElement(ArbitrageBadge, {
      arb: e.arbitrage,
      limit: e.subscription_limit
    }))));
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 10,
      color: 'var(--fg-muted)',
      marginTop: 16,
      lineHeight: 1.6
    }
  }, "\u5206\u503C = \u6EA2\u4EF7\u504F\u79BB\u5386\u53F2\u6EA2\u4EF7\u5747\u503C + \u540C\u7C7B\u8DDF\u8E2A\u8D28\u91CF\u5DEE\u5F02\u3002\u5206\u503C\u8D8A\u9AD8\uFF0C\u5F53\u524D\u6EA2\u4EF7\u8D8A\u4F4E\u4E8E\u5386\u53F2\u6C34\u5E73\u3002\u4EC5\u53CD\u6620\u6EA2\u4EF7\u4F4D\u7F6E\uFF0C\u4E0D\u9884\u6D4B\u677F\u5757\u6DA8\u8DCC\u3002"));
}
window.PCNav = PCNav;
window.PCOverview = PCOverview;
window.PCPremium = PCPremium;

// Mobile layout — tab-based: Overview + Premium Analysis
const {
  useState: useSM
} = React;

/* ── Mobile Tab Bar ── */
function MobTabs({
  tab,
  setTab
}) {
  const ts = [{
    k: 'overview',
    l: '总览',
    d: 'M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z M9 22V12h6v10'
  }, {
    k: 'premium',
    l: '溢价分析',
    d: 'M18 20V10 M12 20V4 M6 20v-6'
  }, {
    k: 'rotation',
    l: '纳指轮动',
    d: 'M17 1l4 4-4 4 M3 11V9a4 4 0 014-4h14 M7 23l-4-4 4-4 M21 13v2a4 4 0 01-4 4H3'
  }];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'fixed',
      bottom: 0,
      left: 0,
      right: 0,
      zIndex: 30,
      background: 'var(--paper)',
      borderTop: '1px solid var(--ink-10)',
      display: 'flex',
      justifyContent: 'space-around',
      padding: '6px 0 2px',
      height: 50
    }
  }, ts.map(t => {
    const a = tab === t.k;
    return /*#__PURE__*/React.createElement("div", {
      key: t.k,
      onClick: () => setTab(t.k),
      style: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 1,
        cursor: 'pointer',
        padding: '4px 16px'
      }
    }, /*#__PURE__*/React.createElement("svg", {
      width: "18",
      height: "18",
      viewBox: "0 0 24 24",
      fill: "none",
      stroke: a ? 'var(--ink)' : 'var(--fg-muted)',
      strokeWidth: "1.5",
      strokeLinecap: "round",
      strokeLinejoin: "round"
    }, t.d.split(' M').map((seg, i) => /*#__PURE__*/React.createElement("path", {
      key: i,
      d: i === 0 ? seg : 'M' + seg
    }))), /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-ui)',
        fontSize: 9,
        color: a ? 'var(--ink)' : 'var(--fg-muted)',
        fontWeight: a ? 600 : 400
      }
    }, t.l));
  }));
}

/* ── Mobile Overview ── */
function MobOverview({
  setTab,
  setIdx
}) {
  if (!REPORT.sections.length) return null;
  const alwaysShow = ['NASDAQ', 'SP500'];
  const topPicks = REPORT.sections.map(s => ({
    s,
    e: s.etfs[0]
  })).filter(({
    s,
    e
  }) => alwaysShow.includes(s.index_type) || e && e.stars >= 3);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '12px 16px 68px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '8px 0 4px'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 10,
      color: 'var(--fg-muted)'
    }
  }, REPORT.data_freshness), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 10,
      color: 'var(--fg-muted)'
    }
  }, REPORT.generated_at?.slice(11)), /*#__PURE__*/React.createElement(RefreshBtn, {
    compact: true
  }))), /*#__PURE__*/React.createElement(FuturesTicker, {
    data: REPORT.futures,
    compact: true
  }), /*#__PURE__*/React.createElement(Label, null, "\u5404\u6307\u6570\u63A8\u8350"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8,
      overflowX: 'auto',
      paddingBottom: 4,
      marginBottom: 24
    }
  }, topPicks.map(({
    s,
    e
  }) => /*#__PURE__*/React.createElement("div", {
    key: s.index_type,
    onClick: () => {
      setIdx(s.index_type);
      setTab('premium');
    },
    style: {
      flexShrink: 0,
      width: 140,
      padding: '12px',
      border: '1px solid var(--ink-10)',
      borderRadius: 2,
      cursor: 'pointer'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 9,
      color: 'var(--fg-muted)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, s.index_name), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-display-cjk)',
      fontSize: 12,
      fontWeight: 500,
      marginTop: 4,
      whiteSpace: 'nowrap',
      overflow: 'hidden',
      textOverflow: 'ellipsis'
    }
  }, e.name), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 15,
      marginTop: 6
    }
  }, e.price.toFixed(3)), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 11,
      color: chg(e.change),
      marginTop: 1
    }
  }, fmtPct(e.change)), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 10,
      color: 'var(--fg-3)',
      marginTop: 4
    }
  }, "\u6EA2\u4EF7 ", /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      color: chg(e.display_premium)
    }
  }, fmtPct(e.display_premium))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 6
    }
  }, /*#__PURE__*/React.createElement(RecCompact, {
    rec: e.recommendation,
    stars: e.stars
  }))))), /*#__PURE__*/React.createElement(Label, {
    right: /*#__PURE__*/React.createElement("span", {
      onClick: () => setTab('premium'),
      style: {
        cursor: 'pointer'
      }
    }, "\u8BE6\u7EC6 \u2192")
  }, "\u5168\u90E8 ETF \u6392\u884C"), (() => {
    const allETFs = REPORT.sections.flatMap(s => s.etfs.map(e => ({
      ...e,
      indexName: s.index_name
    })));
    allETFs.sort((a, b) => b.score - a.score);
    return allETFs.slice(0, 12).map((e, i) => /*#__PURE__*/React.createElement("div", {
      key: e.code,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '10px 0',
        borderTop: '1px solid var(--ink-10)'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        color: 'var(--fg-muted)',
        width: 16,
        textAlign: 'center',
        flexShrink: 0
      }
    }, i + 1), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 6
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-display-cjk)',
        fontSize: 13,
        fontWeight: 500,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis'
      }
    }, e.name), /*#__PURE__*/React.createElement(PoolBadge, {
      pool: e.rotation_pool
    }), /*#__PURE__*/React.createElement(RecCompact, {
      rec: e.recommendation,
      stars: e.stars
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'var(--font-ui)',
        fontSize: 10,
        color: 'var(--fg-muted)'
      }
    }, e.code, " \xB7 ", e.indexName)), /*#__PURE__*/React.createElement("div", {
      style: {
        textAlign: 'right',
        flexShrink: 0
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 13,
        fontWeight: 500
      }
    }, e.score.toFixed(2)), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        color: chg(e.display_premium)
      }
    }, "\u6EA2\u4EF7 ", fmtPct(e.display_premium)))));
  })(), /*#__PURE__*/React.createElement("div", {
    style: {
      borderTop: '1px solid var(--ink-10)'
    }
  }));
}

/* ── Mobile Premium Analysis ── */
function MobPremium({
  activeIdx,
  setActiveIdx
}) {
  if (!REPORT.sections.length) return null;
  const section = REPORT.sections.find(s => s.index_type === activeIdx) || REPORT.sections[0];
  const etfs = section.etfs;
  const fc = section.futures_correction;
  const [expanded, setExpanded] = useSM(null);
  const [selFund, setSelFund] = useSM(null);

  // 基金详情页（全屏）
  if (selFund) {
    const fc = section.futures_correction;
    const r = fc ? 1 + (fc.ratio_pct || 0) / 100 : 1;
    const estNav = selFund.nav * r;
    const holdings = selFund.holdings || [];
    const rows = [['净值', selFund.nav.toFixed(3), null], ['估算净值', estNav.toFixed(3), chg(fc?.ratio_pct)], ['涨幅', fmtPct(selFund.change), chg(selFund.change)], ['估算溢价', fmtPct(selFund.display_premium), chg(selFund.display_premium)], ['3M均溢价', fmtPct(selFund.avg_3m), null], ['6M均溢价', fmtPct(selFund.avg_6m), null], ['1Y均溢价', fmtPct(selFund.avg_1y), null], ['溢价>7%天数', String(selFund.days_gt7), selFund.days_gt7 > 30 ? '#A8342A' : null], ['年净值涨幅', fmtPct(selFund.nav_return_1y), chg(selFund.nav_return_1y)], ['年价格涨幅', fmtPct(selFund.price_return_1y), chg(selFund.price_return_1y)], ['分值', selFund.score.toFixed(2), null]];
    if (selFund.subscription_status) {
      var subMap = {
        closed: '暂停申购',
        limited: '限大额' + (selFund.subscription_limit ? ' ' + selFund.subscription_limit : ''),
        open: '开放申购'
      };
      rows.push(['申购状态', subMap[selFund.subscription_status] || selFund.subscription_status, null]);
    }
    return /*#__PURE__*/React.createElement("div", {
      style: {
        padding: '12px 16px 68px'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '8px 0 12px'
      }
    }, /*#__PURE__*/React.createElement("span", {
      onClick: () => setSelFund(null),
      style: {
        fontFamily: 'var(--font-ui)',
        fontSize: 13,
        color: 'var(--fg-3)',
        cursor: 'pointer'
      }
    }, "\u2190 \u8FD4\u56DE"), selFund.arbitrage && /*#__PURE__*/React.createElement(ArbitrageBadge, {
      arb: selFund.arbitrage,
      limit: selFund.subscription_limit
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start'
      }
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 6
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-display-cjk)',
        fontSize: 18,
        fontWeight: 700
      }
    }, selFund.name), /*#__PURE__*/React.createElement(PoolBadge, {
      pool: selFund.rotation_pool
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        color: 'var(--fg-muted)',
        marginTop: 2
      }
    }, selFund.code, " \xB7 ", section.index_name)), /*#__PURE__*/React.createElement(RecIndicator, {
      rec: selFund.recommendation,
      stars: selFund.stars
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'baseline',
        gap: 10,
        margin: '12px 0 16px'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 28,
        fontWeight: 500
      }
    }, selFund.price.toFixed(3)), /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 14,
        color: chg(selFund.change)
      }
    }, fmtPct(selFund.change))), rows.map(([l, v, c]) => /*#__PURE__*/React.createElement("div", {
      key: l,
      style: {
        display: 'flex',
        justifyContent: 'space-between',
        padding: '6px 0',
        borderBottom: '1px solid var(--ink-10)'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-ui)',
        fontSize: 12,
        color: 'var(--fg-3)'
      }
    }, l), /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 12,
        color: c || 'var(--ink)'
      }
    }, v))), holdings.length > 0 && (() => {
      const totalWeight = holdings.reduce((sum, h) => sum + (h.weight || 0), 0);
      return /*#__PURE__*/React.createElement("div", {
        style: {
          marginTop: 16
        }
      }, totalWeight < 60 && /*#__PURE__*/React.createElement("div", {
        style: {
          padding: '8px 12px',
          background: 'rgba(168,52,42,0.08)',
          border: '1px solid rgba(168,52,42,0.2)',
          borderRadius: 4,
          marginBottom: 12
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          fontFamily: 'var(--font-ui)',
          fontSize: 11,
          color: '#A8342A'
        }
      }, "⚠️ \u6301\u4ED3\u8986\u76D6\u7387\u4EC5 ", totalWeight.toFixed(0), "%\uFF0C\u4F30\u7B97\u51C0\u503C\u53EF\u80FD\u8BEF\u5DEE\u8F83\u5927")), /*#__PURE__*/React.createElement(Label, null, "\u6301\u4ED3\u660E\u7EC6"), holdings.map(h => /*#__PURE__*/React.createElement("div", {
      key: h.ticker,
      style: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '6px 0',
        borderBottom: '1px solid var(--ink-10)'
      }
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 12,
        fontWeight: 500
      }
    }, h.ticker), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'var(--font-ui)',
        fontSize: 10,
        color: 'var(--fg-muted)'
      }
    }, h.name)), /*#__PURE__*/React.createElement("div", {
      style: {
        textAlign: 'right'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 12
      }
    }, h.weight?.toFixed(1), "%"), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        color: chg(h.change_pct)
      }
    }, h.change_pct != null ? fmtPct(h.change_pct) : '—')))));
    })())
  }
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '12px 16px 68px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '4px 0 6px'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 10,
      color: 'var(--fg-muted)'
    }
  }, REPORT.data_freshness), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 10,
      color: 'var(--fg-muted)'
    }
  }, REPORT.generated_at?.slice(11)), /*#__PURE__*/React.createElement(RefreshBtn, {
    compact: true
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6,
      overflowX: 'auto',
      paddingBottom: 8,
      marginBottom: 4
    }
  }, REPORT.sections.map(s => {
    const active = activeIdx === s.index_type;
    return /*#__PURE__*/React.createElement("span", {
      key: s.index_type,
      onClick: () => {
        setActiveIdx(s.index_type);
        setExpanded(null);
      },
      style: {
        fontFamily: 'var(--font-ui)',
        fontSize: 11,
        padding: '3px 10px',
        borderRadius: 999,
        cursor: 'pointer',
        border: active ? '1px solid var(--ink)' : '1px solid var(--ink-20)',
        background: active ? 'var(--ink)' : 'transparent',
        color: active ? 'var(--paper)' : 'var(--fg-2)',
        whiteSpace: 'nowrap'
      }
    }, s.index_name);
  })), fc && /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 10,
      color: 'var(--fg-muted)',
      marginBottom: 12,
      padding: '6px 10px',
      background: 'var(--ink-05)',
      borderRadius: 2
    }
  }, section.nav_date && /*#__PURE__*/React.createElement("span", null, "\u51C0\u503C ", section.nav_date.slice(5), " \xB7 "), fc.symbol, " ", fc.current_futures_price?.toFixed(0), " / ", fc.nav_date_close?.toFixed(0), " = ", fmtPct(fc.ratio_pct)), etfs.map((e, i) => {
    const isExp = expanded === e.code;
    const isTop = e.stars >= 4;
    const r = fc ? 1 + fc.ratio_pct / 100 : 1;
    const estNav = e.nav * r;
    return /*#__PURE__*/React.createElement("div", {
      key: e.code,
      onClick: () => setExpanded(isExp ? null : e.code),
      style: {
        padding: '12px 0',
        borderTop: '1px solid var(--ink-10)',
        cursor: 'pointer',
        background: isTop ? 'rgba(168,52,42,0.03)' : 'transparent'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 6
      }
    }, /*#__PURE__*/React.createElement("span", {
      onClick: ev => {
        ev.stopPropagation();
        setSelFund(e);
      },
      style: {
        fontFamily: 'var(--font-display-cjk)',
        fontSize: 14,
        fontWeight: 500,
        borderBottom: '1px dashed var(--ink-20)',
        cursor: 'pointer'
      }
    }, e.name), /*#__PURE__*/React.createElement(PoolBadge, {
      pool: e.rotation_pool
    }), /*#__PURE__*/React.createElement(RecCompact, {
      rec: e.recommendation,
      stars: e.stars
    }), /*#__PURE__*/React.createElement(ArbitrageBadge, {
      arb: e.arbitrage,
      limit: e.subscription_limit
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'var(--font-ui)',
        fontSize: 10,
        color: 'var(--fg-muted)',
        marginTop: 1
      }
    }, e.code)), /*#__PURE__*/React.createElement("div", {
      style: {
        textAlign: 'right'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 15
      }
    }, e.price.toFixed(3)), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 12,
        color: chg(e.change)
      }
    }, fmtPct(e.change)))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 12,
        marginTop: 8,
        flexWrap: 'wrap'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'var(--font-ui)',
        fontSize: 10,
        color: 'var(--fg-3)'
      }
    }, "\u51C0\u503C ", /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 11
      }
    }, e.nav.toFixed(3))), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'var(--font-ui)',
        fontSize: 10,
        color: 'var(--fg-3)'
      }
    }, "\u4F30\u7B97\u51C0\u503C ", /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        fontWeight: 500
      }
    }, estNav.toFixed(3))), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'var(--font-ui)',
        fontSize: 10,
        color: 'var(--fg-3)'
      }
    }, "\u6EA2\u4EF7 ", /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        color: chg(e.display_premium)
      }
    }, fmtPct(e.display_premium))), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: 'var(--font-ui)',
        fontSize: 10,
        color: 'var(--fg-3)'
      }
    }, "\u5206\u503C ", /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        fontWeight: 600
      }
    }, e.score.toFixed(2)))), isExp && /*#__PURE__*/React.createElement("div", {
      style: {
        marginTop: 12,
        padding: '12px',
        background: 'var(--ink-05)',
        borderRadius: 2
      }
    }, [['净值', e.nav.toFixed(3), null], ['估算净值', estNav.toFixed(3) + ' (' + fmtPct(fc?.ratio_pct) + ')', chg(fc?.ratio_pct)], ['估算溢价', fmtPct(e.display_premium), chg(e.display_premium)], ['3M均溢价', fmtPct(e.avg_3m), null], ['6M均溢价', fmtPct(e.avg_6m), null], ['1Y均溢价', fmtPct(e.avg_1y), null], ['溢价>7%天数', String(e.days_gt7), e.days_gt7 > 30 ? '#A8342A' : null], ['年净值涨幅', fmtPct(e.nav_return_1y), chg(e.nav_return_1y)], ['年价格涨幅', fmtPct(e.price_return_1y), chg(e.price_return_1y)]].map(([l, v, c]) => /*#__PURE__*/React.createElement("div", {
      key: l,
      style: {
        display: 'flex',
        justifyContent: 'space-between',
        padding: '4px 0',
        borderBottom: '1px solid var(--ink-10)'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-ui)',
        fontSize: 10,
        color: 'var(--fg-3)'
      }
    }, l), /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        color: c || 'var(--ink)'
      }
    }, v)))));
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      borderTop: '1px solid var(--ink-10)'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-ui)',
      fontSize: 10,
      color: 'var(--fg-muted)',
      marginTop: 12,
      lineHeight: 1.6
    }
  }, /*#__PURE__*/React.createElement("div", null, "\u70B9\u51FB\u5C55\u5F00\u8BE6\u60C5 \xB7 \u70B9\u51FB\u540D\u79F0\u67E5\u770B\u5B8C\u6574\u4FE1\u606F"), /*#__PURE__*/React.createElement("div", null, "\u5206\u503C = \u6EA2\u4EF7\u504F\u79BB\u5386\u53F2\u6EA2\u4EF7\u5747\u503C + \u540C\u7C7B\u8DDF\u8E2A\u8D28\u91CF\u5DEE\u5F02\u3002\u5206\u503C\u8D8A\u9AD8\uFF0C\u5F53\u524D\u6EA2\u4EF7\u8D8A\u4F4E\u4E8E\u5386\u53F2\u6C34\u5E73\u3002\u4EC5\u53CD\u6620\u6EA2\u4EF7\u4F4D\u7F6E\uFF0C\u4E0D\u9884\u6D4B\u677F\u5757\u6DA8\u8DCC\u3002")));
}
window.MobTabs = MobTabs;
window.MobOverview = MobOverview;
window.MobPremium = MobPremium;

// tweaks-panel.jsx
// Reusable Tweaks shell + form-control helpers.
//
// Owns the host protocol (listens for __activate_edit_mode / __deactivate_edit_mode,
// posts __edit_mode_available / __edit_mode_set_keys / __edit_mode_dismissed) so
// individual prototypes don't re-roll it. Ships a consistent set of controls so you
// don't hand-draw <input type="range">, segmented radios, steppers, etc.
//
// Usage (in an HTML file that loads React + Babel):
//
//   const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
//     "primaryColor": "#D97757",
//     "palette": ["#D97757", "#29261b", "#f6f4ef"],
//     "fontSize": 16,
//     "density": "regular",
//     "dark": false
//   }/*EDITMODE-END*/;
//
//   function App() {
//     const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
//     return (
//       <div style={{ fontSize: t.fontSize, color: t.primaryColor }}>
//         Hello
//         <TweaksPanel>
//           <TweakSection label="Typography" />
//           <TweakSlider label="Font size" value={t.fontSize} min={10} max={32} unit="px"
//                        onChange={(v) => setTweak('fontSize', v)} />
//           <TweakRadio  label="Density" value={t.density}
//                        options={['compact', 'regular', 'comfy']}
//                        onChange={(v) => setTweak('density', v)} />
//           <TweakSection label="Theme" />
//           <TweakColor  label="Primary" value={t.primaryColor}
//                        options={['#D97757', '#2A6FDB', '#1F8A5B', '#7A5AE0']}
//                        onChange={(v) => setTweak('primaryColor', v)} />
//           <TweakColor  label="Palette" value={t.palette}
//                        options={[['#D97757', '#29261b', '#f6f4ef'],
//                                  ['#475569', '#0f172a', '#f1f5f9']]}
//                        onChange={(v) => setTweak('palette', v)} />
//           <TweakToggle label="Dark mode" value={t.dark}
//                        onChange={(v) => setTweak('dark', v)} />
//         </TweaksPanel>
//       </div>
//     );
//   }
//
// ─────────────────────────────────────────────────────────────────────────────

const __TWEAKS_STYLE = `
  .twk-panel{position:fixed;right:16px;bottom:16px;z-index:2147483646;width:280px;
    max-height:calc(100vh - 32px);display:flex;flex-direction:column;
    transform:scale(var(--dc-inv-zoom,1));transform-origin:bottom right;
    background:rgba(250,249,247,.78);color:#29261b;
    -webkit-backdrop-filter:blur(24px) saturate(160%);backdrop-filter:blur(24px) saturate(160%);
    border:.5px solid rgba(255,255,255,.6);border-radius:14px;
    box-shadow:0 1px 0 rgba(255,255,255,.5) inset,0 12px 40px rgba(0,0,0,.18);
    font:11.5px/1.4 ui-sans-serif,system-ui,-apple-system,sans-serif;overflow:hidden}
  .twk-hd{display:flex;align-items:center;justify-content:space-between;
    padding:10px 8px 10px 14px;cursor:move;user-select:none}
  .twk-hd b{font-size:12px;font-weight:600;letter-spacing:.01em}
  .twk-x{appearance:none;border:0;background:transparent;color:rgba(41,38,27,.55);
    width:22px;height:22px;border-radius:6px;cursor:default;font-size:13px;line-height:1}
  .twk-x:hover{background:rgba(0,0,0,.06);color:#29261b}
  .twk-body{padding:2px 14px 14px;display:flex;flex-direction:column;gap:10px;
    overflow-y:auto;overflow-x:hidden;min-height:0;
    scrollbar-width:thin;scrollbar-color:rgba(0,0,0,.15) transparent}
  .twk-body::-webkit-scrollbar{width:8px}
  .twk-body::-webkit-scrollbar-track{background:transparent;margin:2px}
  .twk-body::-webkit-scrollbar-thumb{background:rgba(0,0,0,.15);border-radius:4px;
    border:2px solid transparent;background-clip:content-box}
  .twk-body::-webkit-scrollbar-thumb:hover{background:rgba(0,0,0,.25);
    border:2px solid transparent;background-clip:content-box}
  .twk-row{display:flex;flex-direction:column;gap:5px}
  .twk-row-h{flex-direction:row;align-items:center;justify-content:space-between;gap:10px}
  .twk-lbl{display:flex;justify-content:space-between;align-items:baseline;
    color:rgba(41,38,27,.72)}
  .twk-lbl>span:first-child{font-weight:500}
  .twk-val{color:rgba(41,38,27,.5);font-variant-numeric:tabular-nums}

  .twk-sect{font-size:10px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;
    color:rgba(41,38,27,.45);padding:10px 0 0}
  .twk-sect:first-child{padding-top:0}

  .twk-field{appearance:none;width:100%;height:26px;padding:0 8px;
    border:.5px solid rgba(0,0,0,.1);border-radius:7px;
    background:rgba(255,255,255,.6);color:inherit;font:inherit;outline:none}
  .twk-field:focus{border-color:rgba(0,0,0,.25);background:rgba(255,255,255,.85)}
  select.twk-field{padding-right:22px;
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><path fill='rgba(0,0,0,.5)' d='M0 0h10L5 6z'/></svg>");
    background-repeat:no-repeat;background-position:right 8px center}

  .twk-slider{appearance:none;-webkit-appearance:none;width:100%;height:4px;margin:6px 0;
    border-radius:999px;background:rgba(0,0,0,.12);outline:none}
  .twk-slider::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;
    width:14px;height:14px;border-radius:50%;background:#fff;
    border:.5px solid rgba(0,0,0,.12);box-shadow:0 1px 3px rgba(0,0,0,.2);cursor:default}
  .twk-slider::-moz-range-thumb{width:14px;height:14px;border-radius:50%;
    background:#fff;border:.5px solid rgba(0,0,0,.12);box-shadow:0 1px 3px rgba(0,0,0,.2);cursor:default}

  .twk-seg{position:relative;display:flex;padding:2px;border-radius:8px;
    background:rgba(0,0,0,.06);user-select:none}
  .twk-seg-thumb{position:absolute;top:2px;bottom:2px;border-radius:6px;
    background:rgba(255,255,255,.9);box-shadow:0 1px 2px rgba(0,0,0,.12);
    transition:left .15s cubic-bezier(.3,.7,.4,1),width .15s}
  .twk-seg.dragging .twk-seg-thumb{transition:none}
  .twk-seg button{appearance:none;position:relative;z-index:1;flex:1;border:0;
    background:transparent;color:inherit;font:inherit;font-weight:500;min-height:22px;
    border-radius:6px;cursor:default;padding:4px 6px;line-height:1.2;
    overflow-wrap:anywhere}

  .twk-toggle{position:relative;width:32px;height:18px;border:0;border-radius:999px;
    background:rgba(0,0,0,.15);transition:background .15s;cursor:default;padding:0}
  .twk-toggle[data-on="1"]{background:#34c759}
  .twk-toggle i{position:absolute;top:2px;left:2px;width:14px;height:14px;border-radius:50%;
    background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.25);transition:transform .15s}
  .twk-toggle[data-on="1"] i{transform:translateX(14px)}

  .twk-num{display:flex;align-items:center;height:26px;padding:0 0 0 8px;
    border:.5px solid rgba(0,0,0,.1);border-radius:7px;background:rgba(255,255,255,.6)}
  .twk-num-lbl{font-weight:500;color:rgba(41,38,27,.6);cursor:ew-resize;
    user-select:none;padding-right:8px}
  .twk-num input{flex:1;min-width:0;height:100%;border:0;background:transparent;
    font:inherit;font-variant-numeric:tabular-nums;text-align:right;padding:0 8px 0 0;
    outline:none;color:inherit;-moz-appearance:textfield}
  .twk-num input::-webkit-inner-spin-button,.twk-num input::-webkit-outer-spin-button{
    -webkit-appearance:none;margin:0}
  .twk-num-unit{padding-right:8px;color:rgba(41,38,27,.45)}

  .twk-btn{appearance:none;height:26px;padding:0 12px;border:0;border-radius:7px;
    background:rgba(0,0,0,.78);color:#fff;font:inherit;font-weight:500;cursor:default}
  .twk-btn:hover{background:rgba(0,0,0,.88)}
  .twk-btn.secondary{background:rgba(0,0,0,.06);color:inherit}
  .twk-btn.secondary:hover{background:rgba(0,0,0,.1)}

  .twk-swatch{appearance:none;-webkit-appearance:none;width:56px;height:22px;
    border:.5px solid rgba(0,0,0,.1);border-radius:6px;padding:0;cursor:default;
    background:transparent;flex-shrink:0}
  .twk-swatch::-webkit-color-swatch-wrapper{padding:0}
  .twk-swatch::-webkit-color-swatch{border:0;border-radius:5.5px}
  .twk-swatch::-moz-color-swatch{border:0;border-radius:5.5px}

  .twk-chips{display:flex;gap:6px}
  .twk-chip{position:relative;appearance:none;flex:1;min-width:0;height:46px;
    padding:0;border:0;border-radius:6px;overflow:hidden;cursor:default;
    box-shadow:0 0 0 .5px rgba(0,0,0,.12),0 1px 2px rgba(0,0,0,.06);
    transition:transform .12s cubic-bezier(.3,.7,.4,1),box-shadow .12s}
  .twk-chip:hover{transform:translateY(-1px);
    box-shadow:0 0 0 .5px rgba(0,0,0,.18),0 4px 10px rgba(0,0,0,.12)}
  .twk-chip[data-on="1"]{box-shadow:0 0 0 1.5px rgba(0,0,0,.85),
    0 2px 6px rgba(0,0,0,.15)}
  .twk-chip>span{position:absolute;top:0;bottom:0;right:0;width:34%;
    display:flex;flex-direction:column;box-shadow:-1px 0 0 rgba(0,0,0,.1)}
  .twk-chip>span>i{flex:1;box-shadow:0 -1px 0 rgba(0,0,0,.1)}
  .twk-chip>span>i:first-child{box-shadow:none}
  .twk-chip svg{position:absolute;top:6px;left:6px;width:13px;height:13px;
    filter:drop-shadow(0 1px 1px rgba(0,0,0,.3))}
`;

// ── useTweaks ───────────────────────────────────────────────────────────────
// Single source of truth for tweak values. setTweak persists via the host
// (__edit_mode_set_keys → host rewrites the EDITMODE block on disk).
function useTweaks(defaults) {
  const [values, setValues] = React.useState(defaults);
  // Accepts either setTweak('key', value) or setTweak({ key: value, ... }) so a
  // useState-style call doesn't write a "[object Object]" key into the persisted
  // JSON block.
  const setTweak = React.useCallback((keyOrEdits, val) => {
    const edits = typeof keyOrEdits === 'object' && keyOrEdits !== null ? keyOrEdits : {
      [keyOrEdits]: val
    };
    setValues(prev => ({
      ...prev,
      ...edits
    }));
    window.parent.postMessage({
      type: '__edit_mode_set_keys',
      edits
    }, '*');
    // Same-window signal so in-page listeners (deck-stage rail thumbnails)
    // can react — the parent message only reaches the host, not peers.
    window.dispatchEvent(new CustomEvent('tweakchange', {
      detail: edits
    }));
  }, []);
  return [values, setTweak];
}

// ── TweaksPanel ─────────────────────────────────────────────────────────────
// Floating shell. Registers the protocol listener BEFORE announcing
// availability — if the announce ran first, the host's activate could land
// before our handler exists and the toolbar toggle would silently no-op.
// The close button posts __edit_mode_dismissed so the host's toolbar toggle
// flips off in lockstep; the host echoes __deactivate_edit_mode back which
// is what actually hides the panel.
function TweaksPanel({
  title = 'Tweaks',
  noDeckControls = false,
  children
}) {
  const [open, setOpen] = React.useState(false);
  const dragRef = React.useRef(null);
  // Auto-inject a rail toggle when a <deck-stage> is on the page. The
  // toggle drives the deck's per-viewer _railVisible via window message;
  // state is mirrored from the same localStorage key the deck reads so
  // the control reflects reality across reloads. The mechanism is the
  // message — authors who want custom placement can post it directly
  // and pass noDeckControls to suppress this one.
  const hasDeckStage = React.useMemo(() => typeof document !== 'undefined' && !!document.querySelector('deck-stage'), []);
  // Hide the toggle until the host has actually enabled the rail (the
  // __omelette_rail_enabled window message, posted only when the
  // omelette_deck_rail_enabled flag is on for this user). The initial read
  // covers TweaksPanel mounting after the message already arrived; the
  // listener covers the common case of mounting first.
  const [railEnabled, setRailEnabled] = React.useState(() => hasDeckStage && !!document.querySelector('deck-stage')?._railEnabled);
  React.useEffect(() => {
    if (!hasDeckStage || railEnabled) return undefined;
    const onMsg = e => {
      if (e.data && e.data.type === '__omelette_rail_enabled') setRailEnabled(true);
    };
    window.addEventListener('message', onMsg);
    return () => window.removeEventListener('message', onMsg);
  }, [hasDeckStage, railEnabled]);
  const [railVisible, setRailVisible] = React.useState(() => {
    try {
      return localStorage.getItem('deck-stage.railVisible') !== '0';
    } catch (e) {
      return true;
    }
  });
  const toggleRail = on => {
    setRailVisible(on);
    window.postMessage({
      type: '__deck_rail_visible',
      on
    }, '*');
  };
  const offsetRef = React.useRef({
    x: 16,
    y: 16
  });
  const PAD = 16;
  const clampToViewport = React.useCallback(() => {
    const panel = dragRef.current;
    if (!panel) return;
    const w = panel.offsetWidth,
      h = panel.offsetHeight;
    const maxRight = Math.max(PAD, window.innerWidth - w - PAD);
    const maxBottom = Math.max(PAD, window.innerHeight - h - PAD);
    offsetRef.current = {
      x: Math.min(maxRight, Math.max(PAD, offsetRef.current.x)),
      y: Math.min(maxBottom, Math.max(PAD, offsetRef.current.y))
    };
    panel.style.right = offsetRef.current.x + 'px';
    panel.style.bottom = offsetRef.current.y + 'px';
  }, []);
  React.useEffect(() => {
    if (!open) return;
    clampToViewport();
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', clampToViewport);
      return () => window.removeEventListener('resize', clampToViewport);
    }
    const ro = new ResizeObserver(clampToViewport);
    ro.observe(document.documentElement);
    return () => ro.disconnect();
  }, [open, clampToViewport]);
  React.useEffect(() => {
    const onMsg = e => {
      const t = e?.data?.type;
      if (t === '__activate_edit_mode') setOpen(true);else if (t === '__deactivate_edit_mode') setOpen(false);
    };
    window.addEventListener('message', onMsg);
    window.parent.postMessage({
      type: '__edit_mode_available'
    }, '*');
    return () => window.removeEventListener('message', onMsg);
  }, []);
  const dismiss = () => {
    setOpen(false);
    window.parent.postMessage({
      type: '__edit_mode_dismissed'
    }, '*');
  };
  const onDragStart = e => {
    const panel = dragRef.current;
    if (!panel) return;
    const r = panel.getBoundingClientRect();
    const sx = e.clientX,
      sy = e.clientY;
    const startRight = window.innerWidth - r.right;
    const startBottom = window.innerHeight - r.bottom;
    const move = ev => {
      offsetRef.current = {
        x: startRight - (ev.clientX - sx),
        y: startBottom - (ev.clientY - sy)
      };
      clampToViewport();
    };
    const up = () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
    };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  };
  if (!open) return null;
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("style", null, __TWEAKS_STYLE), /*#__PURE__*/React.createElement("div", {
    ref: dragRef,
    className: "twk-panel",
    "data-noncommentable": "",
    style: {
      right: offsetRef.current.x,
      bottom: offsetRef.current.y
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "twk-hd",
    onMouseDown: onDragStart
  }, /*#__PURE__*/React.createElement("b", null, title), /*#__PURE__*/React.createElement("button", {
    className: "twk-x",
    "aria-label": "Close tweaks",
    onMouseDown: e => e.stopPropagation(),
    onClick: dismiss
  }, "\u2715")), /*#__PURE__*/React.createElement("div", {
    className: "twk-body"
  }, children, hasDeckStage && railEnabled && !noDeckControls && /*#__PURE__*/React.createElement(TweakSection, {
    label: "Deck"
  }, /*#__PURE__*/React.createElement(TweakToggle, {
    label: "Thumbnail rail",
    value: railVisible,
    onChange: toggleRail
  })))));
}

// ── Layout helpers ──────────────────────────────────────────────────────────

function TweakSection({
  label,
  children
}) {
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "twk-sect"
  }, label), children);
}
function TweakRow({
  label,
  value,
  children,
  inline = false
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: inline ? 'twk-row twk-row-h' : 'twk-row'
  }, /*#__PURE__*/React.createElement("div", {
    className: "twk-lbl"
  }, /*#__PURE__*/React.createElement("span", null, label), value != null && /*#__PURE__*/React.createElement("span", {
    className: "twk-val"
  }, value)), children);
}

// ── Controls ────────────────────────────────────────────────────────────────

function TweakSlider({
  label,
  value,
  min = 0,
  max = 100,
  step = 1,
  unit = '',
  onChange
}) {
  return /*#__PURE__*/React.createElement(TweakRow, {
    label: label,
    value: `${value}${unit}`
  }, /*#__PURE__*/React.createElement("input", {
    type: "range",
    className: "twk-slider",
    min: min,
    max: max,
    step: step,
    value: value,
    onChange: e => onChange(Number(e.target.value))
  }));
}
function TweakToggle({
  label,
  value,
  onChange
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: "twk-row twk-row-h"
  }, /*#__PURE__*/React.createElement("div", {
    className: "twk-lbl"
  }, /*#__PURE__*/React.createElement("span", null, label)), /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "twk-toggle",
    "data-on": value ? '1' : '0',
    role: "switch",
    "aria-checked": !!value,
    onClick: () => onChange(!value)
  }, /*#__PURE__*/React.createElement("i", null)));
}
function TweakRadio({
  label,
  value,
  options,
  onChange
}) {
  const trackRef = React.useRef(null);
  const [dragging, setDragging] = React.useState(false);
  // The active value is read by pointer-move handlers attached for the lifetime
  // of a drag — ref it so a stale closure doesn't fire onChange for every move.
  const valueRef = React.useRef(value);
  valueRef.current = value;

  // Segments wrap mid-word once per-segment width runs out. The track is
  // ~248px (280 panel − 28 body pad − 4 seg pad), each button loses 12px
  // to its own padding, and 11.5px system-ui averages ~6.3px/char — so 2
  // options fit ~16 chars each, 3 fit ~10. Past that (or >3 options), fall
  // back to a dropdown rather than wrap.
  const labelLen = o => String(typeof o === 'object' ? o.label : o).length;
  const maxLen = options.reduce((m, o) => Math.max(m, labelLen(o)), 0);
  const fitsAsSegments = maxLen <= ({
    2: 16,
    3: 10
  }[options.length] ?? 0);
  if (!fitsAsSegments) {
    // <select> emits strings — map back to the original option value so the
    // fallback stays type-preserving (numbers, booleans) like the segment path.
    const resolve = s => {
      const m = options.find(o => String(typeof o === 'object' ? o.value : o) === s);
      return m === undefined ? s : typeof m === 'object' ? m.value : m;
    };
    return /*#__PURE__*/React.createElement(TweakSelect, {
      label: label,
      value: value,
      options: options,
      onChange: s => onChange(resolve(s))
    });
  }
  const opts = options.map(o => typeof o === 'object' ? o : {
    value: o,
    label: o
  });
  const idx = Math.max(0, opts.findIndex(o => o.value === value));
  const n = opts.length;
  const segAt = clientX => {
    const r = trackRef.current.getBoundingClientRect();
    const inner = r.width - 4;
    const i = Math.floor((clientX - r.left - 2) / inner * n);
    return opts[Math.max(0, Math.min(n - 1, i))].value;
  };
  const onPointerDown = e => {
    setDragging(true);
    const v0 = segAt(e.clientX);
    if (v0 !== valueRef.current) onChange(v0);
    const move = ev => {
      if (!trackRef.current) return;
      const v = segAt(ev.clientX);
      if (v !== valueRef.current) onChange(v);
    };
    const up = () => {
      setDragging(false);
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };
  return /*#__PURE__*/React.createElement(TweakRow, {
    label: label
  }, /*#__PURE__*/React.createElement("div", {
    ref: trackRef,
    role: "radiogroup",
    onPointerDown: onPointerDown,
    className: dragging ? 'twk-seg dragging' : 'twk-seg'
  }, /*#__PURE__*/React.createElement("div", {
    className: "twk-seg-thumb",
    style: {
      left: `calc(2px + ${idx} * (100% - 4px) / ${n})`,
      width: `calc((100% - 4px) / ${n})`
    }
  }), opts.map(o => /*#__PURE__*/React.createElement("button", {
    key: o.value,
    type: "button",
    role: "radio",
    "aria-checked": o.value === value
  }, o.label))));
}
function TweakSelect({
  label,
  value,
  options,
  onChange
}) {
  return /*#__PURE__*/React.createElement(TweakRow, {
    label: label
  }, /*#__PURE__*/React.createElement("select", {
    className: "twk-field",
    value: value,
    onChange: e => onChange(e.target.value)
  }, options.map(o => {
    const v = typeof o === 'object' ? o.value : o;
    const l = typeof o === 'object' ? o.label : o;
    return /*#__PURE__*/React.createElement("option", {
      key: v,
      value: v
    }, l);
  })));
}
function TweakText({
  label,
  value,
  placeholder,
  onChange
}) {
  return /*#__PURE__*/React.createElement(TweakRow, {
    label: label
  }, /*#__PURE__*/React.createElement("input", {
    className: "twk-field",
    type: "text",
    value: value,
    placeholder: placeholder,
    onChange: e => onChange(e.target.value)
  }));
}
function TweakNumber({
  label,
  value,
  min,
  max,
  step = 1,
  unit = '',
  onChange
}) {
  const clamp = n => {
    if (min != null && n < min) return min;
    if (max != null && n > max) return max;
    return n;
  };
  const startRef = React.useRef({
    x: 0,
    val: 0
  });
  const onScrubStart = e => {
    e.preventDefault();
    startRef.current = {
      x: e.clientX,
      val: value
    };
    const decimals = (String(step).split('.')[1] || '').length;
    const move = ev => {
      const dx = ev.clientX - startRef.current.x;
      const raw = startRef.current.val + dx * step;
      const snapped = Math.round(raw / step) * step;
      onChange(clamp(Number(snapped.toFixed(decimals))));
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "twk-num"
  }, /*#__PURE__*/React.createElement("span", {
    className: "twk-num-lbl",
    onPointerDown: onScrubStart
  }, label), /*#__PURE__*/React.createElement("input", {
    type: "number",
    value: value,
    min: min,
    max: max,
    step: step,
    onChange: e => onChange(clamp(Number(e.target.value)))
  }), unit && /*#__PURE__*/React.createElement("span", {
    className: "twk-num-unit"
  }, unit));
}

// Relative-luminance contrast pick — checkmarks drawn over a swatch need to
// read on both #111 and #fafafa without per-option configuration. Hex input
// only (#rgb / #rrggbb); named or rgb()/hsl() colors fall through to "light".
function __twkIsLight(hex) {
  const h = String(hex).replace('#', '');
  const x = h.length === 3 ? h.replace(/./g, c => c + c) : h.padEnd(6, '0');
  const n = parseInt(x.slice(0, 6), 16);
  if (Number.isNaN(n)) return true;
  const r = n >> 16 & 255,
    g = n >> 8 & 255,
    b = n & 255;
  return r * 299 + g * 587 + b * 114 > 148000;
}
const __TwkCheck = ({
  light
}) => /*#__PURE__*/React.createElement("svg", {
  viewBox: "0 0 14 14",
  "aria-hidden": "true"
}, /*#__PURE__*/React.createElement("path", {
  d: "M3 7.2 5.8 10 11 4.2",
  fill: "none",
  strokeWidth: "2.2",
  strokeLinecap: "round",
  strokeLinejoin: "round",
  stroke: light ? 'rgba(0,0,0,.78)' : '#fff'
}));

// TweakColor — curated color/palette picker. Each option is either a single
// hex string or an array of 1-5 hex strings; the card adapts — a lone color
// renders solid, a palette renders colors[0] as the hero (left ~2/3) with the
// rest stacked in a sharp column on the right. onChange emits the
// option in the shape it was passed (string stays string, array stays array).
// Without options it falls back to the native color input for back-compat.
function TweakColor({
  label,
  value,
  options,
  onChange
}) {
  if (!options || !options.length) {
    return /*#__PURE__*/React.createElement("div", {
      className: "twk-row twk-row-h"
    }, /*#__PURE__*/React.createElement("div", {
      className: "twk-lbl"
    }, /*#__PURE__*/React.createElement("span", null, label)), /*#__PURE__*/React.createElement("input", {
      type: "color",
      className: "twk-swatch",
      value: value,
      onChange: e => onChange(e.target.value)
    }));
  }
  // Native <input type=color> emits lowercase hex per the HTML spec, so
  // compare case-insensitively. String() guards JSON.stringify(undefined),
  // which returns the primitive undefined (no .toLowerCase).
  const key = o => String(JSON.stringify(o)).toLowerCase();
  const cur = key(value);
  return /*#__PURE__*/React.createElement(TweakRow, {
    label: label
  }, /*#__PURE__*/React.createElement("div", {
    className: "twk-chips",
    role: "radiogroup"
  }, options.map((o, i) => {
    const colors = Array.isArray(o) ? o : [o];
    const [hero, ...rest] = colors;
    const sup = rest.slice(0, 4);
    const on = key(o) === cur;
    return /*#__PURE__*/React.createElement("button", {
      key: i,
      type: "button",
      className: "twk-chip",
      role: "radio",
      "aria-checked": on,
      "data-on": on ? '1' : '0',
      "aria-label": colors.join(', '),
      title: colors.join(' · '),
      style: {
        background: hero
      },
      onClick: () => onChange(o)
    }, sup.length > 0 && /*#__PURE__*/React.createElement("span", null, sup.map((c, j) => /*#__PURE__*/React.createElement("i", {
      key: j,
      style: {
        background: c
      }
    }))), on && /*#__PURE__*/React.createElement(__TwkCheck, {
      light: __twkIsLight(hero)
    }));
  })));
}
function TweakButton({
  label,
  onClick,
  secondary = false
}) {
  return /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: secondary ? 'twk-btn secondary' : 'twk-btn',
    onClick: onClick
  }, label);
}
Object.assign(window, {
  useTweaks,
  TweaksPanel,
  TweakSection,
  TweakRow,
  TweakSlider,
  TweakToggle,
  TweakRadio,
  TweakSelect,
  TweakText,
  TweakNumber,
  TweakColor,
  TweakButton
});

// === App + Router ===
function parseRoute() {
  var path = location.pathname;
  var params = new URLSearchParams(location.search);
  var isMobile = /Mobile|Android|iPhone|iPad/i.test(navigator.userAgent) || path.startsWith('/m');
  var view = isMobile ? 'mobile' : 'pc';
  var tab = 'overview';
  if (path.includes('rotation')) tab = 'rotation';
  else if (path.includes('premium') || path.includes('detail')) tab = 'premium';
  var idx = params.get('idx') || 'NASDAQ';
  return { view: view, tab: tab, idx: idx };
}

function App() {
  var route = parseRoute();
  var _vm = React.useState(route.view), viewMode = _vm[0], setViewMode = _vm[1];
  var _tb = React.useState(route.tab), tab = _tb[0], setTab = _tb[1];
  var _ai = React.useState(route.idx), activeIdx = _ai[0], setActiveIdx = _ai[1];
  var _fu = React.useState(0); window.__rerender = function() { _fu[1](function(n) { return n + 1; }); };

  function navigate(view, t, idx) {
    var path = view === 'mobile' ? '/m/' : '/';
    if (t === 'premium') path += 'premium';
    else if (t === 'rotation') path += 'rotation';
    var search = idx && idx !== 'NASDAQ' ? '?idx=' + idx : '';
    history.replaceState(null, '', path + search);
  }

  function switchTab(t) { setTab(t); navigate(viewMode, t, activeIdx); window.scrollTo(0, 0); }
  function switchIdx(idx) { setActiveIdx(idx); navigate(viewMode, tab, idx); }

  var pageKey = tab + activeIdx;

  var page;
  if (tab === 'rotation') {
    page = React.createElement(viewMode === 'pc' ? PCRotation : MobRotation);
  } else if (tab === 'premium') {
    page = React.createElement(viewMode === 'pc' ? PCPremium : MobPremium, { activeIdx: activeIdx, setActiveIdx: switchIdx });
  } else {
    page = React.createElement(viewMode === 'pc' ? PCOverview : MobOverview, { setTab: switchTab, setIdx: switchIdx });
  }

  if (viewMode === 'pc') {
    return React.createElement(React.Fragment, null,
      React.createElement(PCNav, { tab: tab, setTab: switchTab }),
      React.createElement('div', { className: 'fade-in', key: pageKey }, page),
      React.createElement('div', { className: 'ft' }, '© 2026 千里知投 · 数据仅供参考，不构成投资建议')
    );
  }

  return React.createElement('div', { className: 'mob' },
    React.createElement('div', { className: 'fade-in', key: pageKey, style: { minHeight: '100vh' } }, page),
    React.createElement(MobTabs, { tab: tab, setTab: switchTab })
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(App, null));
