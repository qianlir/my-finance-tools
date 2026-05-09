// PC layout — tab-based: Overview + Premium Analysis
const { useState: useS, useMemo: useM, useEffect: useE, useCallback: useC } = React;

/* ── PC Header with Nav ── */
function PCNav({ tab, setTab }) {
  const [scrolled, setScrolled] = useS(false);
  useE(() => { const fn = () => setScrolled(window.scrollY > 12); window.addEventListener('scroll', fn); return () => window.removeEventListener('scroll', fn); }, []);
  const tabs = [
    { k: 'overview', l: '总览' },
    { k: 'premium', l: '溢价分析' },
    { k: 'rotation', l: '纳指轮动' },
  ];
  return (
    <header style={{
      position: 'sticky', top: 0, zIndex: 20, background: 'var(--paper)',
      borderBottom: scrolled ? '1px solid var(--ink-20)' : '1px solid transparent',
      transition: 'border-color 240ms var(--ease-gentle)', height: 52,
    }}>
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 32px', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span style={{ fontFamily: 'var(--font-display-cjk)', fontWeight: 700, fontSize: 20, color: 'var(--ink)', letterSpacing: '-0.02em' }}>千里知投</span>
          <span style={{ fontFamily: 'var(--font-ui)', fontSize: 10, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--fg-muted)' }}>ETF Advisor</span>
        </div>
        <nav style={{ display: 'flex', gap: 24 }}>
          {tabs.map(t => (
            <a key={t.k} href="#" onClick={e => { e.preventDefault(); setTab(t.k); }}
              style={{
                fontFamily: 'var(--font-ui)', fontSize: 13, textDecoration: 'none',
                color: tab === t.k ? 'var(--ink)' : 'var(--fg-3)',
                borderBottom: tab === t.k ? '1px solid var(--ink)' : '1px solid transparent',
                paddingBottom: 2, letterSpacing: '0.01em',
              }}>{t.l}</a>
          ))}
        </nav>
      </div>
    </header>
  );
}

/* ══════════════════════════════════════════
   Overview — light summary, fewer columns
   ══════════════════════════════════════════ */
function PCOverview({ setTab, setIdx }) {
  if (!REPORT.sections.length) return null;
  const [selFund, setSelFund] = useS(null);
  const topPicks = REPORT.sections.map(s => ({ section: s, etf: s.etfs[0] }));

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '32px 32px 64px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontFamily: 'var(--font-ui)', fontSize: 11, color: 'var(--fg-muted)' }}>{REPORT.data_freshness}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-muted)' }}>更新 {REPORT.generated_at}</span>
          <RefreshBtn />
        </div>
      </div>
      <FuturesTicker data={REPORT.futures} />

      {/* Quick picks — one card per index */}
      <Label right={<a href="#" onClick={e => { e.preventDefault(); setTab('premium'); }} style={{ color: 'var(--fg-3)', textDecoration: 'none', borderBottom: '1px solid var(--ink-20)', fontFamily: 'var(--font-ui)', fontSize: 12 }}>详细分析 →</a>}>今日各指数推荐</Label>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${REPORT.sections.length}, 1fr)`, gap: 1, background: 'var(--ink-10)', border: '1px solid var(--ink-10)', marginBottom: 40 }}>
        {topPicks.map(({ section: s, etf: e }) => (
          <div key={s.index_type} onClick={() => { setIdx(s.index_type); setTab('premium'); }} style={{ background: 'var(--paper)', padding: '18px', cursor: 'pointer' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ fontFamily: 'var(--font-ui)', fontSize: 10, fontWeight: 600, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{s.index_name}</span>
              {s.futures_cumulative != null && (
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: chg(s.futures_cumulative) }}>修正 {fmtPct(s.futures_cumulative)}</span>
              )}
            </div>
            <div style={{ fontFamily: 'var(--font-display-cjk)', fontSize: 14, fontWeight: 500, marginTop: 8 }}>{e.name}</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-muted)', marginTop: 1 }}>{e.code}</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 8 }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 500 }}>{e.price.toFixed(3)}</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: chg(e.change) }}>{fmtPct(e.change)}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
              <span style={{ fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-3)' }}>溢价</span>
              <PremBar v={e.display_premium} max={8} />
            </div>
            <div style={{ marginTop: 8 }}>
              <RecCompact rec={e.recommendation} stars={e.stars} />
            </div>
          </div>
        ))}
      </div>

      {/* All ETFs ranked — light table */}
      <Label>全部 ETF 按分值排序</Label>
      {(() => {
        const allETFs = REPORT.sections.flatMap(s => s.etfs.map(e => ({ ...e, indexName: s.index_name })));
        allETFs.sort((a, b) => b.score - a.score);
        return (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={{ ...TH, textAlign: 'left' }}>ETF</th>
              <th style={TH}>指数</th>
              <th style={TH}>价格</th>
              <th style={TH}>涨幅</th>
              <th style={TH}>估算溢价</th>
              <th style={TH}>年净值涨幅</th>
              <th style={TH}>分值</th>
              <th style={TH}>推荐</th>
            </tr></thead>
            <tbody>
              {allETFs.map(e => {
                const isTop = e.stars >= 4;
                const isSell = e.stars < 0;
                const rowBg = isTop ? 'rgba(168,52,42,0.04)' : isSell ? 'rgba(42,107,79,0.04)' : 'transparent';
                return (
                  <tr key={e.code} style={{ background: rowBg }}
                    onMouseEnter={ev => ev.currentTarget.style.background = 'var(--ink-05)'}
                    onMouseLeave={ev => ev.currentTarget.style.background = rowBg}>
                    <td style={TDL} onClick={() => { const s = REPORT.sections.find(s => s.index_name === e.indexName); if (s) { setIdx(s.index_type); setTab('premium'); }}}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
                        <span style={{ fontFamily: 'var(--font-display-cjk)', fontSize: 13, fontWeight: 500, borderBottom: '1px dashed var(--ink-20)' }}>{e.name}</span>
                        <PoolBadge pool={e.rotation_pool} />
                      </div>
                      <div style={{ fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-muted)' }}>{e.code}</div>
                    </td>
                    <td style={{ ...TD, fontFamily: 'var(--font-ui)', fontSize: 11 }}>{e.indexName}</td>
                    <td style={{ ...TDM, fontWeight: 500 }}>{e.price.toFixed(3)}</td>
                    <td style={{ ...TDM, color: chg(e.change) }}>{fmtPct(e.change)}</td>
                    <td style={{ ...TDM, color: chg(e.display_premium), fontWeight: 500 }}>{fmtPct(e.display_premium)}</td>
                    <td style={{ ...TDM, fontSize: 11, color: chg(e.nav_return_1y) }}>{fmtPct(e.nav_return_1y)}</td>
                    <td style={{ ...TDM, fontSize: 13, fontWeight: 700 }}>{e.score.toFixed(2)}</td>
                    <td style={TD}><RecIndicator rec={e.recommendation} stars={e.stars} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        );
      })()}
    </div>
  );
}

/* ══════════════════════════════════════════
   Premium Analysis — full detail per index
   ══════════════════════════════════════════ */
function PCPremium({ activeIdx, setActiveIdx }) {
  if (!REPORT.sections.length) return null;
  const [selFund, setSelFund] = useS(null);
  const section = REPORT.sections.find(s => s.index_type === activeIdx) || REPORT.sections[0];

  // 基金详情页（全页面）
  if (selFund) {
    const fc = section.futures_correction;
    const r = fc ? (1 + (fc.ratio_pct || 0) / 100) : 1;
    const estNav = selFund.nav * r;
    const holdings = selFund.holdings || [];
    const metrics = [
      ['净值', selFund.nav.toFixed(3), null],
      ['估算净值', estNav.toFixed(3), chg(fc?.ratio_pct)],
      ['涨幅', fmtPct(selFund.change), chg(selFund.change)],
      ['估算溢价', fmtPct(selFund.display_premium), chg(selFund.display_premium)],
      ['3M超额(均值)', fmtPct(selFund.excess_3m) + ' (' + fmtPct(selFund.avg_3m) + ')', chg(selFund.excess_3m)],
      ['6M超额(均值)', fmtPct(selFund.excess_6m) + ' (' + fmtPct(selFund.avg_6m) + ')', chg(selFund.excess_6m)],
      ['1Y超额(均值)', fmtPct(selFund.excess_1y) + ' (' + fmtPct(selFund.avg_1y) + ')', chg(selFund.excess_1y)],
      ['综合超额', fmtPct(selFund.composite), chg(selFund.composite)],
      ['年净值涨幅', fmtPct(selFund.nav_return_1y), chg(selFund.nav_return_1y)],
      ['年价格涨幅', fmtPct(selFund.price_return_1y), chg(selFund.price_return_1y)],
      ['>7%天数', String(selFund.days_gt7), selFund.days_gt7 > 30 ? '#A8342A' : null],
      ['分值', selFund.score.toFixed(2), null],
    ];
    return (
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '32px 32px 64px' }}>
        <div style={{ marginBottom: 20 }}>
          <a href="#" onClick={e => { e.preventDefault(); setSelFund(null); }} style={{ fontFamily: 'var(--font-ui)', fontSize: 13, color: 'var(--fg-3)', textDecoration: 'none' }}>← 返回溢价分析</a>
        </div>
        <div style={{ display: 'flex', gap: 40 }}>
          {/* 左栏：基本信息 + 指标 */}
          <div style={{ flex: 1, minWidth: 300 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontFamily: 'var(--font-display-cjk)', fontSize: 24, fontWeight: 700 }}>{selFund.name}</span>
                  <PoolBadge pool={selFund.rotation_pool} />
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-muted)', marginTop: 4 }}>{selFund.code} · {section.index_name}</div>
              </div>
              <RecIndicator rec={selFund.recommendation} stars={selFund.stars} />
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 24 }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 36, fontWeight: 500 }}>{selFund.price.toFixed(3)}</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 16, color: chg(selFund.change) }}>{fmtPct(selFund.change)}</span>
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <tbody>
                {metrics.map(([l, v, c]) => (
                  <tr key={l}>
                    <td style={{ padding: '6px 0', borderBottom: '1px solid var(--ink-10)', fontFamily: 'var(--font-ui)', fontSize: 13, color: 'var(--fg-3)', width: '40%' }}>{l}</td>
                    <td style={{ padding: '6px 0', borderBottom: '1px solid var(--ink-10)', fontFamily: 'var(--font-mono)', fontSize: 13, color: c || 'var(--ink)', textAlign: 'right' }}>{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* 右栏：持仓 */}
          {holdings.length > 0 && (
            <div style={{ width: 340 }}>
              <Label>持仓明细 ({holdings.length})</Label>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead><tr>
                  <th style={{ ...TH, textAlign: 'left' }}>代码</th>
                  <th style={TH}>权重</th>
                  <th style={TH}>价格</th>
                  <th style={TH}>涨跌</th>
                </tr></thead>
                <tbody>
                  {holdings.map(h => (
                    <tr key={h.ticker}>
                      <td style={TDL}>
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 500 }}>{h.ticker}</div>
                        <div style={{ fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-muted)' }}>{h.name}</div>
                      </td>
                      <td style={{ ...TDM, fontSize: 12 }}>{h.weight?.toFixed(1)}%</td>
                      <td style={{ ...TDM, fontSize: 12 }}>{h.price?.toFixed(2) || '—'}</td>
                      <td style={{ ...TDM, fontSize: 12, color: chg(h.change_pct) }}>{h.change_pct != null ? fmtPct(h.change_pct) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    );
  }
  const etfs = section.etfs;
  const fc = section.futures_correction;
  const top = etfs[0];

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '32px 32px 64px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontFamily: 'var(--font-ui)', fontSize: 11, color: 'var(--fg-muted)' }}>{REPORT.data_freshness}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-muted)' }}>更新 {REPORT.generated_at}</span>
          <RefreshBtn />
        </div>
      </div>
      <FuturesTicker data={REPORT.futures} />

      <h1 style={{ fontFamily: 'var(--font-display-cjk)', fontWeight: 700, fontSize: 28, margin: '24px 0 4px', letterSpacing: '-0.02em' }}>溢价分析报告</h1>

      {/* Index tabs */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 20, flexWrap: 'wrap' }}>
        {REPORT.sections.map(s => {
          const active = activeIdx === s.index_type;
          return (
            <span key={s.index_type} onClick={() => setActiveIdx(s.index_type)} style={{
              fontFamily: 'var(--font-ui)', fontSize: 12, padding: '5px 14px', borderRadius: 999, cursor: 'pointer',
              border: active ? '1px solid var(--ink)' : '1px solid var(--ink-20)',
              background: active ? 'var(--ink)' : 'transparent',
              color: active ? 'var(--paper)' : 'var(--fg-2)',
              transition: 'all 120ms', whiteSpace: 'nowrap',
            }}>{s.index_name} ({s.etfs.length})</span>
          );
        })}
      </div>

      {/* Section header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontFamily: 'var(--font-ui)', fontSize: 12, color: 'var(--fg-2)' }}>
          推荐持有
          <span style={{ fontFamily: 'var(--font-display-cjk)', fontWeight: 500 }}>{top.name}</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-muted)' }}>({top.code})</span>
          <RecCompact rec={top.recommendation} stars={top.stars} />
        </div>
        {fc && (
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-muted)' }}>
            {section.nav_date && <span>净值 {section.nav_date.slice(5)} · </span>}
            {fc.symbol}: {fc.current_futures_price?.toFixed(0)} / {fc.nav_date_close?.toFixed(0)} = <span style={{ fontWeight: 500, color: chg(fc.ratio_pct) }}>{fmtPct(fc.ratio_pct)}</span>
          </span>
        )}
      </div>

      {/* Full data table */}
      <div style={{ overflowX: 'auto', marginTop: 12 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ ...TH, textAlign: 'left' }}>代码</th>
              <th style={TH}>价格</th>
              <th style={TH}>净值</th>
              <th style={TH}>估算净值</th>
              <th style={TH}>涨幅</th>
              <th style={TH}>估算溢价</th>
              <th style={TH}>3M超额(均值)</th>
              <th style={TH}>6M超额(均值)</th>
              <th style={TH}>1Y超额(均值)</th>
              <th style={TH}>年净值涨幅</th>
              <th style={TH}>年价格涨幅</th>
              <th style={TH}>{'>'}7%天</th>
              <th style={TH}>分值</th>
              <th style={TH}>推荐</th>
            </tr>
          </thead>
          <tbody>
            {etfs.map(e => {
              const isTop = e.stars >= 4;
              const isSell = e.stars < 0;
              const rowBg = isTop ? 'rgba(168,52,42,0.04)' : isSell ? 'rgba(42,107,79,0.04)' : 'transparent';
              return (
                <tr key={e.code} style={{ background: rowBg }}
                  onMouseEnter={ev => ev.currentTarget.style.background = 'var(--ink-05)'}
                  onMouseLeave={ev => ev.currentTarget.style.background = rowBg}>
                  <td style={TDL} onClick={() => setSelFund(e)}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
                      <span style={{ fontFamily: 'var(--font-display-cjk)', fontSize: 12, fontWeight: 500, borderBottom: '1px dashed var(--ink-20)' }}>{e.name}</span>
                      <PoolBadge pool={e.rotation_pool} />
                    </div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-muted)' }}>{e.code}</div>
                  </td>
                  <td style={{ ...TDM, fontWeight: 500 }}>{e.price.toFixed(3)}</td>
                  <td style={{ ...TDM, color: 'var(--fg-3)' }}>{e.nav.toFixed(3)}</td>
                  <td style={TDM}>
                    {(() => { const r = fc ? (1 + fc.ratio_pct / 100) : 1; const est = e.nav * r; return <span style={{ fontWeight: 500 }}>{est.toFixed(3)}</span>; })()}
                  </td>
                  <td style={{ ...TDM, color: chg(e.change) }}>{fmtPct(e.change)}</td>
                  <td style={{ ...TDM, color: chg(e.display_premium), fontWeight: 500 }}>{fmtPct(e.display_premium)}</td>
                  <td style={TDM}>
                    <span style={{ color: chg(e.excess_3m) }}>{fmtPct(e.excess_3m)}</span>
                    <span style={{ color: 'var(--fg-muted)', fontSize: 10 }}>({fmtPct(e.avg_3m)})</span>
                  </td>
                  <td style={TDM}>
                    <span style={{ color: chg(e.excess_6m) }}>{fmtPct(e.excess_6m)}</span>
                    <span style={{ color: 'var(--fg-muted)', fontSize: 10 }}>({fmtPct(e.avg_6m)})</span>
                  </td>
                  <td style={TDM}>
                    <span style={{ color: chg(e.excess_1y) }}>{fmtPct(e.excess_1y)}</span>
                    <span style={{ color: 'var(--fg-muted)', fontSize: 10 }}>({fmtPct(e.avg_1y)})</span>
                  </td>
                  <td style={{ ...TDM, fontSize: 11, color: chg(e.nav_return_1y) }}>{fmtPct(e.nav_return_1y)}</td>
                  <td style={{ ...TDM, fontSize: 11, color: chg(e.price_return_1y) }}>{fmtPct(e.price_return_1y)}</td>
                  <td style={{ ...TDM, fontSize: 11, color: e.days_gt7 > 30 ? '#A8342A' : 'var(--fg-3)' }}>{e.days_gt7}</td>
                  <td style={{ ...TDM, fontSize: 13, fontWeight: 700 }}>{e.score.toFixed(2)}</td>
                  <td style={TD}><RecIndicator rec={e.recommendation} stars={e.stars} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div style={{ fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-muted)', marginTop: 16, lineHeight: 1.6 }}>
        分值综合考虑当前溢价与历史均值的偏离、实时溢价高低和近一年净值涨幅。溢价越低于历史均值、净值涨幅越大的ETF，分值越高，越值得关注。
      </div>
    </div>
  );
}

window.PCNav = PCNav;
window.PCOverview = PCOverview;
window.PCPremium = PCPremium;
