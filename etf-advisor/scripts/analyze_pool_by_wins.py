#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
池选择方案: 过去N天次日涨幅第一频率最高的M只

测试维度:
1. 不同回看窗口(60/90/120/180天)
2. 不同池大小(3/4/5)
3. 固定窗口 vs 滚动验证
4. 与当前池、均溢价池对比
"""

import sqlite3
from collections import defaultdict, Counter
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
INITIAL = 10000.0


def load_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT date, code, price, premium_rate
        FROM etf_data WHERE code IN ({}) AND date >= '2024-01-01'
        AND price IS NOT NULL AND price > 0
        ORDER BY date, code
    """.format(','.join('?' * len(ALL_CODES))), ALL_CODES).fetchall()
    conn.close()
    data = defaultdict(dict)
    for r in rows:
        data[r['date']][r['code']] = {'price': r['price'], 'premium_rate': r['premium_rate']}
    return data


def get_daily_winners(data, dates):
    """每天次日涨幅最大的ETF。返回 [(date, winner_code, {code: ret}), ...]"""
    winners = []
    for i in range(len(dates) - 1):
        d0, d1 = dates[i], dates[i+1]
        rets = {}
        for c in ALL_CODES:
            if c in data[d0] and c in data[d1]:
                p0, p1 = data[d0][c]['price'], data[d1][c]['price']
                if p0 > 0:
                    rets[c] = (p1 - p0) / p0 * 100
        if rets:
            best = max(rets, key=rets.get)
            winners.append((d0, best, rets))
    return winners


def select_pool_by_wins(winners, top_n):
    """从 winners 列表中统计频率最高的 top_n 只。"""
    counts = Counter(w[1] for w in winners)
    return [c for c, _ in counts.most_common(top_n)]


def simulate(data, dates, pool, threshold=0.5):
    """池内溢价最低轮动。"""
    value = INITIAL
    holding = None
    switches = 0
    for i in range(len(dates) - 1):
        d, nd = dates[i], dates[i+1]
        prems = {c: data[d][c]['premium_rate'] for c in pool
                 if c in data[d] and data[d][c]['premium_rate'] is not None}
        if not prems:
            continue
        lowest = min(prems, key=prems.get)
        if holding is None:
            holding = lowest; switches = 1
        elif holding in prems and prems[holding] - prems[lowest] >= threshold and lowest != holding:
            holding = lowest; switches += 1
        if holding and holding in data.get(nd, {}):
            p0, p1 = data[d][holding]['price'], data[nd][holding]['price']
            if p0 > 0 and p1 > 0:
                value *= (p1 / p0)
    return (value / INITIAL - 1) * 100, switches


