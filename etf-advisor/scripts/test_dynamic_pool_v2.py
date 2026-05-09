#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GEI 第四轮: 找到比固定池更优的动态方案

上一轮的问题: 动态池在池变时强制切换，产生无效交易。
本轮思路:
1. 不强制切换 — 持仓被踢出池子时保留，只在 score 差到阈值才换
2. 更大池 (5-6只) 减少被踢概率
3. 渐变bonus — 不是非0即1，按排名给连续bonus
4. 组合指标选池: avg_premium × std (兼顾水平和波动)
5. 滞后机制: 连续N天排名靠后才踢出
"""

import sqlite3
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
    prem_by_code = defaultdict(list)
    for r in rows:
        data[r['date']][r['code']] = {
            'price': r['price'], 'nav': r['nav'], 'premium_rate': r['premium_rate']
        }
        prem_by_code[r['code']].append((r['date'], r['premium_rate']))
    return data, prem_by_code


def calc_score(code, date, data, prem_by_code):
    """composite score (不含bonus)。"""
    if code not in data[date] or data[date][code]['premium_rate'] is None:
        return None
    prem = data[date][code]['premium_rate']
    plist = prem_by_code[code]
    ci = None
    for i, (d, _) in enumerate(plist):
        if d == date:
            ci = i; break
    if ci is None:
        return None
    cd = datetime.strptime(date, '%Y-%m-%d')
    excess = {}
    for pn, pd in PERIODS:
        if pd:
            ss = (cd - timedelta(days=pd)).strftime('%Y-%m-%d')
            vals = [plist[j][1] for j in range(ci) if plist[j][0] >= ss and plist[j][1] is not None]
        else:
            vals = [plist[j][1] for j in range(ci) if plist[j][1] is not None]
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
    nr = ((nav_now/nav_1y)-1)*100 if nav_1y and nav_1y>0 and nav_now else 0
    return nr*0.10 + (-comp)*0.80 + (-prem)*0.10


def get_win_pool(data, all_dates, before_date, lookback, top_n):
    idx = all_dates.index(before_date)
    si = max(0, idx - lookback)
    wins = Counter()
    for i in range(si, idx-1):
        d0, d1 = all_dates[i], all_dates[i+1]
        rets = {}
        for c in ALL_CODES:
            if c in data[d0] and c in data[d1]:
                p0, p1 = data[d0][c]['price'], data[d1][c]['price']
                if p0 > 0: rets[c] = (p1-p0)/p0*100
        if rets: wins[max(rets, key=rets.get)] += 1
    return [c for c,_ in wins.most_common(top_n)], wins


def simulate(data, prem_by_code, all_dates, get_bonus_fn, threshold, name):
    """
    get_bonus_fn(date, code) -> float bonus for this ETF on this date
    轮动在所有ETF中按 score+bonus 决策，不强制切换。
    """
    td = [d for d in all_dates if d >= START]
    value = INITIAL
    holding = None
    shares = 0
    switches = 0
    trades = []

    for i in range(len(td)-1):
        date, nd = td[i], td[i+1]

        # 计算所有ETF的 score + bonus
        scored = {}
        for c in ALL_CODES:
            s = calc_score(c, date, data, prem_by_code)
            if s is not None:
                scored[c] = s + get_bonus_fn(date, c)

        if not scored:
            continue

        best_c = max(scored, key=scored.get)
        best_s = scored[best_c]

        if holding is None:
            holding = best_c
            shares = value / data[date][holding]['price']
            switches = 1
            trades.append((date, '建仓', None, holding, best_s, value))
        elif holding in scored:
            hs = scored[holding]
            if best_c != holding and (best_s - hs) >= threshold:
                old = holding
                cash = shares * data[date][old]['price']
                holding = best_c
                shares = cash / data[date][holding]['price']
                value = cash
                switches += 1
                trades.append((date, '换仓', old, holding, best_s, value))

        if holding in data.get(nd, {}):
            value = shares * data[nd][holding]['price']

    ret = (value/INITIAL - 1)*100
    return ret, switches, trades


def main():
    print("="*70)
    print("GEI 第四轮: 比固定池更优的动态方案")
    print(f"区间: {START} ~ 最新, T=1.0")
    print("="*70)

    data, pbc = load_all()
    ad = sorted(data.keys())
    td = [d for d in ad if d >= START]

    results = []

    # === A. 基准: 固定池 ===
    fixed = set(['513100','159941','159660','513390'])
    def bonus_fixed(date, code):
        return 0.5 if code in fixed else -0.5
    r, s, t = simulate(data, pbc, ad, bonus_fixed, 1.0, 'A.固定池')
    results.append(('A. 固定池 (基准)', r, s, t))

    # === B. 胜频动态 — 不强制切换 ===
    # 关键改进: 持仓不在池中时仍保留，只用 score+bonus 判断
    for lb in [120, 180]:
        for ps in [4, 5, 6]:
            _cache = {}
            def make_bonus_win(lookback, pool_size, bonus=0.5, penalty=-0.5):
                def fn(date, code):
                    if date not in _cache:
                        pool, _ = get_win_pool(data, ad, date, lookback, pool_size)
                        _cache[date] = set(pool)
                    return bonus if code in _cache[date] else penalty
                return fn

            _cache = {}
            bf = make_bonus_win(lb, ps)
            r, s, t = simulate(data, pbc, ad, bf, 1.0, f'胜频{lb}d Top{ps}')
            results.append((f'B. 胜频{lb}d Top{ps} 不强制切', r, s, t))

    # === C. 渐变bonus — 按排名给不同bonus ===
    for lb in [120, 180]:
        _cache_c = {}
        def make_gradient_bonus(lookback):
            def fn(date, code):
                if date not in _cache_c:
                    _, wins = get_win_pool(data, ad, date, lookback, 10)
                    total = sum(wins.values())
                    if total == 0:
                        _cache_c[date] = {}
                    else:
                        ranked = [c for c,_ in wins.most_common()]
                        # Top1: +0.8, Top2: +0.5, Top3: +0.3, Top4: +0.1, 其余: -0.3
                        bonuses = {}
                        bonus_vals = [0.8, 0.5, 0.3, 0.1]
                        for i, c in enumerate(ranked):
                            bonuses[c] = bonus_vals[i] if i < len(bonus_vals) else -0.3
                        _cache_c[date] = bonuses
                return _cache_c.get(date, {}).get(code, -0.3)
            return fn

        _cache_c = {}
        bf = make_gradient_bonus(lb)
        r, s, t = simulate(data, pbc, ad, bf, 1.0, f'渐变{lb}d')
        results.append((f'C. 渐变bonus {lb}d', r, s, t))

    # === D. 按胜出频率占比给bonus ===
    for lb in [120, 180]:
        _cache_d = {}
        def make_freq_bonus(lookback):
            def fn(date, code):
                if date not in _cache_d:
                    _, wins = get_win_pool(data, ad, date, lookback, 10)
                    total = sum(wins.values()) or 1
                    avg_freq = 1.0 / len(ALL_CODES)  # 10%
                    bonuses = {}
                    for c in ALL_CODES:
                        freq = wins.get(c, 0) / total
                        # freq > avg → positive bonus, < avg → negative
                        bonuses[c] = (freq - avg_freq) * 10  # scale: 10% deviation = 0 bonus
                    _cache_d[date] = bonuses
                return _cache_d.get(date, {}).get(code, -0.5)
            return fn

        _cache_d = {}
        bf = make_freq_bonus(lb)
        r, s, t = simulate(data, pbc, ad, bf, 1.0, f'频率占比{lb}d')
        results.append((f'D. 频率占比bonus {lb}d', r, s, t))

    # === E. 组合: 均溢价×标准差 选池 ===
    for lb in [120, 180]:
        for ps in [4, 5]:
            _cache_e = {}
            def make_combo_pool(lookback, pool_size):
                def fn(date, code):
                    if date not in _cache_e:
                        idx = ad.index(date)
                        si = max(0, idx - lookback)
                        lb_dates = ad[si:idx]
                        import statistics
                        pool_scores = {}
                        for c in ALL_CODES:
                            vals = [data[d][c]['premium_rate'] for d in lb_dates
                                    if c in data[d] and data[d][c]['premium_rate'] is not None]
                            if len(vals) >= 20:
                                pool_scores[c] = statistics.mean(vals) * statistics.stdev(vals)
                        pool = sorted(pool_scores, key=pool_scores.get, reverse=True)[:pool_size]
                        _cache_e[date] = set(pool)
                    return 0.5 if code in _cache_e[date] else -0.5
                return fn

            _cache_e = {}
            bf = make_combo_pool(lb, ps)
            r, s, t = simulate(data, pbc, ad, bf, 1.0, f'均值×标差{lb}d Top{ps}')
            results.append((f'E. 均值×标差 {lb}d Top{ps}', r, s, t))

    # === F. 胜频 + 不同bonus幅度 ===
    for bonus_val in [0.3, 0.5, 0.7, 1.0]:
        penalty_val = -bonus_val
        _cache_f = {}
        def make_bonus_adj(lb, ps, bv, pv):
            def fn(date, code):
                if date not in _cache_f:
                    pool, _ = get_win_pool(data, ad, date, lb, ps)
                    _cache_f[date] = set(pool)
                return bv if code in _cache_f[date] else pv
            return fn

        _cache_f = {}
        bf = make_bonus_adj(120, 4, bonus_val, penalty_val)
        r, s, t = simulate(data, pbc, ad, bf, 1.0, f'胜频120 ±{bonus_val}')
        results.append((f'F. 胜频120d Top4 ±{bonus_val}', r, s, t))

    # === G. 不同T值 ===
    for th in [0.5, 0.8, 1.0, 1.2, 1.5]:
        _cache_g = {}
        def make_g(lb, ps):
            def fn(date, code):
                if date not in _cache_g:
                    pool, _ = get_win_pool(data, ad, date, lb, ps)
                    _cache_g[date] = set(pool)
                return 0.5 if code in _cache_g[date] else -0.5
            return fn
        _cache_g = {}
        bf = make_g(120, 4)
        r, s, t = simulate(data, pbc, ad, bf, th, f'胜频120 T={th}')
        results.append((f'G. 胜频120d Top4 T={th}', r, s, t))

    # 等权基准
    per = INITIAL / len(ALL_CODES)
    eq_sh = {c: per/data[td[0]][c]['price'] for c in ALL_CODES if c in data[td[0]]}
    eq_val = sum(eq_sh.get(c,0)*data[td[-1]].get(c,{}).get('price',0) for c in ALL_CODES)
    eq_ret = (eq_val/INITIAL-1)*100

    # 输出
    results.sort(key=lambda x: -x[1])
    print(f"\n  {'策略':<32s}  {'收益':>7s}  {'切换':>4s}  {'效率':>8s}  {'vs固定池':>7s}")
    print("  " + "-" * 65)
    fixed_ret = [r for n,r,s,t in results if '基准' in n][0]
    for name, ret, sw, trades in results:
        eff = ret/sw if sw>0 else 0
        delta = ret - fixed_ret
        marker = ' ★' if delta > 0 else ''
        print(f"  {name:<32s}  {ret:>+6.1f}%  {sw:>3d}次  {eff:>+7.2f}%/次  {delta:>+6.1f}%{marker}")
    print(f"  {'等权持有':<32s}  {eq_ret:>+6.1f}%")

    # 最优策略详情
    best = results[0]
    if best[0] != 'A. 固定池 (基准)':
        print(f"\n{'='*50}")
        print(f"最优: {best[0]} → {best[1]:+.1f}%, {best[2]}次切换")
        for date, action, sell, buy, score, val in best[3]:
            sn = CODE_NAME.get(sell, '—')
            bn = CODE_NAME.get(buy, buy)
            print(f"  {date} {action}: {sn} → {bn}  ¥{val:,.0f}")


if __name__ == '__main__':
    main()
