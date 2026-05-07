// pages/backtest/backtest.js
Page({
  data: {
    startDate: '2025-01-01',
    indexType: 'ALL',
    indexOptions: ['ALL', 'NASDAQ', 'SP500'],
    indexNames: {'ALL': '全部', 'NASDAQ': '纳指', 'SP500': '标普'},
    loading: false,
    backtestData: null
  },

  onShow() {
    this.loadDefaultBacktest();
  },

  onStartDateChange(e) {
    this.setData({ startDate: e.detail.value });
  },

  onIndexChange(e) {
    const idx = parseInt(e.detail.value);
    this.setData({ indexType: this.data.indexOptions[idx] });
  },

  startBacktest() {
    this.loadBacktest(this.data.startDate, this.data.indexType);
  },

  loadDefaultBacktest() {
    this.loadBacktest('2025-01-01', 'ALL');
  },

  loadBacktest(start, index) {
    this.setData({ loading: true });
    const url = `${getApp().apiBase}/backtest.json?start=${start}&index=${index}&t=${Date.now()}`;

    wx.request({
      url,
      success: (res) => {
        this.setData({ backtestData: res.data });
      },
      fail: (err) => {
        wx.showToast({ title: '加载失败', icon: 'none' });
        console.error(err);
      },
      complete: () => {
        this.setData({ loading: false });
      }
    });
  },

  formatPercent(v) {
    if (v == null) return 'N/A';
    return (v > 0 ? '+' : '') + v.toFixed(2) + '%';
  }
});
