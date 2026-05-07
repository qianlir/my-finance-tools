#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest.py — ETF轮动策略回测

从 2025-01-01 开始，初始资金 100,000，跟踪：
1. 每只 ETF 买入持有的收益率
2. 策略A：每天换仓到分值最高的 ETF
3. 策略B：分值差 > 0.5 时才换仓

支持增量更新，每天运行只追加新数据。

Usage:
    python3 scripts/backtest.py                    # 增量更新到最新
    python3 scripts/backtest.py --force            # 清空重算
    python3 scripts/backtest.py --index NASDAQ     # 只看纳指
    python3 scripts/backtest.py --verbose          # 打印每日详情
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np

# ============= 配置（从 recommend_by_change.py 复制） =============
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR / ".."
DB_PATH = str(PROJECT_ROOT / "data" / "etf_premium.db")

ETF_CONFIG = [
    {'code': '513100', 'name': '国泰纳指ETF', 'index': 'NASDAQ'},
    {'code': '159941', 'name': '广发纳指ETF', 'index': 'NASDAQ'},
    {'code': '159660', 'name': '汇添富纳指ETF', 'index': 'NASDAQ'},
    {'code': '159501', 'name': '嘉实纳指ETF', 'index': 'NASDAQ'},
    {'code': '159632', 'name': '华安纳指ETF', 'index': 'NASDAQ'},
    {'code': '159659', 'name': '招商纳指ETF', 'index': 'NASDAQ'},
    {'code': '513300', 'name': '华夏纳指ETF', 'index': 'NASDAQ'},
    {'code': '513870', 'name': '富国纳指ETF', 'index': 'NASDAQ'},
    {'code': '513390', 'name': '博时纳指ETF', 'index': 'NASDAQ'},
    {'code': '513500', 'name': '博时标普ETF', 'index': 'SP500'},
    {'code': '159655', 'name': '华夏标普ETF', 'index': 'SP500'},
    {'code': '513650', 'name': '南方标普ETF', 'index': 'SP500'},
    {'code': '159612', 'name': '国泰标普ETF', 'index': 'SP500'},
]

EXCLUDED_CODES = ['159509']
CODE_TO_NAME = {e['code']: e['name'] for e in ETF_CONFIG}
CODE_TO_INDEX = {e['code']: e['index'] for e in ETF_CONFIG}

PERIODS = [('1M', 30), ('3M', 90), ('6M', 180), ('1Y', 365), ('ALL', None)]
WEIGHTS = {'1M': 0.35, '3M': 0.25, '6M': 0.20, '1Y': 0.10, 'ALL': 0.10}

DEFAULT_START = '2025-01-01'
DEFAULT_CAPITAL = 100000.0
STRATEGY_B_THRESHOLD = 0.5


