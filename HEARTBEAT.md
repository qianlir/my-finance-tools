# HEARTBEAT

## 定时任务配置

本文件定义了ETF换仓顾问的定时任务。

### 执行时间表

| 任务 | 频率 | 触发时间 | 执行命令 | 说明 |
|------|------|----------|----------|------|
| ETF数据采集 | 每交易日 | 11:15 | `python3 scripts/update_data.py --realtime` | 采集上午收盘前数据 |
| 换仓分析 | 每交易日 | 11:30 | `python3 scripts/recommend_by_change.py --holding 513100 159655` | 中午休市时分析 |

### 执行流程

```
11:15 → 数据采集 → 11:30 → 换仓分析 → 用户查看 → 下午调仓
```

### 执行条件

1. **交易日判断**: 仅在交易日执行（跳过周末和节假日）
2. **依赖检查**: 数据采集成功后才执行换仓分析
3. **重试机制**: 如11:15采集失败，自动重试一次（11:20）

## 任务详情

### Task 1: ETF数据采集

**执行命令**:
```bash
python3 scripts/update_data.py --realtime
```

**输出**:
- `data/etf_premium.db`: 数据库更新
- `memory/knowledge/etf/latest-snapshot.json`: 最新快照

**失败处理**:
- 记录错误日志
- 11:20自动重试一次
- 连续失败则跳过当天分析

### Task 2: 换仓分析

**执行命令**:
```bash
python3 scripts/recommend_by_change.py --holding 513100 159655
```

**触发条件**:
- 数据采集成功

**输出**:
- 终端显示分析报告（详细表格 + 今日推荐汇总）

## 手动触发

### 数据采集

```
采集ETF数据
更新ETF溢价率
collect etf data
```

### 换仓分析

```
换仓建议
ETF分析
etf rebalance advice
今天该持有哪只ETF
```

## 配置修改

如需修改执行时间或参数，编辑本文件即可。
