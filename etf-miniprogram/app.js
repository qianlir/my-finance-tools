App({
  globalData: {
    apiBase: 'https://invest.qianli.wang/data'
  },

  onLaunch: function () {
    // 确保设备 ID 已生成
    this.getDeviceId()
  },

  // 设备唯一标识（首次生成后持久化）
  getDeviceId: function () {
    var id = wx.getStorageSync('device_id')
    if (!id) {
      id = this._uuid()
      wx.setStorageSync('device_id', id)
    }
    return id
  },

  // 期望的用户名（设备 ID）
  expectedUser: function () {
    return this.getDeviceId()
  },

  // 期望的密码（base64 of 用户名）
  expectedPass: function () {
    return this._b64(this.expectedUser())
  },

  isLoggedIn: function () {
    var token = wx.getStorageSync('auth_token')
    if (!token) return false
    var today = this._today()
    return token === today
  },

  login: function (user, pass) {
    if (user === this.expectedUser() && pass === this.expectedPass()) {
      wx.setStorageSync('auth_token', this._today())
      return true
    }
    return false
  },

  logout: function () {
    wx.removeStorageSync('auth_token')
  },

  _today: function () {
    var d = new Date()
    var y = d.getFullYear()
    var m = ('0' + (d.getMonth() + 1)).slice(-2)
    var day = ('0' + d.getDate()).slice(-2)
    return '' + y + m + day
  },

  _uuid: function () {
    // 简易 UUID v4
    var s = ''
    var chars = '0123456789abcdef'
    for (var i = 0; i < 32; i++) {
      if (i === 8 || i === 12 || i === 16 || i === 20) s += '-'
      if (i === 12) s += '4'
      else if (i === 16) s += chars.charAt((Math.random() * 4 | 0) + 8)
      else s += chars.charAt(Math.random() * 16 | 0)
    }
    return s
  },

  _b64: function (str) {
    var chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/='
    var out = ''
    var i = 0
    while (i < str.length) {
      var c1 = str.charCodeAt(i++)
      var c2 = i < str.length ? str.charCodeAt(i++) : NaN
      var c3 = i < str.length ? str.charCodeAt(i++) : NaN
      var e1 = c1 >> 2
      var e2 = ((c1 & 3) << 4) | (isNaN(c2) ? 0 : c2 >> 4)
      var e3 = isNaN(c2) ? 64 : ((c2 & 15) << 2) | (isNaN(c3) ? 0 : c3 >> 6)
      var e4 = isNaN(c3) ? 64 : c3 & 63
      out += chars.charAt(e1) + chars.charAt(e2) + chars.charAt(e3) + chars.charAt(e4)
    }
    return out
  }
})
