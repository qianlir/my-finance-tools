Page({
  data: {
    user: '',
    pass: '',
    err: ''
  },

  onLoad: function () {
    var app = getApp()
    this.setData({ user: app.getDeviceId() })
  },

  onPassInput: function (e) {
    this.setData({ pass: e.detail.value, err: '' })
  },

  onCopyUser: function () {
    var self = this
    wx.setClipboardData({
      data: self.data.user,
      success: function () {
        wx.showToast({ title: '用户名已复制', icon: 'none', duration: 1500 })
      }
    })
  },

  onSubmit: function () {
    var app = getApp()
    var ok = app.login(this.data.user, this.data.pass.trim())
    if (ok) {
      wx.navigateBack()
    } else {
      this.setData({ err: '验证失败' })
    }
  }
})
