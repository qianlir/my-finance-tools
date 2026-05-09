#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calc_rotation_index.py — 纳指ETF轮动指数计算

从 etf_data 历史数据计算每日评分，模拟轮动策略，输出 rotation_index.json。

评分公式:
  Score = NAV涨幅×10% + (-综合超额溢价)×80% + (-当前溢价)×10% + 推荐加分(±0.5)
  池内ETF +0.5, 池外 -0.5 (池子从 rotation-pool.json 读取)
  切换阈值: 最优分值 - 持仓分值 >= T

Usage:
    python3 scripts/calc_rotation_index.py --threshold 1        # 增量更新
    python3 scripts/calc_rotation_index.py --threshold 1 --force # 全量重算
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
POOL_PATH = PROJECT_ROOT / "memory" / "knowledge" / "etf" / "rotation-pool.json"
OUTPUT_DIR = PROJECT_ROOT / "data"

ALL_NASDAQ = [
    {'code': '513100', 'name': '国泰纳指ETF'},
    {'code': '159941', 'name': '广发纳指ETF'},
    {'code': '159660', 'name': '汇添富纳指ETF'},
    {'code': '159501', 'name': '嘉实纳指ETF'},
    {'code': '159632', 'name': '华安纳指ETF'},
    {'code': '159659', 'name': '招商纳指ETF'},
    {'code': '513300', 'name': '华夏纳指ETF'},
    {'code': '513870', 'name': '富国纳指ETF'},
    {'code': '513390', 'name': '博时纳指ETF'},
    {'code': '513110', 'name': '南方纳指ETF'},
]
ALL_CODES = [e['code'] for e in ALL_NASDAQ]
CODE_TO_NAME = {e['code']: e['name'] for e in ALL_NASDAQ}

PERIODS = [('1M', 30), ('3M', 90), ('6M', 180), ('1Y', 365), ('ALL', None)]
WEIGHTS = {'1M': 0.35, '3M': 0.25, '6M': 0.20, '1Y': 0.10, 'ALL': 0.10}

DEFAULT_START = '2025-01-02'
INITIAL_VALUE = 10000.0


