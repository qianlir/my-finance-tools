# Money — 个人投资工具箱

## 项目概述

个人投资分析工具集合，包含多个独立的投资分析 skill。

## 目录结构

```
money/
├── CLAUDE.md                        # 项目上下文（本文件）
├── SOUL.md                          # Agent 人格定义
├── README.md                        # 项目说明
├── .claude/plugin.json              # 项目配置
├── etf-advisor/              # Skill: 纳指/标普ETF智能换仓顾问
│   ├── SKILL.md                     # Skill 定义
│   ├── scripts/                     # 核心脚本
│   │   ├── update_data.py           # 数据采集
│   │   ├── recommend_by_change.py   # 分析推荐（--server 模式输出 JSON）
│   │   └── server_update.sh         # 服务器定时任务脚本
│   ├── data/                        # 数据库 + report.json（小程序数据源）
│   ├── memory/knowledge/etf/        # 配置和快照
│   ├── reports/                     # 分析报告
│   │   └── img/{YYYYMMDD}/          # 表格截图按日期归档
│   ├── docs/                        # 文档
│   └── etf-advisor-test/     # 测试套件
│       └── SKILL.md
├── etf-miniprogram/                 # 微信小程序：ETF溢价分析
│   ├── app.js / app.json / app.wxss # 小程序入口
│   ├── pages/report/                # 单页面（报告展示）
│   └── utils/format.wxs            # WXS格式化模块
├── etf-evaluator/                   # Skill: ETF报告LLM评估
│   ├── SKILL.md                     # Skill 定义
│   └── references/
│       └── evaluation-criteria.md   # 评估维度和约束
├── wechat-publisher/                # Skill: 微信公众号自动发帖
│   ├── SKILL.md                     # Skill 定义
│   ├── scripts/                     # 核心脚本
│   │   ├── wechat_api.py            # 微信 API 操作
│   │   └── md_to_wechat_html.py     # MD→微信HTML转换
│   ├── articles/                    # 文章存放
│   ├── data/                        # 发布记录
│   ├── memory/knowledge/wechat/     # 公众号配置
│   └── references/                  # API 文档
└── stock-analyzer/                  # Skill: A股/港股通个股深度分析
    ├── skills/a-stock-analyzer/     # 核心 Skill
    │   ├── SKILL.md                 # Skill 定义
    │   └── scripts/collect_data.py  # 数据采集+技术分析脚本
    ├── docs/                        # 需求文档
    └── reports/                     # 分析报告
    ├── SKILL.md                     # Skill 定义
    ├── scripts/                     # 核心脚本
    │   ├── wechat_api.py            # 微信 API 操作
    │   └── md_to_wechat_html.py     # MD→微信HTML转换
    ├── articles/                    # 文章存放
    ├── data/                        # 发布记录
    ├── memory/knowledge/wechat/     # 公众号配置
    └── references/                  # API 文档
```

## Skills 列表

| Skill | 说明 | 触发词 |
|-------|------|--------|
| etf-advisor | 纳指/标普ETF智能换仓顾问 | 换仓建议, ETF分析, 采集ETF数据 |
| etf-evaluator | ETF报告LLM评估 | 评估ETF报告, LLM评估, 生成评估 |
| wechat-publisher | 微信公众号自动发帖 | 发公众号, 写公众号文章, 发微信文章 |
| a-stock-analyzer | A股/港股通个股深度分析 | 分析A股, 股票分析, 个股分析, 持仓分析 |

## 数据流

### 本地（公众号发布）
```
11:15 → etf-advisor/scripts/update_data.py --realtime
          ↓
      data/etf_premium.db + memory/knowledge/etf/latest-snapshot.json
          ↓
11:30 → etf-advisor/scripts/recommend_by_change.py --holding <codes>
          ↓
      换仓建议报告（今日推荐 + 详细分析表）
```

### 服务器（小程序实时更新）
```
每5分钟 → server_update.sh
            ├─ update_data.py --realtime
            └─ recommend_by_change.py --server
                  ↓
              data/report.json → Nginx → 小程序 fetch
```
