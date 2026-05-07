Page({
  data: {
    report: null,
    loading: true,
    lastUpdated: '',
    error: null
  },

  _timer: null,

  onLoad: function() {
    this.fetchReport()
  },

  onShow: function() {
    var app = getApp()
    var self = this
    // 启动自动刷新（5分钟）
    this._timer = setInterval(function() {
      self.fetchReport()
    }, app.globalData.refreshInterval)
  },

  onHide: function() {
    this._clearTimer()
  },

  onUnload: function() {
    this._clearTimer()
  },

  onPullDownRefresh: function() {
    var self = this
    this.fetchReport().then(function() {
      wx.stopPullDownRefresh()
    })
  },

  _clearTimer: function() {
    if (this._timer) {
      clearInterval(this._timer)
      this._timer = null
    }
  },

  fetchReport: function() {
    var self = this
    var app = getApp()
    return new Promise(function(resolve) {
      wx.request({
        url: app.globalData.apiBase + '/report.json?t=' + Date.now(),
        method: 'GET',
        dataType: 'json',
        success: function(res) {
          if (res.statusCode === 200 && res.data) {
            var time = res.data.generated_at
              ? res.data.generated_at.split(' ')[1] + ' 更新'
              : ''
            self.setData({
              report: res.data,
              loading: false,
              lastUpdated: time,
              error: null
            })
          }
        },
        fail: function() {
          self.setData({
            error: '数据加载失败，请下拉刷新重试',
            loading: false
          })
        },
        complete: function() {
          resolve()
        }
      })
    })
  }
})
