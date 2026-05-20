#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
find_2etf_pool.py — SP500/NIKKEI 从 4 只中选 2 只组池, 找最优公式 + 阈值

策略空间:
  池子: C(4,2) = 6 个 2 只组合
  公式: F = NAV×a + (-超额)×b + (-溢价)×c, a+b+c=1
  阈值: T

约束:
  - 每个池子单独跑全网格搜索
  - 比较 vs 最低溢价(同样在2只之间换), vs 等权

输出:
  - 各池子最优公式 + 收益
  - 全局最优池子选择
"""
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import combinations
from pathlib import Path

DB_PATH = str(Path(__file__).parent.parent / "data" / "etf_premium.db")
DATA_START = '2025-01-02'
INITIAL = 10000.0
COST = 0.025
PERIODS = [('1M', 30), ('3M', 90), ('6M', 180), ('1Y', 365), ('ALL', None)]
PERIOD_WEIGHTS = {'1M': 0.35, '3M': 0.25, '6M': 0.20, '1Y': 0.10, 'ALL': 0.10}

INDEX_ETFS = {
    'SP500':  [('513500','博时标普'),('159655','华夏标普'),('513650','南方标普'),('159612','国泰标普')],
    'NIKKEI': [('159866','工银日经'),('513000','易方达日经'),('513520','华夏日经'),('513880','华安日经')],
}


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


def simulate(codes_pool, dates, daily, comps, a, b, c_w, threshold, cost):
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
        for cd in codes_pool:
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
            sv = final
            cash = sv * (1 - cost / 100)
            cost_total += sv * cost / 100
            bv = cash
            cash2 = cash * (1 - cost / 100)
            cost_total += bv * cost / 100
            shares = cash2 / day[best_c]['price']
            holding = best_c
            final = cash2
            n += 1
    return (final / INITIAL - 1) * 100, n


def simulate_min_premium(codes_pool, dates, daily, cost):
    holding = None
    shares = 0.0
    final = INITIAL
    n = 0
    for date in dates:
        day = daily.get(date, {})
        if not day:
            continue
        cands = [(day[c]['premium_rate'], c) for c in codes_pool
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
            sv = final
            cash = sv * (1 - cost / 100)
            bv = cash
            cash2 = cash * (1 - cost / 100)
            shares = cash2 / day[lowest]['price']
            holding = lowest
            final = cash2
            n += 1
    return (final / INITIAL - 1) * 100, n


def simulate_equal_weight(codes_pool, dates, daily):
    first = daily.get(dates[0], {})
    per = INITIAL / len(codes_pool)
    shares = {c: per / first[c]['price'] for c in codes_pool if c in first and first[c]['price'] > 0}
    last = INITIAL
    for date in dates:
        day = daily.get(date, {})
        total = sum(shares.get(c, 0) * day.get(c, {}).get('price', 0) for c in codes_pool)
        if total > 0:
            last = total
    return (last / INITIAL - 1) * 100


def search_best_formula(codes_pool, dates, daily, comps, cost):
    """对一个 2 只池子, 网格搜索最优 (a,b,c,T)"""
    best = None
    best_ret = float('-inf')
    a_grid = [round(x * 0.1, 2) for x in range(0, 11)]
    b_grid = [round(x * 0.1, 2) for x in range(0, 11)]
    t_grid = [0.3, 0.5, 0.6, 0.8, 1.0, 1.2, 1.5]
    for a in a_grid:
        for b in b_grid:
            c = 1.0 - a - b
            if c < -1e-6 or c > 1 + 1e-6:
                continue
            c = max(0.0, min(1.0, c))
            for t in t_grid:
                ret, n = simulate(codes_pool, dates, daily, comps, a, b, c, t, cost)
                if ret > best_ret:
                    best_ret = ret
                    best = (a, b, c, t, ret, n)
    return best


def main():
    conn = get_db()

    for idx_name in ['SP500', 'NIKKEI']:
        etfs = INDEX_ETFS[idx_name]
        codes_all = [c for c, _ in etfs]
        name_map = dict(etfs)
        p_by_c, daily = load_all(conn, codes_all, '2023-11-29')
        dates = sorted(set(d for d in daily.keys() if d >= DATA_START))
        comps = compute_components(codes_all, dates, p_by_c, daily)

        # 4 只全池基线
        mp_all, mp_all_n = simulate_min_premium(codes_all, dates, daily, COST)
        eq_all = simulate_equal_weight(codes_all, dates, daily)

        print(f"\n{'='*100}")
        print(f"  {idx_name} - 4选2 池子组合搜索  (含 {COST}% 单边成本)")
        print(f"{'='*100}")
        print(f"4只全池基线: 等权={eq_all:+.2f}%, 最低溢价={mp_all:+.2f}% ({mp_all_n}次换仓)")

        # 6 个 2 只组合
        results = []
        for pair in combinations(etfs, 2):
            codes_pool = [c for c, _ in pair]
            names = [n for _, n in pair]
            pool_label = ' + '.join([f"{c}({n})" for c, n in pair])

            # 找最优公式
            best = search_best_formula(codes_pool, dates, daily, comps, COST)
            a, b, c, t, ret, n = best

            # 池内最低溢价 / 等权
            mp_pool, mp_pool_n = simulate_min_premium(codes_pool, dates, daily, COST)
            eq_pool = simulate_equal_weight(codes_pool, dates, daily)

            results.append({
                'pool': pool_label, 'codes': codes_pool, 'names': names,
                'a': a, 'b': b, 'c': c, 't': t, 'ret': ret, 'n': n,
                'mp': mp_pool, 'mp_n': mp_pool_n, 'eq': eq_pool,
                'vs_mp': ret - mp_pool, 'vs_mp_all': ret - mp_all,
            })

        # 按 vs 全池最低溢价 排序
        results.sort(key=lambda x: x['vs_mp_all'], reverse=True)

        print(f"\n所有 6 个 2 只池子组合 (按 vs 4只全池最低溢价 排序):")
        print(f"\n{'排名':<5}{'池子':<35}{'最优公式 (a,b,c,T)':<25}{'轮动收益':>10}{'池内最低溢价':>13}{'vs池内':>9}{'vs全池最低':>12}{'换仓':>5}")
        print('-' * 120)
        for i, r in enumerate(results, 1):
            formula_str = f"({r['a']:.1f},{r['b']:.1f},{r['c']:.2f}) T={r['t']}"
            vs_pool_flag = '✅' if r['vs_mp'] > 0 else '❌'
            vs_all_flag = '✅' if r['vs_mp_all'] > 0 else '❌'
            short_pool = ' + '.join(r['names'])
            print(f"{i:<5}{short_pool:<35}{formula_str:<25}{r['ret']:>+8.2f}%  "
                  f"{r['mp']:>+8.2f}% {r['vs_mp']:>+7.2f}%{vs_pool_flag} {r['vs_mp_all']:>+9.2f}%{vs_all_flag}{r['n']:>5}")

        # 最佳推荐
        best = results[0]
        print(f"\n🏆 {idx_name} 最佳 2 只池子配置:")
        print(f"   池子: {best['pool']}")
        print(f"   公式: F = NAV×{best['a']} + (-超额)×{best['b']} + (-溢价)×{best['c']:.2f},  T={best['t']}")
        print(f"   收益: {best['ret']:+.2f}%  ({best['n']} 次换仓)")
        print(f"   vs 池内最低溢价: {best['vs_mp']:+.2f}%   {'✅' if best['vs_mp'] > 0 else '❌'}")
        print(f"   vs 4只全池最低溢价: {best['vs_mp_all']:+.2f}%  {'✅' if best['vs_mp_all'] > 0 else '❌'}")

    conn.close()


if __name__ == '__main__':
    main()
