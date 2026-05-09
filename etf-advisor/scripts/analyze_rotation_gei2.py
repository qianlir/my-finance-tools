#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GEI 第二轮：寻找可量化的预测规则

分析维度：
1. 今日涨幅最大 → 明日是否继续？（动量效应）
2. 今日涨幅最小 → 明日反弹？（均值回归）
3. 溢价变化速度（今日溢价-昨日溢价）→ 预测？
4. 多日动量：过去N天累计涨幅最大 → 明日？
5. 溢价分位数：当前溢价在过去N天中的位置
6. 组合特征：动量+溢价
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

START = '2025-01-02'
END = '2026-05-08'
INITIAL = 10000.0


def load_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # 多加载一些历史用于回看
    lookback_start = '2024-07-01'
    rows = conn.execute("""
        SELECT date, code, price, premium_rate, nav
        FROM etf_data
        WHERE code IN ({}) AND date >= ? AND date <= ?
        AND price IS NOT NULL AND price > 0
        ORDER BY date, code
    """.format(','.join('?' * len(ALL_CODES))),
        ALL_CODES + [lookback_start, END]
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


def calc_returns(data, dates):
    """每天每只ETF的涨幅。"""
    # day_returns[date][code] = pct_change from previous day
    day_returns = {}
    for i in range(1, len(dates)):
        today = dates[i]
        yesterday = dates[i-1]
        ret = {}
        for code in ALL_CODES:
            if code in data[today] and code in data[yesterday]:
                p0 = data[yesterday][code]['price']
                p1 = data[today][code]['price']
                if p0 > 0:
                    ret[code] = (p1 - p0) / p0 * 100
        day_returns[today] = ret
    return day_returns


def test_strategy(dates, day_returns, select_fn, name, data=None):
    """通用策略测试框架。
    select_fn(date, available_codes, data, day_returns, dates, date_idx) -> code
    """
    value = INITIAL
    holding = None
    switches = 0
    wins = 0
    total = 0

    # 只在 START 之后交易
    trade_dates = [d for d in dates if d >= START]

    for i, date in enumerate(trade_dates):
        if date not in day_returns:
            continue
        ret = day_returns[date]
        available = [c for c in ALL_CODES if c in ret]
        if not available:
            continue

        global_idx = dates.index(date)
        target = select_fn(date, available, data, day_returns, dates, global_idx)
        if target is None or target not in ret:
            continue

        if target != holding:
            switches += 1
            holding = target

        # 用次日涨幅计算收益
        next_idx = trade_dates.index(date) + 1
        if next_idx >= len(trade_dates):
            break
        next_date = trade_dates[next_idx]
        if next_date not in day_returns or holding not in day_returns[next_date]:
            continue

        next_ret = day_returns[next_date]
        value *= (1 + next_ret[holding] / 100)

        # 是否选中了次日最佳
        best_next = max(next_ret, key=next_ret.get)
        if holding == best_next:
            wins += 1
        total += 1

    ret_pct = (value / INITIAL - 1) * 100
    hit_rate = wins / total * 100 if total > 0 else 0
    return {
        'name': name,
        'return': ret_pct,
        'switches': switches,
        'hit_rate': hit_rate,
        'value': value,
    }


def main():
    print("=" * 70)
    print("GEI 第二轮: 预测规则探索")
    print(f"回测区间: {START} ~ {END}")
    print("=" * 70)

    data = load_data()
    all_dates = sorted(data.keys())
    day_returns = calc_returns(data, all_dates)

    strategies = []

    # === 策略 1: 今日涨幅最大 → 明日继续（动量） ===
    def momentum_today(date, codes, data, dr, dates, idx):
        if date not in dr:
            return None
        return max(codes, key=lambda c: dr[date].get(c, 0))
    strategies.append(test_strategy(all_dates, day_returns, momentum_today, '动量: 今日涨幅最大', data))

    # === 策略 2: 今日涨幅最小 → 明日反弹（均值回归） ===
    def mean_revert_today(date, codes, data, dr, dates, idx):
        if date not in dr:
            return None
        return min(codes, key=lambda c: dr[date].get(c, 0))
    strategies.append(test_strategy(all_dates, day_returns, mean_revert_today, '回归: 今日涨幅最小', data))

    # === 策略 3: 当日溢价最低 ===
    def lowest_premium(date, codes, data, dr, dates, idx):
        prems = {c: data[date][c]['premium_rate'] for c in codes
                 if c in data[date] and data[date][c]['premium_rate'] is not None}
        return min(prems, key=prems.get) if prems else None
    strategies.append(test_strategy(all_dates, day_returns, lowest_premium, '溢价: 当日最低', data))

    # === 策略 4: 当日溢价最高 ===
    def highest_premium(date, codes, data, dr, dates, idx):
        prems = {c: data[date][c]['premium_rate'] for c in codes
                 if c in data[date] and data[date][c]['premium_rate'] is not None}
        return max(prems, key=prems.get) if prems else None
    strategies.append(test_strategy(all_dates, day_returns, highest_premium, '溢价: 当日最高', data))

    # === 策略 5: 溢价下降最快（今日溢价 - 昨日溢价 最小） ===
    def premium_drop_fastest(date, codes, data, dr, dates, idx):
        if idx < 1:
            return None
        yesterday = dates[idx - 1]
        deltas = {}
        for c in codes:
            if (c in data[date] and c in data[yesterday]
                and data[date][c]['premium_rate'] is not None
                and data[yesterday][c]['premium_rate'] is not None):
                deltas[c] = data[date][c]['premium_rate'] - data[yesterday][c]['premium_rate']
        return min(deltas, key=deltas.get) if deltas else None
    strategies.append(test_strategy(all_dates, day_returns, premium_drop_fastest, '溢价变化: 下降最快', data))

    # === 策略 6: 溢价上升最快 ===
    def premium_rise_fastest(date, codes, data, dr, dates, idx):
        if idx < 1:
            return None
        yesterday = dates[idx - 1]
        deltas = {}
        for c in codes:
            if (c in data[date] and c in data[yesterday]
                and data[date][c]['premium_rate'] is not None
                and data[yesterday][c]['premium_rate'] is not None):
                deltas[c] = data[date][c]['premium_rate'] - data[yesterday][c]['premium_rate']
        return max(deltas, key=deltas.get) if deltas else None
    strategies.append(test_strategy(all_dates, day_returns, premium_rise_fastest, '溢价变化: 上升最快', data))

    # === 策略 7: 过去3天累计涨幅最大 ===
    for lookback in [3, 5, 10]:
        def multi_day_momentum(date, codes, data, dr, dates, idx, lb=lookback):
            if idx < lb:
                return None
            cum = {}
            for c in codes:
                total = 0
                valid = True
                for j in range(lb):
                    d = dates[idx - j]
                    if d in dr and c in dr[d]:
                        total += dr[d].get(c, 0)
                    else:
                        valid = False
                        break
                if valid:
                    cum[c] = total
            return max(cum, key=cum.get) if cum else None
        strategies.append(test_strategy(all_dates, day_returns, multi_day_momentum, f'动量: 过去{lookback}天累计最大', data))

    # === 策略 8: 过去3天累计涨幅最小（多日回归） ===
    for lookback in [3, 5]:
        def multi_day_revert(date, codes, data, dr, dates, idx, lb=lookback):
            if idx < lb:
                return None
            cum = {}
            for c in codes:
                total = 0
                valid = True
                for j in range(lb):
                    d = dates[idx - j]
                    if d in dr and c in dr[d]:
                        total += dr[d].get(c, 0)
                    else:
                        valid = False
                        break
                if valid:
                    cum[c] = total
            return min(cum, key=cum.get) if cum else None
        strategies.append(test_strategy(all_dates, day_returns, multi_day_revert, f'回归: 过去{lookback}天累计最小', data))

    # === 策略 9: 溢价低于过去20天均值最多 ===
    def premium_below_avg(date, codes, data, dr, dates, idx, lookback=20):
        if idx < lookback:
            return None
        deviations = {}
        for c in codes:
            if c not in data[date] or data[date][c]['premium_rate'] is None:
                continue
            current = data[date][c]['premium_rate']
            hist = []
            for j in range(1, lookback + 1):
                d = dates[idx - j]
                if c in data[d] and data[d][c]['premium_rate'] is not None:
                    hist.append(data[d][c]['premium_rate'])
            if hist:
                avg = sum(hist) / len(hist)
                deviations[c] = current - avg
        return min(deviations, key=deviations.get) if deviations else None
    strategies.append(test_strategy(all_dates, day_returns, premium_below_avg, '溢价偏离: 低于20日均值最多', data))

    # === 策略 10: 综合 — 溢价偏离低 + 近期涨幅小（低溢价+回归双因子） ===
    def combo_low_prem_revert(date, codes, data, dr, dates, idx, lookback=20, ret_lb=3):
        if idx < max(lookback, ret_lb):
            return None
        scores = {}
        for c in codes:
            if c not in data[date] or data[date][c]['premium_rate'] is None:
                continue
            current_prem = data[date][c]['premium_rate']
            hist = []
            for j in range(1, lookback + 1):
                d = dates[idx - j]
                if c in data[d] and data[d][c]['premium_rate'] is not None:
                    hist.append(data[d][c]['premium_rate'])
            if not hist:
                continue
            prem_deviation = current_prem - sum(hist) / len(hist)

            cum_ret = 0
            for j in range(ret_lb):
                d = dates[idx - j]
                if d in dr and c in dr[d]:
                    cum_ret += dr[d].get(c, 0)

            # 低溢价偏离 + 低近期涨幅 → 低分好
            scores[c] = prem_deviation * 0.5 + cum_ret * 0.5
        return min(scores, key=scores.get) if scores else None
    strategies.append(test_strategy(all_dates, day_returns, combo_low_prem_revert, '组合: 低溢价偏离+3日回归', data))

    # === 策略 11: 高溢价 + 动量（验证高溢价是否有用） ===
    def combo_high_prem_momentum(date, codes, data, dr, dates, idx):
        if idx < 3:
            return None
        scores = {}
        for c in codes:
            if c not in data[date] or data[date][c]['premium_rate'] is None:
                continue
            prem = data[date][c]['premium_rate']
            cum_ret = sum(dr.get(dates[idx-j], {}).get(c, 0) for j in range(3))
            scores[c] = prem * 0.3 + cum_ret * 0.7
        return max(scores, key=scores.get) if scores else None
    strategies.append(test_strategy(all_dates, day_returns, combo_high_prem_momentum, '组合: 高溢价+3日动量', data))

    # === 输出 ===
    print()
    print(f"  {'策略':<32s}  {'收益':>8s}  {'切换':>5s}  {'命中率':>6s}  {'效率':>8s}")
    print("  " + "-" * 68)
    strategies.sort(key=lambda x: -x['return'])
    for s in strategies:
        eff = s['return'] / s['switches'] if s['switches'] > 0 else 0
        print(f"  {s['name']:<32s}  {s['return']:>+7.1f}%  {s['switches']:>4d}次  {s['hit_rate']:>5.1f}%  {eff:>+7.2f}%/次")

    # 等权基准
    trade_dates = [d for d in all_dates if d >= START]
    first = trade_dates[0]
    last = trade_dates[-1]
    per_etf = INITIAL / len(ALL_CODES)
    eq_shares = {c: per_etf / data[first][c]['price'] for c in ALL_CODES if c in data[first]}
    eq_val = sum(eq_shares.get(c, 0) * data[last].get(c, {}).get('price', 0) for c in ALL_CODES)
    eq_ret = (eq_val / INITIAL - 1) * 100
    print(f"  {'等权持有(基准)':<32s}  {eq_ret:>+7.1f}%  {'—':>5s}  {'—':>6s}")

    print()
    print("=" * 70)


if __name__ == '__main__':
    main()
