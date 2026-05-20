#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_pool_volatility.py — 基于波动性分析轮动池子的合理组成

核心思路:
  对每只 ETF, 计算其每日涨跌幅与同指数其他 ETF 平均涨跌幅的差值,
  再求这些差值的平方均值 (即 tracking error variance vs peers).

  波动越小 → 跟踪越稳定 → 越应该纳入池子.

数据起点: 2025-01-01

Usage:
    python3 scripts/analyze_pool_volatility.py
    python3 scripts/analyze_pool_volatility.py --index NASDAQ
"""

import argparse
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR / ".."
DB_PATH = str(PROJECT_ROOT / "data" / "etf_premium.db")

START_DATE = '2025-01-01'

INDEX_ETFS = {
    'NASDAQ': [
        ('513100', '国泰纳指'),
        ('159941', '广发纳指'),
        ('159660', '汇添富纳指'),
        ('159501', '嘉实纳指'),
        ('159632', '华安纳指'),
        ('159659', '招商纳指'),
        ('513300', '华夏纳指'),
        ('513870', '富国纳指'),
        ('513390', '博时纳指'),
        ('513110', '南方纳指'),
    ],
    'SP500': [
        ('513500', '博时标普'),
        ('159655', '华夏标普'),
        ('513650', '南方标普'),
        ('159612', '国泰标普'),
    ],
    'NIKKEI': [
        ('159866', '工银日经'),
        ('513000', '易方达日经'),
        ('513520', '华夏日经'),
        ('513880', '华安日经'),
    ],
    'DAX': [
        ('513030', '华安德国'),
        ('159561', '嘉实德国'),
    ],
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_daily_returns(conn, codes, start_date):
    """加载每只ETF的每日涨跌幅 (基于 price)."""
    rows = conn.execute(f"""
        SELECT date, code, price
        FROM etf_data
        WHERE code IN ({','.join('?' * len(codes))}) AND date >= ?
              AND price IS NOT NULL AND price > 0
        ORDER BY code, date
    """, list(codes) + [start_date]).fetchall()

    prices_by_code = defaultdict(list)
    for r in rows:
        prices_by_code[r['code']].append((r['date'], r['price']))

    # 计算每日涨跌幅 (相对前一交易日)
    returns_by_code = {}  # code -> {date: return_pct}
    for code, plist in prices_by_code.items():
        ret_map = {}
        for i in range(1, len(plist)):
            d, p = plist[i]
            _, p_prev = plist[i - 1]
            if p_prev and p_prev > 0:
                ret_map[d] = (p / p_prev - 1) * 100
        returns_by_code[code] = ret_map

    return returns_by_code


def compute_tracking_variance(returns_by_code, codes):
    """
    对每只 ETF, 计算其每日涨跌幅与"其他ETF平均涨跌幅"的差值的平方均值.

    返回: {code: {variance, mean_diff, n_days}}
    """
    # 找出所有 ETF 都有数据的日期
    all_dates = None
    for code in codes:
        d_set = set(returns_by_code.get(code, {}).keys())
        all_dates = d_set if all_dates is None else (all_dates & d_set)
    common_dates = sorted(all_dates) if all_dates else []

    results = {}
    for code in codes:
        diffs = []
        for d in common_dates:
            my_ret = returns_by_code[code].get(d)
            if my_ret is None:
                continue
            # 其他 ETF 的平均涨跌幅
            peer_rets = [returns_by_code[c].get(d) for c in codes if c != code]
            peer_rets = [r for r in peer_rets if r is not None]
            if not peer_rets:
                continue
            peer_avg = sum(peer_rets) / len(peer_rets)
            diffs.append(my_ret - peer_avg)

        if not diffs:
            results[code] = {'variance': None, 'mean_diff': None, 'n_days': 0, 'std': None}
            continue

        mean_diff = sum(diffs) / len(diffs)
        variance = sum((d - mean_diff) ** 2 for d in diffs) / len(diffs)
        std = variance ** 0.5
        results[code] = {
            'variance': variance,
            'mean_diff': mean_diff,
            'std': std,
            'n_days': len(diffs),
        }
    return results, common_dates


def analyze_index(conn, index_type):
    etfs = INDEX_ETFS.get(index_type, [])
    if not etfs:
        print(f"未找到 {index_type} 的 ETF 列表")
        return

    codes = [c for c, _ in etfs]
    name_map = dict(etfs)

    print(f"\n{'='*70}")
    print(f"指数: {index_type}  (起点: {START_DATE})")
    print(f"{'='*70}")

    returns_by_code = load_daily_returns(conn, codes, START_DATE)
    results, common_dates = compute_tracking_variance(returns_by_code, codes)

    print(f"共同交易日: {len(common_dates)} 天 "
          f"({common_dates[0] if common_dates else '-'} ~ "
          f"{common_dates[-1] if common_dates else '-'})\n")

    # 按 std (跟踪偏离) 排序, 越小越稳定
    rows = []
    for code in codes:
        r = results.get(code, {})
        rows.append((code, name_map[code], r.get('std'), r.get('mean_diff'), r.get('n_days')))

    rows_with_std = [r for r in rows if r[2] is not None]
    rows_with_std.sort(key=lambda x: x[2])

    print(f"{'排名':<4} {'代码':<8} {'名称':<14} {'跟踪偏离σ%':<12} {'平均差%':<10} {'天数':<6}")
    print(f"{'-'*4} {'-'*8} {'-'*14} {'-'*12} {'-'*10} {'-'*6}")
    for i, (code, name, std, mean_diff, n) in enumerate(rows_with_std, 1):
        marker = '⭐' if i <= max(1, len(rows_with_std) // 2) else '  '
        print(f"{marker}{i:<2} {code:<8} {name:<14} "
              f"{std:>10.4f}   {mean_diff:>+8.4f}   {n:>5}")

    # 给出池子建议
    print(f"\n💡 池子建议 ({index_type}):")
    n = len(rows_with_std)
    if n <= 2:
        print(f"   只有 {n} 只 ETF, 建议全部纳入池子 (bonus=0)")
    elif n <= 4:
        print(f"   {n} 只 ETF, 建议全部纳入池子, 但根据偏离σ设置差异化加分:")
        for i, (code, name, std, _, _) in enumerate(rows_with_std):
            # 偏离最小的+0.5, 最大的-0.5, 中间线性
            if n == 1:
                bonus = 0
            else:
                bonus = 0.5 - (i / (n - 1)) * 1.0  # 0.5 → -0.5
            print(f"     {code} {name}: bonus={bonus:+.2f}  (σ={std:.4f})")
    else:
        # 大池子: 偏离最小的前半纳入, 后半排除
        half = n // 2
        print(f"   {n} 只 ETF, 池内 {half} 只 / 池外 {n - half} 只:")
        for i, (code, name, std, _, _) in enumerate(rows_with_std):
            if i < half:
                tag = '✓ 池内 (+0.5)'
            else:
                tag = '× 池外 (-0.5)'
            print(f"     {code} {name}: {tag}  (σ={std:.4f})")


def main():
    parser = argparse.ArgumentParser(description='基于波动性分析轮动池子')
    parser.add_argument('--index', default='all',
                        choices=['all', 'NASDAQ', 'SP500', 'NIKKEI', 'DAX'],
                        help='指数类型')
    args = parser.parse_args()

    conn = get_db()

    if args.index == 'all':
        for idx in ['NASDAQ', 'SP500', 'NIKKEI', 'DAX']:
            analyze_index(conn, idx)
    else:
        analyze_index(conn, args.index)

    conn.close()
    print("\nDone!")


if __name__ == '__main__':
    main()
