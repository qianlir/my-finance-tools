// pages/holdings/holdings.js
Page({
  data: {
    isLoggedIn: false,
    holdings: [],
    loading: false
  },

  onShow() {
    this.checkCookie();
  },

  checkCookie() {
    const cookie = wx.getStorageSync('tzzb_cookie');
    if (cookie) {
      this.setData({ isLoggedIn: true });
      this.fetchHoldings();
    } else {
      this.setData({ isLoggedIn: false });
    }
  },

  goToSettings() {
    wx.navigateTo({ url: '/pages/settings/settings' });
  },

  refresh() {
    this.fetchHoldings();
  },

  fetchHoldings() {
    const cookie = wx.getStorageSync('tzzb_cookie');
    if (!cookie) return;

    this.setData({ loading: true });

    wx.request({
      url: `${getApp().apiBase}/api/holdings?t=${Date.now()}`,
      method: 'POST',
      data: { cookie },
      success: (res) => {
        const holdings = this.extractHoldings(res.data);
        this.setData({ holdings });

        if (holdings.length === 0) {
          wx.showToast({ title: '暂无 ETF 持仓', icon: 'none' });
        }
      },
      fail: (err) => {
        wx.showToast({ title: '获取失败，Cookie可能已过期', icon: 'none' });
        console.error(err);
        wx.removeStorageSync('tzzb_cookie');
        this.setData({ isLoggedIn: false });
      },
      complete: () => {
        this.setData({ loading: false });
      }
    });
  },

  extractHoldings(reportData) {
    const holdings = [];

    if (!reportData || !reportData.sections) {
      return holdings;
    }

    // 从报告数据中提取ETF
    reportData.sections.forEach(section => {
      section.etfs.forEach(etf => {
        holdings.push({
          code: etf.code,
          name: etf.name,
          shares: 0,      // TODO: 从API获取
          value: 0,        // TODO: 从API获取
          display_premium: etf.display_premium,
          score: etf.score,
          recommendation: etf.recommendation,
          composite: etf.composite,
          shouldSwap: false,  // TODO: 与最佳ETF对比
          bestCode: '',
          bestName: '',
          excessDiff: 0
        });
      });
    });

    return holdings;
  }
});
