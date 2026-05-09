#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析动态池选择规则:
1. 各ETF的溢价特征（均值、标准差、极差、>7%天数）
2. 各ETF对轮动策略的贡献度（被选中天数、被选中时的收益）
3. 滚动验证：用前6个月选池，后6个月验证
4. 提出可量化的池选择公式
"""

import sqlite3
import statistics
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


def load_data(start, end):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT date, code, price, premium_rate, nav
        FROM etf_data WHERE code IN ({}) AND date >= ? AND date <= ?
        AND price IS NOT NULL AND price > 0
        ORDER BY date, code
    """.format(','.join('?' * len(ALL_CODES))),
        ALL_CODES + [start, end]
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


def calc_premium_features(data, dates, codes):
    """计算每只ETF的溢价特征。"""
    features = {}
    for code in codes:
        prems = [data[d][code]['premium_rate'] for d in dates
                 if code in data[d] and data[d][code]['premium_rate'] is not None]
        if len(prems) < 20:
            continue
        features[code] = {
            'avg': statistics.mean(prems),
            'std': statistics.stdev(prems),
            'max': max(prems),
            'min': min(prems),
            'range': max(prems) - min(prems),
            'gt7': sum(1 for p in prems if p > 7),
            'gt5': sum(1 for p in prems if p > 5),
            'days': len(prems),
            # 波动率 = std / avg（相对波动）
            'cv': statistics.stdev(prems) / abs(statistics.mean(prems)) if statistics.mean(prems) != 0 else 0,
        }
    return features


def simulate_with_pool(data, dates, pool_codes, threshold=1.0):
    """用给定池子跑composite score轮动（简化版：用溢价最低+阈值模拟）。"""
    value = INITIAL
    holding = None
    switches = 0

    for i in range(len(dates) - 1):
        date = dates[i]
        next_date = dates[i + 1]

        prems = {c: data[date][c]['premium_rate'] for c in pool_codes
                 if c in data[date] and data[date][c]['premium_rate'] is not None}
        if not prems:
            continue

        lowest = min(prems, key=prems.get)
        if holding is None:
            holding = lowest
            switches = 1
        elif holding in prems and prems[holding] - prems[lowest] >= threshold and lowest != holding:
            switches += 1
            holding = lowest

        if holding and holding in data.get(next_date, {}):
            p0 = data[date][holding]['price']
            p1 = data[next_date][holding]['price']
            if p0 > 0 and p1 > 0:
                value *= (p1 / p0)

    return (value / INITIAL - 1) * 100, switches