# ============= 数据库 =============
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS backtest_scores (
            date TEXT NOT NULL,
            code TEXT NOT NULL,
            index_type TEXT NOT NULL,
            price REAL,
            nav REAL,
            premium_rate REAL,
            change_pct REAL,
            composite REAL,
            nav_return_1y REAL,
            score REAL,
            rank_in_index INTEGER,
            UNIQUE(date, code)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS backtest_portfolio (
            date TEXT NOT NULL,
            index_type TEXT NOT NULL,
            portfolio TEXT NOT NULL,
            market_value REAL NOT NULL,
            return_pct REAL NOT NULL,
            holding_code TEXT,
            score REAL,
            UNIQUE(date, index_type, portfolio)
        )
    """)
    conn.commit()


def get_last_computed_date(conn):
    """获取 backtest_scores 中最后的日期"""
    row = conn.execute("SELECT MAX(date) FROM backtest_scores").fetchone()
    return row[0] if row[0] else None


def clear_backtest_data(conn):
    conn.execute("DELETE FROM backtest_scores")
    conn.execute("DELETE FROM backtest_portfolio")
    conn.commit()
    print("  已清空回测数据")


# ============= 数据加载 =============
def load_etf_data(conn, start_date):
    """加载 etf_data，需要 start_date 之前的数据用于计算滚动均值"""
    # 需要 start_date 之前 365 天的数据来计算 hist_avg
    lookback_date = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=400)).strftime('%Y-%m-%d')
    codes = [e['code'] for e in ETF_CONFIG if e['code'] not in EXCLUDED_CODES]
    placeholders = ','.join('?' * len(codes))

    df = pd.read_sql_query(f"""
        SELECT date, code, price, nav, premium_rate
        FROM etf_data
        WHERE code IN ({placeholders})
          AND date >= ?
          AND price IS NOT NULL AND price > 0
          AND nav IS NOT NULL AND nav > 0
          AND premium_rate IS NOT NULL
        ORDER BY date, code
    """, conn, params=codes + [lookback_date])

    df['index_type'] = df['code'].map(CODE_TO_INDEX)
    return df


# ============= 分值计算 =============
def compute_scores(df, trading_dates):
    """计算每个交易日每只 ETF 的分值，返回 DataFrame"""
    all_dates = sorted(df['date'].unique())
    results = []

    for date in trading_dates:
        date_idx = np.searchsorted(all_dates, date)
        if date_idx == 0:
            continue

        # 当天和前一天的数据
        today_data = df[df['date'] == date].copy()
        prev_date = all_dates[date_idx - 1]
        prev_data = df[df['date'] == prev_date].set_index('code')

        if today_data.empty:
            continue

        # 计算涨幅
        today_data['change_pct'] = today_data.apply(
            lambda row: (row['price'] / prev_data.loc[row['code'], 'price'] - 1) * 100
            if row['code'] in prev_data.index else 0.0,
            axis=1
        )

        # 按指数分组计算 avg_change
        for idx_type in ['NASDAQ', 'SP500']:
            mask = today_data['index_type'] == idx_type
            group = today_data[mask]
            if group.empty:
                continue

            avg_change = group['change_pct'].mean()

            for _, row in group.iterrows():
                code = row['code']
                display_premium = row['premium_rate']
                change = row['change_pct']

                # 计算各期历史平均溢价
                excess_by_period = {}
                for period_name, days in PERIODS:
                    if days is not None:
                        period_start = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=days)).strftime('%Y-%m-%d')
                        hist_data = df[(df['code'] == code) & (df['date'] >= period_start) & (df['date'] <= date)]
                    else:
                        hist_data = df[(df['code'] == code) & (df['date'] <= date)]

                    hist_avg = hist_data['premium_rate'].mean() if not hist_data.empty else display_premium
                    excess = display_premium + change - avg_change - hist_avg
                    excess_by_period[period_name] = excess

                # 综合超额
                composite = sum(excess_by_period.get(p, 0) * w for p, w in WEIGHTS.items())

                # 1Y净值涨幅
                year_ago_date = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=365)).strftime('%Y-%m-%d')
                year_ago_data = df[(df['code'] == code) & (df['date'] <= year_ago_date)]
                if not year_ago_data.empty:
                    year_ago_nav = year_ago_data.iloc[-1]['nav']
                    nav_return_1y = (row['nav'] / year_ago_nav - 1) * 100
                else:
                    nav_return_1y = 0.0

                # 分值
                score = nav_return_1y * 0.10 + (-composite) * 0.75 + (-display_premium) * 0.15

                results.append({
                    'date': date,
                    'code': code,
                    'index_type': idx_type,
                    'price': row['price'],
                    'nav': row['nav'],
                    'premium_rate': display_premium,
                    'change_pct': round(change, 4),
                    'composite': round(composite, 4),
                    'nav_return_1y': round(nav_return_1y, 4),
                    'score': round(score, 4),
                })

    if not results:
        return pd.DataFrame()

    scores_df = pd.DataFrame(results)

    # 计算 rank_in_index
    scores_df['rank_in_index'] = scores_df.groupby(['date', 'index_type'])['score'].rank(
        ascending=False, method='min'
    ).astype(int)

    return scores_df


# ============= 策略模拟 =============
def simulate_portfolios(scores_df, capital, index_filter=None):
    """模拟所有组合（买入持有 + 策略A + 策略B），返回 portfolio DataFrame"""
    results = []

    for idx_type in ['NASDAQ', 'SP500']:
        if index_filter and idx_type != index_filter:
            continue

        idx_scores = scores_df[scores_df['index_type'] == idx_type].copy()
        if idx_scores.empty:
            continue

        dates = sorted(idx_scores['date'].unique())
        codes = sorted(idx_scores[idx_scores['date'] == dates[0]]['code'].unique())

        # --- 买入持有：每只 ETF ---
        for code in codes:
            code_data = idx_scores[idx_scores['code'] == code].sort_values('date')
            if code_data.empty:
                continue

            first_price = code_data.iloc[0]['price']
            shares = capital / first_price

            for _, row in code_data.iterrows():
                mv = shares * row['price']
                ret = (mv / capital - 1) * 100
                results.append({
                    'date': row['date'],
                    'index_type': idx_type,
                    'portfolio': code,
                    'market_value': round(mv, 2),
                    'return_pct': round(ret, 4),
                    'holding_code': None,
                    'score': round(row['score'], 4),
                })

        # --- 策略A & B ---
        for strategy, threshold in [('STRATEGY_A', 0.0), ('STRATEGY_B', STRATEGY_B_THRESHOLD)]:
            holding_code = None
            shares = 0.0

            for date in dates:
                day_scores = idx_scores[idx_scores['date'] == date].sort_values('score', ascending=False)
                if day_scores.empty:
                    continue

                best = day_scores.iloc[0]
                best_code = best['code']
                best_score = best['score']

                if holding_code is None:
                    # 首日买入
                    holding_code = best_code
                    shares = capital / best['price']
                else:
                    # 检查是否换仓
                    current_row = day_scores[day_scores['code'] == holding_code]
                    current_score = current_row.iloc[0]['score'] if not current_row.empty else 0.0

                    if best_code != holding_code and (best_score - current_score) > threshold:
                        # 换仓：按当天收盘价卖出再买入
                        current_price = current_row.iloc[0]['price'] if not current_row.empty else best['price']
                        mv = shares * current_price
                        holding_code = best_code
                        shares = mv / best['price']

                # 计算当日市值
                holding_row = day_scores[day_scores['code'] == holding_code]
                if not holding_row.empty:
                    price = holding_row.iloc[0]['price']
                    holding_score = holding_row.iloc[0]['score']
                else:
                    price = best['price']
                    holding_score = best_score

                mv = shares * price
                ret = (mv / capital - 1) * 100

                results.append({
                    'date': date,
                    'index_type': idx_type,
                    'portfolio': strategy,
                    'market_value': round(mv, 2),
                    'return_pct': round(ret, 4),
                    'holding_code': holding_code,
                    'score': round(holding_score, 4),
                })

    return pd.DataFrame(results) if results else pd.DataFrame()


# ============= 统计 =============
def compute_stats(portfolio_df, capital, scores_df=None):
    """计算各组合的统计指标"""
    stats = {}

    # 预计算每只 ETF 的净值涨幅（从 backtest_scores）
    nav_returns = {}
    if scores_df is not None and not scores_df.empty:
        for code in scores_df['code'].unique():
            code_data = scores_df[scores_df['code'] == code].sort_values('date')
            if len(code_data) >= 2:
                first_nav = code_data.iloc[0]['nav']
                last_nav = code_data.iloc[-1]['nav']
                if first_nav and first_nav > 0:
                    nav_returns[code] = round((last_nav / first_nav - 1) * 100, 2)

    for (idx_type, portfolio), group in portfolio_df.groupby(['index_type', 'portfolio']):
        group = group.sort_values('date')
        final_mv = group.iloc[-1]['market_value']
        final_ret = group.iloc[-1]['return_pct']

        # 最大回撤
        cummax = group['market_value'].cummax()
        drawdown = (group['market_value'] - cummax) / cummax * 100
        max_dd = drawdown.min()

        # 换仓次数（策略才有）
        trade_count = 0
        if portfolio.startswith('STRATEGY'):
            holdings = group['holding_code'].tolist()
            for i in range(1, len(holdings)):
                if holdings[i] != holdings[i - 1]:
                    trade_count += 1

        key = (idx_type, portfolio)
        stats[key] = {
            'final_value': round(final_mv, 2),
            'return_pct': round(final_ret, 2),
            'nav_return_pct': nav_returns.get(portfolio),  # 买入持有ETF才有
            'max_drawdown': round(max_dd, 2),
            'trade_count': trade_count,
            'days': len(group),
        }

    return stats


# ============= 输出 =============
def print_summary(stats, portfolio_df, capital, start_date, end_date, index_filter=None):
    """打印汇总表"""
    dates = sorted(portfolio_df['date'].unique())
    n_days = len(dates)
    print(f"\n{'='*60}")
    print(f"  ETF轮动回测 {start_date} ~ {end_date} ({n_days}个交易日)")
    print(f"  初始资金: ¥{capital:,.0f}")
    print(f"{'='*60}")

    for idx_type in ['NASDAQ', 'SP500']:
        if index_filter and idx_type != index_filter:
            continue

        idx_name = '纳指' if idx_type == 'NASDAQ' else '标普'
        print(f"\n  {idx_name}:")

        # 策略对比
        sa = stats.get((idx_type, 'STRATEGY_A'), {})
        sb = stats.get((idx_type, 'STRATEGY_B'), {})

        # 找最佳单ETF
        etf_stats = {k: v for k, v in stats.items() if k[0] == idx_type and not k[1].startswith('STRATEGY')}
        if etf_stats:
            best_etf_key = max(etf_stats, key=lambda k: etf_stats[k]['return_pct'])
            best_etf = etf_stats[best_etf_key]
            best_etf_name = CODE_TO_NAME.get(best_etf_key[1], best_etf_key[1])

            # 等权基准
            avg_ret = sum(v['return_pct'] for v in etf_stats.values()) / len(etf_stats)
        else:
            best_etf = {'return_pct': 0, 'max_drawdown': 0}
            best_etf_name = '-'
            avg_ret = 0

        header = f"  {'':20s} | {'策略A(每日换仓)':>14s} | {'策略B(阈值>0.5)':>14s} | {'最佳: '+best_etf_name:>16s} | {'等权基准':>10s}"
        print(header)
        print(f"  {'-'*20}-+-{'-'*14}-+-{'-'*14}-+-{'-'*16}-+-{'-'*10}")

        def fmt_ret(v):
            return f"{v:+.2f}%" if v else "N/A"

        print(f"  {'收益率':20s} | {fmt_ret(sa.get('return_pct', 0)):>14s} | {fmt_ret(sb.get('return_pct', 0)):>14s} | {fmt_ret(best_etf.get('return_pct', 0)):>16s} | {fmt_ret(avg_ret):>10s}")
        print(f"  {'换仓次数':20s} | {sa.get('trade_count', 0):>13d}次 | {sb.get('trade_count', 0):>13d}次 | {'0':>15s}次 | {'0':>9s}次")
        print(f"  {'最大回撤':20s} | {fmt_ret(sa.get('max_drawdown', 0)):>14s} | {fmt_ret(sb.get('max_drawdown', 0)):>14s} | {fmt_ret(best_etf.get('max_drawdown', 0)):>16s} | {'':>10s}")

        # 总结表：每只ETF的价格收益、净值增长 + 策略A/B
        sa_ret_str = fmt_ret(sa.get('return_pct', 0))
        sb_ret_str = fmt_ret(sb.get('return_pct', 0))
        print(f"\n  总结:")
        print(f"  {'ETF':>8s} | {'名称':12s} | {'价格收益':>10s} | {'净值增长':>10s}")
        print(f"  {'-'*8}-+-{'-'*12}-+-{'-'*10}-+-{'-'*10}")

        sorted_etfs = sorted(etf_stats.items(), key=lambda x: x[1]['return_pct'], reverse=True)
        for (_, code), st in sorted_etfs:
            name = CODE_TO_NAME.get(code, code)
            nav_ret = st.get('nav_return_pct')
            nav_str = fmt_ret(nav_ret) if nav_ret is not None else "N/A"
            print(f"  {code:>8s} | {name:12s} | {fmt_ret(st['return_pct']):>10s} | {nav_str:>10s}")

        print(f"  {'-'*8}-+-{'-'*12}-+-{'-'*10}-+-{'-'*10}")
        print(f"  {'策略A':>8s} | {'每日换仓':12s} | {sa_ret_str:>10s} |")
        print(f"  {'策略B':>8s} | {'阈值>0.5':12s} | {sb_ret_str:>10s} |")

    print()


def print_verbose(portfolio_df, index_filter=None):
    """打印策略每日详情（仅换仓日）"""
    for idx_type in ['NASDAQ', 'SP500']:
        if index_filter and idx_type != index_filter:
            continue

        idx_name = '纳指' if idx_type == 'NASDAQ' else '标普'

        for strategy in ['STRATEGY_A', 'STRATEGY_B']:
            strat_name = '策略A(每日换仓)' if strategy == 'STRATEGY_A' else '策略B(阈值>0.5)'
            group = portfolio_df[
                (portfolio_df['index_type'] == idx_type) &
                (portfolio_df['portfolio'] == strategy)
            ].sort_values('date')

            if group.empty:
                continue

            print(f"\n  === {idx_name} {strat_name} 换仓记录 ===")
            print(f"  {'日期':>12s} | {'持仓':>8s} | {'名称':12s} | {'市值':>12s} | {'收益率':>10s} | {'分值':>6s}")
            print(f"  {'-'*12}-+-{'-'*8}-+-{'-'*12}-+-{'-'*12}-+-{'-'*10}-+-{'-'*6}")

            prev_holding = None
            for _, row in group.iterrows():
                holding = row['holding_code']
                if holding != prev_holding:
                    name = CODE_TO_NAME.get(holding, holding) if holding else '-'
                    print(f"  {row['date']:>12s} | {holding or '-':>8s} | {name:12s} | ¥{row['market_value']:>10,.2f} | {row['return_pct']:>+9.2f}% | {row['score']:>6.2f}")
                    prev_holding = holding

    print()


def generate_report(stats, portfolio_df, capital, start_date, end_date, index_filter=None):
    """生成 Markdown 报告文件"""
    reports_dir = PROJECT_ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / f"backtest_{datetime.now().strftime('%Y%m%d')}.md"

    lines = []
    lines.append(f"# ETF轮动回测报告 {start_date} ~ {end_date}")
    lines.append(f"")
    lines.append(f"> 初始资金: ¥{capital:,.0f}")
    dates = sorted(portfolio_df['date'].unique())
    lines.append(f"> 交易日数: {len(dates)}")
    lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"")

    for idx_type in ['NASDAQ', 'SP500']:
        if index_filter and idx_type != index_filter:
            continue

        idx_name = '纳指' if idx_type == 'NASDAQ' else '标普'
        lines.append(f"## {idx_name}ETF")
        lines.append(f"")

        # 汇总表
        sa = stats.get((idx_type, 'STRATEGY_A'), {})
        sb = stats.get((idx_type, 'STRATEGY_B'), {})
        etf_stats = {k: v for k, v in stats.items() if k[0] == idx_type and not k[1].startswith('STRATEGY')}

        if etf_stats:
            best_key = max(etf_stats, key=lambda k: etf_stats[k]['return_pct'])
            best = etf_stats[best_key]
            avg_ret = sum(v['return_pct'] for v in etf_stats.values()) / len(etf_stats)
        else:
            best = {'return_pct': 0, 'max_drawdown': 0, 'trade_count': 0}
            best_key = (idx_type, '-')
            avg_ret = 0

        lines.append(f"| 指标 | 策略A(每日换仓) | 策略B(阈值>0.5) | 最佳单ETF({best_key[1]}) | 等权基准 |")
        lines.append(f"|------|----------------|----------------|------------|----------|")
        lines.append(f"| 收益率 | {sa.get('return_pct', 0):+.2f}% | {sb.get('return_pct', 0):+.2f}% | {best.get('return_pct', 0):+.2f}% | {avg_ret:+.2f}% |")
        lines.append(f"| 换仓次数 | {sa.get('trade_count', 0)}次 | {sb.get('trade_count', 0)}次 | 0 | 0 |")
        lines.append(f"| 最大回撤 | {sa.get('max_drawdown', 0):+.2f}% | {sb.get('max_drawdown', 0):+.2f}% | {best.get('max_drawdown', 0):+.2f}% | - |")
        lines.append(f"")

        # 买入持有明细
        lines.append(f"### 买入持有对比")
        lines.append(f"")
        lines.append(f"| ETF | 名称 | 价格收益 | 净值增长 |")
        lines.append(f"|-----|------|----------|----------|")
        for (_, code), st in sorted(etf_stats.items(), key=lambda x: x[1]['return_pct'], reverse=True):
            name = CODE_TO_NAME.get(code, code)
            nav_ret = st.get('nav_return_pct')
            nav_str = f"{nav_ret:+.2f}%" if nav_ret is not None else "N/A"
            lines.append(f"| {code} | {name} | {st['return_pct']:+.2f}% | {nav_str} |")
        lines.append(f"| **策略A** | 每日换仓 | **{sa.get('return_pct', 0):+.2f}%** | |")
        lines.append(f"| **策略B** | 阈值>0.5 | **{sb.get('return_pct', 0):+.2f}%** | |")
        lines.append(f"")

    report_path.write_text('\n'.join(lines), encoding='utf-8')
    print(f"  报告已生成: {report_path}")
    return report_path


def generate_json(stats, portfolio_df, capital, start_date, end_date, index_filter=None):
    """生成 JSON 供小程序使用"""
    data_dir = PROJECT_ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    json_path = data_dir / "backtest.json"

    # 获取交易日数
    dates = sorted(portfolio_df['date'].unique())

    result = {
        "date": datetime.now().strftime('%Y-%m-%d'),
        "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M'),
        "backtest_period": {
            "start": start_date,
            "end": end_date,
            "trading_days": len(dates)
        },
        "initial_capital": capital,
        "sections": []
    }

    for idx_type in ['NASDAQ', 'SP500']:
        if index_filter and idx_type != index_filter:
            continue

        idx_name = '纳指' if idx_type == 'NASDAQ' else '标普'

        # 获取策略统计
        sa = stats.get((idx_type, 'STRATEGY_A'), {})
        sb = stats.get((idx_type, 'STRATEGY_B'), {})
        etf_stats = {k: v for k, v in stats.items() if k[0] == idx_type and not k[1].startswith('STRATEGY')}

        # 策略数据
        strategies = []
        if sa:
            strategies.append({
                "name": "STRATEGY_A",
                "display_name": "策略A(每日换仓)",
                "final_value": int(sa.get('final_value', capital)),
                "return_pct": round(sa.get('return_pct', 0), 2),
                "max_drawdown": round(sa.get('max_drawdown', 0), 2),
                "trade_count": sa.get('trade_count', 0)
            })
        if sb:
            strategies.append({
                "name": "STRATEGY_B",
                "display_name": "策略B(阈值>0.5)",
                "final_value": int(sb.get('final_value', capital)),
                "return_pct": round(sb.get('return_pct', 0), 2),
                "max_drawdown": round(sb.get('max_drawdown', 0), 2),
                "trade_count": sb.get('trade_count', 0)
            })

        # 买入持有数据
        buy_hold_etfs = []
        for (_, code), st in sorted(etf_stats.items(), key=lambda x: x[1]['return_pct'], reverse=True):
            buy_hold_etfs.append({
                "code": code,
                "name": CODE_TO_NAME.get(code, code),
                "final_value": int(st.get('final_value', capital)),
                "return_pct": round(st.get('return_pct', 0), 2),
                "nav_return_pct": round(st.get('nav_return_pct', 0), 2) if st.get('nav_return_pct') else None,
                "max_drawdown": round(st.get('max_drawdown', 0), 2)
            })

        # 最佳 ETF
        best_etf = None
        if etf_stats:
            best_key = max(etf_stats, key=lambda k: etf_stats[k]['return_pct'])
            best_code = best_key[1]
            best_etf = {
                "code": best_code,
                "name": CODE_TO_NAME.get(best_code, best_code),
                "return_pct": round(etf_stats[best_key]['return_pct'], 2)
            }

        # 等权基准
        equal_weight_return = round(sum(v['return_pct'] for v in etf_stats.values()) / len(etf_stats), 2) if etf_stats else 0

        result["sections"].append({
            "index_type": idx_type,
            "index_name": idx_name,
            "strategies": strategies,
            "buy_hold_etfs": buy_hold_etfs,
            "best_etf": best_etf,
            "equal_weight_return": equal_weight_return
        })

    # 写入文件
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"  JSON已生成: {json_path}")
    return json_path


# ============= 增量更新 =============
def run_backtest(args):
    conn = get_conn()
    init_tables(conn)

    start_date = args.start
    capital = args.capital
    index_filter = args.index if args.index != 'ALL' else None

    if args.force:
        clear_backtest_data(conn)

    # 检查增量
    last_date = get_last_computed_date(conn)

    # 获取所有可用交易日
    all_trading_dates = pd.read_sql_query(
        "SELECT DISTINCT date FROM etf_data WHERE date >= ? ORDER BY date",
        conn, params=[start_date]
    )['date'].tolist()

    if not all_trading_dates:
        print("  错误: 无可用交易数据")
        conn.close()
        return

    end_date = all_trading_dates[-1]

    if last_date and last_date >= end_date and not args.force:
        print(f"  数据已是最新 (截至 {last_date})，直接输出结果")
        print(f"  如需重算请加 --force")
    else:
        # 需要计算的日期范围
        if last_date and not args.force:
            new_dates = [d for d in all_trading_dates if d > last_date]
            print(f"  增量更新: {last_date} → {end_date} ({len(new_dates)}个新交易日)")
        else:
            new_dates = all_trading_dates
            print(f"  全量计算: {all_trading_dates[0]} → {end_date} ({len(new_dates)}个交易日)")

        if new_dates:
            # 加载数据（需要 lookback 计算滚动均值）
            print("  加载历史数据...")
            df = load_etf_data(conn, start_date)
            print(f"  加载了 {len(df)} 条记录")

            # 计算分值
            print("  计算每日分值...")
            scores_df = compute_scores(df, new_dates)
            if scores_df.empty:
                print("  错误: 无法计算分值")
                conn.close()
                return
            print(f"  计算了 {len(scores_df)} 条分值记录")

            # 保存分值到 DB
            scores_df.to_sql('backtest_scores', conn, if_exists='append', index=False,
                             method='multi', chunksize=500)
            print(f"  分值已保存到 backtest_scores")

            # 模拟组合 — 需要全量分值数据
            print("  模拟投资组合...")
            all_scores = pd.read_sql_query(
                "SELECT * FROM backtest_scores ORDER BY date, code", conn
            )
            portfolio_df = simulate_portfolios(all_scores, capital, index_filter)

            if not portfolio_df.empty:
                # 全量替换 portfolio（因为策略依赖完整历史）
                if index_filter:
                    conn.execute("DELETE FROM backtest_portfolio WHERE index_type = ?", [index_filter])
                else:
                    conn.execute("DELETE FROM backtest_portfolio")
                portfolio_df.to_sql('backtest_portfolio', conn, if_exists='append', index=False,
                                    method='multi', chunksize=500)
                print(f"  组合数据已保存到 backtest_portfolio ({len(portfolio_df)} 条)")

            conn.commit()

    # 读取完整结果并输出
    portfolio_df = pd.read_sql_query("SELECT * FROM backtest_portfolio ORDER BY date", conn)

    if index_filter:
        portfolio_df = portfolio_df[portfolio_df['index_type'] == index_filter]

    if portfolio_df.empty:
        print("  无回测结果")
        conn.close()
        return

    actual_start = portfolio_df['date'].min()
    actual_end = portfolio_df['date'].max()

    # 读取 scores 用于计算净值涨幅
    scores_df = pd.read_sql_query("SELECT * FROM backtest_scores ORDER BY date, code", conn)
    if index_filter:
        scores_df = scores_df[scores_df['index_type'] == index_filter]

    stats = compute_stats(portfolio_df, capital, scores_df)

    # JSON 模式：只输出 JSON，跳过其他输出
    if args.json:
        generate_json(stats, portfolio_df, capital, actual_start, actual_end, index_filter)
        conn.close()
        return

    print_summary(stats, portfolio_df, capital, actual_start, actual_end, index_filter)

    if args.verbose:
        print_verbose(portfolio_df, index_filter)

    generate_report(stats, portfolio_df, capital, actual_start, actual_end, index_filter)

    conn.close()


# ============= CLI =============
def main():
    parser = argparse.ArgumentParser(description='ETF轮动策略回测')
    parser.add_argument('--start', default=DEFAULT_START, help=f'起始日期 (默认 {DEFAULT_START})')
    parser.add_argument('--capital', type=float, default=DEFAULT_CAPITAL, help=f'初始资金 (默认 {DEFAULT_CAPITAL})')
    parser.add_argument('--index', choices=['NASDAQ', 'SP500', 'ALL'], default='ALL', help='指数类型 (默认 ALL)')
    parser.add_argument('--verbose', action='store_true', help='打印每日详情')
    parser.add_argument('--force', action='store_true', help='清空重算')
    parser.add_argument('--json', action='store_true', help='输出JSON格式（供小程序使用）')
    args = parser.parse_args()

    run_backtest(args)


if __name__ == '__main__':
    main()
