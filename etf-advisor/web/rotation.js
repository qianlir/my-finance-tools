// Rotation Index components — PC + Mobile
// Depends on: React, Chart.js, window.ROTATION

var _rotChartInstance = null;

function _rotFmtMoney(v) {
  if (v == null) return '—';
  return '¥' + Math.round(v).toLocaleString();
}
function _rotFmtPct(v) {
  if (v == null) return '—';
  return (v > 0 ? '+' : '') + v.toFixed(2) + '%';
}
function _rotFmtScore(v) {
  if (v == null) return '—';
  return v.toFixed(2);
}
function _rotEtfShort(name) {
  return (name || '').replace(/ETF$/, '').replace(/纳指/, '');
}

function _rotRenderChart(canvasId, data) {
  if (!data || !data.daily) return;
  if (_rotChartInstance) { _rotChartInstance.destroy(); _rotChartInstance = null; }
  var el = document.getElementById(canvasId);
  if (!el) return;
  var ctx = el.getContext('2d');
  var d = data.daily;
  _rotChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: d.dates.map(function(s) { return s.slice(5); }),
      datasets: [
        {
          label: '轮动策略',
          data: d.rotation_values,
          borderColor: '#a8342a',
          backgroundColor: 'rgba(168,52,42,0.06)',
          borderWidth: 2.5,
          fill: true,
          pointRadius: 0,
          pointHitRadius: 8,
          tension: 0.1,
        },
        {
          label: '等权持有',
          data: d.equal_weight_values,
          borderColor: '#8b6914',
          borderWidth: 1.5,
          borderDash: [6, 3],
          fill: false,
          pointRadius: 0,
          pointHitRadius: 8,
          tension: 0.1,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(26,22,19,0.92)',
          titleFont: { size: 12 },
          bodyFont: { size: 12 },
          padding: 10,
          callbacks: {
            title: function(items) {
              var idx = items[0].dataIndex;
              var h = d.holdings[idx];
              return d.dates[idx] + ' · ' + (data.pool_names[h] || h);
            },
            label: function(item) {
              var val = item.raw;
              var ret = ((val / data.initial_value - 1) * 100).toFixed(2);
              var prefix = item.datasetIndex === 0 ? '轮动' : '等权';
              return prefix + ': ¥' + Math.round(val).toLocaleString() + ' (' + (ret > 0 ? '+' : '') + ret + '%)';
            },
            afterBody: function(items) {
              var idx = items[0].dataIndex;
              var lead = d.rotation_values[idx] - d.equal_weight_values[idx];
              return '领先: ' + (lead > 0 ? '+' : '') + '¥' + Math.round(lead).toLocaleString();
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { maxTicksLimit: 10, font: { size: 11 }, color: '#999' },
          grid: { display: false }
        },
        y: {
          ticks: {
            font: { size: 11 }, color: '#999',
            callback: function(v) { return '¥' + (v / 1000).toFixed(0) + 'k'; }
          },
          grid: { color: 'rgba(0,0,0,0.04)' }
        }
      }
    }
  });
}

