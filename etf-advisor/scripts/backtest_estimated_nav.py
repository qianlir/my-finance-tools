#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest_estimated_nav.py — 估算净值误差回测

对比 estimated_nav(T日) vs nav(T+1日确认值), 统计估算准确度.

误差定义:
  error_pct(T) = (estimated_nav(T) / nav_confirmed(T+1) - 1) × 100

只统计 NAV 实际变化的日子 (排除周末/假日重复值).

Usage:
    python3 scripts/backtest_estimated_nav.py                    # 全部
    python3 scripts/backtest_estimated_nav.py --code 513100      # 单只
    python3 scripts/backtest_estimated_nav.py --method futures   # 按方法
"""

import argparse
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path

DB_PATH = str(Path(__file__).parent.parent / "data" / "etf_premium.db")


def backtest(code_filter=None, method_filter=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 获取 fund_config
    fc_rows = conn.execute("""
        SELECT code, estimate_method, estimate_symbol FROM fund_config WHERE enabled = 1
    """).fetchall()
    fc_map = {r['code']: r for r in fc_rows}

    if method_filter:
        fc_map = {c: r for c, r in fc_map.items() if r['estimate_method'] == method_filter}
    if code_filter:
        fc_map = {c: r for c, r in fc_map.items() if c == code_filter}

    # 获取所有 ETF 的名称
    name_map = {}
    for r in conn.execute("SELECT DISTINCT code, name FROM etf_data").fetchall():
        name_map[r['code']] = r['name']

    # 按 ETF 逐个回测
    results_by_code = {}
    results_by_method = defaultdict(list)

    for code, fc in fc_map.items():
        method_key = f"{fc['estimate_method']}/{fc['estimate_symbol'] or '?'}"

        # 取该 ETF 所有有 estimated_nav 的行, 按日期排序
        rows = conn.execute("""
            SELECT date, nav, estimated_nav FROM etf_data
            WHERE code = ? AND estimated_nav IS NOT NULL AND nav IS NOT NULL AND nav > 0
            ORDER BY date
        """, (code,)).fetchall()

        if len(rows) < 2:
            continue

        errors = []
        for i in range(len(rows)):
            est_nav_T = rows[i]['estimated_nav']
            nav_T = rows[i]['nav']

            # 跳过 NAV 没变的日子 (周末/假日, est=nav)
            if i > 0 and abs(nav_T - rows[i - 1]['nav']) < 0.0001:
                continue

            if nav_T <= 0 or est_nav_T <= 0:
                continue

            error_pct = (est_nav_T / nav_T - 1) * 100
            errors.append({
                'date': rows[i]['date'],
                'estimated_nav': est_nav_T,
                'next_nav': nav_T,
                'error_pct': error_pct,
            })

        if not errors:
            continue

        abs_errors = [abs(e['error_pct']) for e in errors]
        signed_errors = [e['error_pct'] for e in errors]

        stats = {
            'code': code,
            'name': name_map.get(code, code),
            'method': method_key,
            'n': len(errors),
            'mae': statistics.mean(abs_errors),
            'me': statistics.mean(signed_errors),
            'median_ae': statistics.median(abs_errors),
            'max_ae': max(abs_errors),
            'std': statistics.stdev(signed_errors) if len(signed_errors) > 1 else 0,
            'hit_05': sum(1 for e in abs_errors if e < 0.5) / len(abs_errors) * 100,
            'hit_10': sum(1 for e in abs_errors if e < 1.0) / len(abs_errors) * 100,
        }

        results_by_code[code] = stats
        results_by_method[method_key].append(stats)

    conn.close()

    # === 输出报告 ===
    print("=" * 110)
    print("  估算净值误差回测报告")
    print("=" * 110)

    # 按方法汇总
    print(f"\n{'方法':<16}{'ETF数':>6}{'天数':>6}{'MAE(%)':>9}{'ME(%)':>9}{'中位误差':>9}{'最大误差':>9}{'命中<0.5%':>10}{'命中<1%':>8}")
    print('-' * 110)

    method_summary = []
    for method, stats_list in sorted(results_by_method.items()):
        total_n = sum(s['n'] for s in stats_list)
        # 加权平均 (按天数加权)
        w_mae = sum(s['mae'] * s['n'] for s in stats_list) / total_n
        w_me = sum(s['me'] * s['n'] for s in stats_list) / total_n
        w_median = sum(s['median_ae'] * s['n'] for s in stats_list) / total_n
        max_ae = max(s['max_ae'] for s in stats_list)
        w_hit05 = sum(s['hit_05'] * s['n'] for s in stats_list) / total_n
        w_hit10 = sum(s['hit_10'] * s['n'] for s in stats_list) / total_n

        print(f"{method:<16}{len(stats_list):>6}{total_n:>6}"
              f"{w_mae:>8.2f}%{w_me:>+8.2f}%{w_median:>8.2f}%{max_ae:>8.2f}%"
              f"{w_hit05:>9.1f}%{w_hit10:>7.1f}%")
        method_summary.append((method, len(stats_list), total_n, w_mae, w_me, w_hit05))

    # 按个股
    print(f"\n{'代码':<8}{'名称':<16}{'方法':<16}{'天数':>5}{'MAE(%)':>9}{'ME(%)':>9}{'最大误差':>9}{'命中<0.5%':>10}")
    print('-' * 110)

    for code in sorted(results_by_code.keys()):
        s = results_by_code[code]
        print(f"{s['code']:<8}{s['name']:<16}{s['method']:<16}{s['n']:>5}"
              f"{s['mae']:>8.2f}%{s['me']:>+8.2f}%{s['max_ae']:>8.2f}%{s['hit_05']:>9.1f}%")

    print(f"\n总计: {len(results_by_code)} 只 ETF, {sum(s['n'] for s in results_by_code.values())} 条误差数据")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='估算净值误差回测')
    parser.add_argument('--code', help='单只 ETF')
    parser.add_argument('--method', choices=['futures', 'index', 'holdings', 'fundgz'], help='按方法')
    args = parser.parse_args()

    backtest(code_filter=args.code, method_filter=args.method)
