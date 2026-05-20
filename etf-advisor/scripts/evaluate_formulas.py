#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evaluate_formulas.py — 评估不同评分公式的实际回测效果

对每个指数, 测试多种评分公式 + 不同阈值的组合,
基于真实历史数据 (2025-01-01 起) 回测, 输出对比矩阵.

公式候选:
  F0 (现行): NAV×0.10 + (-超额)×0.80 + (-溢价)×0.10
  F1 (重溢价): NAV×0.10 + (-超额)×0.40 + (-溢价)×0.50
  F2 (纯溢价): NAV×0.0 + (-超额)×0.0 + (-溢价)×1.0  ≈ 最低溢价
  F3 (重当前): NAV×0.0 + (-超额)×0.30 + (-溢价)×0.70
  F4 (只看溢价超额): NAV×0.0 + (-超额)×1.0 + (-溢价)×0.0
  F5 (NAV+溢价): NAV×0.30 + (-超额)×0.20 + (-溢价)×0.50

阈值: 0.5, 0.8, 1.0, 1.5, 2.0
轮动加分: 池内全部 ETF 用 +0.5, 池外不存在 (即所有ETF同池, 加分无效果)

Usage:
    python3 scripts/evaluate_formulas.py
    python3 scripts/evaluate_formulas.py --index SP500
