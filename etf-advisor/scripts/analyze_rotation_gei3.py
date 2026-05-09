#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GEI 第三轮: 从"溢价最低"出发，优化切换频率和动态池

核心发现: 溢价最低是最强单一信号。
问题: 130次切换太频繁，如何减少？

测试方向:
1. 溢价最低 + 最小持仓天数
2. 溢价最低 + 切换阈值（差额 ≥ X% 才切换）
3. 过去N日平均溢价最低（平滑信号）
4. 溢价最低在子池内选择（动态池 = 过去N天平均溢价最低的M只）
5. 当前策略（composite score + T=1.0）对比
"""

import sqlite3
import json
from collections import defaultdict
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

START = '2025-01-02'
END = '2026-05-08'
INITIAL = 10000.0


def load_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT date, code, price, premium_rate, nav
        FROM etf_data
        WHERE code IN ({}) AND date >= ? AND date <= ?
        AND price IS NOT NULL AND price > 0
        ORDER BY date, code
    """.format(','.join('?' * len(ALL_CODES))),
        ALL_CODES + ['2024-07-01', END]
    ).fetchall()
    conn.close()
    data = defaultdict(dict)
    for r in rows:
        data[r['date']][r['code']] = {
            'price': r['price'],
            'premium_rate': r['premium_rate'],
            'nav': r['nav'],
        }
    return data


def simulate(data, dates, select_fn, name):
    """模拟策略: select_fn(date, data, dates, idx, holding) -> target_code"""
    trade_dates = [d for d in dates if d >= START]
    value = INITIAL
    holding = None
    switches = 0
    trade_log = []

    for i in range(len(trade_dates) - 1):
        date = trade_dates[i]
        next_date = trade_dates[i + 1]
        global_idx = dates.index(date)

        target = select_fn(date, data, dates, global_idx, holding)
        if target is None:
            continue

        if target != holding:
            switches += 1
            trade_log.append((date, holding, target))
            holding = target

        if holding in data.get(next_date, {}):
            p0 = data[date].get(holding, {}).get('price', 0)
            p1 = data[next_date].get(holding, {}).get('price', 0)
            if p0 > 0 and p1 > 0:
                value *= (p1 / p0)

    ret = (value / INITIAL - 1) * 100
    return {'name': name, 'return': ret, 'switches': switches, 'value': value, 'trades': trade_log}


