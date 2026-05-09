#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试动态池 + composite score 轮动

对比:
A. 固定池 (当前: 国泰+广发+汇添富+博时)
B. 胜频动态池 (每120天重选, Top4)
C. 胜频动态池 (每60天重选, Top4)
D. 均溢价动态池 (每120天重选, Top4)

所有策略均使用完整 composite score + T=1.0
"""

import sqlite3
import json
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR / ".."
DB_PATH = str(PROJECT_ROOT / "data" / "etf_premium.db")

ALL_CODES = ['513100', '159941', '159660', '159501', '159632',
             '159659', '513300', '513870', '513390', '513110']
CODE_NAME = {
    '513100': '国泰', '159941': '广发', '159660': '汇添富', '159501': '嘉实',
    '159632': '华安', '159659': '招商', '513300': '华夏', '513870': '富国',
    '513390': '博时', '513110': '南方',
}

PERIODS = [('1M', 30), ('3M', 90), ('6M', 180), ('1Y', 365), ('ALL', None)]
WEIGHTS = {'1M': 0.35, '3M': 0.25, '6M': 0.20, '1Y': 0.10, 'ALL': 0.10}

START = '2025-01-02'
INITIAL = 10000.0


def load_all(start='2023-07-01'):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT date, code, price, nav, premium_rate
        FROM etf_data WHERE code IN ({}) AND date >= ?
        AND price IS NOT NULL AND price > 0
        ORDER BY date, code
    """.format(','.join('?' * len(ALL_CODES))), ALL_CODES + [start]).fetchall()
    conn.close()

    data = defaultdict(dict)
    prem_by_code = defaultdict(list)
    for r in rows:
        data[r['date']][r['code']] = {
            'price': r['price'], 'nav': r['nav'], 'premium_rate': r['premium_rate']
        }
        prem_by_code[r['code']].append((r['date'], r['premium_rate']))
    return data, prem_by_code


def calc_score(code, date, data, prem_by_code, all_dates, date_idx):
    """计算单只ETF的composite score (不含pool bonus)。"""
    if code not in data[date] or data[date][code]['premium_rate'] is None:
        return None

    prem = data[date][code]['premium_rate']
    plist = prem_by_code[code]

    # 找到当前日期在plist中的位置
    current_idx = None
    for i, (d, _) in enumerate(plist):
        if d == date:
            current_idx = i
            break
    if current_idx is None:
        return None

    # 各period超额
    excess = {}
    current_date = datetime.strptime(date, '%Y-%m-%d')
    for pname, pdays in PERIODS:
        if pdays is not None:
            start_str = (current_date - timedelta(days=pdays)).strftime('%Y-%m-%d')
            vals = [plist[j][1] for j in range(current_idx)
                    if plist[j][0] >= start_str and plist[j][1] is not None]
        else:
            vals = [plist[j][1] for j in range(current_idx) if plist[j][1] is not None]
        avg = sum(vals) / len(vals) if vals else prem
        excess[pname] = prem - avg

    composite = sum(excess.get(p, 0) * w for p, w in WEIGHTS.items())

    # nav return 1y
    target = (current_date - timedelta(days=365)).strftime('%Y-%m-%d')
    nav_now = data[date][code]['nav']
    nav_1y = None
    for d, _ in plist:
        if d > target:
            break
        if code in data[d] and data[d][code]['nav'] and data[d][code]['nav'] > 0:
            nav_1y = data[d][code]['nav']
    nav_return = ((nav_now / nav_1y) - 1) * 100 if nav_1y and nav_1y > 0 and nav_now else 0

    score = nav_return * 0.10 + (-composite) * 0.80 + (-prem) * 0.10
    return score