"""

import argparse
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR / ".."
DB_PATH = str(PROJECT_ROOT / "data" / "etf_premium.db")

DATA_START = '2025-01-02'
INITIAL = 10000.0
PERIODS = [('1M', 30), ('3M', 90), ('6M', 180), ('1Y', 365), ('ALL', None)]
WEIGHTS = {'1M': 0.35, '3M': 0.25, '6M': 0.20, '1Y': 0.10, 'ALL': 0.10}

INDEX_ETFS = {
    'NASDAQ': ['513100','159941','159660','159501','159632','159659','513300','513870','513390','513110'],
    'SP500':  ['513500','159655','513650','159612'],
    'NIKKEI': ['159866','513000','513520','513880'],
    'DAX':    ['513030','159561'],
}

# 公式候选: (name, w_nav, w_excess, w_premium)
FORMULAS = [
    ('F0_现行',      0.10, 0.80, 0.10),
    ('F1_重溢价',    0.10, 0.40, 0.50),
    ('F2_纯溢价',    0.00, 0.00, 1.00),
    ('F3_重当前',    0.00, 0.30, 0.70),
    ('F4_只超额',    0.00, 1.00, 0.00),
    ('F5_NAV溢价',   0.30, 0.20, 0.50),
    ('F6_平衡',      0.10, 0.50, 0.40),
    ('F7_保留Nav',   0.20, 0.30, 0.50),
]

THRESHOLDS = [0.3, 0.5, 0.8, 1.0, 1.5]


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


def compute_rolling_avg(plist, cur_idx, period_days):
    if cur_idx < 0:
        return None
    cur_date_str = plist[cur_idx][0]
    cur_date = datetime.strptime(cur_date_str, '%Y-%m-%d')
    if period_days is None:
        vals = [plist[i][1] for i in range(cur_idx) if plist[i][1] is not None]
    else:
        start = (cur_date - timedelta(days=period_days)).strftime('%Y-%m-%d')
        vals = [plist[i][1] for i in range(cur_idx) if plist[i][0] >= start and plist[i][1] is not None]
    return sum(vals) / len(vals) if vals else None


def compute_nav_return_1y(premium_by_code, code, cur_date_str, daily_data):
    cur = daily_data.get(cur_date_str, {}).get(code)
    if not cur or not cur['nav'] or cur['nav'] <= 0:
        return 0.0
    tgt = (datetime.strptime(cur_date_str, '%Y-%m-%d') - timedelta(days=365)).strftime('%Y-%m-%d')
    nav_list = premium_by_code.get(code, [])
    best_nav = None
    for d, _ in nav_list:
        if d > tgt:
            break
        info = daily_data.get(d, {}).get(code)
        if info and info['nav'] and info['nav'] > 0:
            best_nav = info['nav']
    if best_nav and best_nav > 0:
        return (cur['nav'] / best_nav - 1) * 100
    return 0.0


def compute_scores(codes, trading_dates, premium_by_code, daily_data, formula):
    """对每个日期、每只ETF, 用指定公式计算 score, 返回 {date: {code: score}}."""
    name, w_nav, w_excess, w_premium = formula
    idx_maps = {}
    for c in codes:
        plist = premium_by_code.get(c, [])
        idx_maps[c] = (plist, {d: i for i, (d, _) in enumerate(plist)})

    scores = defaultdict(dict)
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
            for pname, pdays in PERIODS:
                hist = compute_rolling_avg(plist, ci, pdays)
                if hist is not None:
                    composite += (premium - hist) * WEIGHTS[pname]
            nav_ret = compute_nav_return_1y(premium_by_code, c, date, daily_data)
            score = nav_ret * w_nav + (-composite) * w_excess + (-premium) * w_premium
            scores[date][c] = score
    return scores


def simulate(codes, trading_dates, daily_data, scores, threshold):
    """模拟轮动: 阈值 threshold. 返回 (final_value, n_switches, switches_list)."""
    holding = None
    shares = 0.0
    n_switches = 0
    final_value = INITIAL
    switches = []  # 记录每次换仓的(date, from, to, premium_diff)

    for date in trading_dates:
        day_scores = scores.get(date, {})
        if not day_scores:
            continue
        day = daily_data.get(date, {})
        # 找到分值最高且有数据的
        best_code = None
        best_score = float('-inf')
        for c in codes:
            if c not in day or c not in day_scores:
                continue
            if day_scores[c] > best_score:
                best_score = day_scores[c]
                best_code = c
        if best_code is None:
            continue

        if holding is None:
            holding = best_code
            shares = INITIAL / day[best_code]['price']
            final_value = INITIAL
            continue

        if holding not in day or holding not in day_scores:
            final_value = shares * day.get(holding, {}).get('price', final_value / shares if shares else INITIAL)
            continue

        holding_score = day_scores[holding]
        final_value = shares * day[holding]['price']

        if best_code != holding and (best_score - holding_score) >= threshold:
            sell_premium = day[holding]['premium_rate']
            buy_premium = day[best_code]['premium_rate']
            switches.append({
                'date': date, 'sell': holding, 'buy': best_code,
                'sell_premium': sell_premium, 'buy_premium': buy_premium,
                'premium_diff': (sell_premium or 0) - (buy_premium or 0),
            })
            cash = final_value
            holding = best_code
            shares = cash / day[best_code]['price']
            final_value = cash
            n_switches += 1

    return final_value, n_switches, switches


def simulate_min_premium(codes, trading_dates, daily_data):
    """最低溢价策略基线."""
    holding = None
    shares = 0.0
    final = INITIAL
    n_switches = 0
    for date in trading_dates:
        day = daily_data.get(date, {})
        if not day:
            continue
        candidates = [(day[c]['premium_rate'], c) for c in codes
                      if c in day and day[c]['premium_rate'] is not None]
        if not candidates:
            continue
        candidates.sort()
        lowest_code = candidates[0][1]
        if holding is None:
            holding = lowest_code
            shares = INITIAL / day[lowest_code]['price']
            continue
        if holding not in day:
            continue
        final = shares * day[holding]['price']
        if lowest_code != holding:
            cash = final
            holding = lowest_code
            shares = cash / day[lowest_code]['price']
            final = cash
            n_switches += 1
    return final, n_switches


def simulate_equal_weight(codes, trading_dates, daily_data):
    """等权 buy & hold."""
    first_date = trading_dates[0] if trading_dates else None
    if not first_date:
        return INITIAL
    first_prices = daily_data.get(first_date, {})
    per = INITIAL / len(codes)
    shares = {}
    for c in codes:
        if c in first_prices and first_prices[c]['price'] > 0:
            shares[c] = per / first_prices[c]['price']
    last_value = INITIAL
    for date in trading_dates:
        day = daily_data.get(date, {})
        total = sum(shares.get(c, 0) * day.get(c, {}).get('price', 0) for c in codes)
        if total > 0:
            last_value = total
    return last_value


def evaluate_index(conn, index_type):
    codes = INDEX_ETFS[index_type]
    print(f"\n{'='*100}")
    print(f"指数: {index_type}  ({len(codes)}只ETF)")
    print(f"{'='*100}")

    # 加载数据
    lookback = '2023-11-29'
    premium_by_code, daily_data = load_all_data(conn, codes, lookback)
    trading_dates = sorted(set(d for d in daily_data.keys() if d >= DATA_START))

    if not trading_dates:
        print("  无数据")
        return

    print(f"回测期: {trading_dates[0]} ~ {trading_dates[-1]} ({len(trading_dates)}天)")

    # 基线
    eq_value = simulate_equal_weight(codes, trading_dates, daily_data)
    eq_ret = (eq_value / INITIAL - 1) * 100
    mp_value, mp_switches = simulate_min_premium(codes, trading_dates, daily_data)
    mp_ret = (mp_value / INITIAL - 1) * 100

    print(f"\n基线 - 等权持有: {eq_ret:+.2f}%")
    print(f"基线 - 最低溢价: {mp_ret:+.2f}% (换仓{mp_switches}次)")
    print(f"\n{'公式':<14} {'阈值':<6} {'收益%':<9} {'vs等权':<9} {'vs最低溢价':<11} {'换仓数':<6} {'平均溢价差':<11}")
    print('-' * 100)

    best = None
    best_alpha_eq = float('-inf')

    for formula in FORMULAS:
        scores = compute_scores(codes, trading_dates, premium_by_code, daily_data, formula)
        for thr in THRESHOLDS:
            final, n_sw, switches = simulate(codes, trading_dates, daily_data, scores, thr)
            ret = (final / INITIAL - 1) * 100
            alpha_eq = ret - eq_ret
            alpha_mp = ret - mp_ret
            avg_pdiff = sum(s['premium_diff'] for s in switches) / len(switches) if switches else 0
            marker = ''
            if alpha_eq > best_alpha_eq:
                best_alpha_eq = alpha_eq
                best = (formula[0], thr, ret, alpha_eq, alpha_mp, n_sw, avg_pdiff)
                marker = ' ⭐'
            print(f"{formula[0]:<14} {thr:<6} {ret:>+7.2f}%  {alpha_eq:>+7.2f}%  {alpha_mp:>+8.2f}%  "
                  f"{n_sw:>4}    {avg_pdiff:>+8.2f}%{marker}")

    print(f"\n🏆 最优组合: 公式 {best[0]}, 阈值 {best[1]}")
    print(f"   收益 {best[2]:+.2f}%, vs等权 {best[3]:+.2f}%, vs最低溢价 {best[4]:+.2f}%, "
          f"{best[5]}次换仓, 平均溢价差 {best[6]:+.2f}%")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', default='all',
                        choices=['all', 'NASDAQ', 'SP500', 'NIKKEI', 'DAX'])
    args = parser.parse_args()

    conn = get_db()
    if args.index == 'all':
        for idx in ['NASDAQ', 'SP500', 'NIKKEI', 'DAX']:
            evaluate_index(conn, idx)
    else:
        evaluate_index(conn, args.index)
    conn.close()


if __name__ == '__main__':
    main()
