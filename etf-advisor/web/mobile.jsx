// Mobile layout — tab-based: Overview + Premium Analysis
const { useState: useSM } = React;

/* ── Mobile Tab Bar ── */
function MobTabs({ tab, setTab }) {
  const ts = [
    { k: 'overview', l: '总览', d: 'M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z M9 22V12h6v10' },
    { k: 'premium', l: '溢价分析', d: 'M18 20V10 M12 20V4 M6 20v-6' },
    { k: 'rotation', l: '纳指轮动', d: 'M17 1l4 4-4 4 M3 11V9a4 4 0 014-4h14 M7 23l-4-4 4-4 M21 13v2a4 4 0 01-4 4H3' },
  ];
  return (
    <div style={{
      position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 30,
      background: 'var(--paper)', borderTop: '1px solid var(--ink-10)',
      display: 'flex', justifyContent: 'space-around', padding: '6px 0 2px', height: 50,
    }}>
      {ts.map(t => {
        const a = tab === t.k;
        return (
          <div key={t.k} onClick={() => setTab(t.k)} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1, cursor: 'pointer', padding: '4px 16px' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={a ? 'var(--ink)' : 'var(--fg-muted)'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              {t.d.split(' M').map((seg, i) => <path key={i} d={i === 0 ? seg : 'M' + seg} />)}
            </svg>
            <span style={{ fontFamily: 'var(--font-ui)', fontSize: 9, color: a ? 'var(--ink)' : 'var(--fg-muted)', fontWeight: a ? 600 : 400 }}>{t.l}</span>
          </div>
        );
      })}
    </div>
  );
}

/* ── Mobile Overview ── */
function MobOverview({ setTab, setIdx }) {
  if (!REPORT.sections.length) return null;
  const topPicks = REPORT.sections.map(s => ({ s, e: s.etfs[0] }));

  return (
    <div style={{ padding: '12px 16px 68px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0 4px' }}>
        <span style={{ fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-muted)' }}>{REPORT.data_freshness}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-muted)' }}>{REPORT.generated_at?.slice(11)}</span>
          <RefreshBtn compact />
        </div>
      </div>
      <FuturesTicker data={REPORT.futures} compact />

      {/* Top picks */}
      <Label>各指数推荐</Label>
      <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4, marginBottom: 24 }}>
        {topPicks.map(({ s, e }) => (
          <div key={s.index_type} onClick={() => { setIdx(s.index_type); setTab('premium'); }}
            style={{ flexShrink: 0, width: 140, padding: '12px', border: '1px solid var(--ink-10)', borderRadius: 2, cursor: 'pointer' }}>
            <div style={{ fontFamily: 'var(--font-ui)', fontSize: 9, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{s.index_name}</div>
            <div style={{ fontFamily: 'var(--font-display-cjk)', fontSize: 12, fontWeight: 500, marginTop: 4, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{e.name}</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 15, marginTop: 6 }}>{e.price.toFixed(3)}</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: chg(e.change), marginTop: 1 }}>{fmtPct(e.change)}</div>
            <div style={{ fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-3)', marginTop: 4 }}>
              溢价 <span style={{ fontFamily: 'var(--font-mono)', color: chg(e.display_premium) }}>{fmtPct(e.display_premium)}</span>
            </div>
            <div style={{ marginTop: 6 }}>
              <RecCompact rec={e.recommendation} stars={e.stars} />
            </div>
          </div>
        ))}
      </div>

      {/* All ETFs ranked */}
      <Label right={<span onClick={() => setTab('premium')} style={{ cursor: 'pointer' }}>详细 →</span>}>全部 ETF 排行</Label>
      {(() => {
        const allETFs = REPORT.sections.flatMap(s => s.etfs.map(e => ({ ...e, indexName: s.index_name })));
        allETFs.sort((a, b) => b.score - a.score);
        return allETFs.slice(0, 12).map((e, i) => (
          <div key={e.code} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0', borderTop: '1px solid var(--ink-10)' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-muted)', width: 16, textAlign: 'center', flexShrink: 0 }}>{i + 1}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontFamily: 'var(--font-display-cjk)', fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{e.name}</span>
                <PoolBadge pool={e.rotation_pool} />
                <RecCompact rec={e.recommendation} stars={e.stars} />
              </div>
              <div style={{ fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-muted)' }}>{e.code} · {e.indexName}</div>
            </div>
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 500 }}>{e.score.toFixed(2)}</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: chg(e.display_premium) }}>溢价 {fmtPct(e.display_premium)}</div>
            </div>
          </div>
        ));
      })()}
      <div style={{ borderTop: '1px solid var(--ink-10)' }}></div>
    </div>
  );
}