def get_win_freq_pool(data, all_dates, before_date, lookback, top_n):
    """过去lookback天次日涨幅第一频率最高的top_n只。"""
    idx = all_dates.index(before_date) if before_date in all_dates else 0
    start_idx = max(0, idx - lookback)
    wins = Counter()
    for i in range(start_idx, idx - 1):
        d0, d1 = all_dates[i], all_dates[i + 1]
        rets = {}
        for c in ALL_CODES:
            if c in data[d0] and c in data[d1]:
                p0, p1 = data[d0][c]['price'], data[d1][c]['price']
                if p0 > 0:
                    rets[c] = (p1 - p0) / p0 * 100
        if rets:
            wins[max(rets, key=rets.get)] += 1
    return [c for c, _ in wins.most_common(top_n)]


def get_avg_prem_pool(data, all_dates, before_date, lookback, top_n):
    """过去lookback天均溢价最高的top_n只。"""
    idx = all_dates.index(before_date) if before_date in all_dates else 0
    start_idx = max(0, idx - lookback)
    lb_dates = all_dates[start_idx:idx]
    avgs = {}
    for c in ALL_CODES:
        vals = [data[d][c]['premium_rate'] for d in lb_dates
                if c in data[d] and data[d][c]['premium_rate'] is not None]
        if vals:
            avgs[c] = sum(vals) / len(vals)
    return sorted(avgs, key=avgs.get, reverse=True)[:top_n]


def simulate_composite(data, prem_by_code, all_dates, pool_fn, threshold, bonus=0.5, default_bonus=-0.5):
    """
    pool_fn(date) -> list of pool codes
    用 composite score + pool bonus 轮动。
    """
    trade_dates = [d for d in all_dates if d >= START]
    value = INITIAL
    holding = None
    shares = 0
    switches = 0
    trade_log = []
    pool_changes = []
    last_pool = None

    for i in range(len(trade_dates) - 1):
        date = trade_dates[i]
        next_date = trade_dates[i + 1]
        date_idx = all_dates.index(date)

        pool = pool_fn(date)
        if pool != last_pool:
            pool_changes.append((date, pool))
            last_pool = pool

        # 计算所有纳指ETF的score, 加pool bonus
        scores = {}
        for code in ALL_CODES:
            s = calc_score(code, date, data, prem_by_code, all_dates, date_idx)
            if s is not None:
                b = bonus if code in pool else default_bonus
                scores[code] = s + b

        # 只看pool内的ETF做轮动决策
        pool_scores = {c: scores[c] for c in pool if c in scores}
        if not pool_scores:
            continue

        best_code = max(pool_scores, key=pool_scores.get)
        best_score = pool_scores[best_code]

        if holding is None:
            holding = best_code
            shares = value / data[date][holding]['price']
            switches = 1
            trade_log.append((date, '建仓', None, holding, best_score, value))
        else:
            # 如果持仓不在当前池中 → 强制切到池内最优
            if holding not in pool_scores:
                old = holding
                cash = shares * data[date][old]['price']
                holding = best_code
                shares = cash / data[date][holding]['price']
                value = cash
                switches += 1
                trade_log.append((date, '池变', old, holding, best_score, value))
            else:
                holding_score = pool_scores[holding]
                if best_code != holding and (best_score - holding_score) >= threshold:
                    old = holding
                    cash = shares * data[date][old]['price']
                    holding = best_code
                    shares = cash / data[date][holding]['price']
                    value = cash
                    switches += 1
                    trade_log.append((date, '换仓', old, holding, best_score, value))

            # 更新市值
            if holding in data.get(next_date, {}):
                value = shares * data[next_date][holding]['price']

    ret = (value / INITIAL - 1) * 100
    return ret, switches, trade_log, pool_changes