def main():
    print("=" * 70)
    print("GEI 第三轮: 优化切换频率 + 动态池")
    print(f"区间: {START} ~ {END}")
    print("=" * 70)

    data = load_data()
    all_dates = sorted(data.keys())
    results = []

    # === 等权基准 ===
    td = [d for d in all_dates if d >= START]
    per = INITIAL / len(ALL_CODES)
    eq_sh = {c: per / data[td[0]][c]['price'] for c in ALL_CODES if c in data[td[0]]}
    eq_val = sum(eq_sh.get(c,0) * data[td[-1]].get(c,{}).get('price',0) for c in ALL_CODES)
    eq_ret = (eq_val / INITIAL - 1) * 100

    # === 1. 溢价最低 + 最小持仓天数 ===
    print("\n【1. 溢价最低 + 最小持仓天数】")
    for min_hold in [1, 2, 3, 5, 7, 10, 15, 20]:
        hold_counter = [0]
        def fn(date, data, dates, idx, holding, mh=min_hold, hc=hold_counter):
            prems = {c: data[date][c]['premium_rate'] for c in ALL_CODES
                     if c in data[date] and data[date][c]['premium_rate'] is not None}
            if not prems:
                return holding
            target = min(prems, key=prems.get)
            if holding is None:
                hc[0] = 1
                return target
            hc[0] += 1
            if hc[0] >= mh and target != holding:
                hc[0] = 0
                return target
            return holding
        hold_counter[0] = 0
        r = simulate(data, all_dates, fn, f'溢价最低 hold≥{min_hold}')
        results.append(r)
        eff = r['return'] / r['switches'] if r['switches'] > 0 else 0
        print(f"  hold≥{min_hold:2d}天: {r['return']:>+7.1f}%  切换{r['switches']:>3d}次  效率{eff:>+.2f}%/次")

    # === 2. 溢价最低 + 切换阈值（溢价差 ≥ X%） ===
    print("\n【2. 溢价最低 + 切换阈值】")
    for threshold in [0.0, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0]:
        def fn(date, data, dates, idx, holding, th=threshold):
            prems = {c: data[date][c]['premium_rate'] for c in ALL_CODES
                     if c in data[date] and data[date][c]['premium_rate'] is not None}
            if not prems:
                return holding
            lowest = min(prems, key=prems.get)
            if holding is None:
                return lowest
            if holding not in prems:
                return lowest
            if prems[holding] - prems[lowest] >= th and lowest != holding:
                return lowest
            return holding
        r = simulate(data, all_dates, fn, f'溢价最低 T≥{threshold}')
        results.append(r)
        eff = r['return'] / r['switches'] if r['switches'] > 0 else 0
        print(f"  T≥{threshold:.1f}%: {r['return']:>+7.1f}%  切换{r['switches']:>3d}次  效率{eff:>+.2f}%/次")

    # === 3. 过去N日平均溢价最低 ===
    print("\n【3. 过去N日平均溢价最低 + 切换阈值】")
    for avg_days in [3, 5, 10, 20]:
        for th in [0.0, 0.5, 1.0]:
            def fn(date, data, dates, idx, holding, ad=avg_days, t=th):
                avg_prems = {}
                for c in ALL_CODES:
                    vals = []
                    for j in range(ad):
                        if idx - j < 0:
                            break
                        d = dates[idx - j]
                        if c in data[d] and data[d][c]['premium_rate'] is not None:
                            vals.append(data[d][c]['premium_rate'])
                    if vals:
                        avg_prems[c] = sum(vals) / len(vals)
                if not avg_prems:
                    return holding
                lowest = min(avg_prems, key=avg_prems.get)
                if holding is None:
                    return lowest
                if holding not in avg_prems:
                    return lowest
                if avg_prems[holding] - avg_prems[lowest] >= t and lowest != holding:
                    return lowest
                return holding
            r = simulate(data, all_dates, fn, f'{avg_days}日均溢价最低 T≥{th}')
            results.append(r)
            eff = r['return'] / r['switches'] if r['switches'] > 0 else 0
            print(f"  {avg_days}日均 T≥{th:.1f}: {r['return']:>+7.1f}%  切换{r['switches']:>3d}次  效率{eff:>+.2f}%/次")

    # === 4. 动态池: 过去N天平均溢价最低的M只 → 其中取当日溢价最低 ===
    print("\n【4. 动态池(N日均溢价最低M只) + 池内当日溢价最低】")
    for pool_n, pool_m in [(20, 3), (20, 4), (20, 5), (30, 3), (30, 4), (60, 4)]:
        for th in [0.0, 0.5, 1.0]:
            def fn(date, data, dates, idx, holding, pn=pool_n, pm=pool_m, t=th):
                # 动态计算池
                avg_prems = {}
                for c in ALL_CODES:
                    vals = []
                    for j in range(pn):
                        if idx - j < 0:
                            break
                        d = dates[idx - j]
                        if c in data[d] and data[d][c]['premium_rate'] is not None:
                            vals.append(data[d][c]['premium_rate'])
                    if vals:
                        avg_prems[c] = sum(vals) / len(vals)
                if len(avg_prems) < pm:
                    return holding
                pool = sorted(avg_prems, key=avg_prems.get)[:pm]

                # 池内当日溢价最低
                day_prems = {c: data[date][c]['premium_rate'] for c in pool
                             if c in data[date] and data[date][c]['premium_rate'] is not None}
                if not day_prems:
                    return holding
                lowest = min(day_prems, key=day_prems.get)
                if holding is None:
                    return lowest
                if holding not in day_prems:
                    return lowest
                if day_prems[holding] - day_prems[lowest] >= t and lowest != holding:
                    return lowest
                return holding
            r = simulate(data, all_dates, fn, f'池{pool_n}d-{pool_m}只 T≥{th}')
            results.append(r)
            eff = r['return'] / r['switches'] if r['switches'] > 0 else 0
            print(f"  池{pool_n}d最低{pool_m}只 T≥{th:.1f}: {r['return']:>+7.1f}%  切换{r['switches']:>3d}次  效率{eff:>+.2f}%/次")

    # === 5. 当前 rotation_index 策略对比 ===
    rot_path = PROJECT_ROOT / "data" / "rotation_index.json"
    if rot_path.exists():
        rot = json.loads(rot_path.read_text())
        rot_ret = rot['summary']['rotation_return']
        rot_switches = rot['summary']['trade_count']
        print(f"\n【当前策略对比】")
        print(f"  当前策略 (composite+T=1.0): {rot_ret:>+7.1f}%  切换{rot_switches:>3d}次  效率{rot_ret/rot_switches:>+.2f}%/次")

    # === TOP 10 汇总 ===
    print("\n" + "=" * 70)
    print("TOP 10 策略 (按效率=收益/切换排序, 排除切换<3次)")
    print("=" * 70)
    valid = [r for r in results if r['switches'] >= 3]
    valid.sort(key=lambda x: x['return'] / x['switches'] if x['switches'] > 0 else 0, reverse=True)
    print(f"  {'策略':<30s}  {'收益':>8s}  {'切换':>5s}  {'效率':>10s}")
    print("  " + "-" * 58)
    for r in valid[:10]:
        eff = r['return'] / r['switches']
        print(f"  {r['name']:<30s}  {r['return']:>+7.1f}%  {r['switches']:>4d}次  {eff:>+8.2f}%/次")
    print(f"  {'等权持有(基准)':<30s}  {eq_ret:>+7.1f}%  {'—':>5s}")

    # === 最佳策略的换仓记录 ===
    best = max(results, key=lambda x: x['return'])
    print(f"\n收益最高策略: {best['name']} → {best['return']:+.1f}%, {best['switches']}次切换")
    if best['trades']:
        print("  换仓记录:")
        for date, sell, buy in best['trades'][:20]:
            sn = CODE_NAME.get(sell, sell or '—')
            bn = CODE_NAME.get(buy, buy or '—')
            print(f"    {date}  {sn} → {bn}")

    print()


if __name__ == '__main__':
    main()
