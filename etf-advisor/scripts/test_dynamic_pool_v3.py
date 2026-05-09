#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GEI 第五轮: 换思路

上一轮发现: 动态换池子不如固定池。
新方向:
1. 固定核心(国泰+博时) + 动态选剩余2只
2. 全部ETF参与，bonus按胜频连续分布（不二值化）
3. 固定池 + 动态T值（波动大时降低T提早切换）
4. 固定池 + 动态bonus幅度（胜频高时bonus大）
5. 扩大到全部10只，完全用动态bonus代替池概念
"""

import sqlite3
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path
import statistics

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


def load_all():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT date, code, price, nav, premium_rate
        FROM etf_data WHERE code IN ({}) AND date >= '2023-07-01'
        AND price IS NOT NULL AND price > 0
        ORDER BY date, code
    """.format(','.join('?' * len(ALL_CODES))), ALL_CODES).fetchall()
    conn.close()
    data = defaultdict(dict)
    pbc = defaultdict(list)
    for r in rows:
        data[r['date']][r['code']] = {
            'price': r['price'], 'nav': r['nav'], 'premium_rate': r['premium_rate']
        }
        pbc[r['code']].append((r['date'], r['premium_rate']))
    return data, pbc


def calc_score(code, date, data, pbc):
    if code not in data[date] or data[date][code]['premium_rate'] is None:
        return None
    prem = data[date][code]['premium_rate']
    plist = pbc[code]
    ci = None
    for i, (d, _) in enumerate(plist):
        if d == date: ci = i; break
    if ci is None: return None
    cd = datetime.strptime(date, '%Y-%m-%d')
    excess = {}
    for pn, pd in PERIODS:
        ss = (cd - timedelta(days=pd)).strftime('%Y-%m-%d') if pd else None
        vals = [plist[j][1] for j in range(ci)
                if (ss is None or plist[j][0] >= ss) and plist[j][1] is not None]
        avg = sum(vals)/len(vals) if vals else prem
        excess[pn] = prem - avg
    comp = sum(excess.get(p,0)*w for p,w in WEIGHTS.items())
    nav_now = data[date][code]['nav']
    target = (cd - timedelta(days=365)).strftime('%Y-%m-%d')
    nav_1y = None
    for d, _ in plist:
        if d > target: break
        if code in data[d] and data[d][code]['nav'] and data[d][code]['nav'] > 0:
            nav_1y = data[d][code]['nav']
    nr = ((nav_now/nav_1y)-1)*100 if nav_1y and nav_1y > 0 and nav_now else 0
    return nr*0.10 + (-comp)*0.80 + (-prem)*0.10


def get_win_stats(data, all_dates, before_date, lookback):
    idx = all_dates.index(before_date)
    si = max(0, idx - lookback)
    wins = Counter()
    total = 0
    for i in range(si, idx-1):
        d0, d1 = all_dates[i], all_dates[i+1]
        rets = {}
        for c in ALL_CODES:
            if c in data[d0] and c in data[d1]:
                p0, p1 = data[d0][c]['price'], data[d1][c]['price']
                if p0 > 0: rets[c] = (p1-p0)/p0*100
        if rets:
            wins[max(rets, key=rets.get)] += 1
            total += 1
    return wins, total


def simulate(data, pbc, all_dates, get_bonus_fn, threshold, name):
    td = [d for d in all_dates if d >= START]
    value = INITIAL; holding = None; shares = 0; switches = 0; trades = []
    for i in range(len(td)-1):
        date, nd = td[i], td[i+1]
        scored = {}
        for c in ALL_CODES:
            s = calc_score(c, date, data, pbc)
            if s is not None:
                scored[c] = s + get_bonus_fn(date, c)
        if not scored: continue
        best_c = max(scored, key=scored.get)
        best_s = scored[best_c]
        if holding is None:
            holding = best_c; shares = value/data[date][holding]['price']
            switches = 1; trades.append((date, '建仓', None, holding, best_s, value))
        elif holding in scored:
            hs = scored[holding]
            if best_c != holding and (best_s - hs) >= threshold:
                old = holding; cash = shares*data[date][old]['price']
                holding = best_c; shares = cash/data[date][holding]['price']
                value = cash; switches += 1
                trades.append((date, '换仓', old, holding, best_s, value))
        if holding in data.get(nd, {}):
            value = shares * data[nd][holding]['price']
    ret = (value/INITIAL - 1)*100
    return ret, switches, trades


