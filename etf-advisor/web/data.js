// Dynamic data loader — fetches report.json + multi-index rotation JSONs from server
// Falls back to empty data if fetch fails

window.REPORT = {
  date: "", generated_at: "", data_freshness: "加载中...",
  futures: [], sections: []
};
window.ROTATION = null;                  // 当前选中的指数数据
window.ROTATION_ALL = {};                // {NASDAQ: data, SP500: data, ...}
window.ROTATION_CURRENT_INDEX = 'NASDAQ'; // 默认显示
window.HOLDINGS = [];
window.DATA_LOADED = false;

window.switchRotationIndex = function(indexType) {
  if (window.ROTATION_ALL[indexType]) {
    window.ROTATION_CURRENT_INDEX = indexType;
    window.ROTATION = window.ROTATION_ALL[indexType];
    if (window.__rerender) window.__rerender();
  }
};

function getDeviceId() {
  var id = localStorage.getItem('device_id');
  if (!id) {
    id = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      var r = Math.random() * 16 | 0;
      return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
    localStorage.setItem('device_id', id);
  }
  return id;
}

(async function loadData() {
  try {
    const headers = { 'X-Device-Id': getDeviceId() };
    const indices = ['nasdaq', 'sp500', 'nikkei', 'dax'];
    const [reportResp, ...rotationResps] = await Promise.all([
      fetch('/data/report.json?t=' + Date.now(), { headers }),
      ...indices.map(idx => fetch('/data/rotation_' + idx + '.json?t=' + Date.now(), { headers })),
    ]);
    if (reportResp.ok) {
      window.REPORT = await reportResp.json();
      window.DATA_LOADED = true;
    }
    for (let i = 0; i < indices.length; i++) {
      const resp = rotationResps[i];
      if (resp.ok) {
        const data = await resp.json();
        const key = (data.index_type || indices[i].toUpperCase());
        window.ROTATION_ALL[key] = data;
      }
    }
    // 默认显示 NASDAQ
    if (window.ROTATION_ALL['NASDAQ']) {
      window.ROTATION = window.ROTATION_ALL['NASDAQ'];
    } else {
      const firstKey = Object.keys(window.ROTATION_ALL)[0];
      if (firstKey) {
        window.ROTATION_CURRENT_INDEX = firstKey;
        window.ROTATION = window.ROTATION_ALL[firstKey];
      }
    }
    if (window.__rerender) window.__rerender();
  } catch (e) {
    console.warn('Failed to load data:', e);
  }
})();
