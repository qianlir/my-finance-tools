#!/usr/bin/env python3
"""计算 prior_year 区间盈亏 + cur_year YTD 盈亏(按标的 + 按板块)。

环境变量同上。

输出:
  data/pnl_by_position.csv
  data/pnl_by_sector.csv
  data/pnl_summary.json
"""
import os
import csv
import json
import openpyxl
from collections import defaultdict
from pathlib import Path

SRC = Path(os.environ['PORTFOLIO_XLSX']).expanduser()
WORK = Path(os.environ['PORTFOLIO_WORK_DIR']).expanduser()
PRIOR = int(os.environ['PORTFOLIO_PRIOR_YEAR'])
CUR = int(os.environ['PORTFOLIO_CUR_YEAR'])
TODAY = os.environ['PORTFOLIO_TODAY']
DATA = WORK / 'data'

D_PRIOR = f'{PRIOR-1}-12-31'  # 期初
D_CUR_END = f'{PRIOR}-12-31'   # prior_year 期末

SECTORS = ['A股','H股','美股(QDII)','日本','德国','法国','印度','沙特','东南亚','海外',
           '可转债','国债+短融货基','商品(黄金/REITs)']


def load_snap(date_str):
    snap = {}
    path = DATA / f'snapshot_{date_str.replace("-","")}.csv'
    if not path.exists(): return snap
    with open(path) as f:
        next(f)
        for row in csv.reader(f):
            snap[row[0]] = {'name': row[1], 'qty': float(row[2])}
    return snap


def load_prices():
    p = {}
    with open(DATA / 'prices.csv') as f:
        for r in csv.DictReader(f):
            p[r['code']] = {
                'p_prior': float(r[f'price_{D_PRIOR}']) if r[f'price_{D_PRIOR}'] else None,
                'p_cur': float(r[f'price_{D_CUR_END}']) if r[f'price_{D_CUR_END}'] else None,
            }
    return p


def load_cashflow(year):
    cf = {}
    path = DATA / f'cashflow_{year}.csv'
    if not path.exists(): return cf
    with open(path) as f:
        for r in csv.DictReader(f):
            cf[r['code']] = {
                'name': r['name'],
                'buy_amt': float(r['buy_amt']), 'sell_amt': float(r['sell_amt']),
                'dividend': float(r['dividend']), 'tax': float(r['tax']),
                'fee': float(r['fee']),
            }
    return cf


def load_sectors():
    s = {}
    with open(DATA / 'sectors.csv') as f:
        for r in csv.DictReader(f):
            s[r['code']] = r['sector']
    return s


