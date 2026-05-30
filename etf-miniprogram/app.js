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

  // 期望的密码（前4个数字作为位置索引，提取对应字符）
  expectedPass: function () {
    var uid = this.expectedUser()
    var numStr = uid.replace(/-/g, '')
    var nums = numStr.match(/\d/g) || []
    var indices = nums.slice(0, 4).map(function(n) { return parseInt(n) })

    var result = ''
    for (var i = 0; i < 4; i++) {
      if (i < indices.length && indices[i] < numStr.length) {
        result += numStr.charAt(indices[i])
      } else {
        result += '0'
      }
    }
    return result
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
  }
})
