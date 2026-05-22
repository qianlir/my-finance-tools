#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
infer_nav_dates.py — 反推历史 nav_date (累积匹配法)

问题: 历史 etf_data 99% 没有 nav_date, 无法精确对齐美股交易日
方法: 用 NAV 变化 vs NQ 累积涨跌匹配, 反推每条记录的 nav_date

算法:
  1. 从已知锚点出发 (有 nav_date 的记录)
  2. 向前逐个 NAV 变化事件, 用累积 NQ 变化匹配最佳美股交易日
  3. 匹配: expected_nav = anchor_nav × nq(candidate) / nq(anchor_navdate)
  4. candidate 和 actual_nav 最接近的就是 nav_date

处理假日:
  - 五一/国庆: A股休 5~7 天, 美股正常, NAV 冻结后跳变
    → 累积匹配自动处理 (NAV 跳变匹配多天累积的 NQ 变化)
  - 美股假日: A股正常但 NAV 不变
    → NAV 不变的天跳过, 不消耗美股交易日

Usage:
    python3 scripts/infer_nav_dates.py                    # 全部
    python3 scripts/infer_nav_dates.py --code 513100      # 单只
    python3 scripts/infer_nav_dates.py --dry-run           # 预览
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


def infer_for_etf(conn, code, close_col, dry_run=False):
    """对单只 ETF 反推所有 nav_date"""

    # 1. ETF 的 NAV 序列 (A股日期, 按日期排序)
    etf_rows = conn.execute("""
        SELECT date, nav, nav_date FROM etf_data
        WHERE code = ? AND nav IS NOT NULL AND nav > 0
        ORDER BY date
    """, (code,)).fetchall()

    if len(etf_rows) < 2:
        return 0

    # 2. 美股/指数交易日序列 (收盘价)
    idx_rows = conn.execute(f"""
        SELECT date, {close_col} as close_price FROM futures_data
        WHERE {close_col} IS NOT NULL AND {close_col} > 0
        ORDER BY date
    """).fetchall()

    if not idx_rows:
        return 0

    idx_dates = [r['date'] for r in idx_rows]
    idx_map = {r['date']: r['close_price'] for r in idx_rows}

    # 3. 找锚点 (有 nav_date 且 NAV 变化了的记录)
    anchors = []
    for i, r in enumerate(etf_rows):
        if r['nav_date'] and i > 0 and r['nav'] != etf_rows[i - 1]['nav']:
            anchors.append((i, r['date'], r['nav'], r['nav_date']))
            break  # 只需第一个

    # 如果没有锚点, 用第一个 NAV 变化事件 + 最近的美股交易日作为初始锚点
    if not anchors:
        for i in range(1, len(etf_rows)):
            if etf_rows[i]['nav'] != etf_rows[i - 1]['nav']:
                a_date = etf_rows[i]['date']
                candidates = [d for d in idx_dates if d < a_date]
                if candidates:
                    anchors = [(i, a_date, etf_rows[i]['nav'], candidates[-1])]
                break

    if not anchors:
        return 0

    # 4. 提取 NAV 变化事件 (date, nav, index_in_etf_rows)
    nav_changes = []  # (etf_index, a_date, nav)
    for i in range(len(etf_rows)):
        if i == 0 or etf_rows[i]['nav'] != etf_rows[i - 1]['nav']:
            nav_changes.append((i, etf_rows[i]['date'], etf_rows[i]['nav']))

    # 5. 从锚点向前（向过去）推断
    anchor_idx, anchor_adate, anchor_nav, anchor_navdate = anchors[0]

    # 找 anchor 在 nav_changes 中的位置
    anchor_nc_pos = None
    for j, (ei, ad, nv) in enumerate(nav_changes):
        if ei == anchor_idx:
            anchor_nc_pos = j
            break

    if anchor_nc_pos is None:
        return 0

    # 向前推断 (从锚点往过去)
    results = {}  # etf_index → nav_date
    results[anchor_idx] = anchor_navdate

    # 当前锚点的 nav_date 在 idx_dates 中的位置
    if anchor_navdate not in idx_map:
        return 0

    cur_navdate = anchor_navdate

    for j in range(anchor_nc_pos - 1, -1, -1):
        ei, a_date, nav_val = nav_changes[j]

        # 从 cur_navdate 往前找最佳匹配的美股交易日
        cur_idx_pos = idx_dates.index(cur_navdate) if cur_navdate in idx_dates else -1
        if cur_idx_pos < 1:
            break

        # 下一个 NAV 变化的 nav (当前锚点的 nav)
        next_nav = nav_changes[j + 1][2]
        nq_cur = idx_map[cur_navdate]

        # 尝试 cur_navdate 往前 1~10 个美股交易日
        best_nd = None
        best_err = float('inf')

        for offset in range(1, min(11, cur_idx_pos + 1)):
            candidate_date = idx_dates[cur_idx_pos - offset]
            nq_candidate = idx_map[candidate_date]

            # expected: next_nav = nav_val × nq_cur / nq_candidate
            # → nav_val = next_nav × nq_candidate / nq_cur
            expected_nav = next_nav * nq_candidate / nq_cur
            err = abs(expected_nav / nav_val - 1)

            if err < best_err:
                best_err = err
                best_nd = candidate_date

        if best_nd and best_err < 0.05:  # 误差 < 5% 才接受
            results[ei] = best_nd
            cur_navdate = best_nd
        else:
            break  # 匹配不上, 停止

    # 向后推断 (从锚点往未来, 处理锚点之后没有 nav_date 的)
    cur_navdate = anchor_navdate
    for j in range(anchor_nc_pos + 1, len(nav_changes)):
        ei, a_date, nav_val = nav_changes[j]

        if etf_rows[ei]['nav_date']:
            # 已有 nav_date, 用它
            cur_navdate = etf_rows[ei]['nav_date']
            results[ei] = cur_navdate
            continue

        prev_nav = nav_changes[j - 1][2]
        nq_cur = idx_map.get(cur_navdate)
        if not nq_cur:
            break

        cur_idx_pos = idx_dates.index(cur_navdate) if cur_navdate in idx_dates else -1
        if cur_idx_pos < 0:
            break

        best_nd = None
        best_err = float('inf')

        for offset in range(1, min(11, len(idx_dates) - cur_idx_pos)):
            candidate_date = idx_dates[cur_idx_pos + offset]
            nq_candidate = idx_map[candidate_date]

            expected_nav = prev_nav * nq_candidate / nq_cur
            err = abs(expected_nav / nav_val - 1)

            if err < best_err:
                best_err = err
                best_nd = candidate_date

        if best_nd and best_err < 0.05:
            results[ei] = best_nd
            cur_navdate = best_nd
        else:
            break

    # 6. NAV 没变的天, nav_date 和前一个相同
    full_results = {}
    last_nd = None
    for i in range(len(etf_rows)):
        if i in results:
            last_nd = results[i]
        full_results[i] = last_nd

    # 7. 写入数据库
    updated = 0
    for i, nd in full_results.items():
        if nd is None:
            continue
        if etf_rows[i]['nav_date'] == nd:
            continue  # 已有且一致
        if etf_rows[i]['nav_date'] and not dry_run:
            continue  # 已有 nav_date 不覆盖

        if not dry_run:
            conn.execute("""
                UPDATE etf_data SET nav_date = ?
                WHERE date = ? AND code = ?
            """, (nd, etf_rows[i]['date'], code))
        updated += 1

    return updated


