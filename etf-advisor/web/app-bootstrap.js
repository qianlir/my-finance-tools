// === App + Router ===
// 此文件包含路由解析、App 根组件、ReactDOM 启动代码
// 不是 JSX，不需要编译，直接追加到 app.js 末尾
// 依赖: PCNav, PCOverview, PCPremium, PCRotation (pc.jsx)
//       MobOverview, MobPremium, MobRotation, MobTabs (mobile.jsx)

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
