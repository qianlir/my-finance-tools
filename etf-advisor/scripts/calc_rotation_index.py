#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calc_rotation_index.py — 多指数轮动指数计算

从 etf_data 历史数据计算每日评分，模拟轮动策略，输出 rotation_index 表。

评分公式:
  Score = NAV涨幅×10% + (-综合超额溢价)×80% + (-当前溢价)×10% + 推荐加分(±bonus)
  池内ETF: +bonus (从 rotation-pool.json 读取)
  池外ETF: default_bonus (通常 -0.5)
  切换阈值: 最优分值 - 持仓分值 >= T (从 rotation-pool.json 读取)

支持指数: NASDAQ, SP500, NIKKEI, DAX

Usage:
    python3 scripts/calc_rotation_index.py --threshold 1.0 --index NASDAQ
    python3 scripts/calc_rotation_index.py --threshold 1.0 --index all  # 所有指数
    python3 scripts/calc_rotation_index.py --threshold 1.0 --force     # 全量重算所有指数
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

# ETF配置：每个指数对应的常规ETF列表（排除LOF）
INDEX_ETFS_CONFIG = {
    'NASDAQ': [
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
    ],
    'SP500': [
        {'code': '513500', 'name': '博时标普ETF'},
        {'code': '159655', 'name': '华夏标普ETF'},
        {'code': '513650', 'name': '南方标普ETF'},
        {'code': '159612', 'name': '国泰标普ETF'},
    ],
    'NIKKEI': [
        {'code': '159866', 'name': '日经ETF工银'},
        {'code': '513000', 'name': '日经225ETF易方达'},
        {'code': '513520', 'name': '日经ETF华夏'},
        {'code': '513880', 'name': '日经225ETF华安'},
    ],
    'DAX': [
        {'code': '513030', 'name': '德国ETF华安'},
        {'code': '159561', 'name': '德国ETF嘉实'},
    ],
}

PERIODS = [('1M', 30), ('3M', 90), ('6M', 180), ('1Y', 365), ('ALL', None)]
WEIGHTS = {'1M': 0.35, '3M': 0.25, '6M': 0.20, '1Y': 0.10, 'ALL': 0.10}

# 所有指数统一从此日期开始计算历史数据
DATA_START_DATE = '2025-01-01'
DEFAULT_START = '2025-01-02'
INITIAL_VALUE = 10000.0


def load_pool_config(index_type):
    """加载指定指数的轮动池配置。"""
    if POOL_PATH.exists():
        cfg = json.loads(POOL_PATH.read_text())
        return cfg.get(index_type, {})
    return {}


def load_all_pool_configs():
    """加载所有指数的轮动池配置。"""
    if POOL_PATH.exists():
        return json.loads(POOL_PATH.read_text())
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


