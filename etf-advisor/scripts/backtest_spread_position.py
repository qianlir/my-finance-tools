#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest_spread_position.py — 溢价离散度仓位控制策略回测

策略:
  1. 每天持有溢价率最低的纳指 ETF（无条件切换）
  2. 仓位 = f(spread)，spread = max_premium - min_premium
     - spread >= 2.5% → 100%
     - 每减 0.5% → 减 20%
     - spread < 0.5% → 0%（空仓，资金闲置）

对照:
  A. 等权买入持有（10 只均分）
  B. 纯最低溢价轮动（每天切换，始终 100% 仓位）
  C. 本策略（最低溢价 + spread 仓位控制）

Usage:
    python3 scripts/backtest_spread_position.py
    python3 scripts/backtest_spread_position.py --start 2025-01-01
"""

import argparse
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR / ".."
DB_PATH = str(PROJECT_ROOT / "data" / "etf_premium.db")

NASDAQ_CODES = [
    '513100', '159941', '159660', '159501',
    '159632', '159659', '513300', '513870',
    '513390', '513110',
]

CODE_NAMES = {
    '513100': '国泰', '159941': '广发', '159660': '汇添富', '159501': '嘉实',
    '159632': '华安', '159659': '招商', '513300': '华夏', '513870': '富国',
    '513390': '博时', '513110': '南方',
}

INITIAL_CAPITAL = 100000.0
TRADE_COST = 0.0  # 无交易成本


def calc_position_pct(spread: float) -> float:
    """根据 spread 计算仓位百分比 (0.0 ~ 1.0)"""
    if spread >= 2.5:
        return 1.0
    elif spread < 0.5:
        return 0.0
    else:
        # 每 0.5% → 20%
        # 2.0-2.5 → 80%, 1.5-2.0 → 60%, 1.0-1.5 → 40%, 0.5-1.0 → 20%
        return min(1.0, int(spread / 0.5) * 0.2)


def load_data(start_date: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    placeholders = ','.join('?' * len(NASDAQ_CODES))
    rows = conn.execute(f"""
        SELECT date, code, price, premium_rate
        FROM etf_data
        WHERE code IN ({placeholders})
          AND date >= ?
          AND price IS NOT NULL AND price > 0
          AND premium_rate IS NOT NULL
        ORDER BY date, code
    """, NASDAQ_CODES + [start_date]).fetchall()
    conn.close()

    by_date = defaultdict(dict)
    for r in rows:
        by_date[r['date']][r['code']] = {
            'price': r['price'],
            'premium': r['premium_rate'],
        }
    return by_date


def run_backtest(start_date: str):
    by_date = load_data(start_date)
    dates = sorted(by_date.keys())

    if not dates:
        print("无数据")
        return

    # ========== 策略 C: spread 仓位控制 ==========
    capital = INITIAL_CAPITAL
    cash = capital
    holding_code = None
    shares = 0.0
    c_values = []  # (date, market_value, holding_code, spread, position_pct)
    c_trades = []

    # ========== 策略 B: 纯最低溢价每天换 100% ==========
    b_cash = INITIAL_CAPITAL
    b_holding = None
    b_shares = 0.0
    b_values = []

    # ========== 策略 A: 等权买入持有 ==========
    a_shares = {}  # code -> shares
    a_initialized = False
    a_values = []

    for date in dates:
        day = by_date[date]
        # 需要足够的 ETF 数据
        available = {c: d for c, d in day.items() if c in NASDAQ_CODES}
        if len(available) < 3:
            continue

        premiums = [(v['premium'], c) for c, v in available.items()]
        premiums.sort()
        min_premium, best_code = premiums[0]
        max_premium = premiums[-1][0]
        spread = max_premium - min_premium

        # --- 策略 A: 等权 ---
        if not a_initialized:
            per_etf = INITIAL_CAPITAL / len(available)
            for c, d in available.items():
                a_shares[c] = per_etf / d['price']
            a_initialized = True

        a_mv = sum(a_shares.get(c, 0) * d['price'] for c, d in available.items())
        a_values.append((date, a_mv))

        # --- 策略 B: 纯最低溢价 100% ---
        if b_holding is None:
            b_holding = best_code
            b_shares = b_cash / available[best_code]['price']
            b_cash = 0
        else:
            if b_holding in available:
                b_mv = b_shares * available[b_holding]['price']
            else:
                b_mv = b_shares * available.get(b_holding, {}).get('price', 0)
                if b_mv == 0:
                    b_values.append((date, b_values[-1][1] if b_values else INITIAL_CAPITAL))
                    continue

            if best_code != b_holding:
                # 卖出 + 买入，扣交易成本
                sell_proceeds = b_mv * (1 - TRADE_COST)
                b_shares = sell_proceeds / available[best_code]['price'] * (1 - TRADE_COST)
                b_holding = best_code
                b_mv = b_shares * available[best_code]['price']

        b_total = b_shares * available.get(b_holding, {}).get('price', 0) if b_holding in available else (b_values[-1][1] if b_values else INITIAL_CAPITAL)
        b_values.append((date, b_total))

        # --- 策略 C: spread 仓位控制 ---
        target_pct = calc_position_pct(spread)

        if holding_code is None:
            # 首日建仓
            invest = capital * target_pct
            cash = capital - invest
            if invest > 0 and best_code in available:
                shares = invest / available[best_code]['price']
                holding_code = best_code
            c_values.append((date, capital, best_code, spread, target_pct))
            continue

        # 计算当前持仓市值
        if holding_code in available:
            stock_value = shares * available[holding_code]['price']
        else:
            stock_value = shares * 0  # 停牌
            c_values.append((date, cash + stock_value, holding_code, spread, target_pct))
            continue

        total_value = cash + stock_value
        target_invest = total_value * target_pct

        # 是否需要换 ETF
        need_switch = (best_code != holding_code)
        # 是否需要调仓位
        current_invest = stock_value
        position_delta = abs(target_invest - current_invest)
        need_rebalance = (position_delta / total_value > 0.05) if total_value > 0 else False  # 超过 5% 才调

        if need_switch or need_rebalance:
            # 全部卖出
            sell_proceeds = stock_value * (1 - TRADE_COST) if stock_value > 0 else 0
            cash += sell_proceeds
            total_after_sell = cash
            shares = 0

            # 按新目标仓位买入
            invest = total_after_sell * target_pct
            cash = total_after_sell - invest

            if invest > 0 and best_code in available:
                buy_amount = invest * (1 - TRADE_COST)
                shares = buy_amount / available[best_code]['price']
                holding_code = best_code
                action = '换仓' if need_switch else '调仓'
                c_trades.append({
                    'date': date,
                    'action': action,
                    'code': best_code,
                    'name': CODE_NAMES.get(best_code, ''),
                    'spread': round(spread, 3),
                    'position_pct': target_pct,
                    'total_value': round(total_after_sell, 2),
                })

        stock_value = shares * available.get(holding_code, {}).get('price', 0) if holding_code in available else 0
        total_value = cash + stock_value
        c_values.append((date, total_value, holding_code, spread, target_pct))

    # ========== 输出结果 ==========
    print("=" * 80)
    print("纳指 ETF 溢价离散度仓位控制策略 — 回测报告")
    print(f"回测期间: {dates[0]} ~ {dates[-1]}  ({len(dates)} 个交易日)")
    print("=" * 80)

    # 最终收益
    print("\n## 最终收益对比\n")
    print(f"{'策略':<30} {'终值':>12} {'收益率':>10} {'年化':>10}")
    print("-" * 65)

    days = (datetime.strptime(dates[-1], '%Y-%m-%d') - datetime.strptime(dates[0], '%Y-%m-%d')).days
    years = days / 365.0 if days > 0 else 1

    for name, values in [
        ('A. 等权买入持有', a_values),
        ('B. 纯最低溢价轮动(100%)', b_values),
        ('C. spread仓位控制(本策略)', c_values),
    ]:
        if not values:
            continue
        if name.startswith('C'):
            final = values[-1][1]
        else:
            final = values[-1][1]
        ret = (final / INITIAL_CAPITAL - 1) * 100
        ann = ((final / INITIAL_CAPITAL) ** (1 / years) - 1) * 100 if years > 0 else 0
        print(f"{name:<30} {final:>12,.2f} {ret:>9.2f}% {ann:>9.2f}%")

    # 最大回撤
    print("\n## 最大回撤\n")
    for name, values in [
        ('A. 等权买入持有', [(v[0], v[1]) for v in a_values]),
        ('B. 纯最低溢价轮动', [(v[0], v[1]) for v in b_values]),
        ('C. spread仓位控制', [(v[0], v[1]) for v in c_values]),
    ]:
        if not values:
            continue
        peak = values[0][1]
        max_dd = 0
        dd_date = ''
        for d, v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100
            if dd > max_dd:
                max_dd = dd
                dd_date = d
        print(f"  {name}: -{max_dd:.2f}% ({dd_date})")

    # 策略 C 仓位分布
    print("\n## 策略C 仓位分布\n")
    pct_counts = defaultdict(int)
    for _, _, _, _, pct in c_values:
        bucket = f"{int(pct*100)}%"
        pct_counts[bucket] += 1

    for bucket in ['0%', '20%', '40%', '60%', '80%', '100%']:
        cnt = pct_counts.get(bucket, 0)
        ratio = cnt / len(c_values) * 100 if c_values else 0
        bar = '█' * int(ratio / 2)
        print(f"  {bucket:>4}: {cnt:>4}天 ({ratio:5.1f}%) {bar}")

    # 交易记录
    print(f"\n## 策略C 交易次数: {len(c_trades)}\n")
    if c_trades:
        print(f"{'日期':<12} {'动作':<6} {'ETF':<8} {'名称':<6} {'spread':>8} {'仓位':>6} {'总值':>12}")
        print("-" * 62)
        # 只打印前 20 和后 10
        show = c_trades[:20] + ([{'date': '...', 'action': '', 'code': '', 'name': '', 'spread': 0, 'position_pct': 0, 'total_value': 0}] if len(c_trades) > 30 else []) + c_trades[-10:]
        for t in show:
            if t['date'] == '...':
                print(f"  ... 省略 {len(c_trades) - 30} 条 ...")
                continue
            print(f"{t['date']:<12} {t['action']:<6} {t['code']:<8} {t['name']:<6} {t['spread']:>7.3f}% {t['position_pct']:>5.0%} {t['total_value']:>12,.2f}")

    # 月度收益
    print("\n## 月度收益对比\n")
    print(f"{'月份':<10} {'等权':>10} {'纯轮动':>10} {'spread策略':>10} {'spread平均':>10}")
    print("-" * 55)

    # 按月聚合
    months = defaultdict(lambda: {'a_start': None, 'a_end': None, 'b_start': None, 'b_end': None, 'c_start': None, 'c_end': None, 'spreads': []})
    for i, (d, mv) in enumerate(a_values):
        m = d[:7]
        if months[m]['a_start'] is None:
            months[m]['a_start'] = mv
        months[m]['a_end'] = mv
    for i, (d, mv) in enumerate(b_values):
        m = d[:7]
        if months[m]['b_start'] is None:
            months[m]['b_start'] = mv
        months[m]['b_end'] = mv
    for d, mv, _, spread, _ in c_values:
        m = d[:7]
        if months[m]['c_start'] is None:
            months[m]['c_start'] = mv
        months[m]['c_end'] = mv
        months[m]['spreads'].append(spread)

    for m in sorted(months.keys()):
        md = months[m]
        a_ret = ((md['a_end'] / md['a_start'] - 1) * 100) if md['a_start'] else 0
        b_ret = ((md['b_end'] / md['b_start'] - 1) * 100) if md['b_start'] else 0
        c_ret = ((md['c_end'] / md['c_start'] - 1) * 100) if md['c_start'] else 0
        avg_spread = sum(md['spreads']) / len(md['spreads']) if md['spreads'] else 0
        print(f"{m:<10} {a_ret:>9.2f}% {b_ret:>9.2f}% {c_ret:>9.2f}% {avg_spread:>9.2f}%")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', default='2025-01-01', help='回测起始日期')
    args = parser.parse_args()
    run_backtest(args.start)