def main():
    print("=" * 70)
    print("动态池 + Composite Score 回测对比")
    print(f"区间: {START} ~ 最新, T=1.0")
    print("=" * 70)

    data, prem_by_code = load_all()
    all_dates = sorted(data.keys())

    strategies = []

    # A. 固定池
    fixed = ['513100', '159941', '159660', '513390']
    ret, sw, trades, pcs = simulate_composite(
        data, prem_by_code, all_dates,
        lambda d: fixed, threshold=1.0
    )
    strategies.append(('A. 固定池 (当前)', ret, sw, trades, pcs))

    # B. 胜频120d动态池
    def win120(d):
        return get_win_freq_pool(data, all_dates, d, 120, 4)
    ret, sw, trades, pcs = simulate_composite(
        data, prem_by_code, all_dates, win120, threshold=1.0
    )
    strategies.append(('B. 胜频120d Top4', ret, sw, trades, pcs))

    # C. 胜频60d动态池
    def win60(d):
        return get_win_freq_pool(data, all_dates, d, 60, 4)
    ret, sw, trades, pcs = simulate_composite(
        data, prem_by_code, all_dates, win60, threshold=1.0
    )
    strategies.append(('C. 胜频60d Top4', ret, sw, trades, pcs))

    # D. 均溢价120d动态池
    def prem120(d):
        return get_avg_prem_pool(data, all_dates, d, 120, 4)
    ret, sw, trades, pcs = simulate_composite(
        data, prem_by_code, all_dates, prem120, threshold=1.0
    )
    strategies.append(('D. 均溢价120d Top4', ret, sw, trades, pcs))

    # E. 胜频120d Top5
    def win120_5(d):
        return get_win_freq_pool(data, all_dates, d, 120, 5)
    ret, sw, trades, pcs = simulate_composite(
        data, prem_by_code, all_dates, win120_5, threshold=1.0
    )
    strategies.append(('E. 胜频120d Top5', ret, sw, trades, pcs))

    # F. 胜频180d Top4
    def win180(d):
        return get_win_freq_pool(data, all_dates, d, 180, 4)
    ret, sw, trades, pcs = simulate_composite(
        data, prem_by_code, all_dates, win180, threshold=1.0
    )
    strategies.append(('F. 胜频180d Top4', ret, sw, trades, pcs))

    # 等权基准
    td = [d for d in all_dates if d >= START]
    per = INITIAL / len(ALL_CODES)
    eq_sh = {c: per / data[td[0]][c]['price'] for c in ALL_CODES if c in data[td[0]]}
    eq_val = sum(eq_sh.get(c, 0) * data[td[-1]].get(c, {}).get('price', 0) for c in ALL_CODES)
    eq_ret = (eq_val / INITIAL - 1) * 100

    # 输出
    print(f"\n  {'策略':<24s}  {'收益':>8s}  {'切换':>4s}  {'效率':>8s}  {'vs等权':>6s}")
    print("  " + "-" * 58)
    for name, ret, sw, _, _ in sorted(strategies, key=lambda x: -x[1]):
        eff = ret / sw if sw > 0 else 0
        alpha = ret - eq_ret
        print(f"  {name:<24s}  {ret:>+7.1f}%  {sw:>3d}次  {eff:>+7.2f}%/次  {alpha:>+5.1f}%")
    print(f"  {'等权持有':<24s}  {eq_ret:>+7.1f}%")

    # 各策略的池变化和换仓详情
    for name, ret, sw, trades, pool_changes in strategies:
        print(f"\n{'='*50}")
        print(f"  {name}: {ret:+.1f}%, {sw}次切换")
        if pool_changes:
            seen = set()
            print(f"  池变化:")
            for date, pool in pool_changes:
                key = tuple(sorted(pool))
                if key not in seen:
                    seen.add(key)
                    names = '+'.join(CODE_NAME[c] for c in pool)
                    print(f"    {date}: {names}")
        print(f"  换仓记录:")
        for date, action, sell, buy, score, val in trades:
            sn = CODE_NAME.get(sell, '—')
            bn = CODE_NAME.get(buy, buy)
            print(f"    {date} {action}: {sn} → {bn}  分值{score:.2f}  市值¥{val:,.0f}")


if __name__ == '__main__':
    main()
