#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
premium_rotation_backtest.py — 溢价轮动策略回测

策略：持有溢价率最低的2只ETF
- 每日换仓：每天重新选择溢价率最低的2只
- 条件换仓：溢价率变化超过阈值时才换

使用价格计算收益（不是净值）
"""

import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "etf_premium.db"

# 纳指ETF代码
NASDAQ_ETFS = ['159660', '159632', '159941', '513100', '513300']

# 日期范围
START_DATE = '2025-03-30'
END_DATE = '2026-03-30'

def get_daily_data():
    """获取每日价格和溢价数据"""
    conn = sqlite3.connect(str(DB_PATH))

    placeholders = ','.join('?' * len(NASDAQ_ETFS))
    query = f"""
        SELECT date, code, price, premium_rate
        FROM etf_data
        WHERE code IN ({placeholders})
          AND date >= ? AND date <= ?
          AND price IS NOT NULL AND price > 0
          AND premium_rate IS NOT NULL
        ORDER BY date, code
    """

    df = pd.read_sql_query(query, conn, params=NASDAQ_ETFS + [START_DATE, END_DATE])
    conn.close()
    return df

def simulate_premium_rotation(df, threshold=None):
    """
    模拟溢价轮动策略

    Args:
        df: 包含 date, code, price, premium_rate 的 DataFrame
        threshold: 换仓阈值（溢价率差值）。None=每日换仓，0.5=差值>0.5%才换
    """
    df = df.sort_values(['date', 'code']).copy()

    # 透视表：每行是一个交易日，每列是一只ETF的价格
    price_df = df.pivot(index='date', columns='code', values='price')

    # 溢价率透视表
    premium_df = df.pivot(index='date', columns='code', values='premium_rate')

    dates = sorted(price_df.index.tolist())
    if not dates:
        return None

    # 初始配置
    initial_capital = 100000
    cash = initial_capital
    holdings = {}  # {code: shares}

    # 策略名称
    strategy_name = f"溢价轮动(阈值={threshold})" if threshold else "溢价轮动(每日)"

    print(f"\n{'='*60}")
    print(f"  {strategy_name}")
    print(f"  日期: {START_DATE} ~ {END_DATE}")
    print(f"  初始资金: ¥{initial_capital:,.0f}")
    print(f"{'='*60}")

    # 第一天：选择溢价率最低的2只
    first_date = dates[0]
    available = premium_df.loc[first_date].dropna()
    if len(available) < 2:
        print(f"  错误: 第一天只有 {len(available)} 只ETF有数据")
        return None

    # 按溢价率排序，选择最低的2只
    sorted_etfs = available.sort_values().index.tolist()
    selected = sorted_etfs[:2]

    # 等权重买入
    per_etf_cash = cash / 2
    for code in selected:
        shares = per_etf_cash / price_df.loc[first_date, code]
        holdings[code] = shares

    print(f"  首日 ({first_date}): 买入 {selected}")

    # 跟踪
    trades = 0
    prev_selected = selected.copy()
    values = []

    for date in dates[1:]:
        # 计算当前市值
        mv = sum(holdings.get(code, 0) * price_df.loc[date, code]
                 for code in holdings if code in price_df.columns)
        values.append({'date': date, 'value': mv})

        # 选择溢价率最低的2只
        available = premium_df.loc[date].dropna()
        sorted_etfs = available.sort_values().index.tolist()
        new_selected = sorted_etfs[:2]

        # 检查是否需要换仓
        needs_rebalance = False

        if threshold is None:
            # 每日换仓
            needs_rebalance = True
        else:
            # 计算当前持仓与新选择的溢价率差值
            # 如果新选择的ETF溢价率明显更低，则换仓
            current_premiums = [premium_df.loc[date, code] for code in prev_selected if code in available.index]
            new_premiums = [premium_df.loc[date, code] for code in new_selected if code in available.index]

            if current_premiums and new_premiums:
                avg_current = sum(current_premiums) / len(current_premiums)
                avg_new = sum(new_premiums) / len(new_premiums)
                if avg_current - avg_new > threshold:
                    needs_rebalance = True

        if needs_rebalance and set(new_selected) != set(prev_selected):
            # 换仓：卖出当前持仓，买入新选择的
            cash = sum(holdings.get(code, 0) * price_df.loc[date, code]
                       for code in prev_selected if code in price_df.columns)

            per_etf_cash = cash / 2
            holdings = {}
            for code in new_selected:
                shares = per_etf_cash / price_df.loc[date, code]
                holdings[code] = shares

            trades += 1
            prev_selected = new_selected

    # 最终市值
    final_date = dates[-1]
    final_mv = sum(holdings.get(code, 0) * price_df.loc[final_date, code]
                   for code in holdings if code in price_df.columns)

    # 收益率
    total_return = (final_mv / initial_capital - 1) * 100

    print(f"  最终市值: ¥{final_mv:,.2f}")
    print(f"  总收益率: {total_return:+.2f}%")
    print(f"  换仓次数: {trades}")

    return {
        'strategy': strategy_name,
        'final_value': final_mv,
        'return_pct': total_return,
        'trades': trades,
        'values': values
    }

def simulate_buy_hold(df):
    """模拟买入持有策略"""
    price_df = df.pivot(index='date', columns='code', values='price')

    dates = sorted(price_df.index.tolist())
    first_date = dates[0]
    last_date = dates[-1]

    initial_capital = 100000

    results = []

    print(f"\n{'='*60}")
    print(f"  买入持有策略")
    print(f"{'='*60}")

    for code in NASDAQ_ETFS:
        if code not in price_df.columns or pd.isna(price_df.loc[first_date, code]):
            continue

        first_price = price_df.loc[first_date, code]
        last_price = price_df.loc[last_date, code]

        shares = initial_capital / first_price
        final_value = shares * last_price
        total_return = (final_value / initial_capital - 1) * 100

        results.append({
            'code': code,
            'first_price': first_price,
            'last_price': last_price,
            'return_pct': total_return
        })

        print(f"  {code}: {first_price:.3f} → {last_price:.3f} = {total_return:+.2f}%")

    avg_return = sum(r['return_pct'] for r in results) / len(results)
    print(f"\n  平均收益: {avg_return:+.2f}%")

    return results, avg_return

def main():
    print(f"\n溢价轮动策略回测分析")
    print(f"数据范围: {START_DATE} ~ {END_DATE}")

    # 获取数据
    df = get_daily_data()
    print(f"数据条数: {len(df)}")

    if df.empty:
        print("  无数据!")
        return

    # 买入持有
    buy_hold_results, avg_return = simulate_buy_hold(df)

    # 溢价轮动 - 每日换仓
    strategy_daily = simulate_premium_rotation(df, threshold=None)

    # 溢价轮动 - 条件换仓 (0.5%阈值)
    strategy_threshold = simulate_premium_rotation(df, threshold=0.5)

    # 汇总对比
    print(f"\n{'='*60}")
    print(f"  策略对比汇总")
    print(f"{'='*60}")
    print(f"  {'策略':<20s} | {'收益率':>12s} | {'换仓次数':>10s}")
    print(f"  {'-'*20}-+-{'-'*12}-+-{'-'*10}")

    print(f"  {'买入持有(平均)':<20s} | {avg_return:>+10.2f}% | {0:>9d}")
    if strategy_daily:
        print(f"  {strategy_daily['strategy']:<20s} | {strategy_daily['return_pct']:>+10.2f}% | {strategy_daily['trades']:>9d}")
    if strategy_threshold:
        print(f"  {strategy_threshold['strategy']:<20s} | {strategy_threshold['return_pct']:>+10.2f}% | {strategy_threshold['trades']:>9d}")

    print()

if __name__ == '__main__':
    main()
