#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_rotation_ceiling.py — 纳指ETF轮动上限分析

1. 计算完美预知下的涨幅上限（每天买入次日涨幅最大的ETF）
2. 分析切换规律：哪些ETF最常胜出、连续持有天数、切换频率
3. 寻找可量化的特征规律

Usage:
    python3 scripts/analyze_rotation_ceiling.py
"""

import sqlite3
import json
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

START = '2025-05-09'
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
        ALL_CODES + [START, END]
    ).fetchall()
    conn.close()

    # {date: {code: {price, premium_rate, nav}}}
    data = defaultdict(dict)
    for r in rows:
        data[r['date']][r['code']] = {
            'price': r['price'],
            'premium_rate': r['premium_rate'],
            'nav': r['nav'],
        }
    return data


def calc_next_day_returns(data, dates):
    """计算每只ETF的次日涨幅。"""
    # returns[i] = {code: next_day_return_pct}  (日期 dates[i] 买入, dates[i+1] 卖出)
    returns = []
    for i in range(len(dates) - 1):
        today = dates[i]
        tomorrow = dates[i + 1]
        day_returns = {}
        for code in ALL_CODES:
            if code in data[today] and code in data[tomorrow]:
                p0 = data[today][code]['price']
                p1 = data[tomorrow][code]['price']
                if p0 > 0:
                    day_returns[code] = (p1 - p0) / p0 * 100
        returns.append((today, tomorrow, day_returns))
    return returns


def analyze_ceiling(returns):
    """完美预知：每天买入次日涨幅最大的ETF。"""
    value = INITIAL
    trades = []
    holding = None
    switches = 0
    win_counts = Counter()

    for today, tomorrow, day_ret in returns:
        if not day_ret:
            continue
        best_code = max(day_ret, key=day_ret.get)
        best_ret = day_ret[best_code]
        win_counts[best_code] += 1

        if holding != best_code:
            switches += 1
            holding = best_code

        value *= (1 + best_ret / 100)
        trades.append({
            'date': today, 'next': tomorrow,
            'code': best_code, 'ret': best_ret,
            'value': value,
        })

    return value, switches, win_counts, trades


def analyze_hold_streaks(returns):
    """分析每只ETF连续胜出的天数分布。"""
    streaks = []  # [(code, streak_length, start_date, end_date)]
    current_code = None
    streak_start = None
    streak_len = 0

    for today, tomorrow, day_ret in returns:
        if not day_ret:
            continue
        best = max(day_ret, key=day_ret.get)
        if best == current_code:
            streak_len += 1
        else:
            if current_code:
                streaks.append((current_code, streak_len, streak_start, today))
            current_code = best
            streak_start = today
            streak_len = 1

    if current_code:
        streaks.append((current_code, streak_len, streak_start, returns[-1][0]))

    return streaks


def analyze_features(data, dates, returns):
    """分析特征与次日胜出的关系。"""
    # 对每天，记录各ETF的特征，看哪些特征与"次日涨幅最大"相关
    feature_analysis = {
        'lowest_premium_wins': 0,
        'lowest_premium_top3': 0,
        'highest_premium_wins': 0,
        'lowest_price_wins': 0,
        'total_days': 0,
    }

    premium_rank_of_winner = []  # 胜者在当日溢价排名中的位置(1=最低)

    for today, tomorrow, day_ret in returns:
        if not day_ret or len(day_ret) < 5:
            continue

        feature_analysis['total_days'] += 1
        best_code = max(day_ret, key=day_ret.get)

        # 当日各ETF溢价排名
        day_premiums = {}
        for code in day_ret:
            if code in data[today] and data[today][code]['premium_rate'] is not None:
                day_premiums[code] = data[today][code]['premium_rate']

        if not day_premiums:
            continue

        sorted_by_prem = sorted(day_premiums, key=day_premiums.get)  # 低→高
        lowest_prem_code = sorted_by_prem[0]
        highest_prem_code = sorted_by_prem[-1]

        if best_code == lowest_prem_code:
            feature_analysis['lowest_premium_wins'] += 1
        if best_code in sorted_by_prem[:3]:
            feature_analysis['lowest_premium_top3'] += 1
        if best_code == highest_prem_code:
            feature_analysis['highest_premium_wins'] += 1

        # 胜者在溢价排名中的位置
        if best_code in sorted_by_prem:
            rank = sorted_by_prem.index(best_code) + 1
            premium_rank_of_winner.append(rank)

        # 最低价格ETF是否胜出
        day_prices = {c: data[today][c]['price'] for c in day_ret if c in data[today]}
        if day_prices:
            lowest_price = min(day_prices, key=day_prices.get)
            if best_code == lowest_price:
                feature_analysis['lowest_price_wins'] += 1

    if premium_rank_of_winner:
        feature_analysis['avg_premium_rank_of_winner'] = sum(premium_rank_of_winner) / len(premium_rank_of_winner)
        # 分布
        rank_dist = Counter(premium_rank_of_winner)
        feature_analysis['premium_rank_distribution'] = dict(sorted(rank_dist.items()))

    return feature_analysis


def analyze_reduced_switching(returns, max_switches_per_month=None):
    """尝试减少切换次数：只在分值差异足够大时切换。
    策略：持有当前ETF，除非有ETF的次日涨幅连续N天超过当前持仓。
    这里用简化版：设置最小持仓天数。
    """
    results = {}

    for min_hold in [1, 2, 3, 5, 7, 10, 15, 20]:
        value = INITIAL
        holding = None
        hold_days = 0
        switches = 0

        for today, tomorrow, day_ret in returns:
            if not day_ret:
                continue
            best_code = max(day_ret, key=day_ret.get)

            if holding is None:
                holding = best_code
                hold_days = 1
                switches = 1
            elif hold_days >= min_hold and best_code != holding:
                holding = best_code
                hold_days = 1
                switches += 1
            else:
                hold_days += 1

            if holding in day_ret:
                value *= (1 + day_ret[holding] / 100)

        ret_pct = (value / INITIAL - 1) * 100
        results[min_hold] = {'value': value, 'return': ret_pct, 'switches': switches}

    return results


def analyze_premium_based_strategy(data, dates, returns):
    """基于溢价的策略：每天买入溢价最低的ETF，分析表现。"""
    strategies = {}

    # 策略1: 每天切换到溢价最低
    value_lowest = INITIAL
    switches_lowest = 0
    holding = None
    for today, tomorrow, day_ret in returns:
        if not day_ret:
            continue
        day_premiums = {c: data[today][c]['premium_rate']
                       for c in day_ret if c in data[today] and data[today][c]['premium_rate'] is not None}
        if not day_premiums:
            continue
        target = min(day_premiums, key=day_premiums.get)
        if target != holding:
            switches_lowest += 1
            holding = target
        if holding in day_ret:
            value_lowest *= (1 + day_ret[holding] / 100)

    strategies['lowest_premium_daily'] = {
        'value': value_lowest,
        'return': (value_lowest / INITIAL - 1) * 100,
        'switches': switches_lowest,
    }

    # 策略2: 溢价最低且持仓>=3天
    for min_hold in [3, 5, 7]:
        value = INITIAL
        switches = 0
        holding = None
        hold_days = 0
        for today, tomorrow, day_ret in returns:
            if not day_ret:
                continue
            day_premiums = {c: data[today][c]['premium_rate']
                           for c in day_ret if c in data[today] and data[today][c]['premium_rate'] is not None}
            if not day_premiums:
                continue
            target = min(day_premiums, key=day_premiums.get)
            if holding is None:
                holding = target
                hold_days = 1
                switches = 1
            elif hold_days >= min_hold and target != holding:
                holding = target
                hold_days = 1
                switches += 1
            else:
                hold_days += 1
            if holding in day_ret:
                value *= (1 + day_ret[holding] / 100)

        strategies[f'lowest_premium_hold{min_hold}'] = {
            'value': value,
            'return': (value / INITIAL - 1) * 100,
            'switches': switches,
        }

    # 策略3: 溢价最低的N只中，选涨幅最大的
    for top_n in [2, 3, 4]:
        value = INITIAL
        switches = 0
        holding = None
        for today, tomorrow, day_ret in returns:
            if not day_ret:
                continue
            day_premiums = {c: data[today][c]['premium_rate']
                           for c in day_ret if c in data[today] and data[today][c]['premium_rate'] is not None}
            if not day_premiums or len(day_premiums) < top_n:
                continue
            low_n = sorted(day_premiums, key=day_premiums.get)[:top_n]
            # 从低溢价N只中选次日涨幅最大的（完美预知版本，后续替换为可计算特征）
            target = max(low_n, key=lambda c: day_ret.get(c, 0))
            if target != holding:
                switches += 1
                holding = target
            if holding in day_ret:
                value *= (1 + day_ret[holding] / 100)

        strategies[f'top{top_n}_lowest_prem_best_ret'] = {
            'value': value,
            'return': (value / INITIAL - 1) * 100,
            'switches': switches,
        }

    return strategies


def main():
    print("=" * 60)
    print("纳指ETF轮动上限分析")
    print(f"区间: {START} ~ {END}")
    print("=" * 60)

    data = load_data()
    dates = sorted(data.keys())
    print(f"共 {len(dates)} 个交易日, {len(ALL_CODES)} 只ETF\n")

    returns = calc_next_day_returns(data, dates)

    # ===== 1. 完美预知上限 =====
    ceiling_value, ceiling_switches, win_counts, ceiling_trades = analyze_ceiling(returns)
    ceiling_ret = (ceiling_value / INITIAL - 1) * 100

    print("【1. 完美预知上限】")
    print(f"  终值: ¥{ceiling_value:,.0f}  收益: {ceiling_ret:+.1f}%  切换: {ceiling_switches}次")
    print(f"  日均切换: {ceiling_switches/len(returns):.2f}次/天")
    print()
    print("  各ETF胜出天数:")
    for code, count in win_counts.most_common():
        pct = count / len(returns) * 100
        print(f"    {CODE_NAME[code]:4s} {code}  {count:3d}天 ({pct:.1f}%)")

    # ===== 2. 连续持有分析 =====
    streaks = analyze_hold_streaks(returns)
    streak_lens = [s[1] for s in streaks]
    print()
    print("【2. 连续持有天数分布】")
    len_dist = Counter(streak_lens)
    for length in sorted(len_dist.keys()):
        print(f"    {length}天: {len_dist[length]}次")
    print(f"  平均连续天数: {sum(streak_lens)/len(streak_lens):.1f}")
    print(f"  最长连续: {max(streak_lens)}天")

    # 统计哪些ETF有长连续
    long_streaks = [(c, l, s, e) for c, l, s, e in streaks if l >= 5]
    if long_streaks:
        print(f"\n  ≥5天连续持有:")
        for code, length, start, end in long_streaks:
            print(f"    {CODE_NAME[code]} {code}: {length}天 ({start} ~ {end})")

    # ===== 3. 减少切换分析 =====
    reduced = analyze_reduced_switching(returns)
    print()
    print("【3. 最小持仓天数 vs 收益】")
    print(f"  {'持仓天数':>8s}  {'收益':>8s}  {'切换次数':>6s}  {'效率(收益/切换)':>12s}")
    for min_hold in sorted(reduced.keys()):
        r = reduced[min_hold]
        eff = r['return'] / r['switches'] if r['switches'] > 0 else 0
        marker = ' ★' if min_hold == 1 else ''
        print(f"  {min_hold:>6d}天  {r['return']:>+7.1f}%  {r['switches']:>5d}次  {eff:>10.2f}%/次{marker}")

    # ===== 4. 特征分析 =====
    features = analyze_features(data, dates, returns)
    total = features['total_days']
    print()
    print("【4. 特征与胜出关系】")
    print(f"  总分析天数: {total}")
    print(f"  溢价最低ETF次日胜出: {features['lowest_premium_wins']}/{total} ({features['lowest_premium_wins']/total*100:.1f}%)")
    print(f"  溢价最低3只含胜者: {features['lowest_premium_top3']}/{total} ({features['lowest_premium_top3']/total*100:.1f}%)")
    print(f"  溢价最高ETF次日胜出: {features['highest_premium_wins']}/{total} ({features['highest_premium_wins']/total*100:.1f}%)")
    print(f"  价格最低ETF次日胜出: {features['lowest_price_wins']}/{total} ({features['lowest_price_wins']/total*100:.1f}%)")
    if 'avg_premium_rank_of_winner' in features:
        print(f"  胜者平均溢价排名: {features['avg_premium_rank_of_winner']:.1f} (1=最低, 10=最高)")
    if 'premium_rank_distribution' in features:
        print(f"  胜者溢价排名分布:")
        for rank, count in features['premium_rank_distribution'].items():
            bar = '█' * (count // 3)
            print(f"    第{rank:2d}低: {count:3d}天 {bar}")

    # ===== 5. 基于溢价的策略对比 =====
    prem_strategies = analyze_premium_based_strategy(data, dates, returns)
    print()
    print("【5. 溢价策略对比】")
    print(f"  {'策略':>30s}  {'收益':>8s}  {'切换':>5s}  {'效率':>8s}")
    print(f"  {'完美预知(上限)':>30s}  {ceiling_ret:>+7.1f}%  {ceiling_switches:>4d}次  {ceiling_ret/ceiling_switches:.2f}%/次")
    for name, r in sorted(prem_strategies.items(), key=lambda x: -x[1]['return']):
        eff = r['return'] / r['switches'] if r['switches'] > 0 else 0
        print(f"  {name:>30s}  {r['return']:>+7.1f}%  {r['switches']:>4d}次  {eff:.2f}%/次")

    # ===== 6. 等权基准 =====
    eq_value = INITIAL
    per_etf = INITIAL / len(ALL_CODES)
    eq_shares = {}
    first_date = dates[0]
    for code in ALL_CODES:
        if code in data[first_date]:
            eq_shares[code] = per_etf / data[first_date][code]['price']
    last_date = dates[-1]
    eq_value = sum(eq_shares.get(c, 0) * data[last_date].get(c, {}).get('price', 0) for c in ALL_CODES)
    eq_ret = (eq_value / INITIAL - 1) * 100
    print(f"  {'等权持有(基准)':>30s}  {eq_ret:>+7.1f}%  {'0':>4s}次")

    print()
    print("=" * 60)


if __name__ == '__main__':
    main()