/* ── Mobile Premium Analysis ── */
function MobPremium({ activeIdx, setActiveIdx }) {
  if (!REPORT.sections.length) return null;
  const section = REPORT.sections.find(s => s.index_type === activeIdx) || REPORT.sections[0];
  const etfs = section.etfs;
  const fc = section.futures_correction;
  const [expanded, setExpanded] = useSM(null);

  return (
    <div style={{ padding: '12px 16px 68px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0 6px' }}>
        <span style={{ fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-muted)' }}>{REPORT.data_freshness}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-muted)' }}>{REPORT.generated_at?.slice(11)}</span>
          <RefreshBtn compact />
        </div>
      </div>
      {/* Index tabs */}
      <div style={{ display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 8, marginBottom: 4 }}>
        {REPORT.sections.map(s => {
          const active = activeIdx === s.index_type;
          return (
            <span key={s.index_type} onClick={() => { setActiveIdx(s.index_type); setExpanded(null); }} style={{
              fontFamily: 'var(--font-ui)', fontSize: 11, padding: '3px 10px', borderRadius: 999, cursor: 'pointer',
              border: active ? '1px solid var(--ink)' : '1px solid var(--ink-20)',
              background: active ? 'var(--ink)' : 'transparent',
              color: active ? 'var(--paper)' : 'var(--fg-2)',
              whiteSpace: 'nowrap',
            }}>{s.index_name}</span>
          );
        })}
      </div>

      {fc && (
        <div style={{ fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-muted)', marginBottom: 12, padding: '6px 10px', background: 'var(--ink-05)', borderRadius: 2 }}>
          {section.nav_date && <span>净值 {section.nav_date.slice(5)} · </span>}
          {fc.symbol} {fc.current_futures_price?.toFixed(0)} / {fc.nav_date_close?.toFixed(0)} = {fmtPct(fc.ratio_pct)}
        </div>
      )}

      {/* ETF cards */}
      {etfs.map((e, i) => {
        const isExp = expanded === e.code;
        const isTop = e.stars >= 4;
        const r = fc ? (1 + fc.ratio_pct / 100) : 1;
        const estNav = e.nav * r;
        return (
          <div key={e.code} onClick={() => setExpanded(isExp ? null : e.code)}
            style={{
              padding: '12px 0', borderTop: '1px solid var(--ink-10)', cursor: 'pointer',
              background: isTop ? 'rgba(168,52,42,0.03)' : 'transparent',
            }}>
            {/* Header row */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontFamily: 'var(--font-display-cjk)', fontSize: 14, fontWeight: 500 }}>{e.name}</span>
                  <PoolBadge pool={e.rotation_pool} />
                  <RecCompact rec={e.recommendation} stars={e.stars} />
                </div>
                <div style={{ fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-muted)', marginTop: 1 }}>{e.code}</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 15 }}>{e.price.toFixed(3)}</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: chg(e.change) }}>{fmtPct(e.change)}</div>
              </div>
            </div>

            {/* Quick stats */}
            <div style={{ display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap' }}>
              <div style={{ fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-3)' }}>
                净值 <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{e.nav.toFixed(3)}</span>
              </div>
              <div style={{ fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-3)' }}>
                估算净值 <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 500 }}>{estNav.toFixed(3)}</span>
              </div>
              <div style={{ fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-3)' }}>
                溢价 <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: chg(e.display_premium) }}>{fmtPct(e.display_premium)}</span>
              </div>
              <div style={{ fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-3)' }}>
                分值 <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600 }}>{e.score.toFixed(2)}</span>
              </div>
            </div>

            {/* Expanded detail */}
            {isExp && (
              <div style={{ marginTop: 12, padding: '12px', background: 'var(--ink-05)', borderRadius: 2 }}>
                {[
                  ['净值', e.nav.toFixed(3), null],
                  ['估算净值', estNav.toFixed(3) + ' (' + fmtPct(fc?.ratio_pct) + ')', chg(fc?.ratio_pct)],
                  ['估算溢价', fmtPct(e.display_premium), chg(e.display_premium)],
                  ['3M超额(均值)', fmtPct(e.excess_3m) + ' (' + fmtPct(e.avg_3m) + ')', chg(e.excess_3m)],
                  ['6M超额(均值)', fmtPct(e.excess_6m) + ' (' + fmtPct(e.avg_6m) + ')', chg(e.excess_6m)],
                  ['1Y超额(均值)', fmtPct(e.excess_1y) + ' (' + fmtPct(e.avg_1y) + ')', chg(e.excess_1y)],
                  ['年净值涨幅', fmtPct(e.nav_return_1y), chg(e.nav_return_1y)],
                  ['年价格涨幅', fmtPct(e.price_return_1y), chg(e.price_return_1y)],
                  ['>7%天数', String(e.days_gt7), e.days_gt7 > 30 ? '#A8342A' : null],
                ].map(([l, v, c]) => (
                  <div key={l} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid var(--ink-10)' }}>
                    <span style={{ fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-3)' }}>{l}</span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: c || 'var(--ink)' }}>{v}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
      <div style={{ borderTop: '1px solid var(--ink-10)' }}></div>
      <div style={{ fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-muted)', marginTop: 12, lineHeight: 1.5 }}>
        点击展开详情
      </div>
    </div>
  );
}

window.MobTabs = MobTabs;
window.MobOverview = MobOverview;
window.MobPremium = MobPremium;