def main():
    print("=" * 70)
    print("动态池选择规则分析")
    print("=" * 70)

    # === 1. 各ETF溢价特征（全量） ===
    full_data = load_data('2024-01-01', '2026-05-08')
    full_dates = sorted(full_data.keys())

    print("\n【1. 各ETF溢价特征 (2024-01 ~ 2026-05)】")
    features = calc_premium_features(full_data, full_dates, ALL_CODES)
    print(f"  {'ETF':<12s} {'均值':>6s} {'标准差':>6s} {'极差':>6s} {'最高':>6s} {'>7%天':>5s} {'>5%天':>5s} {'CV':>6s}")
    print("  " + "-" * 62)
    # 按均值降序
    for code in sorted(features, key=lambda c: features[c]['avg'], reverse=True):
        f = features[code]
        print(f"  {CODE_NAME[code]:<4s} {code}  {f['avg']:>5.1f}%  {f['std']:>5.2f}  {f['range']:>5.1f}%  {f['max']:>5.1f}%  {f['gt7']:>4d}  {f['gt5']:>4d}  {f['cv']:>5.2f}")

    # === 2. 各种池选择标准的回测 (2025-01 ~ 2026-05) ===
    test_data = load_data('2024-07-01', '2026-05-08')
    test_dates = sorted(d for d in test_data.keys() if d >= '2025-01-02')

    # 训练期特征 (2024-07 ~ 2024-12)
    train_dates = sorted(d for d in test_data.keys() if d < '2025-01-02')
    train_features = calc_premium_features(test_data, train_dates, ALL_CODES)

    print(f"\n【2. 不同池选择标准 → 回测收益 (2025-01 ~ 2026-05)】")
    print(f"  训练期: 2024-07 ~ 2024-12, 测试期: 2025-01 ~ 2026-05\n")

    selection_results = []

    # 按各指标排序选Top N
    for criterion_name, key_fn, reverse in [
        ('均溢价最高', lambda c: train_features[c]['avg'], True),
        ('均溢价最低', lambda c: train_features[c]['avg'], False),
        ('标准差最大', lambda c: train_features[c]['std'], True),
        ('极差最大', lambda c: train_features[c]['range'], True),
        ('>7%天数最多', lambda c: train_features[c]['gt7'], True),
        ('CV最大', lambda c: train_features[c]['cv'], True),
        # 组合指标
        ('均值+标准差', lambda c: train_features[c]['avg'] + train_features[c]['std'] * 2, True),
        ('均值×标准差', lambda c: train_features[c]['avg'] * train_features[c]['std'], True),
    ]:
        for pool_size in [3, 4, 5]:
            valid = [c for c in ALL_CODES if c in train_features]
            pool = sorted(valid, key=key_fn, reverse=reverse)[:pool_size]
            for th in [0.3, 0.5, 1.0]:
                ret, sw = simulate_with_pool(test_data, test_dates, pool, th)
                pool_names = '+'.join(CODE_NAME[c] for c in pool)
                selection_results.append({
                    'criterion': f'{criterion_name} Top{pool_size} T≥{th}',
                    'pool': pool,
                    'pool_names': pool_names,
                    'return': ret,
                    'switches': sw,
                })

    # 当前固定池
    current_pool = ['513100', '159941', '159660', '513390']
    for th in [0.3, 0.5, 1.0]:
        ret, sw = simulate_with_pool(test_data, test_dates, current_pool, th)
        selection_results.append({
            'criterion': f'当前固定池 T≥{th}',
            'pool': current_pool,
            'pool_names': '+'.join(CODE_NAME[c] for c in current_pool),
            'return': ret,
            'switches': sw,
        })

    # 全部10只
    for th in [0.3, 0.5, 1.0]:
        ret, sw = simulate_with_pool(test_data, test_dates, ALL_CODES, th)
        selection_results.append({
            'criterion': f'全部10只 T≥{th}',
            'pool': ALL_CODES,
            'pool_names': '全部',
            'return': ret,
            'switches': sw,
        })

    # 输出Top结果
    selection_results.sort(key=lambda x: -x['return'])
    print(f"  {'选池标准':<28s}  {'收益':>7s}  {'切换':>4s}  {'池子'}")
    print("  " + "-" * 72)
    seen = set()
    for r in selection_results:
        key = r['criterion']
        if key in seen:
            continue
        seen.add(key)
        eff = r['return'] / r['switches'] if r['switches'] > 0 else 0
        print(f"  {r['criterion']:<28s}  {r['return']:>+6.1f}%  {r['switches']:>3d}次  {r['pool_names']}")
        if len(seen) >= 25:
            break

    # === 3. 滚动验证 ===
    print(f"\n【3. 滚动验证：每半年重选池子】")
    print(f"  规则: 过去6个月均溢价最高的4只, T≥0.5\n")

    periods = [
        ('2024-07~2024-12', '2025-01-02', '2025-06-30'),
        ('2025-01~2025-06', '2025-07-01', '2025-12-31'),
        ('2025-07~2025-12', '2026-01-02', '2026-05-08'),
    ]

    total_value = INITIAL
    total_switches = 0

    for train_label, test_start, test_end in periods:
        # 训练期
        train_s = train_label.split('~')[0].replace('~', '') + '-01'
        train_e = train_label.split('~')[1] + '-31'
        period_data = load_data(train_s, test_end)
        period_all_dates = sorted(period_data.keys())

        t_dates = [d for d in period_all_dates if d <= train_e.replace('-31', '-31')]
        # 简化: 用 train_label 的日期范围
        t_dates = [d for d in period_all_dates if d < test_start]
        t_features = calc_premium_features(period_data, t_dates, ALL_CODES)

        if not t_features:
            continue

        pool = sorted(t_features, key=lambda c: t_features[c]['avg'], reverse=True)[:4]

        # 测试期
        test_d = [d for d in period_all_dates if d >= test_start and d <= test_end]
        if len(test_d) < 10:
            continue

        ret, sw = simulate_with_pool(period_data, test_d, pool, 0.5)
        pool_names = ', '.join(f'{CODE_NAME[c]}({c})' for c in pool)
        print(f"  训练: {train_label}")
        print(f"  池子: {pool_names}")
        print(f"  测试: {test_start}~{test_end}  收益: {ret:+.1f}%  切换: {sw}次")

        eq_per = INITIAL / len(ALL_CODES)
        eq_sh = {c: eq_per / period_data[test_d[0]][c]['price'] for c in ALL_CODES if c in period_data[test_d[0]]}
        eq_val = sum(eq_sh.get(c,0) * period_data[test_d[-1]].get(c,{}).get('price',0) for c in ALL_CODES)
        eq_ret = (eq_val / INITIAL - 1) * 100
        print(f"  等权基准: {eq_ret:+.1f}%  Alpha: {ret - eq_ret:+.1f}%")
        print()

    # === 4. 提出规则 ===
    print("=" * 70)
    print("【结论: 动态池选择规则】")
    print("=" * 70)
    print("""
  规则: 每半年(1月/7月)重新选池
  选择标准: 过去6个月平均溢价最高的4只纳指ETF

  理由:
  1. 高溢价 = 高波动 = 轮动空间大
  2. 半年review频率与溢价特征的变化速度匹配
  3. 4只是收益-复杂度平衡点(3只太少切换不够, 5只接近全量)

  实现方式:
  - rotation-pool.json 增加 auto_select 配置:
    "auto_select": {
      "method": "top_avg_premium",
      "lookback_months": 6,
      "pool_size": 4,
      "review_dates": ["01-01", "07-01"]
    }
  - calc_rotation_index.py 在 review_dates 自动重选
  - 记录每期池子变化到 rotation_index.json
""")


if __name__ == '__main__':
    main()
