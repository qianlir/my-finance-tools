#!/usr/bin/env python3
"""生成资产清单 data/asset-registry.md(人可读)+ data/sectors.csv(机器可读)。

每个标的打多个标签:主板块 / 市场 / 资产类型 / 行业 / 风险等级。

主板块共 7 类:
  A股 / H股 / 美股(QDII) / 海外其他 / 可转债 / 国债+短融货基 / 商品(黄金/REITs)

资产类型: 个股 / ETF / LOF / 转债 / 货基
市场: A股 / 香港 / 美国 / 海外其他
行业(可选): 科技 / 消费 / 金融 / 医药 / 能源 / 制造 / 周期 / 宽基 / 红利 / 主题 / ...
风险: 低 / 中低 / 中 / 中高 / 高

环境变量:
  PORTFOLIO_XLSX
  PORTFOLIO_WORK_DIR
  PORTFOLIO_PRIOR_YEAR
  PORTFOLIO_CUR_YEAR
  PORTFOLIO_TODAY
"""
import os
import csv
import openpyxl
from pathlib import Path
from collections import Counter

SRC = Path(os.environ['PORTFOLIO_XLSX']).expanduser()
WORK = Path(os.environ['PORTFOLIO_WORK_DIR']).expanduser()
PRIOR = int(os.environ['PORTFOLIO_PRIOR_YEAR'])
CUR = int(os.environ['PORTFOLIO_CUR_YEAR'])
TODAY = os.environ['PORTFOLIO_TODAY']
DATA = WORK / 'data'

# Skill 级归类基线 — 用户累积的"权威归类" (优先级最高)
# 优先用 PORTFOLIO_SKILL_DIR 环境变量(run_analysis 注入);
# 否则尝试 __file__ 推导(skill 源码位置);
# 最后 fallback 到 money 项目硬编码路径
def _find_skill_dir():
    env_dir = os.environ.get('PORTFOLIO_SKILL_DIR')
    if env_dir and (Path(env_dir) / 'references' / 'sector-overrides.csv').exists():
        return Path(env_dir)
    # __file__ 推导
    src_dir = Path(__file__).resolve().parent.parent
    if (src_dir / 'references' / 'sector-overrides.csv').exists():
        return src_dir
    # 兜底: money 项目下固定位置
    fallback = Path('/Users/cmwang/work/money/.claude/skills/portfolio-pnl-analyzer')
    if (fallback / 'references' / 'sector-overrides.csv').exists():
        return fallback
    return None

SKILL_DIR = _find_skill_dir()
OVERRIDES_PATH = (SKILL_DIR / 'references' / 'sector-overrides.csv') if SKILL_DIR else None

OVERRIDES = {}   # code → {sector, markets, asset_type, industries, risk}
if OVERRIDES_PATH and OVERRIDES_PATH.exists():
    with open(OVERRIDES_PATH, encoding='utf-8') as _f:
        _r = csv.DictReader(_f)
        for _row in _r:
            if _row.get('code') and _row.get('sector'):
                OVERRIDES[_row['code']] = {
                    'sector': _row.get('sector') or '',
                    'markets': _row.get('markets') or '',
                    'asset_type': _row.get('asset_type') or '',
                    'industries': _row.get('industries') or '',
                    'risk': _row.get('risk') or '',
                    'name_override': _row.get('name') or '',
                }
    print(f'[03b] 加载 {len(OVERRIDES)} 条 skill 级归类基线(7 列) ← {OVERRIDES_PATH}')
else:
    print(f'[03b] 未找到 skill 基线,使用默认规则')

# 代码级 fallback 规则(基线里没有的新代码才用)
EXPLICIT_SECTOR = {
    # 港股相关 → H 股
    '160125': 'H股', '161124': 'H股', '501301': 'H股',
    '003441': 'H股', '03441': 'H股',
    '003442': 'H股', '03442': 'H股',
    '513550': 'H股', '513010': 'H股', '159711': 'H股',
    # 商品类边界
    '160221': '商品(黄金/REITs)', '160416': '商品(黄金/REITs)',
    '161217': '商品(黄金/REITs)', '161226': '商品(黄金/REITs)',
    '162719': '商品(黄金/REITs)', '163208': '商品(黄金/REITs)',
    '165520': '商品(黄金/REITs)',
    # 美股 QDII 边界
    '160644': '美股(QDII)', '501225': '美股(QDII)',
    # 债券 LOF
    '161216': '国债+短融货基', '160622': '国债+短融货基', '161716': '国债+短融货基',
    # A 股大类
    '161810': 'A股', '168204': 'A股',
}