/* ── PC Rotation ── */
function PCRotation() {
  var data = window.ROTATION;
  var ce = React.createElement;

  React.useEffect(function() {
    if (data) setTimeout(function() { _rotRenderChart('rot-chart-pc', data); }, 50);
    return function() { if (_rotChartInstance) { _rotChartInstance.destroy(); _rotChartInstance = null; } };
  }, [data]);

  if (!data) return ce('div', { style: { padding: 60, textAlign: 'center', color: 'var(--fg-muted)', fontFamily: 'var(--font-ui)', fontSize: 14 } }, '轮动指数数据加载中...');

  var s = data.summary;
  var pool = data.pool || [];
  var poolSet = {};
  pool.forEach(function(c) { poolSet[c] = true; });

  function etfLabel(code) {
    if (!code) return '—';
    var n = (data.pool_names || {})[code] || code;
    return _rotEtfShort(n) + ' ' + code;
  }

  // Metric card helper
  function mc(label, value, cls) {
    return ce('div', { style: { background: 'var(--bg-3)', borderRadius: 2, padding: '14px 16px' } },
      ce('div', { style: { fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 } }, label),
      ce('div', { style: { fontFamily: 'var(--font-mono)', fontSize: 22, fontWeight: 600, color: cls === 'red' ? '#A8342A' : cls === 'green' ? '#2A6B4F' : 'var(--fg-1)' } }, value)
    );
  }

  // Trade table rows
  var tradeRows = data.trades.map(function(t) {
    var isInit = t.action === '建仓';
    var leadColor = (t.lead || 0) > 0 ? '#2A6B4F' : (t.lead || 0) < 0 ? '#A8342A' : 'var(--fg-3)';
    return ce('tr', { key: t.seq, style: { background: isInit ? 'var(--ink-05)' : 'transparent' } },
      ce('td', { style: { textAlign: 'center', color: 'var(--fg-muted)' } }, t.seq),
      ce('td', { style: { fontFamily: 'var(--font-mono)', fontSize: 12 } }, t.date),
      ce('td', null, t.action),
      ce('td', { style: { color: '#A8342A' } }, t.sell_name ? etfLabel(t.sell_code) : '—'),
      ce('td', { style: { fontFamily: 'var(--font-mono)' } }, _rotFmtScore(t.sell_score)),
      ce('td', { style: { color: '#2A6B4F' } }, etfLabel(t.buy_code)),
      ce('td', { style: { fontFamily: 'var(--font-mono)' } }, _rotFmtScore(t.buy_score)),
      ce('td', { style: { fontFamily: 'var(--font-mono)', color: (t.score_diff || 0) > 0 ? '#2A6B4F' : 'var(--fg-3)' } },
        t.score_diff != null ? (t.score_diff > 0 ? '+' : '') + t.score_diff.toFixed(2) : '—'),
      ce('td', { style: { fontFamily: 'var(--font-mono)' } }, _rotFmtMoney(t.rotation_value)),
      ce('td', { style: { fontFamily: 'var(--font-mono)' } }, _rotFmtMoney(t.equal_weight_value)),
      ce('td', { style: { fontFamily: 'var(--font-mono)', color: leadColor } },
        t.lead != null ? (t.lead > 0 ? '+' : '') + _rotFmtMoney(t.lead) : '—')
    );
  });

  var thStyle = { fontFamily: 'var(--font-ui)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--fg-muted)', padding: '10px 8px', textAlign: 'right', borderBottom: '1px solid var(--ink-20)', whiteSpace: 'nowrap' };
  var thL = Object.assign({}, thStyle, { textAlign: 'left' });
  var thC = Object.assign({}, thStyle, { textAlign: 'center' });
  var tdBase = { padding: '9px 8px', textAlign: 'right', borderBottom: '1px solid var(--ink-05)', fontSize: 13 };

  return ce('div', { style: { maxWidth: 1200, margin: '0 auto', padding: '24px 32px 48px' } },
    // Subtitle
    ce('div', { style: { fontFamily: 'var(--font-ui)', fontSize: 11, color: 'var(--fg-muted)', marginBottom: 20 } },
      data.start_date + ' ~ ' + data.end_date + ' · ' + data.trading_days + '交易日 · 当前持有: ' + s.current_holding_name + ' · T=' + data.threshold
    ),

    // Metrics grid
    ce('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 10, marginBottom: 24 } },
      mc('轮动市值', _rotFmtMoney(s.rotation_value), 'red'),
      mc('轮动收益', _rotFmtPct(s.rotation_return), 'red'),
      mc('等权市值', _rotFmtMoney(s.equal_weight_value)),
      mc('等权收益 (' + data.equal_weight_etfs + '只)', _rotFmtPct(s.equal_weight_return)),
      mc('Alpha', _rotFmtPct(s.alpha), 'green'),
      mc('切换次数', String(s.trade_count))
    ),

    // Chart
    ce('div', { style: { background: 'var(--bg-3)', borderRadius: 2, padding: '20px', marginBottom: 24, position: 'relative' } },
      ce('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 } },
        ce('span', { style: { fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' } }, '市值走势'),
        ce('div', { style: { display: 'flex', gap: 16, fontSize: 11, fontFamily: 'var(--font-ui)', color: 'var(--fg-muted)' } },
          ce('span', { style: { display: 'flex', alignItems: 'center', gap: 4 } },
            ce('span', { style: { display: 'inline-block', width: 16, height: 2.5, background: '#a8342a', borderRadius: 1 } }),
            '轮动策略'
          ),
          ce('span', { style: { display: 'flex', alignItems: 'center', gap: 4 } },
            ce('span', { style: { display: 'inline-block', width: 16, height: 0, borderTop: '2px dashed #8b6914' } }),
            '等权持有'
          )
        )
      ),
      ce('div', { style: { height: 360 } }, ce('canvas', { id: 'rot-chart-pc' }))
    ),

    // Trade table
    ce('div', { style: { fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 } }, '换仓记录'),
    ce('table', { style: { width: '100%', borderCollapse: 'collapse', fontSize: 13, fontFamily: 'var(--font-body)' } },
      ce('thead', null,
        ce('tr', null,
          ce('th', thC, '#'),
          ce('th', thL, '日期'),
          ce('th', thL, '操作'),
          ce('th', thL, '卖出'),
          ce('th', thStyle, '卖出分值'),
          ce('th', thL, '买入'),
          ce('th', thStyle, '买入分值'),
          ce('th', thStyle, '分差'),
          ce('th', thStyle, '策略市值'),
          ce('th', thStyle, '等权市值'),
          ce('th', thStyle, '领先')
        )
      ),
      ce('tbody', null, tradeRows)
    ),

    // Note
    ce('div', { style: { fontFamily: 'var(--font-ui)', fontSize: 11, color: 'var(--fg-muted)', marginTop: 20, lineHeight: 1.8 } },
      '分值差 ≥ ' + data.threshold + ' 时切换 · 推荐池: ' + pool.map(function(c) { return (data.pool_names[c] || c); }).join(' / ') +
      ' · 等权: ' + data.equal_weight_etfs + '只纳指ETF各投¥' + Math.round(data.initial_value / data.equal_weight_etfs) + '持有不动 · ' + data.generated_at
    )
  );
}

/* ── Mobile Rotation ── */
function MobRotation() {
  var data = window.ROTATION;
  var ce = React.createElement;

  React.useEffect(function() {
    if (data) setTimeout(function() { _rotRenderChart('rot-chart-mob', data); }, 50);
    return function() { if (_rotChartInstance) { _rotChartInstance.destroy(); _rotChartInstance = null; } };
  }, [data]);

  if (!data) return ce('div', { style: { padding: 60, textAlign: 'center', color: 'var(--fg-muted)', fontFamily: 'var(--font-ui)', fontSize: 13 } }, '加载中...');

  var s = data.summary;
  var poolNames = data.pool_names || {};

  function mc(label, value, cls) {
    return ce('div', { style: { background: 'var(--ink-05)', borderRadius: 2, padding: '10px 12px' } },
      ce('div', { style: { fontFamily: 'var(--font-ui)', fontSize: 9, color: 'var(--fg-muted)', letterSpacing: '0.06em', marginBottom: 2 } }, label),
      ce('div', { style: { fontFamily: 'var(--font-mono)', fontSize: 17, fontWeight: 600, color: cls === 'red' ? '#A8342A' : cls === 'green' ? '#2A6B4F' : 'var(--fg-1)' } }, value)
    );
  }

  // Trade cards for mobile
  var tradeCards = data.trades.map(function(t) {
    var isInit = t.action === '建仓';
    var leadColor = (t.lead || 0) > 0 ? '#2A6B4F' : (t.lead || 0) < 0 ? '#A8342A' : 'var(--fg-3)';
    var buyShort = _rotEtfShort(t.buy_name);
    var sellShort = t.sell_name ? _rotEtfShort(t.sell_name) : null;

    return ce('div', { key: t.seq, style: { padding: '10px 0', borderTop: '1px solid var(--ink-10)' } },
      // Row 1: date + action + lead
      ce('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 } },
        ce('div', { style: { display: 'flex', alignItems: 'center', gap: 6 } },
          ce('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-muted)' } }, t.date.slice(5)),
          ce('span', { style: { fontFamily: 'var(--font-ui)', fontSize: 11, fontWeight: 500, color: isInit ? '#A8342A' : 'var(--fg-2)' } }, t.action)
        ),
        ce('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 12, color: leadColor } },
          t.lead != null && t.lead !== 0 ? (t.lead > 0 ? '+' : '') + _rotFmtMoney(t.lead) : ''
        )
      ),
      // Row 2: sell → buy with codes and scores
      ce('div', { style: { display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, flexWrap: 'wrap' } },
        sellShort
          ? ce(React.Fragment, null,
              ce('span', { style: { color: '#A8342A' } }, sellShort),
              ce('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-muted)' } }, t.sell_code),
              ce('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-muted)' } }, _rotFmtScore(t.sell_score)),
              ce('span', { style: { color: 'var(--fg-muted)', margin: '0 2px' } }, '→')
            )
          : null,
        ce('span', { style: { fontWeight: 500, color: '#2A6B4F' } }, buyShort),
        ce('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-muted)' } }, t.buy_code),
        ce('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-muted)' } }, _rotFmtScore(t.buy_score)),
        t.score_diff != null
          ? ce('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 10, color: '#2A6B4F', marginLeft: 4 } }, '△' + t.score_diff.toFixed(1))
          : null
      ),
      // Row 3: portfolio values
      ce('div', { style: { display: 'flex', gap: 12, marginTop: 3, fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-muted)' } },
        ce('span', null, '轮动 ' + _rotFmtMoney(t.rotation_value)),
        ce('span', null, '等权 ' + _rotFmtMoney(t.equal_weight_value))
      )
    );
  });

  return ce('div', { style: { padding: '12px 16px 68px' } },
    // Info line
    ce('div', { style: { fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-muted)', marginBottom: 10 } },
      '持有: ' + s.current_holding_name + ' · T=' + data.threshold + ' · ' + data.generated_at
    ),

    // Metrics 2×3
    ce('div', { style: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 } },
      mc('轮动市值', _rotFmtMoney(s.rotation_value), 'red'),
      mc('轮动收益', _rotFmtPct(s.rotation_return), 'red'),
      mc('等权市值', _rotFmtMoney(s.equal_weight_value)),
      mc('等权收益', _rotFmtPct(s.equal_weight_return)),
      mc('Alpha', _rotFmtPct(s.alpha), 'green'),
      mc('切换次数', String(s.trade_count))
    ),

    // Chart
    ce('div', { style: { background: 'var(--ink-05)', borderRadius: 2, padding: '12px', marginBottom: 16 } },
      ce('div', { style: { display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-muted)' } },
        ce('span', null, '市值走势'),
        ce('div', { style: { display: 'flex', gap: 10 } },
          ce('span', { style: { display: 'flex', alignItems: 'center', gap: 3 } },
            ce('span', { style: { display: 'inline-block', width: 12, height: 2, background: '#a8342a', borderRadius: 1 } }), '轮动'),
          ce('span', { style: { display: 'flex', alignItems: 'center', gap: 3 } },
            ce('span', { style: { display: 'inline-block', width: 12, height: 0, borderTop: '1.5px dashed #8b6914' } }), '等权')
        )
      ),
      ce('div', { style: { height: 220 } }, ce('canvas', { id: 'rot-chart-mob' }))
    ),

    // Trade cards
    ce('div', { style: { fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-muted)', letterSpacing: '0.06em', marginBottom: 6 } }, '换仓记录 (' + s.trade_count + ')'),
    ce('div', null, tradeCards),

    // Note
    ce('div', { style: { fontFamily: 'var(--font-ui)', fontSize: 10, color: 'var(--fg-muted)', marginTop: 12, lineHeight: 1.6 } },
      '分值差 ≥ ' + data.threshold + ' 时切换 · 等权: ' + data.equal_weight_etfs + '只各投¥' + Math.round(data.initial_value / data.equal_weight_etfs)
    )
  );
}

window.PCRotation = PCRotation;
window.MobRotation = MobRotation;