def main():
    print("="*70)
    print("GEI 第五轮: 动态bonus / 混合池 / 动态T")
    print("="*70)

    data, pbc = load_all()
    ad = sorted(data.keys())
    td = [d for d in ad if d >= START]
    results = []

    # 基准
    fixed = set(['513100','159941','159660','513390'])
    r,s,t = simulate(data, pbc, ad, lambda d,c: 0.5 if c in fixed else -0.5, 1.0, '基准')
    results.append(('A. 固定池 ±0.5 T=1.0 (基准)', r, s))
    fixed_ret = r

    # === 1. 固定核心(国泰+博时) + 动态选2只 ===
    core = set(['513100', '513390'])
    for lb in [90, 120, 180]:
        _c1 = {}
        def make_core_dynamic(lookback):
            def fn(date, code):
                if code in core:
                    return 0.5
                if date not in _c1:
                    wins, _ = get_win_stats(data, ad, date, lookback)
                    # 从非core中选胜频最高的2只
                    non_core = [(c, wins.get(c, 0)) for c in ALL_CODES if c not in core]
                    non_core.sort(key=lambda x: -x[1])
                    _c1[date] = set(c for c, _ in non_core[:2])
                return 0.5 if code in _c1[date] else -0.5
            return fn
        _c1 = {}
        bf = make_core_dynamic(lb)
        r, s, t = simulate(data, pbc, ad, bf, 1.0, f'核心+动态{lb}d')
        results.append((f'1. 核心(国泰博时)+胜频{lb}d选2', r, s))

    # === 2. 全部ETF + 连续bonus（按胜频排名） ===
    for lb in [90, 120, 180]:
        _c2 = {}
        def make_continuous(lookback):
            def fn(date, code):
                if date not in _c2:
                    wins, total = get_win_stats(data, ad, date, lookback)
                    if total == 0:
                        _c2[date] = {c: 0 for c in ALL_CODES}
                    else:
                        # 按胜频排名，线性bonus: 第1名=+0.8, 最后=-0.6
                        ranked = sorted(ALL_CODES, key=lambda c: wins.get(c,0), reverse=True)
                        bonuses = {}
                        for i, c in enumerate(ranked):
                            bonuses[c] = 0.8 - (i / (len(ranked)-1)) * 1.4  # +0.8 to -0.6
                        _c2[date] = bonuses
                return _c2.get(date, {}).get(code, 0)
            return fn
        _c2 = {}
        bf = make_continuous(lb)
        r, s, t = simulate(data, pbc, ad, bf, 1.0, f'连续bonus{lb}d')
        results.append((f'2. 连续bonus {lb}d (0.8~-0.6)', r, s))

    # === 3. 按胜频比例给bonus ===
    for lb in [120, 180]:
        for scale in [5, 8, 10, 15]:
            _c3 = {}
            def make_prop(lookback, sc):
                def fn(date, code):
                    if date not in _c3:
                        wins, total = get_win_stats(data, ad, date, lookback)
                        avg = total / len(ALL_CODES) if total > 0 else 1
                        _c3[date] = {c: (wins.get(c,0) - avg) / avg * sc / 10 for c in ALL_CODES}
                    return _c3.get(date, {}).get(code, 0)
                return fn
            _c3 = {}
            bf = make_prop(lb, scale)
            r, s, t = simulate(data, pbc, ad, bf, 1.0, f'比例{lb}d ×{scale/10}')
            results.append((f'3. 频率比例bonus {lb}d ×{scale/10:.1f}', r, s))

    # === 4. 固定池 + 动态T（溢价分散度大时降低T） ===
    for base_t in [1.0]:
        for spread_scale in [0.3, 0.5, 0.8]:
            def make_dynamic_t(bt, ss):
                def get_t(date):
                    prems = [data[date][c]['premium_rate'] for c in fixed
                             if c in data[date] and data[date][c]['premium_rate'] is not None]
                    if len(prems) >= 2:
                        spread = max(prems) - min(prems)
                        # 分散大→T低，分散小→T高
                        return max(0.3, bt - spread * ss)
                    return bt
                return get_t

            gt = make_dynamic_t(base_t, spread_scale)
            # Custom simulate with dynamic T
            value = INITIAL; holding = None; shares = 0; switches = 0
            for i in range(len(td)-1):
                date, nd = td[i], td[i+1]
                scored = {}
                for c in ALL_CODES:
                    s2 = calc_score(c, date, data, pbc)
                    if s2 is not None:
                        scored[c] = s2 + (0.5 if c in fixed else -0.5)
                if not scored: continue
                best_c = max(scored, key=scored.get)
                best_s = scored[best_c]
                t_val = gt(date)
                if holding is None:
                    holding = best_c; shares = value/data[date][holding]['price']; switches = 1
                elif holding in scored:
                    hs = scored[holding]
                    if best_c != holding and (best_s - hs) >= t_val:
                        cash = shares*data[date][holding]['price']
                        holding = best_c; shares = cash/data[date][holding]['price']
                        value = cash; switches += 1
                if holding in data.get(nd, {}):
                    value = shares * data[nd][holding]['price']
            ret = (value/INITIAL-1)*100
            results.append((f'4. 固定池+动态T (base={base_t}, s={spread_scale})', ret, switches))

    # === 5. 固定池 + 动态bonus幅度 ===
    for lb in [60, 120]:
        _c5 = {}
        def make_adaptive_bonus(lookback):
            def fn(date, code):
                if date not in _c5:
                    wins, total = get_win_stats(data, ad, date, lookback)
                    if total == 0:
                        _c5[date] = 0.5
                    else:
                        # 池内Top4的胜频集中度越高 → bonus越大
                        pool_wins = sum(wins.get(c,0) for c in fixed)
                        concentration = pool_wins / total  # 0~1
                        # concentration ≈ 0.6 时 bonus=0.5, 越高bonus越大
                        _c5[date] = 0.3 + concentration
                bonus = _c5[date]
                return bonus if code in fixed else -bonus
            return fn
        _c5 = {}
        bf = make_adaptive_bonus(lb)
        r, s, t = simulate(data, pbc, ad, bf, 1.0, f'自适应bonus{lb}d')
        results.append((f'5. 固定池+自适应bonus {lb}d', r, s))

    # === 6. 全量测试不同固定池组合 (穷举Top组合) ===
    from itertools import combinations
    print("\n  穷举所有4只组合 (T=1.0, ±0.5)...")
    combo_results = []
    for combo in combinations(ALL_CODES, 4):
        pool_set = set(combo)
        r, s, _ = simulate(data, pbc, ad, lambda d,c,ps=pool_set: 0.5 if c in ps else -0.5, 1.0, '')
        combo_results.append((combo, r, s))
    combo_results.sort(key=lambda x: -x[1])

    print(f"\n  Top 10 固定池组合:")
    print(f"  {'池子':<40s}  {'收益':>7s}  {'切换':>4s}")
    print("  " + "-" * 55)
    for combo, ret, sw in combo_results[:10]:
        names = '+'.join(CODE_NAME[c] for c in combo)
        marker = ' ★当前' if set(combo) == fixed else ''
        print(f"  {names:<40s}  {ret:>+6.1f}%  {sw:>3d}次{marker}")
    print(f"\n  当前池排名: 第{[i+1 for i,(c,_,_) in enumerate(combo_results) if set(c)==fixed][0]}名 / {len(combo_results)}组合")

    # 输出动态策略汇总
    results.sort(key=lambda x: -x[1])
    print(f"\n{'='*70}")
    print(f"  {'策略':<40s}  {'收益':>7s}  {'切换':>4s}  {'vs基准':>7s}")
    print("  " + "-" * 62)
    for name, ret, sw in results[:20]:
        delta = ret - fixed_ret
        marker = ' ★' if delta > 0 else ''
        print(f"  {name:<40s}  {ret:>+6.1f}%  {sw:>3d}次  {delta:>+6.1f}%{marker}")

    # 最优固定池 vs 当前
    best_combo = combo_results[0]
    print(f"\n  最优固定池: {'+'.join(CODE_NAME[c] for c in best_combo[0])} → {best_combo[1]:+.1f}%")
    print(f"  当前固定池: {'+'.join(CODE_NAME[c] for c in fixed)} → {fixed_ret:+.1f}%")
    print(f"  差异: {best_combo[1] - fixed_ret:+.1f}%")


if __name__ == '__main__':
    main()