def classify_sector(code: str, name: str) -> str:
    # 优先级 1: skill 级基线(用户累积知识)
    if code in OVERRIDES: return OVERRIDES[code]['sector']
    # 优先级 2: 脚本内 explicit
    if code in EXPLICIT_SECTOR: return EXPLICIT_SECTOR[code]
    name = name or ''
    us_kw = ['纳指','纳斯达克','纳100','标普','道琼斯','美国','美股','海外科技',
             '美国REIT','海外REIT','美国50','纳指基金','纳指LOF','纳指ETF',
             '纳指100','纳指指数','纳指科技','纳指生物','油气ETF','华宝油气',
             '标普科技','标普医药','标普生物','标普生科','标普油气','标普500',
             '标普消费','标普ETF']
    if any(k in name for k in us_kw): return '美股(QDII)'
    overseas = ['印度','日经','日本','德国','法国','越南','东证','东南亚','沙特','225ETF']
    if any(k in name for k in overseas): return '海外其他'
    if len(code) == 5 and code.isdigit() and code.startswith('0'): return 'H股'
    if '港股' in name or '香港' in name: return 'H股'
    if code.startswith(('11','12')) and len(code) == 6 and code.isdigit(): return '可转债'
    bond_kw = ['国债','短融','政金债','国开','货基','银华日利','十年国债','双债']
    if any(k in name for k in bond_kw): return '国债+短融货基'
    cmd_kw = ['黄金','原油','大宗商品','嘉实原油','南方原油','银华通胀',
              'REIT','国泰商品','石油','有色','资源','煤','白银','油气']
    if any(k in name for k in cmd_kw): return '商品(黄金/REITs)'
    return 'A股'


def asset_type(code: str, name: str) -> str:
    name = name or ''
    if code.startswith(('11','12')) and len(code) == 6 and code.isdigit(): return '转债'
    if '货基' in name or '日利' in name: return '货基'
    if code.startswith(('51','56','58','15','17','18','50','20','68')) and len(code) == 6: return 'ETF'
    if code.startswith('16') and len(code) == 6: return 'LOF'
    if code.startswith('501') and len(code) == 6: return 'ETF/QDII'
    if code.startswith(('5','13','14','5')) and len(code) == 6: return 'ETF'
    return '个股'


def market(code: str, sector: str) -> str:
    if sector == 'H股': return '香港'
    if sector == '美股(QDII)': return '美国'
    if sector == '海外其他': return '海外'
    return 'A股'


def risk_level(code: str, name: str, sector: str) -> str:
    if sector == '国债+短融货基':
        if '30年' in (name or ''): return '中低'   # 长债利率波动
        if '短融' in (name or '') or '日利' in (name or ''): return '极低'
        return '低'
    if sector == '可转债': return '中'
    if sector == '商品(黄金/REITs)':
        if '黄金' in (name or ''): return '中'
        if '原油' in (name or '') or '油气' in (name or ''): return '中高'
        return '中'
    if sector == '美股(QDII)':
        if '纳指' in (name or '') or '科技' in (name or ''): return '高'
        return '中高'
    if sector == 'H股':
        if '小盘' in (name or ''): return '高'
        return '中高'
    if sector == '海外其他':
        return '中高'
    # A 股
    name = name or ''
    if asset_type(code, name) in ('ETF','LOF') and any(k in name for k in ['300','500','A500','红利','低波','宽基','沪深']):
        return '中'
    if asset_type(code, name) == '个股':
        return '中高'
    return '中'


def industry(code: str, name: str, sector: str) -> str:
    name = name or ''
    if sector in ('可转债','国债+短融货基','商品(黄金/REITs)'):
        return ''  # 不打行业
    kws = {
        '科技': ['纳指','科技','互联网','5G','半导体','芯片','软件','云','人工智能','AI','创新'],
        '消费': ['消费','白酒','酒','食品','零食','五粮','茅台','洽洽','潮宏'],
        '医药': ['医药','医疗','生物','生科','药','疫苗'],
        '金融': ['银行','证券','保险','金融'],
        '能源': ['能源','电','油气','石油','煤'],
        '宽基': ['300','500','1000','A500','A50','沪深','宽基'],
        '红利': ['红利','低波','分红','100红利'],
        '周期': ['有色','钢','化工','建材','资源','煤'],
        '地产': ['地产','万科','张江'],
        '基建': ['长江电力','大秦铁路','华能','移动','工商','农业'],
        '创业': ['创业','科创','双创'],
        '主题': ['印度','日本','法国','德国','越南','沙特','日经','东南亚','东证','南方香港','香港']
    }
    for ind, ks in kws.items():
        if any(k in name for k in ks): return ind
    return ''


