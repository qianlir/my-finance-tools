# Futu Data Provider

通过富途 OpenAPI 获取 A 股 / 港股 / 美股实时和历史行情数据，替代当前 portfolio-pnl-analyzer 的腾讯财经 API。

## 为什么换

| | 腾讯财经 API (当前) | 富途 OpenAPI |
|---|---|---|
| A 股 | ✅ 日 K 线 | ✅ 实时 + 分钟/日/周/月 K 线 |
| 港股 | ⚠️ 有延迟 | ✅ 实时（LV1 免费） |
| 美股 | ❌ 无（QDII 只有 A 股价） | ✅ 实时 + 历史（LV1 免费） |
| 基金 NAV | ❌ | ✅ ETF/LOF 实时 |
| 稳定性 | 非官方，随时可能封 | 官方 SDK，长期维护 |
| 频率限制 | 未知 | 明确（30 次/30 秒） |

## 前置条件

1. **富途账户** — 注册 [futu.com](https://www.futu.com)（免费）
2. **Futu OpenD** — 下载并运行 [OpenD](https://openapi.futunn.com/futu-api-doc/opend/opend-cmd.html)
3. **futu-api** — `pip install futu-api`

```bash
# 安装
pip install futu-api

# 启动 OpenD（后台运行）
# macOS: 从 Applications 启动，或命令行:
/Applications/FutuOpenD.app/Contents/MacOS/FutuOpenD &
```

## 用途规划

### Phase 1: 数据源替换（替代腾讯 API）
- `fetch_prices.py` — 批量拉历史日 K 线，供 portfolio-pnl-analyzer 用
- 支持 A 股 + 港股 + 美股，统一接口

### Phase 2: 实时监控
- `realtime_monitor.py` — 订阅持仓标的实时报价
- 盘中 P&L 估算

### Phase 3: 策略回测（可选）
- 利用分钟级 K 线做板块轮动回测
- 模拟盘验证

## 目录结构

```
futu-data-provider/
├── README.md
├── scripts/
│   ├── fetch_kline.py      # 批量拉历史 K 线 → SQLite
│   ├── realtime_quote.py   # 实时报价订阅
│   └── test_connection.py  # 连接测试
├── data/
│   └── futu_kline.db       # K 线缓存
└── config/
    └── watchlist.csv        # 监控标的列表
```

## 富途代码格式

| 市场 | 格式 | 示例 |
|---|---|---|
| A 股(沪) | `SH.600941` | 中国移动 |
| A 股(深) | `SZ.000858` | 五粮液 |
| 港股 | `HK.09988` | 阿里巴巴 |
| 美股 | `US.AAPL` | 苹果 |
| ETF | `SH.513100` / `SZ.159655` | 纳指ETF / 标普ETF |
