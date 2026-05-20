#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
find_2etf_pool_v2.py — 修正版

对比基线变更:
  之前: "池内最低溢价" = 只在 2 只池里选低溢价
  现在: "全池最低溢价(同T)" = 在 4 只全池里, 用公式 (a=0,b=0,c=1) 和同样的阈值 T

这才是公平对比: 池子选 2 只 vs 池子保留 4 只, 公式都是 -溢价, 阈值相同.
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
    """通用模拟: 在给定 codes_pool 中, 用 (a,b,c,T) 公式轮动."""
    holding = None
    shares = 0.0
    final = INITIAL
    n = 0
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
            bv = cash
            cash2 = cash * (1 - cost / 100)
            shares = cash2 / day[best_c]['price']
            holding = best_c
            final = cash2
            n += 1
    return (final / INITIAL - 1) * 100, n


def main():
    conn = get_db()

    for idx_name in ['SP500', 'NIKKEI']:
        etfs = INDEX_ETFS[idx_name]
        codes_all = [c for c, _ in etfs]
        name_map = dict(etfs)
        p_by_c, daily = load_all(conn, codes_all, '2023-11-29')
        dates = sorted(set(d for d in daily.keys() if d >= DATA_START))
        comps = compute_components(codes_all, dates, p_by_c, daily)

        print(f"\n{'='*120}")
        print(f"  {idx_name} - 4 选 2 池子搜索  vs  全池(4只)同T的「分值=-溢价」基线")
        print(f"  ↑↑↑ 关键: 基线公式 (a=0, b=0, c=1) + 同样的 T, 在 4 只全池里跑")
        print(f"{'='*120}")

        # 候选 (a,b,c)
        a_grid = [round(x * 0.1, 2) for x in range(0, 11)]
        b_grid = [round(x * 0.1, 2) for x in range(0, 11)]
        t_grid = [0.3, 0.5, 0.6, 0.8, 1.0, 1.2, 1.5]

        # 预计算: 每个 T 下, 全池4只用 -溢价 的收益
        baseline_by_t = {}  # T -> (return, n_switches)
        for t in t_grid:
            r, n = simulate(codes_all, dates, daily, comps, 0.0, 0.0, 1.0, t, COST)
            baseline_by_t[t] = (r, n)

        print(f"\n全池(4只)同T 基线 [公式: 分值=-溢价, 即 (a=0,b=0,c=1)]:")
        for t in t_grid:
            r, n = baseline_by_t[t]
            print(f"  T={t}: 收益 {r:>+7.2f}%  ({n}次换仓)")

        print(f"\n6 个 2 只池子, 每个找最优 (a,b,c,T), 对比相同 T 下的全池基线:")
        print('-' * 120)
        print(f"{'排名':<5}{'池子':<35}{'最优 (a,b,c,T)':<25}{'2池收益':>9}{'换仓':>5}  "
              f"{'同T全池基线':>13}{'换仓':>5}  {'差(2池-基线)':>15}")
        print('-' * 120)

        results = []
        for pair in combinations(etfs, 2):
            codes_pool = [c for c, _ in pair]
            names = [n for _, n in pair]

            # 网格搜索 2 池最优 (a,b,c,T)
            best = None
            best_ret = float('-inf')
            for a in a_grid:
                for b in b_grid:
                    c = 1.0 - a - b
                    if c < -1e-6 or c > 1 + 1e-6:
                        continue
                    c = max(0.0, min(1.0, c))
                    for t in t_grid:
                        ret, n = simulate(codes_pool, dates, daily, comps, a, b, c, t, COST)
                        if ret > best_ret:
                            best_ret = ret
                            best = (a, b, c, t, ret, n)

            a, b, c, t, ret, n = best
            base_ret, base_n = baseline_by_t[t]
            diff = ret - base_ret
            results.append({
                'pool': ' + '.join(names), 'codes': codes_pool,
                'a': a, 'b': b, 'c': c, 't': t, 'ret': ret, 'n': n,
                'base_ret': base_ret, 'base_n': base_n, 'diff': diff,
            })

        # 按 diff 排序
        results.sort(key=lambda x: x['diff'], reverse=True)
        for i, r in enumerate(results, 1):
            fl = '✅' if r['diff'] > 0 else '❌'
            f_str = f"({r['a']:.1f},{r['b']:.1f},{r['c']:.2f}) T={r['t']}"
            print(f"{i:<5}{r['pool']:<35}{f_str:<25}{r['ret']:>+7.2f}% {r['n']:>4}  "
                  f"{r['base_ret']:>+10.2f}% {r['base_n']:>4}  {r['diff']:>+10.2f}% {fl}")

        best = results[0]
        print(f"\n🏆 {idx_name} 最佳:")
        print(f"   2 只池子: {best['pool']}")
        print(f"   最优公式: F = NAV×{best['a']} + (-超额)×{best['b']} + (-溢价)×{best['c']:.2f},  T={best['t']}")
        print(f"   收益: {best['ret']:+.2f}%  ({best['n']} 次换仓)")
        print(f"   同T全池基线(纯-溢价): {best['base_ret']:+.2f}%  ({best['base_n']} 次换仓)")
        print(f"   差: {best['diff']:+.2f}%  {'✅ 2池+复杂公式比全池纯溢价更好' if best['diff'] > 0 else '❌ 还不如全池纯溢价'}")

    conn.close()


if __name__ == '__main__':
    main()