def main():
    print("=" * 70)
    print("池选择: 次日涨幅第一频率")
    print("=" * 70)

    data = load_data()
    all_dates = sorted(data.keys())
    all_winners = get_daily_winners(data, all_dates)

    # === 1. 全量统计各窗口的胜出频率 ===
    print("\n【1. 各回看窗口的胜出频率 Top5】")
    for lookback_label, lb_start in [('6M (2025-11~)', '2025-11-01'), ('1Y (2025-05~)', '2025-05-01'),
                                      ('1.5Y (2024-11~)', '2024-11-01'), ('全量', '2024-01-01')]:
        subset = [(d, w, r) for d, w, r in all_winners if d >= lb_start]
        counts = Counter(w for _, w, _ in subset)
        total = len(subset)
        print(f"\n  {lookback_label} ({total}天):")
        for code, cnt in counts.most_common(5):
            print(f"    {CODE_NAME[code]:<4s} {code}  {cnt:3d}天 ({cnt/total*100:.1f}%)")

    # === 2. 不同窗口+池大小的回测 ===
    test_start = '2025-01-02'
    test_dates = [d for d in all_dates if d >= test_start]

    print(f"\n{'='*70}")
    print(f"【2. 滚动选池回测 (测试期: {test_start} ~ {all_dates[-1]})】")
    print(f"  方法: 每个交易日用过去N天的胜出频率选池, 池内溢价最低+阈值轮动")
    print(f"{'='*70}")

    results = []

    for lookback in [60, 90, 120, 180]:
        for pool_size in [3, 4, 5]:
            for th in [0.3, 0.5, 1.0]:
                value = INITIAL
                holding = None
                switches = 0
                prev_pool = None

                for i in range(len(test_dates) - 1):
                    d = test_dates[i]
                    nd = test_dates[i+1]
                    gi = all_dates.index(d)

                    # 回看窗口内的 winners
                    lb_start_idx = max(0, gi - lookback)
                    lb_winners = [(wd, wc, wr) for wd, wc, wr in all_winners
                                  if all_dates[lb_start_idx] <= wd < d]
                    if len(lb_winners) < 20:
                        continue

                    pool = select_pool_by_wins(lb_winners, pool_size)

                    prems = {c: data[d][c]['premium_rate'] for c in pool
                             if c in data[d] and data[d][c]['premium_rate'] is not None}
                    if not prems:
                        continue
                    lowest = min(prems, key=prems.get)

                    if holding is None:
                        holding = lowest; switches = 1
                    elif holding in prems and prems[holding] - prems[lowest] >= th and lowest != holding:
                        holding = lowest; switches += 1
                    elif holding not in prems:
                        # 持仓不在新池里，强制切换
                        holding = lowest; switches += 1

                    if holding and holding in data.get(nd, {}):
                        p0, p1 = data[d][holding]['price'], data[nd][holding]['price']
                        if p0 > 0 and p1 > 0:
                            value *= (p1 / p0)

                ret = (value / INITIAL - 1) * 100
                results.append({
                    'name': f'胜频{lookback}d Top{pool_size} T≥{th}',
                    'return': ret, 'switches': switches,
                    'lookback': lookback, 'pool_size': pool_size, 'threshold': th,
                })

    # 对照组: 均溢价选池
    for lookback in [120, 180]:
        for pool_size in [4]:
            for th in [0.5, 1.0]:
                value = INITIAL
                holding = None
                switches = 0
                for i in range(len(test_dates) - 1):
                    d = test_dates[i]
                    nd = test_dates[i+1]
                    gi = all_dates.index(d)
                    lb_start_idx = max(0, gi - lookback)
                    lb_dates = all_dates[lb_start_idx:gi]

                    avg_prems = {}
                    for c in ALL_CODES:
                        vals = [data[dd][c]['premium_rate'] for dd in lb_dates
                                if c in data[dd] and data[dd][c]['premium_rate'] is not None]
                        if vals:
                            avg_prems[c] = sum(vals) / len(vals)
                    pool = sorted(avg_prems, key=avg_prems.get, reverse=True)[:pool_size]

                    prems = {c: data[d][c]['premium_rate'] for c in pool
                             if c in data[d] and data[d][c]['premium_rate'] is not None}
                    if not prems:
                        continue
                    lowest = min(prems, key=prems.get)
                    if holding is None:
                        holding = lowest; switches = 1
                    elif holding in prems and prems[holding] - prems[lowest] >= th and lowest != holding:
                        holding = lowest; switches += 1
                    elif holding not in prems:
                        holding = lowest; switches += 1

                    if holding and holding in data.get(nd, {}):
                        p0, p1 = data[d][holding]['price'], data[nd][holding]['price']
                        if p0 > 0 and p1 > 0:
                            value *= (p1 / p0)
                ret = (value / INITIAL - 1) * 100
                results.append({
                    'name': f'均溢价{lookback}d Top{pool_size} T≥{th}',
                    'return': ret, 'switches': switches,
                    'lookback': lookback, 'pool_size': pool_size, 'threshold': th,
                })

    # 固定池对照
    for th in [0.5, 1.0]:
        ret, sw = simulate(data, test_dates, ['513100', '159941', '159660', '513390'], th)
        results.append({'name': f'固定池(当前) T≥{th}', 'return': ret, 'switches': sw,
                        'lookback': 0, 'pool_size': 4, 'threshold': th})

    # 等权
    first, last = test_dates[0], test_dates[-1]
    per = INITIAL / len(ALL_CODES)
    eq_sh = {c: per / data[first][c]['price'] for c in ALL_CODES if c in data[first]}
    eq_val = sum(eq_sh.get(c,0) * data[last].get(c,{}).get('price',0) for c in ALL_CODES)
    eq_ret = (eq_val / INITIAL - 1) * 100

    # 输出
    results.sort(key=lambda x: -x['return'])
    print(f"\n  {'策略':<30s}  {'收益':>7s}  {'切换':>4s}  {'效率':>8s}")
    print("  " + "-" * 55)
    for r in results[:20]:
        eff = r['return'] / r['switches'] if r['switches'] > 0 else 0
        print(f"  {r['name']:<30s}  {r['return']:>+6.1f}%  {r['switches']:>3d}次  {eff:>+7.2f}%/次")
    print(f"  {'等权持有':<30s}  {eq_ret:>+6.1f}%")

    # === 3. 胜频池 vs 均溢价池：池成员对比 ===
    print(f"\n{'='*70}")
    print(f"【3. 池成员对比: 谁经常被选入？】")
    print(f"{'='*70}")

    # 统计每只ETF在滚动选池中被选入的天数
    for method_name, lookback, pool_size, select_fn in [
        ('胜频120d Top4', 120, 4, 'wins'),
        ('均溢价120d Top4', 120, 4, 'avg_prem'),
    ]:
        membership = Counter()
        for i in range(len(test_dates)):
            d = test_dates[i]
            gi = all_dates.index(d)
            lb_start_idx = max(0, gi - lookback)

            if select_fn == 'wins':
                lb_winners = [(wd, wc, wr) for wd, wc, wr in all_winners
                              if all_dates[lb_start_idx] <= wd < d]
                if len(lb_winners) < 20:
                    continue
                pool = select_pool_by_wins(lb_winners, pool_size)
            else:
                lb_dates = all_dates[lb_start_idx:gi]
                avg_prems = {}
                for c in ALL_CODES:
                    vals = [data[dd][c]['premium_rate'] for dd in lb_dates
                            if c in data[dd] and data[dd][c]['premium_rate'] is not None]
                    if vals:
                        avg_prems[c] = sum(vals) / len(vals)
                pool = sorted(avg_prems, key=avg_prems.get, reverse=True)[:pool_size]

            for c in pool:
                membership[c] += 1

        total_days = len(test_dates)
        print(f"\n  {method_name} — 各ETF入池天数占比:")
        for code in sorted(membership, key=membership.get, reverse=True):
            pct = membership[code] / total_days * 100
            bar = '█' * int(pct / 5)
            print(f"    {CODE_NAME[code]:<4s} {code}  {membership[code]:>3d}天 ({pct:>5.1f}%) {bar}")

    print()


if __name__ == '__main__':
    main()
