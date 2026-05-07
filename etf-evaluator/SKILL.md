---
name: etf-evaluator
description: |
  ETF 分析报告 LLM 评估。读取 Python 脚本生成的数据报告（analysis_{date}.md），
  结合前一天的报告趋势，生成专业的投资评估摘要并保存到独立文件 {date}_llm.md。
  当用户说"评估ETF报告"、"LLM评估"、"生成评估"时触发。
version: 1.0.0
type: analysis
triggers:
  - 评估ETF报告
  - LLM评估
  - 生成今日评估
  - etf evaluation
---

# ETF 报告 LLM 评估

## 目的

读取 `nasdaq-etf-advisor/scripts/recommend_by_change.py` 生成的每日分析报告，
结合前一天报告数据，生成专业的投资评估摘要。评估关注溢价趋势、推荐变化和风险因素，
为用户提供超越固定模板的市场洞察。

## 触发条件

- 用户说"评估ETF报告"、"LLM评估"、"生成评估"、"etf evaluation"
- nasdaq-etf-advisor 完成数据分析后，用户要求生成深度评估

## 工作流程

### 1. 定位报告

使用 Glob 查找 `nasdaq-etf-advisor/reports/analysis_*.md`，取修改时间最新的文件作为当日报告。

### 2. 定位前日报告

从当日报告日期往前查找 1-3 天（应对周末和假日），找到最近的一份历史报告。
若无历史报告，跳过趋势对比，仅基于当日数据评估。

### 3. 读取报告数据

从 MD 报告中提取：
- 期货行情（NQ/ES 价格与涨跌幅）
- 纳指 ETF 表格（代码、估算溢价、综合超额、1Y净值、分值）
- 标普 ETF 表格（同上）
- 今日推荐（推荐的 ETF 代码和分值）

### 4. 生成评估

参考 `references/evaluation-criteria.md` 中的评估维度，生成 ≤ 300 字的评估摘要。
输出包含四个部分：**市场**、**纳指**、**标普**、**风险**。

### 5. 保存到独立文件

使用 Write 工具将评估保存到 `{date}_llm.md` 文件（与主报告在同一目录）。
文件名格式：`analysis_{date}_llm.md`

文件内容格式：
```markdown
# ETF溢价分析评估 {date}

**市场**: [期货行情概括]

**纳指**: [首选 ETF + 分析]

**标普**: [首选 ETF + 分析]

**风险**: [需要关注的因素，既说明机会也说明风险]
```

### 6. 通知用户

告知评估已保存到 `_llm.md` 文件路径，并展示评估内容摘要。

## 注意事项

- 不做涨跌方向预测，只分析溢价结构和趋势
- 使用交易员早间简报的简洁语气
- 评估文案 ≤ 300 字
- 不修改报告中的数据表格和公式说明