def main():
    codes = {}
    for snap_date in [f'{PRIOR-1}-12-31', f'{PRIOR}-12-31', TODAY]:
        path = DATA / f'snapshot_{snap_date.replace("-","")}.csv'
        if not path.exists(): continue
        with open(path) as f:
            next(f)
            for row in csv.reader(f):
                if row[0] not in codes: codes[row[0]] = row[1]
    for p in [str(PRIOR), str(CUR)]:
        path = DATA / f'cashflow_{p}.csv'
        if not path.exists(): continue
        with open(path) as f:
            next(f)
            for row in csv.reader(f):
                if row[0] not in codes: codes[row[0]] = row[1]
    wb = openpyxl.load_workbook(SRC, data_only=True)
    for sheet_name, code_col, name_col in [('已清仓', 2, 3), ('持仓数据', 1, 2)]:
        if sheet_name not in wb.sheetnames: continue
        ws = wb[sheet_name]
        for r in range(2, ws.max_row+1):
            c = ws.cell(r, code_col).value
            n = ws.cell(r, name_col).value
            if not c or str(c) == '汇总': continue
            c_s = str(c).zfill(6) if str(c).isdigit() and len(str(c)) <= 6 else str(c)
            if len(str(c)) == 5 and str(c).isdigit(): c_s = str(c)
            if c_s not in codes: codes[c_s] = n

    # 当前持仓表 — 算每标的当前市值(用于排序展示)
    cur_value = {}
    ws = wb['持仓数据']
    for r in range(2, ws.max_row+1):
        c = ws.cell(r, 1).value
        if not c or str(c) == '汇总': continue
        c_s = str(c).zfill(6) if str(c).isdigit() and len(str(c)) <= 6 else str(c)
        if len(str(c)) == 5 and str(c).isdigit(): c_s = str(c)
        cur_value[c_s] = float(ws.cell(r, 3).value or 0)

    # 应用归类 — 优先用 OVERRIDES 里的全部 5 维(skill 基线是权威),
    # 否则才走默认规则推断
    rows = []
    for code in sorted(codes.keys()):
        name = codes[code] or ''
        ov = OVERRIDES.get(code)
        if ov:
            sec = ov['sector'] or classify_sector(code, name)
            mk = ov['markets'] or market(code, sec)
            at = ov['asset_type'] or asset_type(code, name)
            ind = ov['industries'] or industry(code, name, sec)
            rsk = ov['risk'] or risk_level(code, name, sec)
        else:
            sec = classify_sector(code, name)
            mk = market(code, sec)
            at = asset_type(code, name)
            ind = industry(code, name, sec)
            rsk = risk_level(code, name, sec)
        rows.append({
            'code': code, 'name': name,
            'sector': sec, 'markets': mk, 'asset_type': at,
            'industries': ind, 'risk': rsk,
            'current_value': cur_value.get(code, 0),
        })

    # 写 sectors.csv (机器可读,只含主板块,给 04_calc_pnl 用)
    with open(DATA / 'sectors.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['code','name','sector'])
        for r in rows:
            w.writerow([r['code'], r['name'], r['sector']])

    # 写 asset_registry.csv(全 7 列 schema)
    with open(DATA / 'asset_registry.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['code','name','sector','markets','asset_type',
                                          'industries','risk','current_value'])
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in ['code','name','sector','markets','asset_type',
                                          'industries','risk','current_value']})

    # 写 asset-registry.md (人可读,按板块分组,按当前市值排序)
    SECTORS = ['A股','H股','美股(QDII)','日本','德国','法国','印度','沙特','东南亚','海外',
               '可转债','国债+短融货基','商品(黄金/REITs)']
    md = f"""# 资产清单 · 全标的多维标签

**生成**: {TODAY} · **来源**: `{SRC}`

> 每个标的打 5 个标签:**主板块** / 市场 / 资产类型 / 行业 / 风险等级。
> 此清单决定板块汇总。若想调整某标的归类:编辑 `data/sectors.csv` 后重跑 `04_calc_pnl.py` + `05_report.py`。

"""
    sec_count = Counter(r['sector'] for r in rows)
    total_value = sum(r['current_value'] for r in rows)
    md += "## 总览\n\n"
    md += f"| 主板块 | 标的数 | 当前市值 | 占比 |\n|---|---:|---:|---:|\n"
    for s in SECTORS:
        sv = sum(r['current_value'] for r in rows if r['sector']==s)
        md += f"| **{s}** | {sec_count.get(s, 0)} | ¥{sv:,.0f} | {sv/total_value*100 if total_value else 0:.1f}% |\n"
    md += f"| **合计** | {sum(sec_count.values())} | ¥{total_value:,.0f} | 100.0% |\n\n"

    # 按板块分组列表
    for s in SECTORS:
        sec_rows = [r for r in rows if r['sector']==s]
        sec_rows.sort(key=lambda x: -x['current_value'])
        md += f"\n## {s} ({len(sec_rows)} 个,当前市值 ¥{sum(r['current_value'] for r in sec_rows):,.0f})\n\n"
        md += "| 代码 | 名称 | 当前市值 | 市场 | 类型 | 行业 | 风险 |\n|---|---|---:|---|---|---|---|\n"
        for r in sec_rows:
            md += f"| {r['code']} | {r['name']} | ¥{r['current_value']:,.0f} | {r['markets']} | {r['asset_type']} | {r['industries']} | {r['risk']} |\n"
        md += "\n"

    with open(DATA / 'asset-registry.md', 'w', encoding='utf-8') as f:
        f.write(md)

    print(f'\n=== 归类结果 ===')
    for s in SECTORS:
        sv = sum(r['current_value'] for r in rows if r['sector']==s)
        print(f'  {s}: {sec_count.get(s, 0)} 个, 当前市值 ¥{sv:,.0f}')
    print(f'\n资产清单已写入: {DATA / "asset-registry.md"}')


if __name__ == '__main__':
    main()
