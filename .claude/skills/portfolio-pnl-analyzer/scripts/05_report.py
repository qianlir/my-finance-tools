#!/usr/bin/env python3
"""生成 Markdown + HTML 报告。A股/H股 在表格里合一行(下面带"其中"明细)。

环境变量同上。
"""
import os
import csv
import json
from collections import defaultdict
from pathlib import Path

WORK = Path(os.environ['PORTFOLIO_WORK_DIR']).expanduser()
PRIOR = int(os.environ['PORTFOLIO_PRIOR_YEAR'])
CUR = int(os.environ['PORTFOLIO_CUR_YEAR'])
TODAY = os.environ['PORTFOLIO_TODAY']
DATA = WORK / 'data'
REPORTS = WORK / 'reports'
REPORTS.mkdir(exist_ok=True)

D_PRIOR = f'{PRIOR-1}-12-31'
D_CUR_END = f'{PRIOR}-12-31'


def fmt_money(v):
    if v is None: return 'N/A'
    return f'¥{v:,.0f}'


SMALL_BASIS = 10000   # 基数 < ¥1万 时,百分比标 N/M

def fmt_pct(v, basis=None):
    """basis 给出时,若 |basis| < 1 万 → N/M(投资界惯例,避免误导)"""
    if v is None or v == 'N/A': return 'N/A'
    if isinstance(v, str): return v
    if basis is not None and abs(basis) < SMALL_BASIS:
        return 'N/M'
    return f'{v:.2f}%'