def load_pool_config():
    if POOL_PATH.exists():
        cfg = json.loads(POOL_PATH.read_text())
        return cfg.get('NASDAQ', {})
    return {}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rotation_scores (
            date TEXT NOT NULL,
            index_type TEXT NOT NULL DEFAULT 'NASDAQ',
            code TEXT NOT NULL,
            price REAL,
            nav REAL,
            premium_rate REAL,
            composite REAL,
            nav_return_1y REAL,
            score REAL,
            pool_score REAL,
            UNIQUE(date, index_type, code)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rotation_index (
            date TEXT NOT NULL,
            strategy TEXT NOT NULL DEFAULT 'NASDAQ_T1.0',
            holding_code TEXT NOT NULL,
            holding_score REAL,
            best_code TEXT,
            best_score REAL,
            switched INTEGER DEFAULT 0,
            switch_from TEXT,
            rotation_value REAL NOT NULL,
            equal_weight_value REAL NOT NULL,
            UNIQUE(date, strategy)
        )
    """)
    conn.commit()


def get_trading_dates(conn, start_date):
    rows = conn.execute(
        "SELECT DISTINCT date FROM etf_data WHERE date >= ? ORDER BY date",
        (start_date,)
    ).fetchall()
    return [r['date'] for r in rows]


def load_all_data(conn, lookback_start):
    """预加载所有需要的数据到内存，避免逐日查询。"""
    rows = conn.execute("""
        SELECT date, code, price, nav, premium_rate
        FROM etf_data
        WHERE code IN ({}) AND date >= ? AND price IS NOT NULL AND price > 0
        ORDER BY date, code
    """.format(','.join('?' * len(ALL_CODES))),
        ALL_CODES + [lookback_start]
    ).fetchall()

    premium_by_code = defaultdict(list)
    daily_data = defaultdict(dict)

    for r in rows:
        code = r['code']
        date = r['date']
        premium_by_code[code].append((date, r['premium_rate']))
        daily_data[date][code] = {
            'price': r['price'],
            'nav': r['nav'],
            'premium_rate': r['premium_rate'],
        }

    return premium_by_code, daily_data


def compute_rolling_avg(premium_list, current_idx, period_days):
    if current_idx < 0:
        return None
    current_date_str = premium_list[current_idx][0]
    current_date = datetime.strptime(current_date_str, '%Y-%m-%d')

    if period_days is None:
        vals = [premium_list[i][1] for i in range(current_idx)
                if premium_list[i][1] is not None]
    else:
        start_date = current_date - timedelta(days=period_days)
        start_str = start_date.strftime('%Y-%m-%d')
        vals = [premium_list[i][1] for i in range(current_idx)
                if premium_list[i][0] >= start_str and premium_list[i][1] is not None]

    return sum(vals) / len(vals) if vals else None


def compute_nav_return_1y(premium_by_code, code, current_date_str, daily_data):
    current = daily_data.get(current_date_str, {}).get(code)
    if not current or not current['nav'] or current['nav'] <= 0:
        return 0.0

    target_date = datetime.strptime(current_date_str, '%Y-%m-%d') - timedelta(days=365)
    target_str = target_date.strftime('%Y-%m-%d')

    nav_list = premium_by_code.get(code, [])
    best_nav = None
    for date_str, _ in nav_list:
        if date_str > target_str:
            break
        d = daily_data.get(date_str, {}).get(code)
        if d and d['nav'] and d['nav'] > 0:
            best_nav = d['nav']

    if best_nav and best_nav > 0:
        return (current['nav'] / best_nav - 1) * 100
    return 0.0


def compute_all_scores(conn, trading_dates, premium_by_code, daily_data, pool_cfg):
    """计算所有交易日所有纳指ETF的评分，写入 rotation_scores。"""
    pool = pool_cfg.get('pool', {})
    default_bonus = pool_cfg.get('default_bonus', 0)

    code_date_idx = {}
    for code in ALL_CODES:
        plist = premium_by_code.get(code, [])
        idx_map = {d: i for i, (d, _) in enumerate(plist)}
        code_date_idx[code] = (plist, idx_map)

    rows_to_insert = []

    for date in trading_dates:
        day_data = daily_data.get(date, {})

        for code in ALL_CODES:
            if code not in day_data:
                continue

            info = day_data[code]
            price = info['price']
            nav = info['nav']
            premium_rate = info['premium_rate']

            if premium_rate is None:
                continue

            plist, idx_map = code_date_idx[code]
            current_idx = idx_map.get(date)
            if current_idx is None:
                continue

            excess_by_period = {}
            for period_name, period_days in PERIODS:
                hist_avg = compute_rolling_avg(plist, current_idx, period_days)
                if hist_avg is not None:
                    excess_by_period[period_name] = premium_rate - hist_avg
                else:
                    excess_by_period[period_name] = 0.0

            composite = sum(
                excess_by_period.get(p, 0) * w for p, w in WEIGHTS.items()
            )

            nav_return_1y = compute_nav_return_1y(premium_by_code, code, date, daily_data)

            score = (
                nav_return_1y * 0.10
                + (-composite) * 0.80
                + (-premium_rate) * 0.10
            )

            bonus = pool[code]['bonus'] if code in pool else default_bonus
            pool_score = score + bonus

            rows_to_insert.append((
                date, 'NASDAQ', code, price, nav, premium_rate,
                composite, nav_return_1y, score, pool_score
            ))

    conn.executemany("""
        INSERT OR REPLACE INTO rotation_scores
        (date, index_type, code, price, nav, premium_rate, composite, nav_return_1y, score, pool_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows_to_insert)
    conn.commit()
    print(f"  rotation_scores: {len(rows_to_insert)} rows written")


def simulate_rotation(conn, strategy_name, threshold, pool_codes, initial=INITIAL_VALUE):
    """从 rotation_scores 读取评分，模拟轮动策略。"""
    rows = conn.execute("""
        SELECT date, code, price, premium_rate, pool_score
        FROM rotation_scores
        WHERE index_type = 'NASDAQ' AND code IN ({})
        ORDER BY date, pool_score DESC
    """.format(','.join('?' * len(pool_codes))),
        pool_codes
    ).fetchall()

    by_date = defaultdict(list)
    for r in rows:
        by_date[r['date']].append({
            'code': r['code'],
            'price': r['price'],
            'premium_rate': r['premium_rate'],
            'pool_score': r['pool_score'],
        })

    dates = sorted(by_date.keys())
    if not dates:
        return [], []

    eq_shares, eq_dates = compute_equal_weight(conn, dates)

    holding_code = None
    shares = 0.0
    result_rows = []
    trades = []
    trade_seq = 0

    for i, date in enumerate(dates):
        day_etfs = by_date[date]
        if not day_etfs:
            continue

        best = day_etfs[0]
        best_code = best['code']
        best_score = best['pool_score']

        eq_value = eq_dates.get(date, initial)

        if holding_code is None:
            holding_code = best_code
            shares = initial / best['price']
            rotation_value = initial

            trade_seq += 1
            trades.append({
                'seq': trade_seq, 'date': date, 'action': '建仓',
                'sell_code': None, 'sell_name': None, 'sell_premium': None, 'sell_score': None,
                'buy_code': best_code, 'buy_name': CODE_TO_NAME.get(best_code, best_code),
                'buy_price': best['price'], 'buy_premium': best['premium_rate'],
                'buy_score': round(best_score, 2),
                'premium_diff': None, 'score_diff': None,
                'rotation_value': round(rotation_value, 2),
                'equal_weight_value': round(eq_value, 2),
                'lead': 0,
            })

            result_rows.append((
                date, strategy_name, holding_code, best_score,
                best_code, best_score, 1, None,
                round(rotation_value, 2), round(eq_value, 2)
            ))
            continue

        holding_info = None
        for e in day_etfs:
            if e['code'] == holding_code:
                holding_info = e
                break

        if holding_info is None:
            continue

        holding_score = holding_info['pool_score']
        rotation_value = shares * holding_info['price']

        switched = 0
        switch_from = None

        if best_code != holding_code and (best_score - holding_score) >= threshold:
            switch_from = holding_code
            old_premium = holding_info['premium_rate']
            cash = shares * holding_info['price']
            holding_code = best_code
            shares = cash / best['price']
            rotation_value = cash
            switched = 1

            trade_seq += 1
            trades.append({
                'seq': trade_seq, 'date': date, 'action': '换仓',
                'sell_code': switch_from, 'sell_name': CODE_TO_NAME.get(switch_from, switch_from),
                'sell_premium': round(old_premium, 2) if old_premium else None,
                'sell_score': round(holding_score, 2),
                'buy_code': best_code, 'buy_name': CODE_TO_NAME.get(best_code, best_code),
                'buy_price': best['price'], 'buy_premium': round(best['premium_rate'], 2) if best['premium_rate'] else None,
                'buy_score': round(best_score, 2),
                'premium_diff': round((old_premium or 0) - (best['premium_rate'] or 0), 2),
                'score_diff': round(best_score - holding_score, 2),
                'rotation_value': round(rotation_value, 2),
                'equal_weight_value': round(eq_value, 2),
                'lead': round(rotation_value - eq_value, 2),
            })

        result_rows.append((
            date, strategy_name, holding_code, holding_score,
            best_code, best_score, switched, switch_from,
            round(rotation_value, 2), round(eq_value, 2)
        ))

    conn.execute("DELETE FROM rotation_index WHERE strategy = ?", (strategy_name,))
    conn.executemany("""
        INSERT INTO rotation_index
        (date, strategy, holding_code, holding_score, best_code, best_score,
         switched, switch_from, rotation_value, equal_weight_value)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, result_rows)
    conn.commit()
    print(f"  rotation_index: {len(result_rows)} rows written for {strategy_name}")

    return result_rows, trades


def compute_equal_weight(conn, dates):
    """计算等权基准: 所有纳指ETF，buy-and-hold 不再平衡。"""
    if not dates:
        return {}, {}

    first_date = dates[0]
    per_etf = INITIAL_VALUE / len(ALL_CODES)

    all_dates_data = conn.execute("""
        SELECT date, code, price FROM etf_data
        WHERE code IN ({}) AND date IN ({}) AND price IS NOT NULL AND price > 0
        ORDER BY date
    """.format(
        ','.join('?' * len(ALL_CODES)),
        ','.join('?' * len(dates))
    ), ALL_CODES + dates).fetchall()

    price_map = defaultdict(dict)
    for r in all_dates_data:
        price_map[r['date']][r['code']] = r['price']

    first_prices = price_map.get(first_date, {})
    eq_shares = {}
    for code in ALL_CODES:
        if code in first_prices and first_prices[code] > 0:
            eq_shares[code] = per_etf / first_prices[code]

    eq_dates = {}
    for date in dates:
        day_prices = price_map.get(date, {})
        total = sum(
            eq_shares.get(code, 0) * day_prices.get(code, 0)
            for code in ALL_CODES
            if code in eq_shares and code in day_prices
        )
        eq_dates[date] = total

    return eq_shares, eq_dates


def generate_json(conn, strategy_name, threshold, pool_codes, pool_cfg, trades, output_path):
    """生成 rotation_index.json。"""
    rows = conn.execute("""
        SELECT date, holding_code, rotation_value, equal_weight_value
        FROM rotation_index WHERE strategy = ? ORDER BY date
    """, (strategy_name,)).fetchall()

    if not rows:
        print("  No data to generate JSON")
        return

    dates = [r['date'] for r in rows]
    rotation_values = [r['rotation_value'] for r in rows]
    equal_weight_values = [r['equal_weight_value'] for r in rows]
    holdings = [r['holding_code'] for r in rows]

    final_rv = rotation_values[-1]
    final_ev = equal_weight_values[-1]
    rotation_return = (final_rv / INITIAL_VALUE - 1) * 100
    equal_weight_return = (final_ev / INITIAL_VALUE - 1) * 100

    pool_names = {code: CODE_TO_NAME.get(code, code) for code in pool_codes}

    data = {
        'strategy': strategy_name,
        'pool': pool_codes,
        'pool_names': pool_names,
        'threshold': threshold,
        'initial_value': INITIAL_VALUE,
        'start_date': dates[0],
        'end_date': dates[-1],
        'trading_days': len(dates),
        'formula': 'score = NAV涨幅×10% + (-综合超额)×80% + (-当前溢价)×10% + 推荐加分(±0.5)',
        'equal_weight_etfs': len(ALL_CODES),
        'summary': {
            'rotation_value': round(final_rv, 2),
            'rotation_return': round(rotation_return, 2),
            'equal_weight_value': round(final_ev, 2),
            'equal_weight_return': round(equal_weight_return, 2),
            'alpha': round(rotation_return - equal_weight_return, 2),
            'trade_count': len(trades),
            'current_holding': holdings[-1],
            'current_holding_name': CODE_TO_NAME.get(holdings[-1], holdings[-1]),
        },
        'daily': {
            'dates': dates,
            'rotation_values': rotation_values,
            'equal_weight_values': equal_weight_values,
            'holdings': holdings,
        },
        'trades': trades,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"  JSON: {output_path} ({len(dates)} days, {len(trades)} trades)")


def main():
    parser = argparse.ArgumentParser(description='计算纳指ETF轮动指数')
    parser.add_argument('--threshold', type=float, required=True, help='切换阈值 T')
    parser.add_argument('--force', action='store_true', help='全量重算')
    parser.add_argument('--start', default=DEFAULT_START, help='起始日期')
    args = parser.parse_args()

    threshold = args.threshold
    strategy_name = f'NASDAQ_T{threshold}'

    pool_cfg = load_pool_config()
    pool_codes = list(pool_cfg.get('pool', {}).keys())
    if not pool_codes:
        print("ERROR: No pool config found in rotation-pool.json")
        return

    conn = get_db()
    init_tables(conn)

    if args.force:
        conn.execute("DELETE FROM rotation_scores WHERE index_type = 'NASDAQ'")
        conn.execute("DELETE FROM rotation_index WHERE strategy = ?", (strategy_name,))
        conn.commit()
        print("Force mode: cleared existing data")

    last_score_date = conn.execute(
        "SELECT MAX(date) FROM rotation_scores WHERE index_type = 'NASDAQ'"
    ).fetchone()[0]

    score_start = args.start
    if last_score_date and not args.force:
        score_start = last_score_date
        print(f"Incremental: scores from {score_start}")

    lookback = (datetime.strptime(score_start, '%Y-%m-%d') - timedelta(days=400)).strftime('%Y-%m-%d')
    trading_dates = get_trading_dates(conn, score_start)

    if not trading_dates:
        print("No trading dates found")
        conn.close()
        return

    print(f"Loading data from {lookback}...")
    premium_by_code, daily_data = load_all_data(conn, lookback)

    print(f"Computing scores for {len(trading_dates)} dates...")
    compute_all_scores(conn, trading_dates, premium_by_code, daily_data, pool_cfg)

    print(f"Simulating {strategy_name} (threshold={threshold})...")
    result_rows, trades = simulate_rotation(conn, strategy_name, threshold, pool_codes)

    output_file = OUTPUT_DIR / 'rotation_index.json'
    print("Generating JSON...")
    generate_json(conn, strategy_name, threshold, pool_codes, pool_cfg, trades, output_file)

    conn.close()
    print("Done!")


if __name__ == '__main__':
    main()
