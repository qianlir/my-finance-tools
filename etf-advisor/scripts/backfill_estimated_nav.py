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


def build_trading_days(conn):
    """判断美股真实交易日, 两个条件同时满足:
    1. 工作日 (周一~周五)
    2. NQ/ES/YM 任一 close 相比前一天变化了
    返回美股真实交易日的 set"""
    from datetime import datetime
    rows = conn.execute("""
        SELECT date, nq_close, es_close, ym_close FROM futures_data
        WHERE (nq_close IS NOT NULL OR es_close IS NOT NULL OR ym_close IS NOT NULL)
        ORDER BY date
    """).fetchall()
    us_trading_days = set()
    prev = {}
    for r in rows:
        # 条件1: 工作日
        dt = datetime.strptime(r['date'], '%Y-%m-%d')
        if dt.weekday() >= 5:
            continue
        # 条件2: 价格变化
        changed = False
        for col in ['nq_close', 'es_close', 'ym_close']:
            val = r[col]
            if val is not None and val != prev.get(col):
                changed = True
            if val is not None:
                prev[col] = val
        if changed:
            us_trading_days.add(r['date'])
    return us_trading_days


def backfill(method_filter=None, code_filter=None, dry_run=False, force=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 用价格变化判断美股真实交易日
    us_trading_days = build_trading_days(conn)

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

        # 期货/指数收盘价 (只取真实交易日)
        idx_map = {}
        for r in conn.execute(f"""
            SELECT date, {close_col} as close_price FROM futures_data
            WHERE {close_col} IS NOT NULL AND {close_col} > 0
            ORDER BY date
        """).fetchall():
            if r['date'] in us_trading_days:
                idx_map[r['date']] = r['close_price']

        if not idx_map:
            continue

        idx_dates_list = sorted(idx_map.keys())

        # A股有NAV的日期 (不要求美股同日有收盘, 调休日也包含)
        all_etf_dates = sorted(etf_map.keys())
        if len(all_etf_dates) < 2:
            continue

        # 构建 nav_date 映射
        nd_map = {}
        for r in conn.execute("""
            SELECT date, nav_date FROM etf_data
            WHERE code = ? AND nav_date IS NOT NULL
        """, (code,)).fetchall():
            nd_map[r['date']] = r['nav_date']

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

        for T in all_etf_dates:
            if T not in need_fill:
                prev_nav = etf_map[T]
                prev_date = T
                continue

            # NAV 没变 → 直接复制
            if prev_nav and etf_map[T] == prev_nav:
                if not dry_run:
                    conn.execute("""
                        UPDATE etf_data SET estimated_nav = ?
                        WHERE date = ? AND code = ?
                    """, (round(etf_map[T], 4), T, code))
                updated += 1
                continue

            est = None

            # 取 T 和 prev_date 对应的美股收盘价
            # 优先直接匹配, A股调休日 fallback 到前一个美股交易日
            import bisect
            def _get_close(d):
                if d in idx_map:
                    return idx_map[d]
                pos = bisect.bisect_right(idx_dates_list, d) - 1
                return idx_map[idx_dates_list[pos]] if pos >= 0 else None

            c_T = _get_close(T)
            c_prev = _get_close(prev_date) if prev_date else None

            if prev_nav and c_T and c_prev:
                est = prev_nav * c_T / c_prev

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
                  f"(A股交易日 {len(all_etf_dates)})")

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
