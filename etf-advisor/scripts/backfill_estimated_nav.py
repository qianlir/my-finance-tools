#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backfill_estimated_nav.py — 历史回填估算净值 (共同交易日公式)

公式:
  est(T) = nav(T_prev) × close(T) / close(T_prev)

  T_prev = T 之前最近的"共同交易日" (A股有NAV 且 期货/指数有收盘价)
  close  = futures_data 中对应的期货/指数收盘价

此公式回测 MAE:
  NQ纳指 0.277%, ES标普 0.213%, YM道指 0.183%
  GDAXI德国 0.300%, N225日经 0.457%, CAC法国 0.287%

Usage:
    python3 scripts/backfill_estimated_nav.py                  # 全部
    python3 scripts/backfill_estimated_nav.py --method futures  # 仅期货型
    python3 scripts/backfill_estimated_nav.py --code 513100     # 单只
    python3 scripts/backfill_estimated_nav.py --dry-run         # 预览
    python3 scripts/backfill_estimated_nav.py --force           # 覆盖已有值
"""

import argparse
import sqlite3
from pathlib import Path

DB_PATH = str(Path(__file__).parent.parent / "data" / "etf_premium.db")

SYMBOL_TO_COL = {
    'NQ': 'nq_close', 'ES': 'es_close', 'YM': 'ym_close',
    'GC': 'gc_close', 'CL': 'cl_close',
    'N225': 'nk_idx_close', 'GDAXI': 'dax_idx_close',
    'CAC': 'cac_idx_close', 'SENSEX': 'sensex_idx_close', 'SOX': 'sox_idx_close',
}


def backfill(method_filter=None, code_filter=None, dry_run=False, force=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    fc_rows = conn.execute("""
        SELECT code, estimate_method, estimate_symbol
        FROM fund_config
        WHERE enabled = 1 AND estimate_method IN ('futures', 'index')
    """).fetchall()

    if method_filter:
        fc_rows = [r for r in fc_rows if r['estimate_method'] == method_filter]
    if code_filter:
        fc_rows = [r for r in fc_rows if r['code'] == code_filter]

    print(f"回填范围: {len(fc_rows)} 只 ETF (method={method_filter or 'all'}, code={code_filter or 'all'})")
    if dry_run:
        print("*** DRY RUN ***")

    total_updated = 0
    total_skipped = 0

    for fc in fc_rows:
        code = fc['code']
        symbol = fc['estimate_symbol']
        close_col = SYMBOL_TO_COL.get(symbol)
        if not close_col:
            continue

        # A股日期 → NAV
        etf_map = {}
        for r in conn.execute("""
            SELECT date, nav FROM etf_data
            WHERE code = ? AND nav IS NOT NULL AND nav > 0
            ORDER BY date
        """, (code,)).fetchall():
            etf_map[r['date']] = r['nav']

        # 期货/指数日期 → 收盘价
        idx_map = {}
        for r in conn.execute(f"""
            SELECT date, {close_col} as close_price FROM futures_data
            WHERE {close_col} IS NOT NULL AND {close_col} > 0
            ORDER BY date
        """).fetchall():
            idx_map[r['date']] = r['close_price']

        if not idx_map:
            continue

        # 共同交易日 (A股有NAV 且 期货有收盘价)
        common = sorted(d for d in etf_map if d in idx_map)
        if len(common) < 2:
            continue

        # 构建 nav_date 映射
        nd_map = {}
        for r in conn.execute("""
            SELECT date, nav_date FROM etf_data
            WHERE code = ? AND nav_date IS NOT NULL
        """, (code,)).fetchall():
            nd_map[r['date']] = r['nav_date']

        # 美股真实交易日索引 (用于找 nd 的前一个)
        idx_dates_list = sorted(idx_map.keys())
        idx_pos = {d: i for i, d in enumerate(idx_dates_list)}

        # 哪些天需要回填
        if force:
            need_fill = set(etf_map.keys())
        else:
            existing = set()
            for r in conn.execute("""
                SELECT date FROM etf_data
                WHERE code = ? AND estimated_nav IS NOT NULL AND estimated_nav > 0
            """, (code,)).fetchall():
                existing.add(r['date'])
            need_fill = set(etf_map.keys()) - existing

        updated = 0
        skipped = 0

        # 找前一个 NAV 变化的 A 股日期
        prev_nav = None
        prev_date = None

        for i in range(len(common)):
            T = common[i]

            if T not in need_fill:
                prev_nav = etf_map[T]
                prev_date = T
                continue

            # 跳过 NAV 没变的天
            if prev_nav and etf_map[T] == prev_nav:
                if not dry_run:
                    conn.execute("""
                        UPDATE etf_data SET estimated_nav = ?
                        WHERE date = ? AND code = ?
                    """, (round(etf_map[T], 4), T, code))
                updated += 1
                continue

            est = None

            # 方法1: 精确公式 (有 nav_date 时)
            nd_T = nd_map.get(T)
            nd_prev = nd_map.get(prev_date) if prev_date else None
            if nd_T and nd_prev and nd_T in idx_map and nd_prev in idx_map:
                est = prev_nav * idx_map[nd_T] / idx_map[nd_prev]

            # 方法2: fallback 共同交易日公式
            if est is None and prev_nav and T in idx_map and prev_date and prev_date in idx_map:
                est = prev_nav * idx_map[T] / idx_map[prev_date]

            if est and abs(est / etf_map[T] - 1) < 0.5:
                if not dry_run:
                    conn.execute("""
                        UPDATE etf_data SET estimated_nav = ?
                        WHERE date = ? AND code = ?
                    """, (round(est, 4), T, code))
                updated += 1
            else:
                skipped += 1

            prev_nav = etf_map[T]
            prev_date = T

        total_updated += updated
        total_skipped += skipped

        if updated > 0 or skipped > 0:
            print(f"  {code} ({symbol}): 回填 {updated}, 跳过 {skipped} "
                  f"(共同交易日 {len(common)})")

    if not dry_run:
        conn.commit()
    conn.close()

    print(f"\n总计: 回填 {total_updated}, 跳过 {total_skipped}")
    return total_updated


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='历史回填估算净值 (共同交易日公式)')
    parser.add_argument('--method', choices=['futures', 'index'], help='仅指定方法')
    parser.add_argument('--code', help='仅指定 ETF 代码')
    parser.add_argument('--dry-run', action='store_true', help='预览不写入')
    parser.add_argument('--force', action='store_true', help='覆盖已有值')
    args = parser.parse_args()

    backfill(method_filter=args.method, code_filter=args.code,
             dry_run=args.dry_run, force=args.force)
