Page({
  data: {
    loading: true,
    error: null,
    report: null,
    lastUpdated: '',
    activeIdx: '',
    activeSection: null,
    expanded: null,
    logged: false
  },

  onLoad: function () {
    this.fetchReport()
  },

  onShow: function () {
    this.setData({ logged: getApp().isLoggedIn() })
  },

  onPullDownRefresh: function () {
    var self = this
    this.fetchReport().then(function () {
      wx.stopPullDownRefresh()
    })
  },

  onTabChange: function (e) {
    var idx = e.currentTarget.dataset.idx
    var section = this.data.report.sections.find(function (s) { return s.index_type === idx })
    this.setData({ activeIdx: idx, activeSection: section, expanded: null })
  },

  onToggle: function (e) {
    if (!this.data.logged) return
    var code = e.currentTarget.dataset.code
    this.setData({ expanded: this.data.expanded === code ? null : code })
  },

  onTapVersion: function () {
    wx.navigateTo({ url: '/pages/login/login' })
  },

  fetchReport: function () {
    var self = this
    var app = getApp()
    return new Promise(function (resolve) {
      wx.request({
        url: app.globalData.apiBase + '/report.json?t=' + Date.now(),
        method: 'GET',
        header: { 'X-Device-Id': app.getDeviceId() },
        dataType: 'json',
        success: function (res) {
          if (res.statusCode === 429) {
            self.setData({ error: '访问繁忙，请稍后再试', loading: false })
          } else if (res.statusCode === 200 && res.data) {
            var d = res.data
            var time = d.generated_at ? d.generated_at.split(' ')[1] : ''
            var firstSection = d.sections && d.sections.length > 0 ? d.sections[0] : null
            self.setData({
              report: d,
              loading: false,
              lastUpdated: time,
              error: null,
              activeIdx: firstSection ? firstSection.index_type : '',
              activeSection: firstSection,
              logged: getApp().isLoggedIn()
            })
          }
        },
        fail: function () {
          self.setData({
            error: '数据加载失败，请下拉刷新',
            loading: false
          })
        },
        complete: function () {
          resolve()
        }
      })
    })
  }
})
