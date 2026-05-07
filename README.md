# 纳指/标普ETF智能换仓顾问

基于超额溢价模型的ETF智能换仓推荐系统。

## 功能

- **自动数据采集**: 每个交易日自动采集所有纳指和标普ETF的溢价率数据
- **智能换仓分析**: 基于超额溢价模型，推荐同指数内溢价最低的ETF
- **个性化建议**: 指定当前持仓，获取是否换仓的具体建议（考虑交易成本）

## 快速开始

### 1. 采集数据

```bash
python3 scripts/update_data.py --realtime
```

### 2. 分析换仓

```bash
# 无持仓，查看整体推荐
python3 scripts/recommend_by_change.py

# 有持仓，获取个性化建议
python3 scripts/recommend_by_change.py --holding 513100 159655
```

## 定时任务

系统配置了定时任务，每个交易日自动执行：

- **11:15**: 采集ETF数据
- **11:30**: 生成换仓建议

## 项目结构

```
nasdaq-etf-advisor/
├── scripts/
│   ├── update_data.py            # 数据采集脚本
│   └── recommend_by_change.py    # 推荐分析脚本
├── memory/knowledge/etf/         # 配置文件
│   ├── nasdaq-etf-list.md        # ETF列表
│   ├── advisor-config.md         # 分析配置
│   └── latest-snapshot.json      # 最新数据快照
├── data/
│   └── etf_premium.db            # 数据库
├── SKILL.md                      # Skill定义
├── HEARTBEAT.md                  # 定时任务配置
├── CLAUDE.md                     # 项目上下文
└── README.md                     # 本文件
```

## 配置

### 添加/删除ETF

编辑 `memory/knowledge/etf/nasdaq-etf-list.md`

### 调整分析阈值

编辑 `memory/knowledge/etf/advisor-config.md`

## 依赖

- Python 3.9+
- requests 库

```bash
pip install requests
```

## 注意事项

1. 数据采集需要在交易日执行
2. 高溢价ETF（如159509纳指科技ETF）已排除分析
3. 建议分批换仓，降低时点风险
4. 本系统仅供参考，投资需谨慎
