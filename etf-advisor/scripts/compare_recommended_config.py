#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compare_recommended_config.py — 推荐配置 vs 最低溢价 vs 现行 vs 等权 全面对比

用稳健调参得出的推荐配置, 在【全期】数据上回测,
对比四种策略的实际效果 (含交易成本).

推荐配置:
  NASDAQ: a=0.30, b=0.60, c=0.10, T=0.80
  SP500:  a=0.60, b=0.20, c=0.20, T=0.30
  NIKKEI: a=0.50, b=0.10, c=0.40, T=1.00
  DAX:    a=0.90, b=0.00, c=0.10, T=1.50

现行配置: a=0.10, b=0.80, c=0.10, T=1.00 (所有指数都用)
"""

import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = str(Path(__file__).parent.parent / "data" / "etf_premium.db")
DATA_START = '2025-01-02'
INITIAL = 10000.0
COST = 0.025  # 单边交易成本 %
PERIODS = [('1M', 30), ('3M', 90), ('6M', 180), ('1Y', 365), ('ALL', None)]
PERIOD_WEIGHTS = {'1M': 0.35, '3M': 0.25, '6M': 0.20, '1Y': 0.10, 'ALL': 0.10}

INDEX_ETFS = {
    'NASDAQ': ['513100','159941','159660','159501','159632','159659','513300','513870','513390','513110'],
    'SP500':  ['513500','159655','513650','159612'],
    'NIKKEI': ['159866','513000','513520','513880'],
    'DAX':    ['513030','159561'],
}

RECOMMENDED = {
    'NASDAQ': (0.30, 0.60, 0.10, 0.80),
    'SP500':  (0.60, 0.20, 0.20, 0.30),
    'NIKKEI': (0.50, 0.10, 0.40, 1.00),
    'DAX':    (0.90, 0.00, 0.10, 1.50),
}

CURRENT = (0.10, 0.80, 0.10, 1.00)  # 现行配置


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_all(conn, codes, lookback):
    rows = conn.execute("""
        SELECT date, code, price, nav, premium_rate FROM etf_data
        WHERE code IN ({}) AND date >= ? AND price IS NOT NULL AND price > 0
        ORDER BY date, code
    """.format(','.join('?' * len(codes))), list(codes) + [lookback]).fetchall()
    p_by_c = defaultdict(list)
    daily = defaultdict(dict)
    for r in rows:
        p_by_c[r['code']].append((r['date'], r['premium_rate']))
        daily[r['date']][r['code']] = {
            'price': r['price'], 'nav': r['nav'], 'premium_rate': r['premium_rate']
        }
    return p_by_c, daily


def compute_components(codes, dates, p_by_c, daily):
    idx_maps = {c: (p_by_c.get(c, []), {d: i for i, (d, _) in enumerate(p_by_c.get(c, []))}) for c in codes}
    comps = defaultdict(dict)
    for date in dates:
        day = daily.get(date, {})
        for c in codes:
            info = day.get(c)
            if not info or info['premium_rate'] is None:
                continue
            premium = info['premium_rate']
            plist, idx_map = idx_maps[c]
            ci = idx_map.get(date)
            if ci is None:
                continue
            composite = 0
            cur = datetime.strptime(date, '%Y-%m-%d')
            for pn, pd in PERIODS:
                if pd is None:
                    vals = [plist[i][1] for i in range(ci) if plist[i][1] is not None]
                else:
                    start = (cur - timedelta(days=pd)).strftime('%Y-%m-%d')
                    vals = [plist[i][1] for i in range(ci)
                            if plist[i][0] >= start and plist[i][1] is not None]
                if vals:
                    composite += (premium - sum(vals) / len(vals)) * PERIOD_WEIGHTS[pn]
            nav_ret = 0.0
            if info['nav'] and info['nav'] > 0:
                tgt = (cur - timedelta(days=365)).strftime('%Y-%m-%d')
                best = None
                for d, _ in plist:
                    if d > tgt:
                        break
                    di = daily.get(d, {}).get(c)
                    if di and di['nav'] and di['nav'] > 0:
                        best = di['nav']
                if best and best > 0:
                    nav_ret = (info['nav'] / best - 1) * 100
            comps[date][c] = (nav_ret, composite, premium)
    return comps


def simulate(codes, dates, daily, comps, a, b, c_w, threshold, cost):
    """轮动模拟,含交易成本.返回 (终值, 收益%, 换仓次数, 总成本%)."""
    holding = None
    shares = 0.0
    final = INITIAL
    n = 0
    cost_total = 0
    for date in dates:
        cm = comps.get(date, {})
        if not cm:
            continue
        day = daily.get(date, {})
        best_c, best_s = None, float('-inf')
        for cd in codes:
            if cd not in cm or cd not in day:
                continue
            nr, co, pr = cm[cd]
            sc = nr * a + (-co) * b + (-pr) * c_w
            if sc > best_s:
                best_s, best_c = sc, cd
        if best_c is None:
            continue
        if holding is None:
            holding = best_c
            shares = INITIAL / day[best_c]['price']
            continue
        if holding not in day or holding not in cm:
            continue
        nr_h, co_h, pr_h = cm[holding]
        hs = nr_h * a + (-co_h) * b + (-pr_h) * c_w
        final = shares * day[holding]['price']
        if best_c != holding and (best_s - hs) >= threshold:
            sell_value = final
            cash = sell_value * (1 - cost / 100)
            cost_total += sell_value * cost / 100
            buy_value = cash
            cash_after = cash * (1 - cost / 100)
            cost_total += buy_value * cost / 100
            shares = cash_after / day[best_c]['price']
            holding = best_c
            final = cash_after
            n += 1
    ret_pct = (final / INITIAL - 1) * 100
    return final, ret_pct, n, cost_total


def simulate_min_premium(codes, dates, daily, cost):
    holding = None
    shares = 0.0
    final = INITIAL
    n = 0
    cost_total = 0
    for date in dates:
        day = daily.get(date, {})
        if not day:
            continue
        cands = [(day[c]['premium_rate'], c) for c in codes
                 if c in day and day[c]['premium_rate'] is not None]
        if not cands:
            continue
        cands.sort()
        lowest = cands[0][1]
        if holding is None:
            holding = lowest
            shares = INITIAL / day[lowest]['price']
            continue
        if holding not in day:
            continue
        final = shares * day[holding]['price']
        if lowest != holding:
            sell_v = final
            cash = sell_v * (1 - cost / 100)
            cost_total += sell_v * cost / 100
            buy_v = cash
            cash_after = cash * (1 - cost / 100)
            cost_total += buy_v * cost / 100
            shares = cash_after / day[lowest]['price']
            holding = lowest
            final = cash_after
            n += 1
    ret_pct = (final / INITIAL - 1) * 100
    return final, ret_pct, n, cost_total


def simulate_equal_weight(codes, dates, daily):
    if not dates:
        return INITIAL, 0
    first = daily.get(dates[0], {})
    per = INITIAL / len(codes)
    shares = {c: per / first[c]['price'] for c in codes if c in first and first[c]['price'] > 0}
    last = INITIAL
    for date in dates:
        day = daily.get(date, {})
        total = sum(shares.get(c, 0) * day.get(c, {}).get('price', 0) for c in codes)
        if total > 0:
            last = total
    return last, (last / INITIAL - 1) * 100


def main():
    conn = get_db()
    print(f"{'='*95}")
    print(f"  推荐配置 vs 最低溢价 vs 现行 vs 等权  (含 {COST}% 单边交易成本)")
    print(f"  基于真实历史数据, 起点 {DATA_START}")
    print(f"{'='*95}\n")

    summary = []
    for idx in ['NASDAQ', 'SP500', 'NIKKEI', 'DAX']:
        codes = INDEX_ETFS[idx]
        p_by_c, daily = load_all(conn, codes, '2023-11-29')
        dates = sorted(set(d for d in daily.keys() if d >= DATA_START))
        if not dates:
            continue
        comps = compute_components(codes, dates, p_by_c, daily)

        print(f"\n【{idx}】 ({len(codes)}只 ETF, {len(dates)}天, {dates[0]} ~ {dates[-1]})")
        print("-" * 95)

        # 4 种策略
        eq_v, eq_r = simulate_equal_weight(codes, dates, daily)
        _, mp_r, mp_n, mp_c = simulate_min_premium(codes, dates, daily, COST)
        a, b, c, t = CURRENT
        _, cur_r, cur_n, cur_c = simulate(codes, dates, daily, comps, a, b, c, t, COST)
        a, b, c, t = RECOMMENDED[idx]
        _, rec_r, rec_n, rec_c = simulate(codes, dates, daily, comps, a, b, c, t, COST)

        print(f"  等权持有        : {eq_r:+7.2f}%   (基准)")
        print(f"  最低溢价        : {mp_r:+7.2f}%   {mp_n}次换仓, 成本¥{mp_c:.0f}")
        print(f"  现行 F0+T1.0    : {cur_r:+7.2f}%   {cur_n}次换仓, 成本¥{cur_c:.0f}")
        print(f"  ⭐推荐配置        : {rec_r:+7.2f}%   {rec_n}次换仓, 成本¥{rec_c:.0f}")
        print(f"   配置: NAV×{RECOMMENDED[idx][0]} + (-超额)×{RECOMMENDED[idx][1]} "
              f"+ (-溢价)×{RECOMMENDED[idx][2]:.2f}, T={RECOMMENDED[idx][3]}")
        print(f"  ─────")
        print(f"  推荐 vs 等权    : {rec_r - eq_r:+7.2f}%")
        print(f"  推荐 vs 最低溢价 : {rec_r - mp_r:+7.2f}%   {'✅ 跑赢' if rec_r > mp_r else '❌ 不如最低溢价'}")
        print(f"  推荐 vs 现行    : {rec_r - cur_r:+7.2f}%   {'✅ 比现行好' if rec_r > cur_r else '❌ 不如现行'}")

        summary.append({
            'idx': idx, 'eq': eq_r, 'mp': mp_r, 'cur': cur_r, 'rec': rec_r,
            'rec_vs_mp': rec_r - mp_r, 'rec_vs_cur': rec_r - cur_r,
        })

    # 汇总表
    print(f"\n{'='*95}")
    print("📋 汇总")
    print(f"{'='*95}")
    print(f"{'指数':<10}{'等权':>9}{'最低溢价':>11}{'现行':>9}{'推荐':>9}  {'vs最低溢价':>12}{'vs现行':>10}")
    print('-' * 95)
    for s in summary:
        flag_mp = '✅' if s['rec_vs_mp'] > 0 else '❌'
        flag_cur = '✅' if s['rec_vs_cur'] > 0 else '❌'
        print(f"{s['idx']:<10}{s['eq']:>+7.2f}% {s['mp']:>+8.2f}% "
              f"{s['cur']:>+7.2f}% {s['rec']:>+7.2f}%  "
              f"{s['rec_vs_mp']:>+8.2f}% {flag_mp}  {s['rec_vs_cur']:>+7.2f}% {flag_cur}")

    conn.close()


if __name__ == '__main__':
    main()
