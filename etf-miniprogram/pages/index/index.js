// pages/index/index.js
Page({
  data: {
    loading: true,
    // 期货数据
    nqChange: 0,
    esChange: 0,
    nqPrice: 0,
    esPrice: 0,
    // 回测摘要
    strategyAReturn: 0,
    strategyBReturn: 0,
    maxDrawdown: 0,
    // 持仓状态
    hasHoldings: false,
    holdingsCount: 0,
    // 更新时间
    lastUpdate: ''
  },

  onShow() {
    this.loadAllData();
  },

  onPullDownRefresh() {
    this.loadAllData();
    setTimeout(() => {
      wx.stopPullDownRefresh();
    }, 1000);
  },

  loadAllData() {
    this.setData({ loading: true });
    Promise.all([
      this.loadReportSummary(),
      this.loadBacktestSummary(),
      this.checkHoldings()
    ]).finally(() => {
      this.setData({ loading: false });
    });
  },

  loadReportSummary() {
    return new Promise(resolve => {
      wx.request({
        url: getApp().apiBase + '/report.json?t=' + Date.now(),
        success: (res) => {
          const futures = res.data.futures || [];
          if (futures.length > 0) {
            const f = futures[futures.length - 1];
            this.setData({
              nqChange: f.nq_change || 0,
              esChange: f.es_change || 0,
              nqPrice: f.nq_price || 0,
              esPrice: f.es_price || 0,
              lastUpdate: res.data.generated_at || ''
            });
          }
          resolve();
        },
        fail: () => resolve()
      });
    });
  },

  loadBacktestSummary() {
    return new Promise(resolve => {
      wx.request({
        url: getApp().apiBase + '/backtest.json?t=' + Date.now(),
        success: (res) => {
          const sections = res.data.sections || [];
          let strategyA = 0, strategyB = 0, maxDD = 0;
          sections.forEach(s => {
            s.strategies.forEach(st => {
              if (st.name === 'STRATEGY_A') {
                strategyA = st.return_pct;
                maxDD = st.max_drawdown;
              }
              if (st.name === 'STRATEGY_B') strategyB = st.return_pct;
            });
          });
          this.setData({
            strategyAReturn: strategyA,
            strategyBReturn: strategyB,
            maxDrawdown: maxDD
          });
          resolve();
        },
        fail: () => resolve()
      });
    });
  },

  // 刷新数据
  onRefresh() {
    this.loadAllData();
  },

  checkHoldings() {
    const cookie = wx.getStorageSync('tzzb_cookie');
    this.setData({
      hasHoldings: !!cookie,
      holdingsCount: cookie ? 3 : 0  // TODO: 从后端获取实际数量
    });
  },

  // 导航方法
  goToReport() {
    wx.switchTab({ url: '/pages/report/report' });
  },

  goToBacktest() {
    wx.switchTab({ url: '/pages/backtest/backtest' });
  },

  goToHoldings() {
    wx.switchTab({ url: '/pages/holdings/holdings' });
  }
});