def load_all_data(conn, codes, lookback_start):
    """预加载指定ETF的所有需要的数据到内存，避免逐日查询。"""
    if not codes:
        return {}, {}

    rows = conn.execute("""
        SELECT date, code, price, nav, premium_rate
        FROM etf_data
        WHERE code IN ({}) AND date >= ? AND price IS NOT NULL AND price > 0
        ORDER BY date, code
    """.format(','.join('?' * len(codes))),
        list(codes) + [lookback_start]
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


def compute_all_scores(conn, index_type, codes, trading_dates, premium_by_code, daily_data, pool_cfg):
    """计算所有交易日指定指数ETF的评分，写入 rotation_scores。

    评分公式 (z-score 标准化, abc 满足 a+b+c=1):
        nav_excess = NAV_return_1y - 池均值
        F = (nav_excess/σ_nav) * a + (-composite/σ_excess) * b + (-premium/σ_premium) * c

    其中 σ_nav, σ_excess, σ_premium 是池内全期标准差, 从 rotation-pool.json 的 sigmas 字段读取.
    标准化使分值落在 [-10, +10] 内, T 仍然自由设置 (从 threshold 字段读取).
    """
    pool = pool_cfg.get('pool', {})
    default_bonus = pool_cfg.get('default_bonus', -0.5)
    formula = pool_cfg.get('formula', {'a': 0.10, 'b': 0.80, 'c': 0.10})
    w_nav = formula.get('a', 0.10)
    w_excess = formula.get('b', 0.80)
    w_premium = formula.get('c', 0.10)

    # z-score 标准化所需的 σ (从配置读取, 不在配置时用 1.0 退化为不标准化)
    sigmas = pool_cfg.get('sigmas', {'nav': 1.0, 'excess': 1.0, 'premium': 1.0})
    sig_nav = sigmas.get('nav', 1.0) or 1.0
    sig_excess = sigmas.get('excess', 1.0) or 1.0
    sig_premium = sigmas.get('premium', 1.0) or 1.0

    pool_codes_set = set(pool.keys()) if pool else set(codes)

    code_date_idx = {}
    for code in codes:
        plist = premium_by_code.get(code, [])
        idx_map = {d: i for i, (d, _) in enumerate(plist)}
        code_date_idx[code] = (plist, idx_map)

    rows_to_insert = []

    for date in trading_dates:
        day_data = daily_data.get(date, {})

        nav_1y_by_code = {}
        for code in codes:
            if code not in day_data:
                continue
            nav_1y_by_code[code] = compute_nav_return_1y(
                premium_by_code, code, date, daily_data
            )

        pool_navs = [nav_1y_by_code[c] for c in nav_1y_by_code if c in pool_codes_set]
        nav_pool_mean = sum(pool_navs) / len(pool_navs) if pool_navs else 0.0

        for code in codes:
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

            nav_return_1y = nav_1y_by_code.get(code, 0.0)
            nav_excess = nav_return_1y - nav_pool_mean

            # z-score 标准化: 每个分量除以池内 σ
            score = (
                (nav_excess / sig_nav) * w_nav
                + (-composite / sig_excess) * w_excess
                + (-premium_rate / sig_premium) * w_premium
            )

            bonus = pool[code]['bonus'] if code in pool else default_bonus
            pool_score = score + bonus

            rows_to_insert.append((
                date, index_type, code, price, nav, premium_rate,
                composite, nav_return_1y, score, pool_score
            ))

    conn.executemany("""
        INSERT OR REPLACE INTO rotation_scores
        (date, index_type, code, price, nav, premium_rate, composite, nav_return_1y, score, pool_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows_to_insert)
    conn.commit()
    print(f"  rotation_scores[{index_type}]: {len(rows_to_insert)} rows written")


def simulate_rotation(conn, index_type, strategy_name, threshold, pool_codes, code_to_name, initial=INITIAL_VALUE):
    """从 rotation_scores 读取评分，模拟轮动策略。"""
    rows = conn.execute("""
        SELECT date, code, price, premium_rate, pool_score
        FROM rotation_scores
        WHERE index_type = ? AND code IN ({})
        ORDER BY date, pool_score DESC
    """.format(','.join('?' * len(pool_codes))),
        [index_type] + list(pool_codes)
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

    eq_shares, eq_dates = compute_equal_weight(conn, index_type, pool_codes, dates)

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
                'buy_code': best_code, 'buy_name': code_to_name.get(best_code, best_code),
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
                'sell_code': switch_from, 'sell_name': code_to_name.get(switch_from, switch_from),
                'sell_premium': round(old_premium, 2) if old_premium else None,
                'sell_score': round(holding_score, 2),
                'buy_code': best_code, 'buy_name': code_to_name.get(best_code, best_code),
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
    print(f"  rotation_index[{strategy_name}]: {len(result_rows)} rows written")

    return result_rows, trades


def simulate_min_premium(conn, codes, dates, initial=INITIAL_VALUE, threshold=1.0):
    """模拟纯溢价策略 (公平基线): F = -premium_rate, 与轮动相同的 T 阈值.
    当 (lowest_premium - holding_premium) * (-1) >= T (即 holding_premium - lowest_premium >= T) 时切换.
    通俗讲: 持仓溢价比最低的高 T% 时才换仓.
    无交易成本 (与轮动策略保持口径一致).
    """
    if not codes:
        return {}

    rows = conn.execute("""
        SELECT date, code, price, premium_rate
        FROM etf_data
        WHERE code IN ({}) AND date IN ({}) AND price IS NOT NULL AND price > 0
        ORDER BY date, code
    """.format(
        ','.join('?' * len(codes)),
        ','.join('?' * len(dates))
    ), list(codes) + list(dates)).fetchall()

    by_date = defaultdict(list)
    for r in rows:
        by_date[r['date']].append({
            'code': r['code'],
            'price': r['price'],
            'premium_rate': r['premium_rate'],
        })

    holding_code = None
    shares = 0.0
    result = {}

    for date in dates:
        day_etfs = by_date.get(date, [])
        if not day_etfs:
            continue

        candidates = [(e['premium_rate'], e) for e in day_etfs if e['premium_rate'] is not None]
        if not candidates:
            continue
        candidates.sort(key=lambda x: x[0])
        lowest = candidates[0][1]

        if holding_code is None:
            holding_code = lowest['code']
            shares = initial / lowest['price']
            result[date] = initial
            continue

        held = next((e for e in day_etfs if e['code'] == holding_code), None)
        if held is None:
            continue

        current_value = shares * held['price']

        # 切换条件: 持有溢价比最低溢价高 threshold (T=1 时, 高 1%)
        if (lowest['code'] != holding_code
                and (held['premium_rate'] - lowest['premium_rate']) >= threshold):
            cash = current_value  # 无成本
            shares = cash / lowest['price']
            holding_code = lowest['code']
            current_value = cash

        result[date] = round(current_value, 2)

    return result


def compute_equal_weight(conn, index_type, codes, dates):
    """计算等权基准: 指定指数的所有ETF，buy-and-hold 不再平衡。"""
    if not dates or not codes:
        return {}, {}

    first_date = dates[0]
    per_etf = INITIAL_VALUE / len(codes)

    all_dates_data = conn.execute("""
        SELECT date, code, price FROM etf_data
        WHERE code IN ({}) AND date IN ({}) AND price IS NOT NULL AND price > 0
        ORDER BY date
    """.format(
        ','.join('?' * len(codes)),
        ','.join('?' * len(dates))
    ), list(codes) + list(dates)).fetchall()

    price_map = defaultdict(dict)
    for r in all_dates_data:
        price_map[r['date']][r['code']] = r['price']

    first_prices = price_map.get(first_date, {})
    eq_shares = {}
    for code in codes:
        if code in first_prices and first_prices[code] > 0:
            eq_shares[code] = per_etf / first_prices[code]

    eq_dates = {}
    for date in dates:
        day_prices = price_map.get(date, {})
        total = sum(
            eq_shares.get(code, 0) * day_prices.get(code, 0)
            for code in codes
            if code in eq_shares and code in day_prices
        )
        eq_dates[date] = total

    return eq_shares, eq_dates


def generate_json(conn, index_type, strategy_name, threshold, pool_codes, codes, code_to_name, trades, output_path):
    """生成 rotation_{index}.json。"""
    rows = conn.execute("""
        SELECT date, holding_code, rotation_value, equal_weight_value
        FROM rotation_index WHERE strategy = ? ORDER BY date
    """, (strategy_name,)).fetchall()

    if not rows:
        print(f"  {index_type}: No data to generate JSON")
        return

    dates = [r['date'] for r in rows]
    rotation_values = [r['rotation_value'] for r in rows]
    equal_weight_values = [r['equal_weight_value'] for r in rows]
    holdings = [r['holding_code'] for r in rows]

    print(f"  {index_type}: Computing min-premium strategy...")
    mp_values_map = simulate_min_premium(conn, codes, dates)
    min_premium_values = [mp_values_map.get(d, INITIAL_VALUE) for d in dates]

    final_rv = rotation_values[-1]
    final_ev = equal_weight_values[-1]
    final_mp = min_premium_values[-1] if min_premium_values else INITIAL_VALUE
    rotation_return = (final_rv / INITIAL_VALUE - 1) * 100
    equal_weight_return = (final_ev / INITIAL_VALUE - 1) * 100
    min_premium_return = (final_mp / INITIAL_VALUE - 1) * 100

    pool_names = {code: code_to_name.get(code, code) for code in pool_codes}

    for t in trades:
        t['min_premium_value'] = round(mp_values_map.get(t['date'], INITIAL_VALUE), 2)

    data = {
        'index_type': index_type,
        'strategy': strategy_name,
        'pool': pool_codes,
        'pool_names': pool_names,
        'threshold': threshold,
        'initial_value': INITIAL_VALUE,
        'start_date': dates[0],
        'end_date': dates[-1],
        'trading_days': len(dates),
        'formula': 'score = NAV涨幅×10% + (-综合超额)×80% + (-当前溢价)×10% + 推荐加分(±0.5)',
        'equal_weight_etfs': len(codes),
        'summary': {
            'rotation_value': round(final_rv, 2),
            'rotation_return': round(rotation_return, 2),
            'equal_weight_value': round(final_ev, 2),
            'equal_weight_return': round(equal_weight_return, 2),
            'alpha': round(rotation_return - equal_weight_return, 2),
            'min_premium_value': round(final_mp, 2),
            'min_premium_return': round(min_premium_return, 2),
            'trade_count': len(trades),
            'current_holding': holdings[-1],
            'current_holding_name': code_to_name.get(holdings[-1], holdings[-1]),
        },
        'daily': {
            'dates': dates,
            'rotation_values': rotation_values,
            'equal_weight_values': equal_weight_values,
            'min_premium_values': min_premium_values,
            'holdings': holdings,
        },
        'trades': trades,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"  JSON: {output_path.name} ({len(dates)} days, {len(trades)} trades)")
    return data


def process_index(conn, index_type, pool_cfg, args):
    """处理单个指数的轮动计算。"""
    print(f"\n{'='*60}")
    print(f"处理指数: {index_type}")
    print(f"{'='*60}")

    # 获取该指数的ETF列表
    etf_configs = INDEX_ETFS_CONFIG.get(index_type)
    if not etf_configs:
        print(f"ERROR: 未找到{index_type}的ETF配置")
        return

    codes = [e['code'] for e in etf_configs]
    code_to_name = {e['code']: e['name'] for e in etf_configs}

    # 获取轮动池配置
    threshold = pool_cfg.get('threshold', 1.0)
    pool_codes = list(pool_cfg.get('pool', {}).keys())

    if not pool_codes:
        print(f"ERROR: {index_type}没有配置轮动池")
        return

    strategy_name = f'{index_type}_T{threshold}'

    # 处理增量更新
    if args.force:
        conn.execute(f"DELETE FROM rotation_scores WHERE index_type = ?", (index_type,))
        conn.execute(f"DELETE FROM rotation_index WHERE strategy LIKE ?", (f'{index_type}_%',))
        conn.commit()
        print(f"强制模式: 清空{index_type}的现有数据")

    last_score_date = conn.execute(
        "SELECT MAX(date) FROM rotation_scores WHERE index_type = ?",
        (index_type,)
    ).fetchone()[0]

    score_start = args.start
    if last_score_date and not args.force:
        score_start = last_score_date
        print(f"增量更新: 从{score_start}开始")

    lookback = (datetime.strptime(score_start, '%Y-%m-%d') - timedelta(days=400)).strftime('%Y-%m-%d')
    trading_dates = get_trading_dates(conn, score_start)

    if not trading_dates:
        print(f"未找到{index_type}的交易日期")
        return

    print(f"从{lookback}加载数据...")
    premium_by_code, daily_data = load_all_data(conn, codes, lookback)

    print(f"为{len(trading_dates)}个交易日计算评分...")
    compute_all_scores(conn, index_type, codes, trading_dates, premium_by_code, daily_data, pool_cfg)

    print(f"模拟{strategy_name}(阈值={threshold})...")
    result_rows, trades = simulate_rotation(conn, index_type, strategy_name, threshold, pool_codes, code_to_name)

    # 生成 JSON 输出
    output_file = OUTPUT_DIR / f'rotation_{index_type.lower()}.json'
    generate_json(conn, index_type, strategy_name, threshold, pool_codes, codes, code_to_name, trades, output_file)

    print(f"完成{index_type}处理: {len(result_rows)}条记录")

    return {
        'index_type': index_type,
        'strategy': strategy_name,
        'records': len(result_rows),
        'trades': len(trades),
        'codes': codes,
        'code_to_name': code_to_name,
    }


def main():
    parser = argparse.ArgumentParser(description='多指数轮动指数计算')
    parser.add_argument('--threshold', type=float, help='切换阈值(覆盖配置文件)')
    parser.add_argument('--index', default='all',
                        choices=['all', 'NASDAQ', 'SP500', 'NIKKEI', 'DAX'],
                        help='指数类型，all表示所有指数')
    parser.add_argument('--force', action='store_true', help='全量重算')
    parser.add_argument('--start', default=DEFAULT_START, help='起始日期')
    args = parser.parse_args()

    conn = get_db()
    init_tables(conn)

    all_pool_cfgs = load_all_pool_configs()
    if not all_pool_cfgs:
        print("ERROR: 未找到 rotation-pool.json 的配置")
        conn.close()
        return

    # 确定要处理的指数
    indices_to_process = []
    if args.index == 'all':
        indices_to_process = ['NASDAQ', 'SP500', 'NIKKEI', 'DAX']
    else:
        indices_to_process = [args.index]

    results = {}
    for index_type in indices_to_process:
        pool_cfg = all_pool_cfgs.get(index_type)
        if not pool_cfg:
            print(f"警告: {index_type}在rotation-pool.json中没有配置，跳过")
            continue

        # 如果命令行指定了threshold，覆盖配置文件
        if args.threshold:
            pool_cfg['threshold'] = args.threshold

        result = process_index(conn, index_type, pool_cfg, args)
        if result:
            results[index_type] = result

    conn.close()

    print(f"\n{'='*60}")
    print("处理完成")
    print(f"{'='*60}")
    for idx_type, info in results.items():
        print(f"{idx_type}: {info['records']}条记录, {info['trades']}次轮动")
    print("Done!")


if __name__ == '__main__':
    main()