def main():
    parser = argparse.ArgumentParser(description='反推历史 nav_date')
    parser.add_argument('--code', help='单只 ETF')
    parser.add_argument('--dry-run', action='store_true', help='预览不写入')
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    fc_rows = conn.execute("""
        SELECT code, estimate_method, estimate_symbol
        FROM fund_config WHERE enabled = 1 AND estimate_method IN ('futures', 'index')
    """).fetchall()

    if args.code:
        fc_rows = [r for r in fc_rows if r['code'] == args.code]

    name_map = {r['code']: r['name'] for r in
                conn.execute("SELECT DISTINCT code, name FROM etf_data").fetchall()}

    print(f"反推 nav_date (累积匹配法), {'DRY RUN' if args.dry_run else '写入DB'}")
    print("=" * 70)

    total = 0
    for fc in fc_rows:
        code = fc['code']
        col = SYMBOL_TO_COL.get(fc['estimate_symbol'])
        if not col:
            continue

        updated = infer_for_etf(conn, code, col, args.dry_run)
        if updated > 0:
            name = name_map.get(code, code)[:14]
            print(f"  {code} {name}: 推断 {updated} 天 nav_date")
        total += updated

    if not args.dry_run:
        conn.commit()
    conn.close()

    print(f"\n总计: {total} 条 nav_date 被推断")


if __name__ == '__main__':
    main()
