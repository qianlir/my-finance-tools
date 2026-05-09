#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GEI 第六轮: 用波动率、相关性、溢价spread等深层特征选池

思路: 好的池成员应该满足:
1. 溢价波动大 (std高) → 轮动空间大
2. 池内ETF之间溢价相关性低 → 不同步涨跌，切换有意义
3. 溢价均值偏高 → 经常出现高溢价，给composite score更大判别空间
4. 价格涨跌与溢价变化的关联 → 溢价能有效预测价格走势

新选池方法:
A. 溢价波动率 Top N
B. 波动率 × 均值 (兼顾)
C. 低相关性选择: 贪心选波动大且与已选ETF相关性低的
D. 溢价spread (max-min) Top N
E. 溢价回归速度: 偏离均值后回归的速度 (越快=轮动越有效)
"""

import sqlite3
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from itertools import combinations

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
        vals = [plist[j][1] for j in range(ci) if (ss is None or plist[j][0] >= ss) and plist[j][1] is not None]
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


def simulate(data, pbc, all_dates, get_bonus_fn, threshold):
    td = [d for d in all_dates if d >= START]
    value = INITIAL; holding = None; shares = 0; switches = 0
    for i in range(len(td)-1):
        date, nd = td[i], td[i+1]
        scored = {}
        for c in ALL_CODES:
            s = calc_score(c, date, data, pbc)
            if s is not None:
                scored[c] = s + get_bonus_fn(date, c)
        if not scored: continue
        best_c = max(scored, key=scored.get); best_s = scored[best_c]
        if holding is None:
            holding = best_c; shares = value/data[date][holding]['price']; switches = 1
        elif holding in scored:
            hs = scored[holding]
            if best_c != holding and (best_s - hs) >= threshold:
                cash = shares*data[date][holding]['price']
                holding = best_c; shares = cash/data[date][holding]['price']
                value = cash; switches += 1
        if holding in data.get(nd, {}):
            value = shares * data[nd][holding]['price']
    return (value/INITIAL - 1)*100, switches


def calc_premium_features(data, dates, codes):
    """计算溢价特征。"""
    features = {}
    for c in codes:
        vals = [data[d][c]['premium_rate'] for d in dates
                if c in data[d] and data[d][c]['premium_rate'] is not None]
        if len(vals) < 20: continue
        mean = sum(vals)/len(vals)
        std = (sum((v-mean)**2 for v in vals)/(len(vals)-1))**0.5
        features[c] = {
            'mean': mean, 'std': std, 'max': max(vals), 'min': min(vals),
            'range': max(vals)-min(vals),
            'mean_x_std': mean * std,
            'vals': vals,
        }
    return features


def calc_correlation(vals1, vals2):
    """Pearson correlation."""
    n = min(len(vals1), len(vals2))
    if n < 10: return 0
    v1, v2 = vals1[:n], vals2[:n]
    m1, m2 = sum(v1)/n, sum(v2)/n
    cov = sum((a-m1)*(b-m2) for a,b in zip(v1,v2))/(n-1)
    s1 = (sum((a-m1)**2 for a in v1)/(n-1))**0.5
    s2 = (sum((b-m2)**2 for b in v2)/(n-1))**0.5
    return cov/(s1*s2) if s1>0 and s2>0 else 0


def select_low_corr_pool(features, pool_size):
    """贪心选择: 波动率最高的开始，每次加入与已选集合平均相关性最低的。"""
    available = sorted(features.keys(), key=lambda c: features[c]['std'], reverse=True)
    if not available: return []
    pool = [available[0]]
    for _ in range(pool_size - 1):
        best_c, best_score = None, float('inf')
        for c in available:
            if c in pool: continue
            avg_corr = sum(abs(calc_correlation(features[c]['vals'], features[p]['vals'])) for p in pool) / len(pool)
            # 选相关性低 + 波动高的
            score = avg_corr - features[c]['std'] * 0.1  # 低score好
            if score < best_score:
                best_score = score; best_c = c
        if best_c: pool.append(best_c)
    return pool


def calc_reversion_speed(data, dates, code):
    """溢价回归速度: 偏离20日均值后，几天回归一半。越快=越好。"""
    prems = [data[d][code]['premium_rate'] for d in dates
             if code in data[d] and data[d][code]['premium_rate'] is not None]
    if len(prems) < 30: return None
    speeds = []
    for i in range(20, len(prems)):
        avg20 = sum(prems[i-20:i]) / 20
        deviation = prems[i] - avg20
        if abs(deviation) < 0.5: continue
        # 看几天回归到偏离的一半
        half = deviation / 2
        for j in range(1, min(11, len(prems)-i)):
            new_dev = prems[i+j] - avg20
            if abs(new_dev) <= abs(half):
                speeds.append(j)
                break
    return sum(speeds)/len(speeds) if speeds else None


def main():
    print("="*70)
    print("GEI 第六轮: 波动率/相关性/回归速度选池")
    print("="*70)

    data, pbc = load_all()
    ad = sorted(data.keys())
    td = [d for d in ad if d >= START]

    # 基准
    fixed = set(['513100','159941','159660','513390'])
    r0, s0 = simulate(data, pbc, ad, lambda d,c: 0.5 if c in fixed else -0.5, 1.0)
    print(f"\n  基准(固定池 T=1.0): {r0:+.1f}%, {s0}次切换\n")

    results = []
    results.append(('固定池(基准)', r0, s0))

    # === 特征分析 ===
    # 用2024-07~2024-12作为训练期
    train_dates = [d for d in ad if '2024-07-01' <= d <= '2024-12-31']
    features = calc_premium_features(data, train_dates, ALL_CODES)

    print("  训练期(2024-07~12)特征:")
    print(f"  {'ETF':<12s} {'均值':>5s} {'标准差':>5s} {'均×标':>6s} {'极差':>5s} {'回归速度':>8s}")
    print("  " + "-" * 50)
    for c in sorted(features, key=lambda c: features[c]['mean_x_std'], reverse=True):
        f = features[c]
        rs = calc_reversion_speed(data, train_dates, c)
        rs_str = f'{rs:.1f}天' if rs else '—'
        print(f"  {CODE_NAME[c]:<4s} {c}  {f['mean']:>4.1f}%  {f['std']:>4.2f}  {f['mean_x_std']:>5.2f}  {f['range']:>4.1f}%  {rs_str:>6s}")

    # === 相关性矩阵 ===
    print(f"\n  溢价相关性矩阵 (训练期):")
    codes_sorted = sorted(features.keys(), key=lambda c: features[c]['mean_x_std'], reverse=True)
    print(f"  {'':>6s}", end='')
    for c in codes_sorted[:6]:
        print(f"  {CODE_NAME[c]:>4s}", end='')
    print()
    for c1 in codes_sorted[:6]:
        print(f"  {CODE_NAME[c1]:>6s}", end='')
        for c2 in codes_sorted[:6]:
            corr = calc_correlation(features[c1]['vals'], features[c2]['vals'])
            print(f"  {corr:>4.2f}", end='')
        print()

    # === 动态策略: 滚动特征选池 ===
    print(f"\n  滚动选池回测 (每天重算特征, 取过去120天数据)...")

    for method_name, select_fn in [
        ('波动率Top4', lambda f: sorted(f, key=lambda c: f[c]['std'], reverse=True)[:4]),
        ('波动率Top5', lambda f: sorted(f, key=lambda c: f[c]['std'], reverse=True)[:5]),
        ('均×标Top4', lambda f: sorted(f, key=lambda c: f[c]['mean_x_std'], reverse=True)[:4]),
        ('均×标Top5', lambda f: sorted(f, key=lambda c: f[c]['mean_x_std'], reverse=True)[:5]),
        ('极差Top4', lambda f: sorted(f, key=lambda c: f[c]['range'], reverse=True)[:4]),
        ('低相关4只', lambda f: select_low_corr_pool(f, 4)),
        ('低相关5只', lambda f: select_low_corr_pool(f, 5)),
    ]:
        _cache = {}
        def make_fn(sel_fn, lookback=120):
            def bonus_fn(date, code):
                if date not in _cache:
                    idx = ad.index(date)
                    si = max(0, idx - lookback)
                    lb_dates = ad[si:idx]
                    f = calc_premium_features(data, lb_dates, ALL_CODES)
                    if f:
                        _cache[date] = set(sel_fn(f))
                    else:
                        _cache[date] = fixed
                return 0.5 if code in _cache[date] else -0.5
            return bonus_fn
        _cache = {}
        bf = make_fn(select_fn)
        r, s = simulate(data, pbc, ad, bf, 1.0)
        results.append((method_name, r, s))

    # === 组合: 波动率选池 + 不同T ===
    for th in [0.5, 0.8, 1.0, 1.2]:
        _cache_t = {}
        def make_std_pool(lookback=120):
            def bonus_fn(date, code):
                if date not in _cache_t:
                    idx = ad.index(date)
                    si = max(0, idx - lookback)
                    lb_dates = ad[si:idx]
                    f = calc_premium_features(data, lb_dates, ALL_CODES)
                    if f:
                        _cache_t[date] = set(sorted(f, key=lambda c: f[c]['std'], reverse=True)[:4])
                    else:
                        _cache_t[date] = fixed
                return 0.5 if code in _cache_t[date] else -0.5
            return bonus_fn
        _cache_t = {}
        bf = make_std_pool()
        r, s = simulate(data, pbc, ad, bf, th)
        results.append((f'波动率Top4 T={th}', r, s))

    # === 回归速度选池 ===
    _cache_rs = {}
    def reversion_bonus(date, code, lookback=120):
        if date not in _cache_rs:
            idx = ad.index(date)
            si = max(0, idx - lookback)
            lb_dates = ad[si:idx]
            speeds = {}
            for c in ALL_CODES:
                sp = calc_reversion_speed(data, lb_dates, c)
                if sp: speeds[c] = sp
            if speeds:
                # 回归越快(天数越少)=越好
                pool = sorted(speeds, key=speeds.get)[:4]
                _cache_rs[date] = set(pool)
            else:
                _cache_rs[date] = fixed
        return 0.5 if code in _cache_rs[date] else -0.5
    r, s = simulate(data, pbc, ad, reversion_bonus, 1.0)
    results.append(('回归速度Top4', r, s))

    # === 综合指标: 波动率×回归速度 ===
    _cache_combo = {}
    def combo_bonus(date, code, lookback=120):
        if date not in _cache_combo:
            idx = ad.index(date)
            si = max(0, idx - lookback)
            lb_dates = ad[si:idx]
            f = calc_premium_features(data, lb_dates, ALL_CODES)
            scores = {}
            for c in ALL_CODES:
                if c not in f: continue
                sp = calc_reversion_speed(data, lb_dates, c)
                # 波动大 + 回归快 = 好
                speed_score = 1.0 / sp if sp and sp > 0 else 0
                scores[c] = f[c]['std'] * speed_score
            if scores:
                pool = sorted(scores, key=scores.get, reverse=True)[:4]
                _cache_combo[date] = set(pool)
            else:
                _cache_combo[date] = fixed
        return 0.5 if code in _cache_combo[date] else -0.5
    r, s = simulate(data, pbc, ad, combo_bonus, 1.0)
    results.append(('波动率/回归速度 Top4', r, s))

    # 输出
    results.sort(key=lambda x: -x[1])
    print(f"\n{'='*70}")
    print(f"  {'策略':<30s}  {'收益':>7s}  {'切换':>4s}  {'vs基准':>7s}")
    print("  " + "-" * 52)
    for name, ret, sw in results:
        delta = ret - r0
        marker = ' ★' if delta > 0 else ''
        print(f"  {name:<30s}  {ret:>+6.1f}%  {sw:>3d}次  {delta:>+6.1f}%{marker}")


if __name__ == '__main__':
    main()
