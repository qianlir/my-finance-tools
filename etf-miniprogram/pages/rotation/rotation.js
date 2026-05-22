Page({
  data: {
    loading: true,
    error: null,
    logged: false,
    summary: null,
    trades: [],
    pool_names: {},
    start_date: '',
    end_date: '',
    trading_days: 0,
    threshold: 0,
    equal_weight_etfs: 0
  },

  _chartData: null,

  onLoad: function () {
    this.checkAndLoad()
  },

  onShow: function () {
    var logged = getApp().isLoggedIn()
    this.setData({ logged: logged })
    if (logged && !this.data.summary) {
      this.fetchData()
    }
  },

  onPullDownRefresh: function () {
    var self = this
    if (!this.data.logged) {
      wx.stopPullDownRefresh()
      return
    }
    this.fetchData().then(function () {
      wx.stopPullDownRefresh()
    })
  },

  checkAndLoad: function () {
    var logged = getApp().isLoggedIn()
    this.setData({ logged: logged })
    if (logged) {
      this.fetchData()
    } else {
      this.setData({ loading: false })
    }
  },

  onTapLogin: function () {
    wx.navigateTo({ url: '/pages/login/login' })
  },

  fetchData: function () {
    var self = this
    var app = getApp()
    return new Promise(function (resolve) {
      wx.request({
        url: app.globalData.apiBase + '/rotation_index.json?t=' + Date.now(),
        method: 'GET',
        dataType: 'json',
        success: function (res) {
          if (res.statusCode === 200 && res.data) {
            var d = res.data
            var trades = (d.trades || []).slice().reverse()

            self._chartData = d.daily || null

            self.setData({
              summary: d.summary || {},
              trades: trades,
              pool_names: d.pool_names || {},
              start_date: d.start_date || '',
              end_date: d.end_date || '',
              trading_days: d.trading_days || 0,
              threshold: d.threshold || 0,
              equal_weight_etfs: d.equal_weight_etfs || 0,
              loading: false,
              error: null
            })

            setTimeout(function () { self.drawChart() }, 100)
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
  },

  drawChart: function () {
    var d = this._chartData
    if (!d || !d.dates || !d.rotation_values) return

    var self = this
    var query = wx.createSelectorQuery().in(this)
    query.select('#rotChart').fields({ node: true, size: true }).exec(function (res) {
      if (!res || !res[0]) return
      var canvas = res[0].node
      var w = res[0].width
      var h = res[0].height
      var dpr = wx.getWindowInfo().pixelRatio
      canvas.width = w * dpr
      canvas.height = h * dpr
      var ctx = canvas.getContext('2d')
      ctx.scale(dpr, dpr)

      var rv = d.rotation_values
      var ew = d.equal_weight_values || []
      var mp = d.min_premium_values || []
      var n = rv.length
      if (n < 2) return

      var allVals = rv.concat(ew).concat(mp)
      var minV = Math.min.apply(null, allVals)
      var maxV = Math.max.apply(null, allVals)
      var pad = (maxV - minV) * 0.08
      minV -= pad
      maxV += pad
      var range = maxV - minV

      var ml = 40, mr = 8, mt = 8, mb = 24
      var cw = w - ml - mr
      var ch = h - mt - mb

      function x(i) { return ml + (i / (n - 1)) * cw }
      function y(v) { return mt + (1 - (v - minV) / range) * ch }

      // Grid
      ctx.strokeStyle = 'rgba(26,22,19,0.06)'
      ctx.lineWidth = 0.5
      var gridCount = 4
      for (var g = 0; g <= gridCount; g++) {
        var gy = mt + (g / gridCount) * ch
        ctx.beginPath()
        ctx.moveTo(ml, gy)
        ctx.lineTo(w - mr, gy)
        ctx.stroke()

        var gv = maxV - (g / gridCount) * range
        ctx.fillStyle = 'rgba(26,22,19,0.3)'
        ctx.font = '9px Menlo, monospace'
        ctx.textAlign = 'right'
        ctx.fillText((gv / 1000).toFixed(1) + 'k', ml - 4, gy + 3)
      }

      // X labels
      ctx.fillStyle = 'rgba(26,22,19,0.3)'
      ctx.font = '9px Menlo, monospace'
      ctx.textAlign = 'center'
      var labelInterval = Math.floor(n / 5)
      for (var li = 0; li < n; li += labelInterval) {
        ctx.fillText(d.dates[li].slice(5), x(li), h - 4)
      }
      ctx.fillText(d.dates[n - 1].slice(5), x(n - 1), h - 4)

      function drawLine(data, color, width, dash) {
        if (!data || data.length < 2) return
        ctx.strokeStyle = color
        ctx.lineWidth = width
        ctx.setLineDash(dash || [])
        ctx.beginPath()
        ctx.moveTo(x(0), y(data[0]))
        for (var i = 1; i < data.length; i++) {
          ctx.lineTo(x(i), y(data[i]))
        }
        ctx.stroke()
        ctx.setLineDash([])
      }

      // Fill under rotation line
      ctx.fillStyle = 'rgba(168,52,42,0.06)'
      ctx.beginPath()
      ctx.moveTo(x(0), y(rv[0]))
      for (var fi = 1; fi < rv.length; fi++) {
        ctx.lineTo(x(fi), y(rv[fi]))
      }
      ctx.lineTo(x(rv.length - 1), mt + ch)
      ctx.lineTo(x(0), mt + ch)
      ctx.closePath()
      ctx.fill()

      drawLine(ew, '#8b6914', 1, [4, 3])
      drawLine(mp, '#2A6B4F', 1.2, [3, 3])
      drawLine(rv, '#A8342A', 2)
    })
  }
})
