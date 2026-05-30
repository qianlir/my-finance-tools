---
name: portfolio-pnl-analyzer
description: |
  个人投资组合按板块年度盈亏分析。输入同花顺导出的 Excel(汇总持仓 / 已清仓 / 交易记录 三个 sheet),
  输出 Markdown 报告 + 板块汇总 CSV,按 6 个板块(A股+H股/美股/海外其他/可转债/国债短融/商品)展示
  指定年份的精确区间盈亏 + 当前年 YTD 盈亏。

  口径(精确重建):
  - 区间 P&L = 期末市值 − 期初市值 + (期间卖出 + 分红 − 个税 − 期间买入 − 手续费)
  - 联网拉腾讯财经历史收盘价重建快照
  - 当前 YTD 用持仓表"今年盈亏" + 已清仓表 当年总盈亏

  触发词: 分析投资组合, 板块盈亏, 板块收益, 持仓盈亏分析, 投资盈利, portfolio pnl
version: 1.0.0
author: Alan (cmwang's GEI portfolio)
triggers:
  - 分析投资组合
  - 板块盈亏
  - 板块收益分析
  - 持仓盈亏分析
  - 投资盈利分析
  - portfolio pnl
  - 投资组合分析
  - 同花顺导出分析
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - AskUserQuestion
---

# Portfolio P&L Analyzer · 个人组合板块盈亏分析

## 用什么时候

用户从同花顺投资账本(或类似工具)导出 Excel,问"分析我去年和今年的盈亏 / 按板块" / "投资组合盈利" 这类问题时。

## 输入合约

**必需 Excel** 必须含三个 sheet:

| Sheet | 必需列 |
|---|---|
| **持仓数据** | `代码` / `名称` / `持有金额` / `今年盈亏` / `累计盈亏` / `持有数量` / `最新价` |
| **已清仓** | `清仓日期` / `代码` / `名称` / `总盈亏` |
| **交易记录** | `成交日期` / `代码` / `名称` / `交易类别` / `成交数量` / `成交价格` / `发生金额` / `费用` |

> 同花顺 PC 端"投资账本 → 导出持仓汇总"产出的标准格式即可。

## 输出

| 文件 | 内容 |
|---|---|
| `reports/analysis-YYYY-MM-DD.md` | Markdown 总报告:TL;DR + 2 张板块表 + 每板块 Top3 贡献/拖累 + 数据完整度 + 局限说明 |
| `data/pnl_by_sector.csv` | 板块汇总(可 Excel 打开) |
| `data/pnl_by_position.csv` | 每个标的的区间 P&L 明细 |
| `data/sectors.csv` | 板块归类结果(可手工微调后重跑 step 4) |
| `data/snapshot_*.csv` | 两个时点的持仓快照 |
| `data/cashflow_*.csv` | 各期间现金流 |
| `data/prices.csv` | 历史价格 |

## 工作流程

按顺序跑 4 个脚本,中间不需要用户介入:

```bash
cd <work_dir>   # 创建工作目录 e.g. ~/gei-workspace/output/portfolio-pnl-YYYY-MM-DD/
python3 scripts/01_build_snapshots.py   # 重建快照(秒级,~20s for 13k 交易)
python3 scripts/02_fetch_prices.py      # 联网拉 2 个时点收盘价(~1-2 分钟,151 标的)
python3 scripts/03_classify_sectors.py  # 板块归类
python3 scripts/04_calc_pnl.py          # 算 P&L + 写 CSV
python3 scripts/05_report.py            # 生成 Markdown 报告
```

## 调用约定

**当用户触发本 skill,Claude 应该:**

1. **询问关键参数**(AskUserQuestion · 单题):
   - Excel 文件路径(默认 `~/Downloads/汇总持仓*.xlsx`,自动 Glob)
   - 分析的"去年"具体是哪一年(默认 当前年 - 1,即今年是 2026 那"去年" = 2025)
   - 工作目录路径(默认 `~/gei-workspace/output/portfolio-pnl-YYYY-MM-DD/`)

2. **修改脚本中的硬编码日期**(由 Claude 替换 `SRC` 常量和 `SNAP_DATES` / `PERIODS`):
   - `01_build_snapshots.py` 顶部的 `SRC` 改为用户提供的 Excel 路径
   - `SNAP_DATES` 改为 `['{prev_year}-12-31', '{cur_year}-12-31', '{today}']`
   - `PERIODS` 改为 `{'<prev_year>': ('<prev_year>-01-01','<prev_year>-12-31'), '<cur_year>': ('<cur_year>-01-01','<today>')}`
   - `04_calc_pnl.py` 类似

3. **检查依赖**: akshare(可选)/ openpyxl(必需) / pandas(必需)。缺则 `pip install --user openpyxl pandas`。

4. **跑完后展示 TL;DR** + 提示用户报告路径,问"要不要打开 Chrome 看"。

## 板块归类规则(7 个细板块 + 显示时合并)

**细板块(用于内部统计)**: `A股 / H股 / 美股(QDII) / 海外其他 / 可转债 / 国债+短融货基 / 商品(黄金/REITs)`

**显示时**: A 股 + H 股 合并成 1 行(下方有"其中"明细)。

### 归类优先级链

1. **`references/sector-overrides.csv`** ← **Skill 级权威基线**(用户累积知识,248+ 标的)
2. **`scripts/03b_generate_registry.py` 的 `EXPLICIT_SECTOR` dict** ← 代码硬编码的边界标的
3. **关键词规则**:
   - 美股: 纳指/标普/道琼斯/美国/海外科技/REIT
   - 海外其他: 印度/日经/法国/德国/越南/沙特/东证
   - 国债+短融: 国债/短融/政金债/货基
   - 商品: 黄金/原油/有色/资源/煤/白银/油气
4. **代码模式**:
   - H 股: 5 位 0 开头
   - 可转债: 11/12 开头 6 位
   - A 股: 6/0/3 开头 6 位
5. **兜底** → `A股`

### 如何调整归类

**临时调整(只影响本次报告)**:
编辑 `<work_dir>/data/sectors.csv`,改第 3 列板块名,重跑 `04_calc_pnl.py` + `05_report.py`。

**永久调整(以后跑都生效)**:
确认归类后,把 work_dir 的 sectors.csv 合并回 skill 基线:

```bash
python3 ~/work/money/.claude/skills/portfolio-pnl-analyzer/scripts/sync_overrides.py \
  <work_dir>/data/sectors.csv
```

合并模式默认:新代码追加 + 已有代码用新归类覆盖(自动备份原基线到 `.bak`)。

## 算法不变量

- **2025 区间 P&L 公式**: `MV_end - MV_start + (sell + dividend + tax - buy - fee)` —— 等价于"会计盈亏"
- **当前 YTD**: 用持仓表"今年盈亏"字段 + 已清仓当年总盈亏 —— 因为这是用户工具的权威数
- **逆回购代码** `131810/131811/204001/204002/204007` 默认排除(不算入持仓,只算入现金管理利息)
- **百分比分母**: 2025 用期初市值(2024-12-31),当前 YTD 用当前市值

## 已知局限

1. 北交所代码变更(8xxxxx → 9xxxxx)历史数据可能拉不到 — 影响 < 0.5%
2. 场外基金分红再投资可能有捕获缺口 — 影响 < 1%
3. 重建数量 vs 持仓表数量在 1-3 个老持仓上可能有 1-100 股差异(送股 / 转债转换),影响 < 2%
4. A股+H股 板块是兜底,边界标的(港股通基金)归在此处。如想拆出"H 股独立",手工调 sectors.csv 后重跑。

## 参考阅读

- 详细口径选择讨论: `references/methodology.md`
- 数据源切换说明: `references/data-sources.md`(腾讯主 / akshare 备 / 用户手填降级)

## 关联项目

- 本 skill 与 `etf-advisor`(ETF 换仓顾问) 共享数据源思路,可独立运行
- 输出可作为 `wechat-publisher` 月报材料(整理后)
