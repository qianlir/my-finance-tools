// pages/settings/settings.js
Page({
  data: {
    cookieValue: '',
    hasCookie: false
  },

  onLoad() {
    this.loadCookie();
  },

  loadCookie() {
    const cookie = wx.getStorageSync('tzzb_cookie') || '';
    this.setData({
      cookieValue: cookie,
      hasCookie: !!cookie
    });
  },

  onCookieInput(e) {
    this.setData({ cookieValue: e.detail.value });
  },

  onSave() {
    const cookie = this.data.cookieValue.trim();
    if (!cookie) {
      wx.showToast({ title: '请输入Cookie', icon: 'none' });
      return;
    }
    wx.setStorageSync('tzzb_cookie', cookie);
    this.setData({ hasCookie: true });
    wx.showToast({ title: '已保存', icon: 'success' });
  },

  onClear() {
    wx.removeStorageSync('tzzb_cookie');
    this.setData({
      cookieValue: '',
      hasCookie: false
    });
    wx.showToast({ title: '已清除', icon: 'success' });
  },

  onTest() {
    const cookie = this.data.cookieValue.trim();
    if (!cookie) {
      wx.showToast({ title: '请先输入Cookie', icon: 'none' });
      return;
    }

    wx.showLoading({ title: '测试中...' });

    // 测试API连接
    wx.request({
      url: getApp().apiBase + '/api/holdings/test',
      method: 'POST',
      data: { cookie: cookie },
      success: (res) => {
        wx.hideLoading();
        if (res.statusCode === 200) {
          wx.showModal({
            title: '测试成功',
            content: `成功获取 ${res.data.count || 0} 只基金`,
            showCancel: false
          });
        } else {
          wx.showToast({ title: 'Cookie可能已过期', icon: 'none' });
        }
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: '连接失败，请检查网络', icon: 'none' });
      }
    });
  }
});
