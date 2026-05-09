// Dynamic data loader — fetches report.json + rotation_index.json from server
// Falls back to empty data if fetch fails

window.REPORT = {
  date: "", generated_at: "", data_freshness: "加载中...",
  futures: [], sections: []
};
window.ROTATION = null;
window.HOLDINGS = [];
window.DATA_LOADED = false;

(async function loadData() {
  try {
    const [reportResp, rotationResp] = await Promise.all([
      fetch('/data/report.json?t=' + Date.now()),
      fetch('/data/rotation_index.json?t=' + Date.now()),
    ]);
    if (reportResp.ok) {
      window.REPORT = await reportResp.json();
      window.DATA_LOADED = true;
    }
    if (rotationResp.ok) {
      window.ROTATION = await rotationResp.json();
    }
    if (window.__rerender) window.__rerender();
  } catch (e) {
    console.warn('Failed to load data:', e);
  }
})();