def main():
    snap_prior = load_snap(D_PRIOR)
    snap_cur_end = load_snap(D_CUR_END)
    snap_today = load_snap(TODAY)
    prices = load_prices()
    cf_prior = load_cashflow(PRIOR)
    cf_cur = load_cashflow(CUR)
    sectors = load_sectors()

    # 不使用清仓表 — 纯交易记录算法
    realised_prior = defaultdict(float)
    realised_cur = defaultdict(float)
    realised_prior_meta = {}
    realised_cur_meta = {}

    wb = openpyxl.load_workbook(SRC, data_only=True)
    print(f'[B 口径] 不使用已清仓 sheet,纯交易记录 + 市值重建')

    ytd_cur_by_code = {}
    ws = wb['持仓数据']
    for r in range(2, ws.max_row+1):
        c = ws.cell(r, 1).value
        n = ws.cell(r, 2).value
        ytd = ws.cell(r, 16).value or 0
        cum = ws.cell(r, 12).value or 0
        if not c or str(c) == '汇总': continue
        c_s = str(c).zfill(6) if str(c).isdigit() and len(str(c)) <= 6 else str(c)
        if len(str(c)) == 5 and str(c).isdigit(): c_s = str(c)
        # col 21 = 最新价(用作 today 价格,免联网)
        ytd_cur_by_code[c_s] = {'name': n, 'ytd': ytd, 'cum': cum,
                                  'value': float(ws.cell(r, 3).value or 0),
                                  'qty': float(ws.cell(r, 18).value or 0),
                                  'price_today': float(ws.cell(r, 21).value or 0)}

    # prior_year P&L (精确重建)
    pl_prior = {}
    all_codes = set(snap_prior) | set(snap_cur_end) | set(cf_prior) | set(realised_prior)
    missing = []
    for code in all_codes:
        name = (snap_cur_end.get(code,{}).get('name')
                or snap_prior.get(code,{}).get('name')
                or cf_prior.get(code,{}).get('name')
                or realised_prior_meta.get(code, '?'))
        q_p = snap_prior.get(code,{}).get('qty', 0)
        q_c = snap_cur_end.get(code,{}).get('qty', 0)
        p_p = prices.get(code,{}).get('p_prior')
        p_c = prices.get(code,{}).get('p_cur')
        cf = cf_prior.get(code, {'buy_amt':0,'sell_amt':0,'dividend':0,'tax':0,'fee':0})

        mv_p = (q_p * p_p) if (q_p > 0 and p_p) else 0
        mv_c = (q_c * p_c) if (q_c > 0 and p_c) else 0
        net_in = cf['sell_amt'] + cf['dividend'] + cf['tax'] - cf['buy_amt'] - cf['fee']
        pl = mv_c - mv_p + net_in

        is_missing = (q_p > 0 and not p_p) or (q_c > 0 and not p_c)
        if is_missing: missing.append(code)

        pl_prior[code] = {
            'name': name, 'sector': sectors.get(code, 'A股'),
            'mv_prior': mv_p, 'mv_cur_end': mv_c, 'net_cash_in': net_in,
            'pl_prior_year': pl, 'missing_price': is_missing,
        }

    # 检测"LOF 套利模式"标的 — 这类标的的"股份转入/转出"无法准确算 P&L,改用持仓表"今年盈亏"
    # 判断:该标的 2025 或 2026 内"转入+转出"笔数 / 总交易笔数 > 30%
    import openpyxl as _opx
    _wb = _opx.load_workbook(SRC, data_only=True, read_only=True)
    _ws = _wb['交易记录']
    _trade_stats = {}  # code -> {'total':n, 'transfer':n}
    for r in _ws.iter_rows(min_row=2, values_only=True):
        d = str(r[0])[:10] if r[0] else ''
        c = r[2]
        t = r[4]
        if not c or not t or not d[:4] in (str(PRIOR), str(CUR)): continue
        c_s = str(c).zfill(6) if str(c).isdigit() and len(str(c)) <= 6 else str(c)
        if len(str(c)) == 5 and str(c).isdigit(): c_s = str(c)
        s = _trade_stats.setdefault(c_s, {'total':0, 'transfer':0})
        s['total'] += 1
        if t in ('股份转入', '股份转出', '转债转入', '转债转出'):
            s['transfer'] += 1
    _wb.close()
    arbitrage_codes = {c for c, s in _trade_stats.items()
                       if s['total'] >= 5 and s['transfer']/s['total'] > 0.3}
    # 港股(5 位代码,0 开头)涉及汇率换算 → 信任同花顺(它已自动换汇)
    hk_codes = {c for c in (set(snap_today.keys()) | set(snap_cur_end.keys()))
                if len(c) == 5 and c.isdigit() and c.startswith('0')}
    trust_thinkstock = arbitrage_codes | hk_codes
    print(f'[Hybrid 算法] 套利标的 {len(arbitrage_codes)} + 港股 {len(hk_codes)} = {len(trust_thinkstock)} 个用同花顺字段')

    # cur_year YTD — Hybrid:B 算法默认,套利标的用同花顺字段
    pl_cur = {}
    all_codes_cur = set(snap_cur_end) | set(snap_today) | set(cf_cur) | set(realised_cur)
    missing_cur = []
    for code in all_codes_cur:
        name = (snap_today.get(code,{}).get('name')
                or ytd_cur_by_code.get(code,{}).get('name')
                or snap_cur_end.get(code,{}).get('name')
                or cf_cur.get(code,{}).get('name')
                or realised_cur_meta.get(code, '?'))
        # 期初:2025-12-31 持仓 × 2025-12-31 价
        q_start = snap_cur_end.get(code,{}).get('qty', 0)
        p_start = prices.get(code,{}).get('p_cur')
        mv_start = (q_start * p_start) if (q_start > 0 and p_start) else 0
        # 期末:当前持仓 × 持仓表"最新价"(免联网)
        q_end = snap_today.get(code,{}).get('qty', 0)
        p_end = ytd_cur_by_code.get(code,{}).get('price_today', 0)
        mv_end = (q_end * p_end) if (q_end > 0 and p_end) else 0
        # 期间现金流
        cf = cf_cur.get(code, {'buy_amt':0,'sell_amt':0,'dividend':0,'tax':0,'fee':0})
        net_in = cf['sell_amt'] + cf['dividend'] + cf['tax'] - cf['buy_amt'] - cf['fee']
        # Hybrid:套利标的 + 港股(汇率问题)回退用同花顺持仓表"今年盈亏"
        if code in trust_thinkstock and code in ytd_cur_by_code:
            pl_b = ytd_cur_by_code[code]['ytd']
            algo_used = 'thinkstock_ytd'
        else:
            pl_b = mv_end - mv_start + net_in
            algo_used = 'B'

        # 对账:同花顺持仓表"今年盈亏" + 已清仓表 2026 同代码累计(用户当年所有清仓)
        ths_ytd = ytd_cur_by_code.get(code, {}).get('ytd', 0)
        realised_2026 = realised_cur.get(code, 0)
        diff_vs_ths = pl_b - (ths_ytd + (realised_2026 if code not in ytd_cur_by_code else 0))
        is_missing = (q_start > 0 and not p_start) or (q_end > 0 and not p_end)
        if is_missing: missing_cur.append(code)

        cur_value = mv_end if mv_end > 0 else ytd_cur_by_code.get(code, {}).get('value', 0)
        pl_cur[code] = {
            'name': name, 'sector': sectors.get(code, 'A股'),
            'mv_2025_end': mv_start, 'mv_today': mv_end,
            'net_cash_in_2026': net_in,
            'pl_total': pl_b,                              # 新 B 口径主算
            'pl_held_ytd': ths_ytd,                        # 同花顺持仓表"今年盈亏"(对账用)
            'pl_realised': realised_2026,                  # 已清仓 2026(对账用)
            'recon_diff': diff_vs_ths,                     # B 算法 vs 同花顺差额
            'current_value': cur_value,
            'missing_price_cur': is_missing,
        }

    # by-position CSV
    with open(DATA / 'pnl_by_position.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['code','name','sector',
                    f'mv_{D_PRIOR}', f'mv_{D_CUR_END}', f'net_cash_in_{PRIOR}',
                    f'pl_{PRIOR}', 'missing_price_flag',
                    f'pl_held_ytd_{CUR}', f'pl_realised_{CUR}', f'pl_{CUR}_total',
                    'current_value'])
        all_c = set(pl_prior) | set(pl_cur)
        for code in sorted(all_c):
            a = pl_prior.get(code, {})
            b = pl_cur.get(code, {})
            w.writerow([code, a.get('name') or b.get('name'),
                        a.get('sector') or b.get('sector', '?'),
                        round(a.get('mv_prior', 0), 2),
                        round(a.get('mv_cur_end', 0), 2),
                        round(a.get('net_cash_in', 0), 2),
                        round(a.get('pl_prior_year', 0), 2),
                        a.get('missing_price', False),
                        round(b.get('pl_held_ytd', 0), 2),
                        round(b.get('pl_realised', 0), 2),
                        round(b.get('pl_total', 0), 2),
                        round(b.get('current_value', 0), 2)])

    # 板块汇总
    sec_agg = {s: {
        'mv_prior': 0, 'mv_cur_end': 0,
        'pl_prior_year': 0, 'pl_prior_missing': 0,
        'pl_cur_total': 0, 'pl_held_ytd': 0, 'pl_realised_cur': 0,
        'current_value': 0,
        'positions_prior': 0, 'positions_cur': 0,
    } for s in SECTORS}

    for code, d in pl_prior.items():
        s = d['sector'] if d['sector'] in sec_agg else 'A股'
        sec_agg[s]['mv_prior'] += d['mv_prior']
        sec_agg[s]['mv_cur_end'] += d['mv_cur_end']
        if not d['missing_price']:
            sec_agg[s]['pl_prior_year'] += d['pl_prior_year']
        else:
            sec_agg[s]['pl_prior_missing'] += 1
        if d['mv_prior'] > 0 or d['mv_cur_end'] > 0:
            sec_agg[s]['positions_prior'] += 1

    for code, d in pl_cur.items():
        s = d['sector'] if d['sector'] in sec_agg else 'A股'
        sec_agg[s]['pl_held_ytd'] += d['pl_held_ytd']
        sec_agg[s]['pl_realised_cur'] += d['pl_realised']
        sec_agg[s]['pl_cur_total'] += d['pl_total']
        sec_agg[s]['current_value'] += d['current_value']
        if d['pl_total'] != 0 or d['current_value'] > 0:
            sec_agg[s]['positions_cur'] += 1

    # 算 total 用于求占比
    total_cv = sum(d['current_value'] for d in sec_agg.values())
    total_pl_prior = sum(d['pl_prior_year'] for d in sec_agg.values())
    total_pl_cur = sum(d['pl_cur_total'] for d in sec_agg.values())

    for s in SECTORS:
        d = sec_agg[s]
        d['return_prior_initial'] = (d['pl_prior_year'] / d['mv_prior'] * 100) if d['mv_prior'] > 0 else None
        avg_mv = (d['mv_prior'] + d['mv_cur_end']) / 2
        d['return_prior_avg'] = (d['pl_prior_year'] / avg_mv * 100) if avg_mv > 0 else None
        d['return_cur_ytd'] = (d['pl_cur_total'] / d['current_value'] * 100) if d['current_value'] > 0 else None
        # 新增 v3: 仓位占比 + 绝对贡献占比
        d['position_pct'] = (d['current_value'] / total_cv * 100) if total_cv > 0 else None
        d['contribution_prior_pct'] = (d['pl_prior_year'] / total_pl_prior * 100) if total_pl_prior != 0 else None
        d['contribution_cur_pct'] = (d['pl_cur_total'] / total_pl_cur * 100) if total_pl_cur != 0 else None

    with open(DATA / 'pnl_by_sector.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['板块', f'{D_PRIOR} 市值', f'{D_CUR_END} 市值', f'{PRIOR} P&L',
                    f'{PRIOR} 收益率(期初市值,%)', f'{PRIOR} 收益率(平均市值,%)',
                    f'{CUR} 当前市值', f'{CUR} 持仓 YTD 盈亏', f'{CUR} 已清仓盈亏', f'{CUR} YTD 总盈亏',
                    f'{CUR} YTD 收益率(当前市值,%)', f'{PRIOR} 持仓数', f'{CUR} 持仓数', '缺价标的数'])
        for s in SECTORS:
            d = sec_agg[s]
            w.writerow([s, round(d['mv_prior'], 0), round(d['mv_cur_end'], 0),
                        round(d['pl_prior_year'], 0),
                        round(d['return_prior_initial'], 2) if d['return_prior_initial'] else 'N/A',
                        round(d['return_prior_avg'], 2) if d['return_prior_avg'] else 'N/A',
                        round(d['current_value'], 0),
                        round(d['pl_held_ytd'], 0),
                        round(d['pl_realised_cur'], 0),
                        round(d['pl_cur_total'], 0),
                        round(d['return_cur_ytd'], 2) if d['return_cur_ytd'] else 'N/A',
                        d['positions_prior'], d['positions_cur'],
                        d['pl_prior_missing']])

    total = {
        'pl_prior_year': sum(d['pl_prior_year'] for d in sec_agg.values()),
        'pl_cur_total': sum(d['pl_cur_total'] for d in sec_agg.values()),
        'current_value': sum(d['current_value'] for d in sec_agg.values()),
        'mv_prior': sum(d['mv_prior'] for d in sec_agg.values()),
        'mv_cur_end': sum(d['mv_cur_end'] for d in sec_agg.values()),
    }
    total['return_prior'] = (total['pl_prior_year'] / total['mv_prior'] * 100) if total['mv_prior'] > 0 else None
    total['return_cur'] = (total['pl_cur_total'] / total['current_value'] * 100) if total['current_value'] > 0 else None

    with open(DATA / 'pnl_summary.json', 'w', encoding='utf-8') as f:
        json.dump({
            'prior_year': PRIOR, 'cur_year': CUR, 'today': TODAY,
            'd_prior': D_PRIOR, 'd_cur_end': D_CUR_END,
            'sector_breakdown': {s: sec_agg[s] for s in SECTORS},
            'total': total,
            'missing_price_codes': missing[:30],
        }, f, ensure_ascii=False, indent=2, default=str)

    print(f'\n=== {PRIOR} P&L: ¥{total["pl_prior_year"]:,.0f} ({total["return_prior"]:.2f}%) ===')
    print(f'=== {CUR} YTD P&L: ¥{total["pl_cur_total"]:,.0f} ({total["return_cur"]:.2f}%) ===')
    print(f'当前总市值: ¥{total["current_value"]:,.0f}')


if __name__ == '__main__':
    main()