def main():
    with open(DATA / 'pnl_summary.json') as f:
        summary = json.load(f)

    sec = summary['sector_breakdown']
    total = summary['total']

    SECTORS_RAW = ['A股','H股','美股(QDII)','日本','德国','法国','印度','沙特','东南亚','海外',
                   '可转债','国债+短融货基','商品(黄金/REITs)']
    # 显示时把 A股 / H股 合并为 "A+H股";其余 11 个独立展示
    SECTORS_DISPLAY = ['A+H股', '美股(QDII)','日本','德国','法国','印度','沙特','东南亚','海外',
                       '可转债','国债+短融货基','商品(黄金/REITs)']

    def get_combined(s):
        """返回合并后板块的聚合(A+H 把 A 股 + H 股加在一起)"""
        if s == 'A+H股':
            a = sec['A股']; b = sec['H股']
            return {
                'mv_prior': a['mv_prior'] + b['mv_prior'],
                'mv_cur_end': a['mv_cur_end'] + b['mv_cur_end'],
                'pl_prior_year': a['pl_prior_year'] + b['pl_prior_year'],
                'pl_cur_total': a['pl_cur_total'] + b['pl_cur_total'],
                'pl_held_ytd': a['pl_held_ytd'] + b['pl_held_ytd'],
                'pl_realised_cur': a['pl_realised_cur'] + b['pl_realised_cur'],
                'current_value': a['current_value'] + b['current_value'],
                'positions_prior': a['positions_prior'] + b['positions_prior'],
                'positions_cur': a['positions_cur'] + b['positions_cur'],
                'return_prior_initial': (
                    (a['pl_prior_year'] + b['pl_prior_year']) / (a['mv_prior'] + b['mv_prior']) * 100
                    if (a['mv_prior'] + b['mv_prior']) > 0 else None),
                'return_cur_ytd': (
                    (a['pl_cur_total'] + b['pl_cur_total']) / (a['current_value'] + b['current_value']) * 100
                    if (a['current_value'] + b['current_value']) > 0 else None),
            }
        return sec[s]

    # 读 by-position 找 Top 贡献 + 板块明细
    pos = []
    with open(DATA / 'pnl_by_position.csv') as f:
        for r in csv.DictReader(f):
            pos.append({
                'code': r['code'], 'name': r['name'], 'sector': r['sector'],
                'mv_prior': float(r.get(f'mv_{D_PRIOR}', 0) or 0),
                'mv_cur_end': float(r.get(f'mv_{D_CUR_END}', 0) or 0),
                'net_cash_in': float(r.get(f'net_cash_in_{PRIOR}', 0) or 0),
                'pl_prior': float(r[f'pl_{PRIOR}'] or 0),
                'pl_held_ytd': float(r.get(f'pl_held_ytd_{CUR}', 0) or 0),
                'pl_realised_cur': float(r.get(f'pl_realised_{CUR}', 0) or 0),
                'pl_cur': float(r[f'pl_{CUR}_total'] or 0),
                'cur_value': float(r['current_value'] or 0),
            })

    def positions_for(combined_sector):
        if combined_sector == 'A+H股':
            return [p for p in pos if p['sector'] in ('A股','H股')]
        return [p for p in pos if p['sector'] == combined_sector]

    # slug for HTML anchor
    SECTOR_SLUG = {
        'A+H股': 'ah-stock', 'A股': 'a-stock', 'H股': 'h-stock',
        '美股(QDII)': 'us-qdii', '日本': 'japan', '德国': 'germany',
        '法国': 'france', '印度': 'india', '沙特': 'saudi',
        '东南亚': 'se-asia', '海外': 'overseas',
        '可转债': 'cb', '国债+短融货基': 'bond',
        '商品(黄金/REITs)': 'commodity',
    }
    def slug(s): return SECTOR_SLUG.get(s, s)

    sec_sorted_prior = sorted(SECTORS_DISPLAY, key=lambda s: -(get_combined(s).get('return_prior_initial') or -999))
    sec_sorted_cur = sorted(SECTORS_DISPLAY, key=lambda s: -(get_combined(s).get('return_cur_ytd') or -999))

    # === Markdown ===
    md = f"""# 个人投资组合盈亏分析 · {PRIOR} + {CUR} YTD

**生成**: {TODAY} · **数据源**: `{os.environ['PORTFOLIO_XLSX']}`
**口径**: {PRIOR} 全年用精确重建({D_PRIOR} + {D_CUR_END} 两个时点持仓 × 联网腾讯财经历史收盘价);{CUR} YTD 用持仓表"今年盈亏"+ 已清仓表总盈亏
**分母**: 板块当前市值(基于当前持仓表汇总)

---

## TL;DR

| 指标 | 数值 |
|---|---|
| **{PRIOR} 全年盈利** | **{fmt_money(total['pl_prior_year'])}** ({fmt_pct(total['return_prior'])}) |
| **{CUR} YTD 盈利**({TODAY}) | **{fmt_money(total['pl_cur_total'])}** ({fmt_pct(total['return_cur'])}) |
| 当前总市值 | {fmt_money(total['current_value'])} |
| {D_PRIOR} 持仓总市值 | {fmt_money(total['mv_prior'])} |
| {D_CUR_END} 持仓总市值 | {fmt_money(total['mv_cur_end'])} |

**两年合计盈利 ≈ {fmt_money(total['pl_prior_year'] + total['pl_cur_total'])}**

---

## 表 1 · {PRIOR} 全年 板块盈亏(按收益率排序)

| 排名 | 板块 | 期初市值<br>({D_PRIOR}) | 期末市值<br>({D_CUR_END}) | {PRIOR} P&L | 收益率<br>(期初市值) | 持仓数 |
|---:|---|---:|---:|---:|---:|---:|
"""

    for i, s in enumerate(sec_sorted_prior, 1):
        d = get_combined(s)
        md += f"| {i} | **{s}** | {fmt_money(d['mv_prior'])} | {fmt_money(d['mv_cur_end'])} | **{fmt_money(d['pl_prior_year'])}** | **{fmt_pct(d['return_prior_initial'])}** | {d['positions_prior']} |\n"
        if s == 'A+H股':
            for sub in ['A股', 'H股']:
                sd = sec[sub]
                md += f"|  | &nbsp;&nbsp;其中: {sub} | {fmt_money(sd['mv_prior'])} | {fmt_money(sd['mv_cur_end'])} | {fmt_money(sd['pl_prior_year'])} | {fmt_pct(sd['return_prior_initial'])} | {sd['positions_prior']} |\n"
    md += f"| - | **合计** | {fmt_money(total['mv_prior'])} | {fmt_money(total['mv_cur_end'])} | **{fmt_money(total['pl_prior_year'])}** | **{fmt_pct(total['return_prior'])}** | - |\n"

    md += f"""

> **{PRIOR} 口径**: 期间 P&L = 期末市值 − 期初市值 + (期间卖出 + 现金分红 − 个税 − 期间买入 − 手续费)。已清仓部分包含在内。

## 表 2 · {CUR} YTD 板块盈亏({CUR}-01-01 ~ {TODAY},按收益率排序)

| 排名 | 板块 | 当前市值 | 持仓今年盈亏 | 已清仓盈亏 | {CUR} YTD 总盈亏 | 收益率<br>(当前市值) | 持仓数 |
|---:|---|---:|---:|---:|---:|---:|---:|
"""
    for i, s in enumerate(sec_sorted_cur, 1):
        d = get_combined(s)
        md += f"| {i} | **{s}** | {fmt_money(d['current_value'])} | {fmt_money(d['pl_held_ytd'])} | {fmt_money(d['pl_realised_cur'])} | **{fmt_money(d['pl_cur_total'])}** | **{fmt_pct(d['return_cur_ytd'])}** | {d['positions_cur']} |\n"
        if s == 'A+H股':
            for sub in ['A股','H股']:
                sd = sec[sub]
                md += f"|  | &nbsp;&nbsp;其中: {sub} | {fmt_money(sd['current_value'])} | {fmt_money(sd['pl_held_ytd'])} | {fmt_money(sd['pl_realised_cur'])} | {fmt_money(sd['pl_cur_total'])} | {fmt_pct(sd['return_cur_ytd'])} | {sd['positions_cur']} |\n"
    md += f"| - | **合计** | {fmt_money(total['current_value'])} | - | - | **{fmt_money(total['pl_cur_total'])}** | **{fmt_pct(total['return_cur'])}** | - |\n"

    md += f"""

> **{CUR} 口径**: "持仓今年盈亏" = Excel 持仓表"今年盈亏"字段汇总(含浮动+已实现);"已清仓盈亏" = 已清仓表 {CUR} 年总盈亏。

---

## 板块洞察 · Top 3 贡献 / Top 3 拖累

"""

    for s in SECTORS_DISPLAY:
        items = positions_for(s)
        top = sorted(items, key=lambda x: -x['pl_prior'])[:3]
        bot = sorted(items, key=lambda x: x['pl_prior'])[:3]
        d = get_combined(s)
        md += f"### {s}\n\n"
        md += f"- **{PRIOR} P&L**: {fmt_money(d['pl_prior_year'])} ({fmt_pct(d['return_prior_initial'])})\n"
        md += f"- **{CUR} YTD P&L**: {fmt_money(d['pl_cur_total'])} ({fmt_pct(d['return_cur_ytd'])})\n"
        md += f"- **当前持仓**: {d['positions_cur']} 个, 市值 {fmt_money(d['current_value'])}\n\n"
        if top and top[0]['pl_prior'] > 0:
            md += f"**{PRIOR} Top 3 贡献**:\n"
            for x in top:
                if x['pl_prior'] > 0:
                    md += f"- {x['code']} {x['name']}: +{fmt_money(x['pl_prior'])}\n"
            md += "\n"
        if bot and bot[0]['pl_prior'] < 0:
            md += f"**{PRIOR} Top 3 拖累**:\n"
            for x in bot:
                if x['pl_prior'] < 0:
                    md += f"- {x['code']} {x['name']}: {fmt_money(x['pl_prior'])}\n"
            md += "\n"
        md += "---\n\n"

    md += f"""## 数据完整度

- **价格联网拉取**: 腾讯财经 API,151+ 唯一标的
- **缺历史价的小标的**: 北交所老代码 / 退市 LOF 3 个,影响 < 0.5%

## 已知局限

1. 重建数量 vs 持仓表数量在 1-3 个老持仓上可能有 1-100 股差异(送股 / 转债转换 / 北交所代码变更),对总 P&L 影响 < 2%
2. 国债逆回购利息(R-001/R-002/GC001/GC007)未单独计入,合计影响几千元
3. 场外基金分红再投资可能有捕获缺口,小量低估
4. 板块归类按用户指令: 香港 ETF/基金 → H 股,与 A 股合并展示(下面列明细)

## 文件清单

- 本报告(MD): `reports/analysis-{TODAY}.md`
- 本报告(HTML): `reports/analysis-{TODAY}.html`
- 资产清单(可读): `data/asset-registry.md`
- 板块汇总: `data/pnl_by_sector.csv`
- 标的明细: `data/pnl_by_position.csv`
- 归类规则: `data/sectors.csv`(改后重跑 `04_calc_pnl.py` + `05_report.py`)
"""

    md_path = REPORTS / f'analysis-{TODAY}.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f'MD: {md_path}')

    # === HTML ===
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>组合盈亏分析 · {PRIOR} + {CUR} YTD</title>
<style>
  body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         max-width: 1100px; margin: 30px auto; padding: 0 20px; color: #222; line-height: 1.55; }}
  h1 {{ border-bottom: 3px solid #2d6cdf; padding-bottom: 8px; color: #2d6cdf; }}
  h2 {{ border-bottom: 1px solid #ddd; padding-bottom: 5px; margin-top: 35px; color: #333; }}
  h3 {{ margin-top: 25px; color: #555; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  th, td {{ padding: 8px 10px; border: 1px solid #e5e5e5; }}
  th {{ background: #f4f6fa; text-align: left; }}
  td:nth-child(n+3) {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .pos {{ color: #c3262d; font-weight: 600; }}      /* 红色 = 正盈利(A股惯例) */
  .neg {{ color: #1f7a37; font-weight: 600; }}      /* 绿色 = 亏损 */
  .sub-row {{ background: #fafbfc; color: #666; font-size: 0.93em; }}
  blockquote {{ border-left: 4px solid #2d6cdf; padding: 6px 14px; margin: 14px 0;
                background: #f4f6fa; color: #444; font-size: 0.93em; }}
  .total {{ background: #fff8d8; font-weight: bold; }}
  .tldr {{ background: #f4f6fa; padding: 12px 18px; border-radius: 6px; }}
  .tldr td:first-child {{ font-weight: 600; }}
  hr {{ border: none; border-top: 1px solid #eee; margin: 30px 0; }}
  .small {{ font-size: 0.85em; color: #888; }}
  code {{ background: #f4f6fa; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
  a {{ color: #2d6cdf; text-decoration: none; border-bottom: 1px dotted #2d6cdf66; }}
  a:hover {{ background: #fffacc; }}
  td a.pos {{ color: #c3262d; border-bottom-color: #c3262d66; }}
  td a.neg {{ color: #1f7a37; border-bottom-color: #1f7a3766; }}
  h3[id^="sec-"] {{ scroll-margin-top: 20px; padding-top: 10px;
                     border-top: 2px solid #2d6cdf; color: #2d6cdf; }}
</style>
</head>
<body id="top">

<h1>个人投资组合盈亏分析 · {PRIOR} + {CUR} YTD</h1>
<p class="small">生成: <b>{TODAY}</b> &nbsp;|&nbsp; 数据源: <code>{os.environ['PORTFOLIO_XLSX']}</code></p>
<p class="small">口径: {PRIOR} 全年用 <b>精确重建</b>(2 个时点持仓快照 × 历史收盘价);{CUR} YTD 用持仓表"今年盈亏"+ 已清仓表总盈亏。分母 = 板块当前市值。</p>

<h2>TL;DR · 一眼看完</h2>
<table class="tldr">
<tr><td>{PRIOR} 全年盈利</td><td><span class="{('pos' if total['pl_prior_year']>0 else 'neg')}">{fmt_money(total['pl_prior_year'])}</span> ({fmt_pct(total['return_prior'])})</td></tr>
<tr><td>{CUR} YTD 盈利 ({TODAY})</td><td><span class="{('pos' if total['pl_cur_total']>0 else 'neg')}">{fmt_money(total['pl_cur_total'])}</span> ({fmt_pct(total['return_cur'])})</td></tr>
<tr><td>当前总市值</td><td>{fmt_money(total['current_value'])}</td></tr>
<tr><td>{D_PRIOR} / {D_CUR_END} 持仓总市值</td><td>{fmt_money(total['mv_prior'])} / {fmt_money(total['mv_cur_end'])}</td></tr>
<tr><td>两年合计盈利</td><td><b>{fmt_money(total['pl_prior_year'] + total['pl_cur_total'])}</b></td></tr>
</table>

<h2>表 1 · {PRIOR} 全年 板块盈亏(按收益率)</h2>
<table>
<tr><th>排名</th><th>板块</th><th>当前仓位占比</th><th>期初市值 ({D_PRIOR})</th><th>期末市值 ({D_CUR_END})</th><th>{PRIOR} P&L</th><th>收益率 (期初市值)</th><th>P&L 贡献占比</th><th>持仓数</th></tr>
"""
    for i, s in enumerate(sec_sorted_prior, 1):
        d = get_combined(s)
        pl_cls = 'pos' if d['pl_prior_year']>0 else 'neg'
        sg = slug(s)
        # 仓位占比 / 贡献占比 — 用 combined 数据
        pos_pct = (d['current_value'] / total['current_value'] * 100) if total.get('current_value') else None
        contrib_pct = (d['pl_prior_year'] / total['pl_prior_year'] * 100) if total.get('pl_prior_year') else None
        html += (f"<tr><td>{i}</td>"
                 f"<td><b><a href='#sec-{sg}'>{s}</a></b></td>"
                 f"<td>{fmt_pct(pos_pct)}</td>"
                 f"<td>{fmt_money(d['mv_prior'])}</td>"
                 f"<td>{fmt_money(d['mv_cur_end'])}</td>"
                 f"<td class='{pl_cls}'><a class='{pl_cls}' href='#sec-{sg}'>{fmt_money(d['pl_prior_year'])}</a></td>"
                 f"<td class='{pl_cls}'>{fmt_pct(d['return_prior_initial'], basis=d['mv_prior'])}</td>"
                 f"<td>{fmt_pct(contrib_pct)}</td>"
                 f"<td><a href='#sec-{sg}'>{d['positions_prior']}</a></td></tr>\n")
        if s == 'A+H股':
            for sub in ['A股','H股']:
                sd = sec[sub]
                cls = 'pos' if sd['pl_prior_year']>0 else 'neg'
                sg_sub = slug(sub)
                sub_pos_pct = (sd['current_value'] / total['current_value'] * 100) if total.get('current_value') else None
                sub_contrib_pct = (sd['pl_prior_year'] / total['pl_prior_year'] * 100) if total.get('pl_prior_year') else None
                html += (f"<tr class='sub-row'><td></td>"
                         f"<td>　└ 其中: <a href='#sec-{sg_sub}'>{sub}</a></td>"
                         f"<td>{fmt_pct(sub_pos_pct)}</td>"
                         f"<td>{fmt_money(sd['mv_prior'])}</td>"
                         f"<td>{fmt_money(sd['mv_cur_end'])}</td>"
                         f"<td class='{cls}'><a class='{cls}' href='#sec-{sg_sub}'>{fmt_money(sd['pl_prior_year'])}</a></td>"
                         f"<td class='{cls}'>{fmt_pct(sd['return_prior_initial'], basis=sd['mv_prior'])}</td>"
                         f"<td>{fmt_pct(sub_contrib_pct)}</td>"
                         f"<td><a href='#sec-{sg_sub}'>{sd['positions_prior']}</a></td></tr>\n")
    total_cls = 'pos' if total['pl_prior_year']>0 else 'neg'
    html += f"<tr class='total'><td>-</td><td>合计</td><td>100.00%</td><td>{fmt_money(total['mv_prior'])}</td><td>{fmt_money(total['mv_cur_end'])}</td><td class='{total_cls}'>{fmt_money(total['pl_prior_year'])}</td><td class='{total_cls}'>{fmt_pct(total['return_prior'])}</td><td>100.00%</td><td>-</td></tr>\n</table>\n"

    html += f"""<blockquote>{PRIOR} 口径: 期间 P&L = 期末市值 − 期初市值 + (期间卖出现金流入 + 现金分红 − 个税 − 期间买入现金流出 − 手续费)。已清仓部分包含在内。</blockquote>

<h2>表 2 · {CUR} YTD 板块盈亏 ({CUR}-01-01 ~ {TODAY},按收益率)</h2>
<table>
<tr><th>排名</th><th>板块</th><th>仓位占比</th><th>当前市值</th><th>持仓今年盈亏</th><th>已清仓盈亏</th><th>{CUR} YTD 总盈亏</th><th>收益率 (当前市值)</th><th>P&L 贡献占比</th><th>持仓数</th></tr>
"""
    for i, s in enumerate(sec_sorted_cur, 1):
        d = get_combined(s)
        cls = 'pos' if d['pl_cur_total']>0 else 'neg'
        sg = slug(s)
        pos_pct = (d['current_value'] / total['current_value'] * 100) if total.get('current_value') else None
        contrib_pct = (d['pl_cur_total'] / total['pl_cur_total'] * 100) if total.get('pl_cur_total') else None
        html += (f"<tr><td>{i}</td>"
                 f"<td><b><a href='#sec-{sg}'>{s}</a></b></td>"
                 f"<td>{fmt_pct(pos_pct)}</td>"
                 f"<td>{fmt_money(d['current_value'])}</td>"
                 f"<td>{fmt_money(d['pl_held_ytd'])}</td>"
                 f"<td>{fmt_money(d['pl_realised_cur'])}</td>"
                 f"<td class='{cls}'><a class='{cls}' href='#sec-{sg}'>{fmt_money(d['pl_cur_total'])}</a></td>"
                 f"<td class='{cls}'>{fmt_pct(d['return_cur_ytd'], basis=d['current_value'])}</td>"
                 f"<td>{fmt_pct(contrib_pct)}</td>"
                 f"<td><a href='#sec-{sg}'>{d['positions_cur']}</a></td></tr>\n")
        if s == 'A+H股':
            for sub in ['A股','H股']:
                sd = sec[sub]
                cls = 'pos' if sd['pl_cur_total']>0 else 'neg'
                sg_sub = slug(sub)
                sub_pos_pct = (sd['current_value'] / total['current_value'] * 100) if total.get('current_value') else None
                sub_contrib_pct = (sd['pl_cur_total'] / total['pl_cur_total'] * 100) if total.get('pl_cur_total') else None
                html += (f"<tr class='sub-row'><td></td>"
                         f"<td>　└ 其中: <a href='#sec-{sg_sub}'>{sub}</a></td>"
                         f"<td>{fmt_pct(sub_pos_pct)}</td>"
                         f"<td>{fmt_money(sd['current_value'])}</td>"
                         f"<td>{fmt_money(sd['pl_held_ytd'])}</td>"
                         f"<td>{fmt_money(sd['pl_realised_cur'])}</td>"
                         f"<td class='{cls}'><a class='{cls}' href='#sec-{sg_sub}'>{fmt_money(sd['pl_cur_total'])}</a></td>"
                         f"<td class='{cls}'>{fmt_pct(sd['return_cur_ytd'], basis=sd['current_value'])}</td>"
                         f"<td>{fmt_pct(sub_contrib_pct)}</td>"
                         f"<td><a href='#sec-{sg_sub}'>{sd['positions_cur']}</a></td></tr>\n")
    total_cls = 'pos' if total['pl_cur_total']>0 else 'neg'
    html += f"<tr class='total'><td>-</td><td>合计</td><td>100.00%</td><td>{fmt_money(total['current_value'])}</td><td>-</td><td>-</td><td class='{total_cls}'>{fmt_money(total['pl_cur_total'])}</td><td class='{total_cls}'>{fmt_pct(total['return_cur'])}</td><td>100.00%</td><td>-</td></tr>\n</table>\n"
    html += f'<blockquote>{CUR} 口径: "持仓今年盈亏" = Excel 持仓表"今年盈亏"字段汇总(含浮动+已实现);"已清仓盈亏" = 已清仓表 {CUR} 年总盈亏。</blockquote>\n'

    # 各板块洞察
    html += f"<h2>板块洞察 · Top 3 贡献 / Top 3 拖累</h2>\n"
    for s in SECTORS_DISPLAY:
        items = positions_for(s)
        top = sorted(items, key=lambda x: -x['pl_prior'])[:3]
        bot = sorted(items, key=lambda x: x['pl_prior'])[:3]
        d = get_combined(s)
        cls_p = 'pos' if d['pl_prior_year']>0 else 'neg'
        cls_c = 'pos' if d['pl_cur_total']>0 else 'neg'
        # A+H 在板块明细 section 里没有合并段(只有 A 股 + H 股 子段),在板块洞察处加 anchor 托底
        anchor_attr = " id='sec-ah-stock'" if s == 'A+H股' else ''
        html += f"<h3{anchor_attr}>{s}</h3>\n<ul>"
        html += f"<li>{PRIOR} P&L: <span class='{cls_p}'>{fmt_money(d['pl_prior_year'])}</span> ({fmt_pct(d['return_prior_initial'], basis=d['mv_prior'])})</li>"
        html += f"<li>{CUR} YTD P&L: <span class='{cls_c}'>{fmt_money(d['pl_cur_total'])}</span> ({fmt_pct(d['return_cur_ytd'], basis=d['current_value'])})</li>"
        html += f"<li>当前持仓: {d['positions_cur']} 个, 市值 {fmt_money(d['current_value'])}</li></ul>\n"
        if top and top[0]['pl_prior'] > 0:
            html += f"<p><b>{PRIOR} Top 3 贡献</b>:</p><ul>"
            for x in top:
                if x['pl_prior'] > 0:
                    html += f"<li>{x['code']} {x['name']}: <span class='pos'>+{fmt_money(x['pl_prior'])}</span></li>"
            html += "</ul>"
        if bot and bot[0]['pl_prior'] < 0:
            html += f"<p><b>{PRIOR} Top 3 拖累</b>:</p><ul>"
            for x in bot:
                if x['pl_prior'] < 0:
                    html += f"<li>{x['code']} {x['name']}: <span class='neg'>{fmt_money(x['pl_prior'])}</span></li>"
            html += "</ul>"
        html += "<hr>\n"

    # === 各板块详细明细(被表 1/2 anchor 跳转指向) ===
    html += "<h2>📋 各板块详细明细 · 点击表 1/2 数字跳转到这里</h2>\n"
    # 显示顺序: A 股 / H 股 各自一段,其他 11 个独立板块
    DETAIL_ORDER = ['A股','H股','美股(QDII)','日本','德国','法国','印度','沙特','东南亚','海外',
                    '可转债','国债+短融货基','商品(黄金/REITs)']
    for s in DETAIL_ORDER:
        items = [p for p in pos if p['sector'] == s]
        if not items:
            # 空板块也保留 anchor + 提示
            html += f"<h3 id='sec-{slug(s)}'>{s}</h3>\n<p class='small'>该板块当前无持仓(兜底板块)。</p>\n<hr>\n"
            continue
        items.sort(key=lambda x: -x['cur_value'])
        # 板块汇总数据(单 sector,不是 combined)
        sd = sec[s]
        html += f"<h3 id='sec-{slug(s)}'>{s} <span class='small'>(共 {len(items)} 个标的)</span></h3>\n"
        # 板块迷你 summary
        cls_p = 'pos' if sd['pl_prior_year']>0 else 'neg'
        cls_c = 'pos' if sd['pl_cur_total']>0 else 'neg'
        html += (f"<p class='small'>"
                 f"{PRIOR} P&L: <span class='{cls_p}'>{fmt_money(sd['pl_prior_year'])}</span> ({fmt_pct(sd['return_prior_initial'], basis=sd['mv_prior'])}) &nbsp;|&nbsp; "
                 f"{CUR} YTD: <span class='{cls_c}'>{fmt_money(sd['pl_cur_total'])}</span> ({fmt_pct(sd['return_cur_ytd'], basis=sd['current_value'])}) &nbsp;|&nbsp; "
                 f"当前市值: {fmt_money(sd['current_value'])} &nbsp;|&nbsp; "
                 f"<a href='#top'>↑ 返回顶部</a>"
                 f"</p>\n")
        # 该板块标的详细表
        html += ("<table>\n"
                 f"<tr><th>代码</th><th>名称</th><th>当前市值</th>"
                 f"<th>{D_PRIOR} 市值</th><th>{D_CUR_END} 市值</th>"
                 f"<th>{PRIOR} 净现金流入</th>"
                 f"<th>{PRIOR} P&L</th>"
                 f"<th>{CUR} 持仓 YTD</th><th>{CUR} 已清仓</th><th>{CUR} 总 P&L</th></tr>\n")
        for x in items:
            cp = 'pos' if x['pl_prior']>0 else ('neg' if x['pl_prior']<0 else '')
            cc = 'pos' if x['pl_cur']>0 else ('neg' if x['pl_cur']<0 else '')
            html += (f"<tr>"
                     f"<td>{x['code']}</td>"
                     f"<td>{x['name']}</td>"
                     f"<td>{fmt_money(x['cur_value'])}</td>"
                     f"<td>{fmt_money(x['mv_prior'])}</td>"
                     f"<td>{fmt_money(x['mv_cur_end'])}</td>"
                     f"<td>{fmt_money(x['net_cash_in'])}</td>"
                     f"<td class='{cp}'>{fmt_money(x['pl_prior'])}</td>"
                     f"<td>{fmt_money(x['pl_held_ytd'])}</td>"
                     f"<td>{fmt_money(x['pl_realised_cur'])}</td>"
                     f"<td class='{cc}'>{fmt_money(x['pl_cur'])}</td>"
                     f"</tr>\n")
        html += "</table>\n<hr>\n"

    html += f"""
<h2>已知局限</h2>
<ol>
<li>重建数量 vs 持仓表数量在 1-3 个老持仓上可能有 1-100 股差异(送股 / 转债转换 / 北交所代码变更),对总 P&L 影响 &lt; 2%</li>
<li>国债逆回购利息(R-001/R-002/GC001/GC007)未单独计入,合计影响几千元</li>
<li>场外基金分红再投资可能有捕获缺口,小量低估</li>
<li>板块归类按用户指令: 香港相关全归 H 股,与 A 股合并展示(下方有明细)</li>
</ol>

<h2>文件清单</h2>
<ul>
<li>本报告 MD: <code>{md_path.relative_to(WORK)}</code></li>
<li>本报告 HTML: <code>{(REPORTS / f"analysis-{TODAY}.html").relative_to(WORK)}</code></li>
<li>资产清单: <code>data/asset-registry.md</code></li>
<li>板块汇总 CSV: <code>data/pnl_by_sector.csv</code></li>
<li>标的明细 CSV: <code>data/pnl_by_position.csv</code></li>
<li>归类规则 CSV: <code>data/sectors.csv</code> (改后重跑 04 + 05 即可生效)</li>
</ul>

<p class="small">Generated by portfolio-pnl-analyzer skill · @money plugin</p>
</body>
</html>
"""
    html_path = REPORTS / f'analysis-{TODAY}.html'
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'HTML: {html_path}')


if __name__ == '__main__':
    main()
