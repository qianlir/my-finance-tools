#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_tune_formula.py — 自动寻找最优评分公式参数

求解问题:
  公式: F(a,b,c) = NAV×a + (-超额)×b + (-溢价)×c
  约束: a + b + c = 1.0,  a,b,c ∈ [0, 1]
  目标: 最大化 vs 等权 alpha (扣除交易成本后)

算法: 三层评估
  L1: 全网格搜索 (步长 0.1, 共 66 组合) × 阈值 (0.3~1.5, 5档) × 4指数
  L2: 在 L1 top 5 附近做精细化搜索 (步长 0.05)
  L3: Walk-forward 验证 (前80%训练, 后20%验证), 防止过拟合

输出:
  - 各指数最优参数
  - 全部参数空间的 heatmap (csv)
  - 训练/验证集对比 (反映过拟合程度)

Usage:
  python3 scripts/auto_tune_formula.py                    # 跑所有指数
  python3 scripts/auto_tune_formula.py --index SP500      # 单指数
  python3 scripts/auto_tune_formula.py --cost 0.025       # 自定义单边交易成本
"""

import argparse
import csv
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR / ".."
DB_PATH = str(PROJECT_ROOT / "data" / "etf_premium.db")
OUTPUT_DIR = PROJECT_ROOT / "data" / "tuning"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DATA_START = '2025-01-02'
INITIAL = 10000.0
PERIODS = [('1M', 30), ('3M', 90), ('6M', 180), ('1Y', 365), ('ALL', None)]
PERIOD_WEIGHTS = {'1M': 0.35, '3M': 0.25, '6M': 0.20, '1Y': 0.10, 'ALL': 0.10}
DEFAULT_COST = 0.025  # 单边交易成本 %, 买+卖共 0.05%

INDEX_ETFS = {
    'NASDAQ': ['513100','159941','159660','159501','159632','159659','513300','513870','513390','513110'],
    'SP500':  ['513500','159655','513650','159612'],
    'NIKKEI': ['159866','513000','513520','513880'],
    'DAX':    ['513030','159561'],
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_all_data(conn, codes, lookback_start):
    rows = conn.execute("""
        SELECT date, code, price, nav, premium_rate FROM etf_data
        WHERE code IN ({}) AND date >= ? AND price IS NOT NULL AND price > 0
        ORDER BY date, code
    """.format(','.join('?' * len(codes))),
        list(codes) + [lookback_start]).fetchall()
    premium_by_code = defaultdict(list)
    daily_data = defaultdict(dict)
    for r in rows:
        premium_by_code[r['code']].append((r['date'], r['premium_rate']))
        daily_data[r['date']][r['code']] = {
            'price': r['price'], 'nav': r['nav'], 'premium_rate': r['premium_rate']
        }
    return premium_by_code, daily_data


def compute_components(codes, trading_dates, premium_by_code, daily_data):
    """
    预计算每个 (date, code) 的三个分量: nav_return_1y, composite_excess, premium.
    这样后面尝试不同 (a,b,c) 时不必重复计算.
    """
    idx_maps = {}
    for c in codes:
        plist = premium_by_code.get(c, [])
        idx_maps[c] = (plist, {d: i for i, (d, _) in enumerate(plist)})

    components = defaultdict(dict)  # date -> code -> (nav_ret, composite, premium)
    for date in trading_dates:
        day = daily_data.get(date, {})
        for c in codes:
            info = day.get(c)
            if not info or info['premium_rate'] is None:
                continue
            premium = info['premium_rate']
            plist, idx_map = idx_maps[c]
            ci = idx_map.get(date)
            if ci is None:
                continue
            # 综合超额溢价
            composite = 0
            cur_date = datetime.strptime(date, '%Y-%m-%d')
            for pname, pdays in PERIODS:
                if pdays is None:
                    vals = [plist[i][1] for i in range(ci) if plist[i][1] is not None]
                else:
                    start = (cur_date - timedelta(days=pdays)).strftime('%Y-%m-%d')
                    vals = [plist[i][1] for i in range(ci)
                            if plist[i][0] >= start and plist[i][1] is not None]
                if vals:
                    composite += (premium - sum(vals) / len(vals)) * PERIOD_WEIGHTS[pname]
            # NAV 1y return
            nav_ret = 0.0
            cur = info
            if cur['nav'] and cur['nav'] > 0:
                tgt = (cur_date - timedelta(days=365)).strftime('%Y-%m-%d')
                best_nav = None
                for d, _ in plist:
                    if d > tgt:
                        break
                    di = daily_data.get(d, {}).get(c)
                    if di and di['nav'] and di['nav'] > 0:
                        best_nav = di['nav']
                if best_nav and best_nav > 0:
                    nav_ret = (cur['nav'] / best_nav - 1) * 100
            components[date][c] = (nav_ret, composite, premium)
    return components


def simulate_with_params(codes, trading_dates, daily_data, components,
                         a, b, c_w, threshold, cost):
    """用给定 (a,b,c,T) 进行轮动回测, 扣除单边交易成本."""
    holding = None
    shares = 0.0
    final = INITIAL
    n_switches = 0

    for date in trading_dates:
        comps = components.get(date, {})
        if not comps:
            continue
        day = daily_data.get(date, {})

        best_code, best_score = None, float('-inf')
        for cd in codes:
            if cd not in comps or cd not in day:
                continue
            nav_ret, composite, premium = comps[cd]
            score = nav_ret * a + (-composite) * b + (-premium) * c_w
            if score > best_score:
                best_score, best_code = score, cd
        if best_code is None:
            continue

        if holding is None:
            holding = best_code
            shares = INITIAL / day[best_code]['price']
            continue

        if holding not in day or holding not in comps:
            continue

        nav_h, comp_h, prem_h = comps[holding]
        holding_score = nav_h * a + (-comp_h) * b + (-prem_h) * c_w
        final = shares * day[holding]['price']

        if best_code != holding and (best_score - holding_score) >= threshold:
            cash = final * (1 - cost / 100)  # 卖出成本
            shares = cash / day[best_code]['price']
            cash = shares * day[best_code]['price'] * (1 - cost / 100)  # 买入成本
            shares = cash / day[best_code]['price']
            holding = best_code
            final = cash
            n_switches += 1
    return final, n_switches


def simulate_equal_weight(codes, trading_dates, daily_data):
    if not trading_dates:
        return INITIAL
    first = daily_data.get(trading_dates[0], {})
    per = INITIAL / len(codes)
    shares = {c: per / first[c]['price'] for c in codes if c in first and first[c]['price'] > 0}
    last = INITIAL
    for date in trading_dates:
        day = daily_data.get(date, {})
        total = sum(shares.get(c, 0) * day.get(c, {}).get('price', 0) for c in codes)
        if total > 0:
            last = total
    return last


def simulate_min_premium(codes, trading_dates, daily_data, cost):
    holding = None
    shares = 0.0
    final = INITIAL
    n = 0
    for date in trading_dates:
        day = daily_data.get(date, {})
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
            cash = final * (1 - cost / 100)
            shares = cash / day[lowest]['price']
            cash = shares * day[lowest]['price'] * (1 - cost / 100)
            shares = cash / day[lowest]['price']
            holding = lowest
            final = cash
            n += 1
    return final, n


def grid_search(codes, trading_dates, daily_data, components,
                a_grid, b_grid, t_grid, cost):
    """
    网格搜索. 由于 a+b+c=1, 只需遍历 (a, b), c = 1-a-b.
    返回 [(a, b, c, threshold, final_return, n_switches), ...]
    """
    results = []
    for a in a_grid:
        for b in b_grid:
            c_w = 1.0 - a - b
            if c_w < -1e-6 or c_w > 1.0 + 1e-6:
                continue
            c_w = max(0.0, min(1.0, c_w))
            for thr in t_grid:
                final, n_sw = simulate_with_params(
                    codes, trading_dates, daily_data, components, a, b, c_w, thr, cost
                )
                ret = (final / INITIAL - 1) * 100
                results.append((a, b, c_w, thr, ret, n_sw))
    return results


def walk_forward_split(trading_dates, train_pct=0.8):
    """前 80% 训练, 后 20% 验证."""
    n = len(trading_dates)
    cut = int(n * train_pct)
    return trading_dates[:cut], trading_dates[cut:]


def tune_index(conn, index_type, cost):
    codes = INDEX_ETFS[index_type]
    print(f"\n{'='*100}")
    print(f"指数: {index_type}  (单边成本 {cost}%)")
    print(f"{'='*100}")

    lookback = '2023-11-29'
    premium_by_code, daily_data = load_all_data(conn, codes, lookback)
    all_dates = sorted(set(d for d in daily_data.keys() if d >= DATA_START))
    if not all_dates:
        print("无数据")
        return

    print(f"全期: {all_dates[0]} ~ {all_dates[-1]} ({len(all_dates)}天)")
    train_dates, valid_dates = walk_forward_split(all_dates, 0.8)
    print(f"训练集: {train_dates[0]} ~ {train_dates[-1]} ({len(train_dates)}天)")
    print(f"验证集: {valid_dates[0]} ~ {valid_dates[-1]} ({len(valid_dates)}天)")

    print(f"\n预计算分量...")
    components = compute_components(codes, all_dates, premium_by_code, daily_data)

    # ===== L1: 粗网格 (步长 0.1) =====
    a_grid = [round(x * 0.1, 2) for x in range(0, 11)]
    b_grid = [round(x * 0.1, 2) for x in range(0, 11)]
    t_grid = [0.3, 0.5, 0.8, 1.0, 1.5]
    print(f"\n[L1] 粗网格搜索: {len(a_grid)}×{len(b_grid)}×{len(t_grid)} = {len(a_grid)*len(b_grid)*len(t_grid)}组合")

    # 基线
    eq_train = simulate_equal_weight(codes, train_dates, daily_data)
    eq_train_ret = (eq_train / INITIAL - 1) * 100
    mp_train, mp_n = simulate_min_premium(codes, train_dates, daily_data, cost)
    mp_train_ret = (mp_train / INITIAL - 1) * 100
    eq_valid = simulate_equal_weight(codes, valid_dates, daily_data)
    eq_valid_ret = (eq_valid / INITIAL - 1) * 100
    mp_valid, _ = simulate_min_premium(codes, valid_dates, daily_data, cost)
    mp_valid_ret = (mp_valid / INITIAL - 1) * 100

    print(f"训练集基线: 等权 {eq_train_ret:+.2f}% | 最低溢价 {mp_train_ret:+.2f}% ({mp_n}次换仓)")
    print(f"验证集基线: 等权 {eq_valid_ret:+.2f}% | 最低溢价 {mp_valid_ret:+.2f}%")

    results_train = grid_search(codes, train_dates, daily_data, components,
                                a_grid, b_grid, t_grid, cost)
    results_train.sort(key=lambda x: x[4], reverse=True)

    # 在验证集上重算 top 10
    print(f"\n训练集 Top 10:")
    print(f"{'排名':<5}{'a':>5}{'b':>5}{'c':>5}{'T':>5}  {'训练%':>8}{'vs等权':>8}{'验证%':>8}{'vs等权':>8}{'换仓':>5}")
    print('-' * 88)
    top_candidates = []
    for i, (a, b, c, t, ret, n) in enumerate(results_train[:10], 1):
        valid_final, valid_n = simulate_with_params(codes, valid_dates, daily_data,
                                                     components, a, b, c, t, cost)
        valid_ret = (valid_final / INITIAL - 1) * 100
        top_candidates.append((a, b, c, t, ret, ret - eq_train_ret,
                              valid_ret, valid_ret - eq_valid_ret, n + valid_n))
        print(f"{i:<5}{a:>5.2f}{b:>5.2f}{c:>5.2f}{t:>5.2f}  "
              f"{ret:>+7.2f}%{ret-eq_train_ret:>+7.2f}%"
              f"{valid_ret:>+7.2f}%{valid_ret-eq_valid_ret:>+7.2f}%{n+valid_n:>5}")

    # ===== L2: 在训练集 top 3 附近精细化 =====
    print(f"\n[L2] 在训练集 Top 3 附近做精细化 (步长 0.05)")
    fine_results = []
    for a0, b0, c0, t0, _, _ in results_train[:3]:
        for da in [-0.1, -0.05, 0, 0.05, 0.1]:
            for db in [-0.1, -0.05, 0, 0.05, 0.1]:
                for dt in [-0.2, -0.1, 0, 0.1, 0.2]:
                    a, b, t = round(a0 + da, 3), round(b0 + db, 3), round(t0 + dt, 2)
                    c = round(1.0 - a - b, 3)
                    if a < 0 or b < 0 or c < 0 or t < 0.2 or t > 2.0:
                        continue
                    final, n = simulate_with_params(codes, all_dates, daily_data,
                                                     components, a, b, c, t, cost)
                    ret = (final / INITIAL - 1) * 100
                    fine_results.append((a, b, c, t, ret, n))
    fine_results.sort(key=lambda x: x[4], reverse=True)

    print(f"全期(L2精细化) Top 5:")
    print(f"{'排名':<5}{'a':>5}{'b':>5}{'c':>5}{'T':>5}  {'收益%':>8}{'vs等权':>8}{'换仓':>5}")
    print('-' * 60)
    eq_all = simulate_equal_weight(codes, all_dates, daily_data)
    eq_all_ret = (eq_all / INITIAL - 1) * 100
    mp_all, _ = simulate_min_premium(codes, all_dates, daily_data, cost)
    mp_all_ret = (mp_all / INITIAL - 1) * 100
    print(f"  全期基线: 等权 {eq_all_ret:+.2f}% | 最低溢价 {mp_all_ret:+.2f}%")
    for i, (a, b, c, t, ret, n) in enumerate(fine_results[:5], 1):
        print(f"{i:<5}{a:>5.2f}{b:>5.2f}{c:>5.2f}{t:>5.2f}  "
              f"{ret:>+7.2f}%{ret-eq_all_ret:>+7.2f}%{n:>5}")

    # 选择稳健最优: 训练 top 5 中, 验证集表现最好的
    train_top5 = top_candidates[:5]
    train_top5_sorted_by_valid = sorted(train_top5, key=lambda x: x[6], reverse=True)
    best_robust = train_top5_sorted_by_valid[0]
    a, b, c, t, train_ret, train_alpha, valid_ret, valid_alpha, total_n = best_robust

    print(f"\n🏆 稳健推荐 (训练集 Top5 中验证集最好):")
    print(f"   公式: F = NAV×{a} + (-超额)×{b} + (-溢价)×{c},  阈值 T={t}")
    print(f"   训练集: {train_ret:+.2f}% (vs等权 {train_alpha:+.2f}%)")
    print(f"   验证集: {valid_ret:+.2f}% (vs等权 {valid_alpha:+.2f}%)")
    print(f"   过拟合差: {abs(train_alpha - valid_alpha):.2f}% (越小越稳)")
    print(f"   总换仓: {total_n} 次, 估算总交易成本 {total_n * cost * 2:.2f}%")

    # 同时给出激进最优
    best_aggressive = fine_results[0]
    print(f"\n⚡ 激进推荐 (全期最优, 可能过拟合):")
    print(f"   公式: F = NAV×{best_aggressive[0]} + (-超额)×{best_aggressive[1]} + (-溢价)×{best_aggressive[2]}, T={best_aggressive[3]}")
    print(f"   全期: {best_aggressive[4]:+.2f}% (vs等权 {best_aggressive[4]-eq_all_ret:+.2f}%)")

    # 保存完整结果
    csv_path = OUTPUT_DIR / f'tuning_{index_type.lower()}.csv'
    with open(csv_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['a', 'b', 'c', 'threshold', 'train_return', 'train_alpha',
                    'valid_return', 'valid_alpha', 'switches'])
        for x in top_candidates:
            w.writerow(x)
    print(f"   完整训练集 Top 10 已存: {csv_path}")

    return {
        'index': index_type,
        'robust': {'a': a, 'b': b, 'c': c, 't': t,
                   'train': train_ret, 'valid': valid_ret,
                   'train_alpha': train_alpha, 'valid_alpha': valid_alpha},
        'aggressive': {'a': best_aggressive[0], 'b': best_aggressive[1],
                       'c': best_aggressive[2], 't': best_aggressive[3],
                       'return': best_aggressive[4]},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', default='all',
                        choices=['all', 'NASDAQ', 'SP500', 'NIKKEI', 'DAX'])
    parser.add_argument('--cost', type=float, default=DEFAULT_COST,
                        help=f'单边交易成本 %% (默认 {DEFAULT_COST})')
    args = parser.parse_args()

    conn = get_db()
    summary = []
    indices = ['NASDAQ', 'SP500', 'NIKKEI', 'DAX'] if args.index == 'all' else [args.index]
    for idx in indices:
        r = tune_index(conn, idx, args.cost)
        if r:
            summary.append(r)
    conn.close()

    if len(summary) > 1:
        print(f"\n{'='*100}")
        print("📋 汇总: 各指数稳健推荐配置")
        print(f"{'='*100}")
        print(f"{'指数':<10}{'a':>6}{'b':>6}{'c':>6}{'T':>6}  {'训练α%':>9}{'验证α%':>9}{'过拟合':>9}")
        print('-' * 75)
        for r in summary:
            rb = r['robust']
            print(f"{r['index']:<10}{rb['a']:>6.2f}{rb['b']:>6.2f}{rb['c']:>6.2f}{rb['t']:>6.2f}  "
                  f"{rb['train_alpha']:>+8.2f}%{rb['valid_alpha']:>+8.2f}%"
                  f"{abs(rb['train_alpha']-rb['valid_alpha']):>8.2f}%")


if __name__ == '__main__':
    main()
