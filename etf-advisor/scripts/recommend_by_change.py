#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
recommend_by_change.py — 基于涨幅偏离的ETF推荐

逻辑：
1. 获取各ETF的显示溢价、历史平均溢价、当天涨幅
2. 计算平均涨幅（作为纳指/标普的基准涨幅）
3. 计算超额溢价 = 显示溢价 + 当天涨幅 - 平均涨幅 - 历史平均溢价
4. 按超额溢价排序，给出买入/卖出建议

Usage:
    python3 recommend_by_change.py
    python3 recommend_by_change.py --holding 513100 159655
"""

import sqlite3
import subprocess
import sys
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple
import statistics

# ============= 配置 =============
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR / ".."
DB_PATH = str(PROJECT_ROOT / "data" / "etf_premium.db")

# 推荐池配置
_pool_path = PROJECT_ROOT / "memory" / "knowledge" / "etf" / "rotation-pool.json"
ROTATION_POOL = json.loads(_pool_path.read_text()) if _pool_path.exists() else {}

# 指数类型映射：期货代码、字段名、显示名
INDEX_CONFIG = {
    'NASDAQ': {
        'symbol': 'NQ',
        'close_col': 'nq_close',
        'prev_col': 'nq_prev_close',
        'change_col': 'nq_change_pct',
        'source_col': 'nq_source',
        'name_cn': '纳指'
    },
    'SP500': {
        'symbol': 'ES',
        'close_col': 'es_close',
        'prev_col': 'es_prev_close',
        'change_col': 'es_change_pct',
        'source_col': 'es_source',
        'name_cn': '标普'
    },
    'DOW': {
        'symbol': 'YM',
        'close_col': 'ym_close',
        'prev_col': 'ym_prev_close',
        'change_col': 'ym_change_pct',
        'source_col': 'ym_source',
        'name_cn': '道琼斯'
    },
    'NIKKEI': {
        'symbol': 'NK',
        'close_col': 'nk_idx_close',
        'prev_col': 'nk_idx_prev_close',
        'change_col': 'nk_idx_change_pct',
        'source_col': 'nk_source',
        'name_cn': '日经225',
        'nav_label': '日股收盘',
        'use_index': True,
    },
    'DAX': {
        'symbol': 'DAX',
        'close_col': 'dax_idx_close',
        'prev_col': 'dax_idx_prev_close',
        'change_col': 'dax_idx_change_pct',
        'source_col': 'nq_source',
        'name_cn': '德国DAX',
        'nav_label': '欧股收盘',
        'use_index': True,
    },
    'OTHERS': {
        'symbol': '',
        'name_cn': '其他',
        'nav_label': '美股收盘',
        'use_holdings': True,
    },
    'LOF': {
        'symbol': '',
        'name_cn': 'LOF',
        'nav_label': '美股收盘',
        'use_holdings': True,
    }
}

# ETF列表（排除纳指科技）
ETF_CONFIG = [
    # 纳斯达克ETF
    {'code': '513100', 'name': '国泰纳指ETF', 'index': 'NASDAQ'},
    {'code': '159941', 'name': '广发纳指ETF', 'index': 'NASDAQ'},
    {'code': '159660', 'name': '汇添富纳指ETF', 'index': 'NASDAQ'},
    {'code': '159501', 'name': '嘉实纳指ETF', 'index': 'NASDAQ'},
    {'code': '159632', 'name': '华安纳指ETF', 'index': 'NASDAQ'},
    {'code': '159659', 'name': '招商纳指ETF', 'index': 'NASDAQ'},
    {'code': '513300', 'name': '华夏纳指ETF', 'index': 'NASDAQ'},
    {'code': '513870', 'name': '富国纳指ETF', 'index': 'NASDAQ'},
    {'code': '513390', 'name': '博时纳指ETF', 'index': 'NASDAQ'},
    {'code': '513110', 'name': '南方纳指ETF', 'index': 'NASDAQ'},
    {'code': '161130', 'name': '纳斯达克100LOF', 'index': 'NASDAQ'},
    # 标普500ETF
    {'code': '513500', 'name': '博时标普ETF', 'index': 'SP500'},
    {'code': '159655', 'name': '华夏标普ETF', 'index': 'SP500'},
    {'code': '513650', 'name': '南方标普ETF', 'index': 'SP500'},
    {'code': '159612', 'name': '国泰标普ETF', 'index': 'SP500'},
    {'code': '161125', 'name': '标普500LOF', 'index': 'SP500'},
    # 德国DAX ETF
    {'code': '513030', 'name': '德国ETF华安', 'index': 'DAX'},
    {'code': '159561', 'name': '德国ETF嘉实', 'index': 'DAX'},
    # 日经225ETF
    {'code': '159866', 'name': '日经ETF工银', 'index': 'NIKKEI'},
    {'code': '513000', 'name': '日经225ETF易方达', 'index': 'NIKKEI'},
    {'code': '513520', 'name': '日经ETF华夏', 'index': 'NIKKEI'},
    {'code': '513880', 'name': '日经225ETF华安', 'index': 'NIKKEI'},
    # 其他 ETF
    {'code': '513400', 'name': '国泰道琼斯ETF', 'index': 'OTHERS'},
    {'code': '159509', 'name': '纳指科技ETF', 'index': 'OTHERS'},
    {'code': '159529', 'name': '标普消费ETF', 'index': 'OTHERS'},
    {'code': '513290', 'name': '美国生物ETF', 'index': 'OTHERS'},
    {'code': '513080', 'name': '法国CAC40ETF', 'index': 'OTHERS'},
    # LOF
    {'code': '501312', 'name': '海外科技LOF', 'index': 'LOF'},
    {'code': '162415', 'name': '美国消费LOF', 'index': 'LOF'},
    {'code': '161128', 'name': '标普科技LOF', 'index': 'LOF'},
    {'code': '160140', 'name': '美国REIT LOF', 'index': 'LOF'},
    {'code': '161126', 'name': '标普医药LOF', 'index': 'LOF'},
    {'code': '161127', 'name': '标普生物LOF', 'index': 'LOF'},
    {'code': '162411', 'name': '华宝油气LOF', 'index': 'LOF'},
    {'code': '164824', 'name': '印度LOF', 'index': 'LOF'},
    {'code': '160719', 'name': '嘉实黄金LOF', 'index': 'LOF'},
    {'code': '161116', 'name': '易方达黄金LOF', 'index': 'LOF'},
    {'code': '160723', 'name': '嘉实原油LOF', 'index': 'LOF'},
    {'code': '161129', 'name': '易方达原油LOF', 'index': 'LOF'},
    {'code': '160216', 'name': '国泰商品LOF', 'index': 'LOF'},
]

EXCLUDED_CODES = []

# 多维度时间窗口
PERIODS = [
    ('1M',  30),
    ('3M',  90),
    ('6M',  180),
    ('1Y',  365),
    ('ALL', None),
]

# 综合评分权重（近期权重更高）
WEIGHTS = {'1M': 0.35, '3M': 0.25, '6M': 0.20, '1Y': 0.10, 'ALL': 0.10}


# ============= 数据库操作 =============
def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def check_recent_prices(days=5):
    """检查最近N天的价格数据是否完整，通过API对比验证"""
    # 关键ETF代码（纳指和标普各选一个代表）
    check_codes = {
        '159660': ('sz', '汇添富纳指ETF'),
        '159655': ('sz', '华夏标普ETF'),
    }

    conn = get_db_connection()
    cursor = conn.cursor()

    # 获取数据库中最近的日期
    cursor.execute("SELECT DISTINCT date FROM etf_data ORDER BY date DESC LIMIT ?", (days,))
    db_dates = [row['date'] for row in cursor.fetchall()]
    conn.close()

    if not db_dates:
        print("  警告: 数据库中无数据")
        return

    print(f"\n  检查最近{days}天价格数据...")
    issues = []

    for code, (market, name) in check_codes.items():
        # 从API获取最近价格
        try:
            url = f"http://qt.gtimg.cn/q={market}{code}"
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            response.encoding = 'gbk'

            if '~' in response.text and 'none_match' not in response.text:
                data = response.text.split('"')[1]
                parts = data.split('~')
                api_price = float(parts[3]) if len(parts) > 3 and parts[3] else None

                if api_price:
                    # 对比数据库中最新价格
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT date, price FROM etf_data
                        WHERE code = ? ORDER BY date DESC LIMIT 1
                    """, (code,))
                    row = cursor.fetchone()
                    conn.close()

                    if row:
                        db_price = row['price']
                        db_date = row['date']
                        diff_pct = abs(api_price - db_price) / db_price * 100 if db_price else 0

                        if diff_pct > 0.5:  # 差异超过0.5%则警告
                            issues.append(f"{code}({name}): API={api_price:.3f}, DB={db_price:.3f} ({db_date})")
                        else:
                            print(f"    {code}: ✓ {db_date} 价格 {db_price:.3f}")
                    else:
                        issues.append(f"{code}({name}): 数据库中无记录")
        except Exception as e:
            issues.append(f"{code}({name}): API查询失败 ({e})")

    if issues:
        print("  发现差异:")
        for issue in issues:
            print(f"    ⚠ {issue}")
        print("  建议: 运行 python3 scripts/update_data.py --realtime 更新数据")


def get_current_data() -> Dict[str, Dict]:
    """获取当前最新数据"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 获取最新日期
    cursor.execute("SELECT MAX(date) as max_date FROM etf_data")
    max_date_row = cursor.fetchone()
    max_date = max_date_row['max_date'] if max_date_row else None

    if not max_date:
        conn.close()
        return {}

    # 获取最新数据（包含 change_pct, nav_date）
    cursor.execute("""
        SELECT code, name, price, nav, premium_rate, change_pct, prev_close, nav_date
        FROM etf_data
        WHERE date = ? AND nav IS NOT NULL
        ORDER BY code
    """, (max_date,))

    current = {}
    for row in cursor.fetchall():
        current[row['code']] = {
            'code': row['code'],
            'name': row['name'],
            'price': row['price'],
            'nav': row['nav'],
            'premium_rate': row['premium_rate'],
            'change_pct': row['change_pct'],  # API报告的涨跌幅
            'prev_close': row['prev_close'],   # 昨收价
            'nav_date': row['nav_date'],       # 净值对应的美股收盘日
        }

    conn.close()
    return current


def get_previous_data() -> Tuple[Dict[str, float], str]:  # 返回 (价格字典, 日期)
    """获取前一天的价格（用于计算涨幅）"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 获取最近两个交易日的数据（使用DISTINCT获取不同日期）
    cursor.execute("""
        SELECT DISTINCT date FROM etf_data
        ORDER BY date DESC LIMIT 2
    """)

    dates = [row['date'] for row in cursor.fetchall()]

    if len(dates) < 2:
        conn.close()
        return {}, dates[0] if dates else None

    prev_date = dates[1]

    # 获取前一天的价格
    cursor.execute("""
        SELECT code, price
        FROM etf_data
        WHERE date = ? AND price IS NOT NULL
        ORDER BY code
    """, (prev_date,))

    previous = {row['code']: row['price'] for row in cursor.fetchall()}
    conn.close()
    return previous, prev_date


def _get_holdings_with_prices(fund_code: str) -> list:
    """获取基金持仓及对应的股票价格"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT h.ticker, h.stock_name, h.weight_pct,
               p.price, p.prev_close, p.after_hours, p.change_pct
        FROM fund_holdings h
        LEFT JOIN stock_prices p ON h.ticker = p.ticker
        WHERE h.fund_code = ?
        ORDER BY h.weight_pct DESC
    """, (fund_code,))
    rows = cursor.fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({
            'ticker': r['ticker'],
            'name': r['stock_name'],
            'weight': round(r['weight_pct'], 2),
            'price': round(r['price'], 2) if r['price'] else None,
            'prev_close': round(r['prev_close'], 2) if r['prev_close'] else None,
            'after_hours': round(r['after_hours'], 2) if r['after_hours'] and r['after_hours'] > 0 else None,
            'change_pct': round(r['change_pct'], 2) if r['change_pct'] is not None else None,
        })
    return result


def _get_fund_config(code: str) -> dict:
    """从 fund_config 表获取基金配置"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM fund_config WHERE code = ?", (code,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def get_nav_info(code: str) -> Dict:
    """获取某个ETF的净值信息：最新净值、净值实际日期、前一日净值、涨跌幅
    返回: {'nav': float, 'nav_date': str, 'prev_nav': float, 'nav_change': float}

    注意:
    - nav_date: 净值实际日期(美股收盘日)，来自nav_date字段
    - 优先使用有nav_date的记录（历史确认数据）
    - 跳过重复的净值值，找到真正变化的前一日净值
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 获取更多记录以便跳过重复值
    cursor.execute("""
        SELECT date, nav, nav_date, is_fixed FROM etf_data
        WHERE code = ? AND nav IS NOT NULL
        ORDER BY date DESC LIMIT 20
    """, (code,))

    all_rows = cursor.fetchall()
    conn.close()

    if not all_rows:
        return {'nav': 0, 'nav_date': None, 'prev_nav': 0, 'nav_change': 0}

    # 筛选有nav_date的记录（历史确认数据）
    valid_rows = [r for r in all_rows if r['nav_date']]

    if not valid_rows:
        # 如果没有有nav_date的记录，回退到使用所有记录
        valid_rows = all_rows

    latest_nav = valid_rows[0]['nav']
    latest_date = valid_rows[0]['nav_date'] or valid_rows[0]['date']

    # 找到第一个不同的净值值作为前一日净值
    prev_nav = latest_nav
    for row in valid_rows[1:]:
        if row['nav'] and row['nav'] != latest_nav:
            prev_nav = row['nav']
            break

    nav_change = 0
    if prev_nav and prev_nav > 0 and latest_nav != prev_nav:
        nav_change = (latest_nav - prev_nav) / prev_nav * 100
    else:
        # 如果在 valid_rows 中没找到不同的净值（历史 nav_date 缺失），
        # 尝试从 all_rows 中查找前一个不同的净值值
        for row in all_rows[1:]:
            if row['nav'] and row['nav'] != latest_nav:
                prev_nav = row['nav']
                nav_change = (latest_nav - prev_nav) / prev_nav * 100
                break

    return {
        'nav': latest_nav,
        'nav_date': latest_date,
        'prev_nav': prev_nav,
        'nav_change': nav_change
    }


def get_multi_period_avg_premium() -> Dict[str, Dict[str, float]]:
    """获取多时间维度的历史平均溢价
    返回: {code: {'1M': avg, '3M': avg, ..., '1Y_max': max, '1Y_gt7': days, '1Y_gt6': days}}
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    today = datetime.now().strftime('%Y-%m-%d')
    result = {}

    # 各时间窗口的平均溢价
    for period_name, days in PERIODS:
        if days is not None:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT code, AVG(premium_rate) as avg_premium
                FROM etf_data
                WHERE date >= ? AND premium_rate IS NOT NULL
                GROUP BY code
            """, (start_date,))
        else:
            cursor.execute("""
                SELECT code, AVG(premium_rate) as avg_premium
                FROM etf_data
                WHERE premium_rate IS NOT NULL
                GROUP BY code
            """)

        for row in cursor.fetchall():
            code = row['code']
            if code not in result:
                result[code] = {}
            result[code][period_name] = row['avg_premium']

    # 风险指标：过去1年的最高溢价、>7%天数、>6%天数
    start_1y = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    cursor.execute("""
        SELECT code,
            MAX(premium_rate) as max_1y,
            SUM(CASE WHEN premium_rate > 7 THEN 1 ELSE 0 END) as gt7_days,
            SUM(CASE WHEN premium_rate > 6 THEN 1 ELSE 0 END) as gt6_days
        FROM etf_data
        WHERE date >= ? AND premium_rate IS NOT NULL
        GROUP BY code
    """, (start_1y,))

    for row in cursor.fetchall():
        code = row['code']
        if code not in result:
            result[code] = {}
        result[code]['1Y_max'] = row['max_1y']
        result[code]['1Y_gt7'] = row['gt7_days'] or 0
        result[code]['1Y_gt6'] = row['gt6_days'] or 0

    # 1Y净值涨幅：对比1年前的净值与最新净值
    cursor.execute("""
        SELECT a.code,
            a.nav as current_nav,
            b.nav as year_ago_nav,
            (a.nav - b.nav) / b.nav * 100 as nav_return_1y
        FROM etf_data a
        INNER JOIN (
            SELECT code, nav, date FROM etf_data
            WHERE date = (SELECT MAX(date) FROM etf_data WHERE date <= ?)
            AND nav IS NOT NULL AND nav > 0
        ) b ON a.code = b.code
        WHERE a.date = (SELECT MAX(date) FROM etf_data)
        AND a.nav IS NOT NULL AND a.nav > 0
    """, (start_1y,))

    for row in cursor.fetchall():
        code = row['code']
        if code not in result:
            result[code] = {}
        result[code]['nav_return_1y'] = row['nav_return_1y'] or 0

    # 1Y价格涨幅：对比1年前的价格与最新价格
    cursor.execute("""
        SELECT a.code,
            a.price as current_price,
            b.price as year_ago_price,
            (a.price - b.price) / b.price * 100 as price_return_1y
        FROM etf_data a
        INNER JOIN (
            SELECT code, price, date FROM etf_data
            WHERE date = (SELECT MAX(date) FROM etf_data WHERE date <= ?)
            AND price IS NOT NULL AND price > 0
        ) b ON a.code = b.code
        WHERE a.date = (SELECT MAX(date) FROM etf_data)
        AND a.price IS NOT NULL AND a.price > 0
    """, (start_1y,))

    for row in cursor.fetchall():
        code = row['code']
        if code not in result:
            result[code] = {}
        result[code]['price_return_1y'] = row['price_return_1y'] or 0

    conn.close()
    return result


def get_futures_info() -> List[Dict]:
    """获取最近2天期货数据
    返回: [{date, nq_price, nq_change, es_price, es_change, ym_price, ym_change}, ...] 按日期升序

    注意：使用 us_date（美股交易日）作为显示日期，无需时区转换
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT us_date, nq_close, nq_prev_close, nq_change_pct,
               es_close, es_prev_close, es_change_pct,
               ym_close, ym_prev_close, ym_change_pct,
               nk_close, nk_prev_close, nk_change_pct
        FROM futures_data
        WHERE us_date IS NOT NULL
        ORDER BY us_date DESC LIMIT 2
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return []

    result = []

    # 直接使用 us_date，无需显示层修正
    for i, row in enumerate(rows):
        entry = {'date': row['us_date']}

        if row['nq_close'] is not None:
            entry['nq_price'] = row['nq_close']
            entry['nq_change'] = row['nq_change_pct']

        if row['es_close'] is not None:
            entry['es_price'] = row['es_close']
            entry['es_change'] = row['es_change_pct']

        if row['ym_close'] is not None:
            entry['ym_price'] = row['ym_close']
            entry['ym_change'] = row['ym_change_pct']

        try:
            if row['nk_close'] is not None:
                entry['nk_price'] = row['nk_close']
                entry['nk_change'] = row['nk_change_pct']
        except (IndexError, KeyError):
            pass

        result.append(entry)

    # 按日期排序（升序）
    result.sort(key=lambda x: x['date'])
    return result


def detect_data_freshness() -> str:
    """判断净值数据时效性（T+1机制：今天查到的是前一天的净值）

    例: 今天3/26查到的净值1.8058，实际是3/25美股收盘后的净值
    DB中的date是爬取日期，净值对应T-1美股收盘
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 取一个代表性ETF检查
    cursor.execute("""
        SELECT date, nav FROM etf_data
        WHERE code = '513100' AND nav IS NOT NULL
        ORDER BY date DESC LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    if not row:
        return ""

    crawl_date = datetime.strptime(row['date'], '%Y-%m-%d').date()
    today = datetime.now().date()
    gap_days = (today - crawl_date).days

    if gap_days == 0:
        # 今天已爬取，净值对应昨天美股收盘
        return f"净值已更新（对应昨日美股收盘），价格为今日实时"
    elif gap_days == 1:
        # 昨天爬取，净值对应前天美股收盘
        return f"净值未更新（仍为{row['date']}数据），价格为今日实时"
    elif gap_days == 2:
        weekday = today.weekday()
        if weekday == 0:  # 周一，上周五未爬取
            return f"净值未更新（仍为上周五数据），价格为今日实时"
        else:
            return f"净值滞后2天（{row['date']}），价格为今日实时"
    elif gap_days > 2:
        return f"净值滞后{gap_days}天（{row['date']}起），价格为今日实时"
    else:
        return f"净值为{row['date']}，价格为今日实时"


def detect_nav_stale_days(code: str) -> int:
    """检测NAV滞后天数：净值实际日期(nav_date)到今天之间有几个交易日需要修正
    
    逻辑：用 nav_date（净值对应的美股收盘日）与今天比较，
    差几个美股交易日就需要几天的期货修正。
    如果没有 nav_date，回退到用连续相同净值天数的方法。
    
    返回: 需要修正的天数（correction_days = stale_days - 1）
    """
    from datetime import datetime, timedelta
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 优先使用 nav_date 判断滞后
    cursor.execute("""
        SELECT date, nav, nav_date FROM etf_data
        WHERE code = ? AND nav IS NOT NULL
        ORDER BY date DESC LIMIT 1
    """, (code,))
    row = cursor.fetchone()
    
    if row and row['nav_date']:
        nav_date = row['nav_date']
        # 净值日期到今天之间的美股交易日天数
        try:
            nav_dt = datetime.strptime(nav_date, '%Y-%m-%d').date()
            today = datetime.now().date()
            gap = (today - nav_dt).days
        except:
            gap = 0
        
        # 估算交易日：gap 天中约 gap*5/7 是交易日（粗略）
        # 更准确：逐天计数跳过周末
        trading_days = 0
        d = nav_dt
        while d < today:
            d += timedelta(days=1)
            if d.weekday() < 5:  # 周一到周五
                trading_days += 1
        
        # stale_days = 净值已覆盖1天 + 需要修正的交易日
        # correction_days = stale_days - 1 = trading_days
        # 所以 stale_days = trading_days + 1
        conn.close()
        return max(1, trading_days + 1)
    
    # 回退：用连续相同净值天数
    cursor.execute("""
        SELECT date, nav FROM etf_data
        WHERE code = ? AND nav IS NOT NULL
        ORDER BY date DESC LIMIT 10
    """, (code,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return 0

    current_nav = rows[0]['nav']
    count = 1
    for i in range(1, len(rows)):
        if abs(rows[i]['nav'] - current_nav) < 0.0001:
            count += 1
        else:
            break
    return count


def get_cumulative_futures_change(index_type: str, days: int) -> float:
    """获取最近N个交易日的累计期货涨跌幅（复合计算）"""
    detail = get_futures_change_detail(index_type, days)
    if not detail:
        return 0.0
    factor = 1.0
    for _, chg in detail:
        factor *= (1 + chg / 100)
    return (factor - 1) * 100


def get_futures_change_detail(index_type: str, days: int) -> List[Tuple[str, float]]:
    """获取最近N个交易日的期货逐日涨跌明细
    返回: [(date, change_pct), ...] 按日期升序
    """
    if days <= 0:
        return []

    if index_type not in INDEX_CONFIG:
        return []

    conn = get_db_connection()
    cursor = conn.cursor()

    col = INDEX_CONFIG[index_type]['change_col']
    cursor.execute(f"""
        SELECT date, {col} as change_pct FROM futures_data
        ORDER BY date DESC LIMIT ?
    """, (days,))
    rows = cursor.fetchall()
    conn.close()

    # 按日期升序返回
    return [(r['date'], r['change_pct'] or 0.0) for r in reversed(rows)]



# ============= 价格比值法 =============
def _is_nikkei_market_hours():
    """日经开盘时间：北京时间 8:00-14:00"""
    h = datetime.now().hour
    return 8 <= h < 14


def get_nav_date_futures_close(nav_date: str, index_type: str) -> float:
    """获取净值日对应的期货/指数收盘价

    美股ETF: 查期货 prev_close
    日经ETF: 开盘时用指数，非开盘时用NK期货
    DAX ETF: 用DAX指数

    返回: 收盘价 或 0
    """
    if not nav_date or index_type not in INDEX_CONFIG:
        return 0

    cfg = INDEX_CONFIG.get(index_type, {})

    # 持仓型（OTHERS）：不需要期货/指数比值，返回 0
    if cfg.get('use_holdings'):
        return 0

    # 日经/DAX：用指数收盘
    if cfg.get('use_index'):
        return _get_index_nav_date_close(nav_date, cfg['close_col'])

    return _get_us_nav_date_close(nav_date, index_type)


def _get_index_nav_date_close(nav_date: str, close_col: str) -> float:
    """指数型ETF（日经/DAX）: 找 ≤ nav_date 最近一个有指数收盘的交易日

    nav_date 是中国日期，可能是对方市场的假日，
    此时实际净值基于上一个交易日的指数收盘。
    """
    if not nav_date:
        return 0
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT {close_col} FROM futures_data
        WHERE date <= ? AND {close_col} IS NOT NULL
        ORDER BY date DESC LIMIT 1
    """, (nav_date,))
    row = cursor.fetchone()
    conn.close()
    return float(row[0]) if row and row[0] else 0


def _get_us_nav_date_close(nav_date: str, index_type: str) -> float:
    """美股ETF: 查期货真收盘价（下一交易日的 prev_close）"""
    conn = get_db_connection()
    cursor = conn.cursor()

    close_col = INDEX_CONFIG[index_type]['close_col']
    prev_col = INDEX_CONFIG[index_type]['prev_col']

    # 路径1: 后续交易日的 prev_close = nav_date 的真收盘价
    try:
        nav_dt = datetime.strptime(nav_date, '%Y-%m-%d')
        next_dt = nav_dt + timedelta(days=1)
        for _ in range(10):
            while next_dt.weekday() >= 5:
                next_dt += timedelta(days=1)
            next_date = next_dt.strftime('%Y-%m-%d')
            cursor.execute(f"SELECT {prev_col} FROM futures_data WHERE us_date = ? AND {prev_col} IS NOT NULL", (next_date,))
            row = cursor.fetchone()
            if row and row[0]:
                conn.close()
                return float(row[0])
            next_dt += timedelta(days=1)
    except:
        pass

    # 路径2: 当天的 close（盘中价，精度较差）
    cursor.execute(f"SELECT {close_col} FROM futures_data WHERE us_date = ?", (nav_date,))
    row = cursor.fetchone()
    conn.close()
    return float(row[0]) if row and row[0] else 0


def get_current_futures_price(index_type: str) -> float:
    """获取最新期货/指数价格"""
    if index_type not in INDEX_CONFIG:
        return 0

    cfg = INDEX_CONFIG.get(index_type, {})
    if cfg.get('use_holdings'):
        return 0
    # 日经：开盘时用指数，非开盘时用期货
    if index_type == 'NIKKEI':
        close_col = 'nk_idx_close' if _is_nikkei_market_hours() else 'nk_close'
    else:
        close_col = cfg.get('close_col')
        if not close_col:
            return 0

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT {close_col} FROM futures_data WHERE {close_col} IS NOT NULL ORDER BY date DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if row and row[0]:
        return float(row[0])
    return 0

# ============= 计算函数 =============
def calculate_daily_change(current: float, previous: float) -> float:
    """计算涨幅"""
    if previous and previous > 0:
        return (current - previous) / previous * 100
    return 0.0


def calculate_average_change(etf_data: List[Dict]) -> float:
    """计算平均涨幅（作为基准）"""
    changes = [d['change'] for d in etf_data if d.get('change') is not None]
    if changes:
        return statistics.mean(changes)
    return 0.0


def calculate_excess_premium(display_premium: float, hist_avg_premium: float) -> float:
    """计算超额溢价 = 当前溢价 - 历史平均溢价"""
    return display_premium - hist_avg_premium


def get_recommendation_level(score: float) -> str:
    """根据分值计算推荐程度
    分值越高=越推荐买入，分值越低=越推荐卖出
    """
    if score >= 2.5:
        return '买入 ' + '✅' * 5
    elif score >= 2.0:
        return '买入 ' + '✅' * 4
    elif score >= 1.5:
        return '买入 ' + '✅' * 3
    elif score >= 1.0:
        return '买入 ' + '✅' * 2
    elif score >= 0.5:
        return '买入 ' + '✅'
    elif score >= 0:
        return '观望'
    elif score >= -0.5:
        return '卖出 ' + '❌'
    elif score >= -1.0:
        return '卖出 ' + '❌' * 2
    else:
        return '卖出 ' + '❌' * 3


# ============= 主函数 =============
def analyze_etfs(index_type: str) -> Tuple[List[Dict], List[str], Dict]:
    """分析某类ETF（纳指或标普），返回 (结果列表, 数据不足列表, 期货修正信息)"""

    # 获取数据
    current_data = get_current_data()
    previous_data, prev_date = get_previous_data()
    multi_avg = get_multi_period_avg_premium()

    # 筛选指定类型的ETF
    etf_list = [e for e in ETF_CONFIG if e['index'] == index_type and e['code'] not in EXCLUDED_CODES]

    results = []
    insufficient_data = []

    for etf in etf_list:
        code = etf['code']
        name = etf['name']

        # 跳过没有数据的
        if code not in current_data or code not in previous_data:
            insufficient_data.append(f"{code}({name})")
            continue

        current = current_data[code]
        previous = previous_data.get(code, current['price'])

        # 优先使用API报告的涨跌幅，否则计算（使用价格变化，反映今天A股的实际涨跌）
        if current.get('change_pct') is not None:
            # API报告的涨跌幅（基于API的昨收，更准确）
            change = current['change_pct']
        else:
            # 回退到使用数据库前一天价格计算
            change = calculate_daily_change(current['price'], previous)

        # 获取净值详细信息（日期、前一日净值、涨跌幅）
        nav_info = get_nav_info(code)
        nav = nav_info['nav']
        nav_date = nav_info['nav_date']  # 净值实际日期(美股收盘日)
        nav_change = nav_info['nav_change']

        # 估算溢价：根据估算方式选择
        cfg = INDEX_CONFIG.get(index_type, {})
        if cfg.get('use_holdings'):
            # 持仓估算：查 fund_config 确定具体方式
            _fc = _get_fund_config(code)
            if _fc and _fc['estimate_method'] == 'holdings' and nav:
                import sys; sys.path.insert(0, str(SCRIPT_DIR))
                from update_data import estimate_nav_by_holdings
                estimated_nav, _est_chg = estimate_nav_by_holdings(code, nav)
                display_premium = (current['price'] - estimated_nav) / estimated_nav * 100
            elif _fc and _fc['estimate_method'] == 'futures' and _fc.get('estimate_symbol') and nav:
                # OTHERS 中的期货型（如道琼斯）
                _sym = _fc['estimate_symbol']
                _idx_type_for_sym = {'NQ': 'NASDAQ', 'ES': 'SP500', 'YM': 'DOW'}.get(_sym, 'DOW')
                nav_date_close = get_nav_date_futures_close(nav_date, _idx_type_for_sym)
                current_futures_price = get_current_futures_price(_idx_type_for_sym)
                if nav_date_close and current_futures_price:
                    estimated_nav = nav * (current_futures_price / nav_date_close)
                    display_premium = (current['price'] - estimated_nav) / estimated_nav * 100
                else:
                    estimated_nav = nav
                    display_premium = current.get('premium_rate', 0)
            else:
                estimated_nav = nav
                display_premium = current.get('premium_rate', 0)
        else:
            # 期货/指数比值法（现有逻辑）
            nav_date_close = get_nav_date_futures_close(nav_date, index_type)
            current_futures_price = get_current_futures_price(index_type)
            if nav and nav_date_close and current_futures_price:
                estimated_nav = nav * (current_futures_price / nav_date_close)
                display_premium = (current['price'] - estimated_nav) / estimated_nav * 100
            elif nav:
                estimated_nav = nav
                display_premium = current.get('premium_rate', 0)
            else:
                estimated_nav = None
                display_premium = current.get('premium_rate', 0)

        avg_by_period = multi_avg.get(code, {})

        results.append({
            'code': code,
            'name': name,
            'price': current['price'],
            'nav': nav,
            'nav_date': nav_date,      # 净值实际日期(美股收盘日)
            'nav_change': nav_change,   # 净值较前一日涨跌百分比
            'display_premium': display_premium,
            'change': change,           # 涨幅使用价格变化（今天A股实际涨跌）
            'avg_by_period': avg_by_period,
            # 风险指标
            '1Y_max': avg_by_period.get('1Y_max', 0),
            '1Y_gt7': avg_by_period.get('1Y_gt7', 0),
            '1Y_gt6': avg_by_period.get('1Y_gt6', 0),
            # 1Y净值涨幅
            'nav_return_1y': avg_by_period.get('nav_return_1y', 0),
            # 1Y价格涨幅
            'price_return_1y': avg_by_period.get('price_return_1y', 0),
        })

    # 获取期货价格比值法数据
    # 用第一个ETF的nav_date作为代表
    rep_nav_date = None
    for etf in etf_list:
        info = get_nav_info(etf['code'])
        if info.get('nav_date'):
            rep_nav_date = info['nav_date']
            break
    
    nav_date_close = get_nav_date_futures_close(rep_nav_date, index_type) if rep_nav_date else 0
    current_futures_price = get_current_futures_price(index_type)
    futures_ratio = (current_futures_price / nav_date_close) if nav_date_close and current_futures_price else 0

    # 获取期货显示数据
    futures_display = get_futures_info()

    ft_info = {
        'futures_ratio': futures_ratio,
        'nav_date_close': nav_date_close,
        'current_futures_price': current_futures_price,
        'futures_display': futures_display,
        'nav_date': rep_nav_date,
    }

    if not results:
        return [], insufficient_data, ft_info

    # 计算平均涨幅（使用期货复合涨幅）
    # 期货复合涨幅 = (1+r1) * (1+r2) * ... - 1
    futures_info = get_futures_info()
    avg_change = 0.0
    idx_cfg = INDEX_CONFIG.get(index_type, {})
    if futures_info and len(futures_info) > 0 and idx_cfg.get('change_col'):
        change_key = idx_cfg['change_col'].replace('_pct', '_change')
        changes = [f.get(change_key, 0) for f in futures_info if f.get(change_key) is not None]
        if changes:
            # 复合涨幅 = (1+r1) * (1+r2) * ... - 1
            combined = 1.0
            for c in changes:
                combined *= (1 + c / 100)
            avg_change = (combined - 1) * 100

    # 计算超额净值涨幅（vs 同 sub_category 均值）
    _sub_groups = {}
    for r in results:
        fc = _get_fund_config(r['code'])
        sub = (fc['sub_category'] if fc and fc.get('sub_category') else None) or ('_solo_' + r['code'])
        r['_sub'] = sub
        _sub_groups.setdefault(sub, []).append(r)
    for sub, group in _sub_groups.items():
        avg_nav = sum(r.get('nav_return_1y', 0) for r in group) / len(group) if group else 0
        for r in group:
            r['excess_nav_return'] = r.get('nav_return_1y', 0) - avg_nav

    # 计算多维度超额溢价 + 综合评分
    for r in results:
        r['avg_change'] = avg_change
        r['excess_by_period'] = {}

        for period_name, _ in PERIODS:
            hist_avg = r['avg_by_period'].get(period_name, r['display_premium'])
            excess = calculate_excess_premium(r['display_premium'], hist_avg)
            r['excess_by_period'][period_name] = excess

        # 综合超额溢价 = 加权平均
        r['composite'] = sum(
            r['excess_by_period'].get(p, 0) * w for p, w in WEIGHTS.items()
        )

        # 分值 = 超额净值涨幅×10% + (-超额溢价)×80% + (-溢价)×10%
        # 超额净值涨幅 = 我的1Y净值涨幅 - 同sub_category均值（空=自己，差值为0）
        r['score'] = (
            r.get('excess_nav_return', 0) * 0.10
            + (-r['composite']) * 0.80
            + (-r['display_premium']) * 0.10
        )

        # 板块历史溢价特征加分：1Y均溢价 × 10%，反映该板块过去的溢价水平
        avg_1y_premium = r['avg_by_period'].get('1Y', 0)
        r['score'] += avg_1y_premium * 0.10
        pool_cfg = ROTATION_POOL.get(index_type, {})
        pool = pool_cfg.get('pool', {})
        etf_pool_cfg = pool.get(r['code'])
        r['rotation_pool'] = etf_pool_cfg is not None
        r['rotation_bonus'] = etf_pool_cfg['bonus'] if etf_pool_cfg else pool_cfg.get('default_bonus', 0)
        r['score'] += r['rotation_bonus']

    # === 推荐等级（按 sub_category 分组归一化）===
    results.sort(key=lambda x: x['score'], reverse=True)

    # 按 sub_category 分组，每组独立归一化
    _rec_groups = {}
    for r in results:
        _rec_groups.setdefault(r.get('_sub', r['code']), []).append(r)

    for sub, group in _rec_groups.items():
        max_score = group[0]['score'] if group else 0
        adjustment = max(0, max_score - 2.5)
        for r in group:
            score_for_rec = r['score']
            if adjustment > 0 and score_for_rec > 0:
                score_for_rec = max(0, score_for_rec - adjustment)
            r['recommendation'] = get_recommendation_level(score_for_rec)

    # LOF 套利标注
    if index_type == 'LOF':
        for r in results:
            fc = _get_fund_config(r['code'])
            sub_status = fc.get('subscription_status', 'unknown') if fc else 'unknown'
            sub_limit = fc.get('subscription_limit') if fc else None
            r['subscription_status'] = sub_status
            r['subscription_limit'] = sub_limit
            prem = r['display_premium']
            if prem < -1.5:
                r['arbitrage'] = 'redeem'
            elif prem > 2.0 and sub_status in ('open', 'limited'):
                r['arbitrage'] = 'subscribe'
            else:
                r['arbitrage'] = None

    return results, insufficient_data, ft_info


def format_percent(value: float, decimals: int = 2) -> str:
    """格式化百分比"""
    if value is None:
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{decimals}f}%"


# ============= JSON 报告（小程序用） =============
def _parse_recommendation(rec_str: str) -> Tuple[str, int]:
    """解析 '买入 ✅✅✅✅' → ('买入', 4)，'卖出 ❌❌' → ('卖出', -2)"""
    check_count = rec_str.count('✅')
    cross_count = rec_str.count('❌')
    if check_count > 0:
        return '买入', check_count
    elif cross_count > 0:
        return '卖出', -cross_count
    else:
        return '观望', 0


def _format_futures_json(futures_list: List[Dict]) -> List[Dict]:
    """期货数据转 JSON 格式"""
    result = []
    for entry in futures_list:
        item = {"date": entry['date']}
        if entry.get('nq_price') is not None:
            item["nq_price"] = round(entry['nq_price'])
            item["nq_change"] = round(entry.get('nq_change', 0) or 0, 2)
        if entry.get('es_price') is not None:
            item["es_price"] = round(entry['es_price'])
            item["es_change"] = round(entry.get('es_change', 0) or 0, 2)
        if entry.get('ym_price') is not None:
            item["ym_price"] = round(entry['ym_price'])
            item["ym_change"] = round(entry.get('ym_change', 0) or 0, 2)
        result.append(item)
    return result


def _get_report_timestamp() -> Tuple[str, str]:
    """返回当前报告时间戳 (日期, 生成时间)"""
    now = datetime.now()
    return now.strftime('%Y-%m-%d'), now.strftime('%Y-%m-%d %H:%M')


def generate_report_json(nasdaq_results: List[Dict], sp500_results: List[Dict],
                         nasdaq_insufficient: List[str], sp500_insufficient: List[str],
                         nq_ft: Dict = None, es_ft: Dict = None,
                         dow_results: List[Dict] = None, dow_insufficient: List[str] = None,
                         ym_ft: Dict = None,
                         nikkei_results: List[Dict] = None, nikkei_insufficient: List[str] = None,
                         nk_ft: Dict = None,
                         dax_results: List[Dict] = None, dax_insufficient: List[str] = None,
                         dax_ft: Dict = None,
                         others_results: List[Dict] = None, others_insufficient: List[str] = None,
                         others_ft: Dict = None,
                         lof_results: List[Dict] = None, lof_insufficient: List[str] = None,
                         lof_ft: Dict = None) -> Path:
    """生成 report.json 供小程序使用"""
    import json

    today, gen_time = _get_report_timestamp()
    futures = get_futures_info()
    freshness = detect_data_freshness()

    def build_section(index_type, results, insufficient, ft_info):
        ft_info = ft_info or {}
        cfg = INDEX_CONFIG.get(index_type, {})
        index_name = cfg.get('name_cn', index_type)
        futures_ratio = ft_info.get('futures_ratio', 0)
        has_correction = futures_ratio and abs(futures_ratio - 1) > 0.0001
        prem_col = "估算溢价" if has_correction else "当前溢价"

        symbol = cfg.get('symbol', 'NQ')
        nav_date_close = ft_info.get('nav_date_close', 0)
        current_futures_price = ft_info.get('current_futures_price', 0)
        correction = {
            "symbol": symbol,
            "method": "price_ratio",
            "nav_date_close": nav_date_close,
            "current_futures_price": current_futures_price,
            "ratio": round(futures_ratio, 6) if futures_ratio else 1.0,
            "ratio_pct": round((futures_ratio - 1) * 100, 2) if futures_ratio else 0.0
        } if nav_date_close and current_futures_price else None

        etfs = []
        for r in results:
            rec_text, stars = _parse_recommendation(r['recommendation'])
            etfs.append({
                "code": r['code'],
                "name": r['name'],
                "price": round(r['price'], 3),
                "nav": round(r.get('nav', 0), 3),
                "nav_change": round(r.get('nav_change', 0), 2),
                "change": round(r['change'], 2),
                "display_premium": round(r['display_premium'], 2),
                "excess_3m": round(r['excess_by_period'].get('3M', 0), 2),
                "avg_3m": round(r['avg_by_period'].get('3M', 0), 2),
                "excess_6m": round(r['excess_by_period'].get('6M', 0), 2),
                "avg_6m": round(r['avg_by_period'].get('6M', 0), 2),
                "excess_1y": round(r['excess_by_period'].get('1Y', 0), 2),
                "avg_1y": round(r['avg_by_period'].get('1Y', 0), 2),
                "composite": round(r['composite'], 2),
                "nav_return_1y": round(r.get('nav_return_1y', 0), 2),
                "excess_nav_return": round(r.get('excess_nav_return', 0), 2),
                "price_return_1y": round(r.get('price_return_1y', 0), 2),
                "days_gt7": r['1Y_gt7'],
                "score": round(r['score'], 2),
                "recommendation": rec_text,
                "stars": stars,
                "rotation_pool": r.get('rotation_pool', False),
                "rotation_bonus": r.get('rotation_bonus', 0),
                "holdings": _get_holdings_with_prices(r['code']) if index_type in ('OTHERS', 'LOF') else None,
                "arbitrage": r.get('arbitrage'),
                "subscription_status": r.get('subscription_status'),
                "subscription_limit": r.get('subscription_limit')
            })

        # 净值日期（取第一个ETF的nav_date）
        nav_date = results[0].get('nav_date') if results else None

        return {
            "index_type": index_type,
            "index_name": index_name,
            "nav_date": nav_date,
            "premium_col_name": prem_col,
            "futures_correction": correction,
            "futures_cumulative": round((futures_ratio - 1) * 100, 2) if futures_ratio else None,
            "insufficient": insufficient or [],
            "etfs": etfs
        }

    # 构建所有sections
    sections = [
        build_section('NASDAQ', nasdaq_results, nasdaq_insufficient, nq_ft),
        build_section('SP500', sp500_results, sp500_insufficient, es_ft),
    ]
    if dax_results is not None:
        sections.append(build_section('DAX', dax_results, dax_insufficient or [], dax_ft))
    if nikkei_results is not None:
        sections.append(build_section('NIKKEI', nikkei_results, nikkei_insufficient or [], nk_ft))
    if lof_results is not None:
        sections.append(build_section('LOF', lof_results, lof_insufficient or [], lof_ft))
    if others_results is not None:
        sections.append(build_section('OTHERS', others_results, others_insufficient or [], others_ft))

    report = {
        "date": today,
        "generated_at": gen_time,
        "data_freshness": freshness,
        "futures": _format_futures_json(futures),
        "sections": sections,
        "formula_notes": [
            "格式: 超额溢价(历史均值)  按分值排序（越高=越推荐）",
            "综合超额 = 1M×35% + 3M×25% + 6M×20% + 1Y×10% + ALL×10%",
            "分值 = 溢价偏离历史溢价均值 + 同类跟踪质量差异 + 板块历史溢价水平",
            "分值越高，当前溢价越低于历史水平。仅反映溢价位置，不预测板块涨跌。"
        ]
    }

    output_path = PROJECT_ROOT / "data" / "report.json"
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    print(f"JSON报告: {output_path.resolve()}")
    return output_path


def display_width(s: str) -> int:
    """计算字符串显示宽度（CJK字符占2列）"""
    import unicodedata
    w = 0
    for c in s:
        eaw = unicodedata.east_asian_width(c)
        if eaw in ('W', 'F'):
            w += 2
        else:
            w += 1
    return w


def pad(text, width):
    """按显示宽度对齐"""
    s = str(text)
    return s + ' ' * max(0, width - display_width(s))


def print_results(index_type: str, results: List[Dict], insufficient_data: List[str] = None,
                   ft_info: Dict = None):
    """打印分析结果（管道分隔中文表格）"""

    if not results:
        print(f"\n=== {index_type}ETF ===")
        print("无数据")
        return

    ft_info = ft_info or {}
    futures_ratio = ft_info.get('futures_ratio', 0)
    cfg = INDEX_CONFIG.get(index_type, {})
    index_name = cfg.get('name_cn', index_type)
    if futures_ratio and abs(futures_ratio - 1) > 0.0001:
        ratio_type = "日经指数比值" if index_type == 'NIKKEI' else "期货价格比值"
        ft_label = f"（{ratio_type}{futures_ratio:.4f}修正）"
        prem_col = "估算溢价"
    else:
        ft_label = ""
        prem_col = "当前溢价"

    print(f"\n=== {index_name} ETF 分析（按分值排序）{ft_label}===\n")

    # 列定义: (header, width) — width是单元格内容区的显示宽度
    # (列名, 内容宽度, header额外补偿空格数)
    # 补偿: 中文字符在VSCode中渲染宽度略窄于2倍ASCII，需要额外空格对齐
    cols = [
        ('代码',        6, 1),
        ('价格',        5, 0),
        ('净值',       18, 1),  # 扩宽以显示日期和涨跌
        ('涨幅',        6, 1),
        (prem_col,      8, 1),
        ('3M超额(均值)', 15, 1),
        ('6M超额(均值)', 15, 1),
        ('1Y超额(均值)', 15, 2),
        ('综合超额',     8, 1),
        ('1Y最高溢价',   8, 1),
        ('1Y净值',       7, 1),
        ('1Y价格',       7, 1),
        ('>7%天',        5, 0),
        ('分值',         5, 0),
        ('推荐',         9, 0),
    ]

    def fmt_row(cells, is_header=False):
        """用管道分隔各列，每列内容左对齐"""
        parts = []
        for val, (_, w, extra) in zip(cells, cols):
            if is_header:
                parts.append(' ' + pad(val, w + extra) + ' ')
            else:
                parts.append(' ' + pad(val, w) + ' ')
        return '|' + '|'.join(parts) + '|'

    # 表头（带CJK补偿）
    headers = [name for name, _, _ in cols]
    print(fmt_row(headers, is_header=True))

    # 分隔线（纯ASCII，与数据行完美对齐）
    sep = '|' + '|'.join('-' * (w + 2) for _, w, _ in cols) + '|'
    print(sep)

    # 数据行
    for r in results:
        excess = r['excess_by_period']
        avg = r['avg_by_period']
        col_3m = f"{format_percent(excess.get('3M', 0))}({format_percent(avg.get('3M', 0))})"
        col_6m = f"{format_percent(excess.get('6M', 0))}({format_percent(avg.get('6M', 0))})"
        col_1y = f"{format_percent(excess.get('1Y', 0))}({format_percent(avg.get('1Y', 0))})"

        # 净值列：显示净值和涨跌，如 "1.806 (-0.9%)"
        nav_val = r.get('nav', 0)
        nav_chg = r.get('nav_change', 0)
        if nav_val:
            nav_str = f"{nav_val:.3f} ({nav_chg:+.1f}%)"
        else:
            nav_str = "-"

        cells = [
            r['code'],
            f"{r['price']:.3f}",
            nav_str,
            format_percent(r['change']),
            format_percent(r['display_premium']),
            col_3m,
            col_6m,
            col_1y,
            format_percent(r['composite']),
            format_percent(r.get('1Y_max', 0)),
            format_percent(r.get('nav_return_1y', 0)),
            format_percent(r.get('price_return_1y', 0)),
            f"{r['1Y_gt7']}",
            f"{r['score']:.2f}",
            r['recommendation'],
        ]
        print(fmt_row(cells))

    if insufficient_data:
        print(f"\n  * 数据不足暂未纳入: {', '.join(insufficient_data)}")

    cfg = INDEX_CONFIG.get(index_type, {})
    nav_label = cfg.get('nav_label', '美股收盘')
    if results and results[0].get('nav_date'):
        nav_date_str = results[0]['nav_date'][-5:]
        nav_dt = datetime.strptime(nav_date_str, '%m-%d')
        print(f"> 净值日期: {nav_dt.strftime('%-m/%-d')}（{nav_label}）")

    futures_ratio = ft_info.get('futures_ratio', 0)
    nav_date_close = ft_info.get('nav_date_close', 0)
    current_futures_price = ft_info.get('current_futures_price', 0)
    if futures_ratio and nav_date_close and current_futures_price and index_type in INDEX_CONFIG:
        ratio_pct = (futures_ratio - 1) * 100
        if cfg.get('use_index'):
            idx_name = cfg['name_cn']
            print(f"> {idx_name}指数估算: {current_futures_price:.0f} / {nav_date_close:.0f} = {ratio_pct:+.2f}%")
            # 日经：未开盘时补充期货估算
            if index_type == 'NIKKEI':
                hour = datetime.now().hour
                if hour < 8 or hour >= 14:
                    nk_ft = get_futures_from_db('NK')
                    if nk_ft and nav_date_close:
                        ft_ratio = (nk_ft / nav_date_close - 1) * 100
                        print(f"> NK期货估算: {nk_ft:.0f} / {nav_date_close:.0f} = {ft_ratio:+.2f}% (日经未开盘)")
        else:
            ft_name = cfg['symbol']
            print(f"> {ft_name}期货修正: {current_futures_price:.0f} / {nav_date_close:.0f} = {ratio_pct:+.2f}%")

    print(f"\n  按分值排序（越高=越推荐）  分值 = 溢价偏离历史均值 + 同类跟踪质量 + 板块溢价特征")
    print()


def print_actionable_summary(all_results: Dict[str, List[Dict]], holdings: List[str]):
    """打印简洁的每日推荐"""
    today = datetime.now().strftime('%Y-%m-%d')

    print(f"\n{'=' * 65}")
    print(f"  今日推荐 ({today})")
    print(f"{'=' * 65}")

    for idx_type, results in all_results.items():
        if not results:
            continue
        cfg = INDEX_CONFIG.get(idx_type, {})
        index_name = cfg.get('name_cn', idx_type)

        best = results[0]  # 已按分值降序排列（最高优先）

        print(f"\n  {index_name}推荐持有: {best['code']} ({best['name']})")
        print(f"  分值: {best['score']:.2f} | 综合超额: {format_percent(best['composite'])} | "
              f">7%天数: {best['1Y_gt7']}天")

        # 查找用户所有持仓（支持同指数多只）
        held_list = [r for r in results if r['code'] in holdings]

        if held_list:
            for i, held in enumerate(held_list):
                is_last = (i == len(held_list) - 1)
                prefix = "└─" if is_last else "├─"

                if held['code'] == best['code']:
                    print(f"  {prefix} {held['code']} 已是最优ETF，继续持有 ✅")
                else:
                    excess_diff = held['composite'] - best['composite']

                    print(f"  ├─ 你持有: {held['code']} ({held['name']})  "
                          f"综合超额: {format_percent(held['composite'])}")

                    if excess_diff > 0.8:
                        print(f"  {prefix} 建议: 换仓到 {best['code']}（超额差 {format_percent(excess_diff)}）✅✅")
                    elif excess_diff > 0.3:
                        print(f"  {prefix} 建议: 可以考虑换仓（超额差 {format_percent(excess_diff)}）")
                    else:
                        print(f"  {prefix} 建议: 继续持有（差距小）")

    if not holdings:
        print(f"\n  提示: 使用 --holding 513100 159655 获取个性化换仓建议")

    print(f"\n{'=' * 65}")


def get_futures_from_db(symbol: str) -> float:
    """从DB获取最新的期货价格"""
    col_map = {'NQ': 'nq_close', 'ES': 'es_close', 'YM': 'ym_close', 'NK': 'nk_close'}
    col = col_map.get(symbol)
    if not col:
        return 0
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT {col} FROM futures_data WHERE {col} IS NOT NULL ORDER BY date DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return float(row[0]) if row and row[0] else 0


def _get_nikkei_futures_ratio(ft_info: Dict) -> dict:
    """获取NK期货的比值（用于日经footer对比显示）"""
    nav_date = ft_info.get('nav_date')
    if not nav_date:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    # nav_date 的 NK 期货收盘
    next_date = (datetime.strptime(nav_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    cursor.execute("SELECT nk_prev_close FROM futures_data WHERE us_date = ?", (next_date,))
    row = cursor.fetchone()
    nav_date_nk = float(row[0]) if row and row[0] else 0
    if not nav_date_nk:
        cursor.execute("SELECT nk_close FROM futures_data WHERE us_date = ?", (nav_date,))
        row = cursor.fetchone()
        nav_date_nk = float(row[0]) if row and row[0] else 0
    # 当前 NK 期货
    cursor.execute("SELECT nk_close FROM futures_data ORDER BY date DESC LIMIT 1")
    row = cursor.fetchone()
    current_nk = float(row[0]) if row and row[0] else 0
    conn.close()
    if nav_date_nk and current_nk:
        return {'nav_date': nav_date_nk, 'current': current_nk,
                'pct': (current_nk / nav_date_nk - 1) * 100}
    return None


def generate_md_table(index_type: str, results: List[Dict], insufficient_data: List[str] = None,
                      ft_info: Dict = None) -> str:
    """生成markdown格式的分析表格"""
    if not results:
        return ""

    ft_info = ft_info or {}
    futures_ratio = ft_info.get('futures_ratio', 0)
    futures_display = ft_info.get('futures_display', [])

    cfg = INDEX_CONFIG.get(index_type, {})
    index_name = cfg.get('name_cn', index_type)
    has_correction = futures_ratio and abs(futures_ratio - 1) > 0.0001
    prem_col = "估算溢价" if has_correction else "当前溢价"
    lines = []
    lines.append(f"## {index_name} ETF 分析\n")

    # 表头
    lines.append(f"| 代码 | 价格 | 净值 | 涨幅 | {prem_col} | 3M超额(均值) | 6M超额(均值) | 1Y超额(均值) | 综合超额 | 1Y最高溢价 | 1Y净值 | 1Y价格 | >7%天 | 分值 | 推荐 |")
    lines.append("|------|------|------|------|------|----------|----------|----------|----------|----------|--------|--------|-------|------|------|")

    for r in results:
        excess = r['excess_by_period']
        avg = r['avg_by_period']
        col_3m = f"{format_percent(excess.get('3M', 0))}({format_percent(avg.get('3M', 0))})"
        col_6m = f"{format_percent(excess.get('6M', 0))}({format_percent(avg.get('6M', 0))})"
        col_1y = f"{format_percent(excess.get('1Y', 0))}({format_percent(avg.get('1Y', 0))})"

        # 净值列：显示净值和涨跌，如 "1.806 (-0.90%)"
        nav_val = r.get('nav', 0)
        nav_chg = r.get('nav_change', 0)
        if nav_val:
            nav_str = f"{nav_val:.3f} ({nav_chg:+.2f}%)"
        else:
            nav_str = "-"

        lines.append(
            f"| {r['code']} "
            f"| {r['price']:.3f} "
            f"| {nav_str} "
            f"| {format_percent(r['change'])} "
            f"| {format_percent(r['display_premium'])} "
            f"| {col_3m} "
            f"| {col_6m} "
            f"| {col_1y} "
            f"| {format_percent(r['composite'])} "
            f"| {format_percent(r.get('1Y_max', 0))} "
            f"| {format_percent(r.get('nav_return_1y', 0))} "
            f"| {format_percent(r.get('price_return_1y', 0))} "
            f"| {r['1Y_gt7']} "
            f"| {r['score']:.2f} "
            f"| {r['recommendation']} |"
        )

    if insufficient_data:
        lines.append(f"\n> 数据不足暂未纳入: {', '.join(insufficient_data)}")

    # 净值日期说明（取第一个ETF的净值日期）
    # nav_date 现在是净值实际日期(美股收盘日)，直接使用无需减1天
    cfg = INDEX_CONFIG.get(index_type, {})
    nav_label = cfg.get('nav_label', '美股收盘')
    if results and results[0].get('nav_date'):
        nav_date_str = results[0]['nav_date'][-5:]
        nav_dt = datetime.strptime(nav_date_str, '%m-%d')
        lines.append(f"> 净值日期: {nav_dt.strftime('%-m/%-d')}（{nav_label}）")

    futures_ratio = ft_info.get('futures_ratio', 0)
    nav_date_close = ft_info.get('nav_date_close', 0)
    current_futures_price = ft_info.get('current_futures_price', 0)
    if futures_ratio and nav_date_close and current_futures_price and index_type in INDEX_CONFIG:
        ratio_pct = (futures_ratio - 1) * 100
        if cfg.get('use_index'):
            idx_name = cfg['name_cn']
            lines.append(f"> {idx_name}指数估算: {current_futures_price:.0f} / {nav_date_close:.0f} = **{ratio_pct:+.2f}%**")
            if index_type == 'NIKKEI':
                hour = datetime.now().hour
                if hour < 8 or hour >= 14:
                    nk_ft = get_futures_from_db('NK')
                    if nk_ft and nav_date_close:
                        ft_ratio = (nk_ft / nav_date_close - 1) * 100
                        lines.append(f"> NK期货估算: {nk_ft:.0f} / {nav_date_close:.0f} = **{ft_ratio:+.2f}%** (日经未开盘)")
        else:
            ft_name = cfg['symbol']
            lines.append(f"> {ft_name}期货修正: {current_futures_price:.0f} / {nav_date_close:.0f} = **{ratio_pct:+.2f}%**")

    lines.append("")

    return "\n".join(lines)


def md_to_html(md_text: str, title: str, gen_time: str = None) -> str:
    """将 markdown 报告转为 HTML（支持表格、标题、引用）"""
    import re
    html_lines = []
    in_table = False

    for line in md_text.split('\n'):
        stripped = line.strip()

        # 跳过分隔行
        if re.match(r'^\|[-:|\s]+\|$', stripped):
            continue

        # 表格行
        if stripped.startswith('|') and stripped.endswith('|'):
            cells = [c.strip() for c in stripped.strip('|').split('|')]
            if not in_table:
                in_table = True
                html_lines.append('<table>')
                html_lines.append('<tr>' + ''.join(f'<th>{c}</th>' for c in cells) + '</tr>')
            else:
                # 高亮推荐行
                row_class = ''
                row_text = ' '.join(cells)
                if '✅✅✅' in row_text:
                    row_class = ' class="top"'
                elif '✅✅' in row_text:
                    row_class = ' class="good"'
                html_lines.append(f'<tr{row_class}>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>')
            continue

        if in_table:
            in_table = False
            html_lines.append('</table>')

        # 标题
        if stripped.startswith('# '):
            html_lines.append(f'<h1>{stripped[2:]}</h1>')
        elif stripped.startswith('## '):
            html_lines.append(f'<h2>{stripped[3:]}</h2>')
        # 引用
        elif stripped.startswith('> '):
            html_lines.append(f'<p class="note">{stripped[2:]}</p>')
        # 列表
        elif stripped.startswith('- '):
            content = stripped[2:]
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
            html_lines.append(f'<p class="rec">{content}</p>')
        elif stripped:
            html_lines.append(f'<p>{stripped}</p>')

    if in_table:
        html_lines.append('</table>')

    body = '\n'.join(html_lines)
    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>ETF分析 {title}</title>
<style>
  body {{ font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; max-width: 1100px; margin: 20px auto; padding: 0 16px; background: #f8f9fa; color: #333; }}
  h1 {{ color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 8px; }}
  h2 {{ color: #333; margin-top: 24px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13px; }}
  th {{ background: #1a73e8; color: #fff; padding: 8px 6px; text-align: center; white-space: nowrap; }}
  td {{ padding: 6px; text-align: center; border-bottom: 1px solid #e0e0e0; white-space: nowrap; }}
  tr:hover {{ background: #e8f0fe; }}
  tr.top {{ background: #e6f4ea; font-weight: bold; }}
  tr.good {{ background: #fef7e0; }}
  .note {{ color: #666; font-size: 12px; margin: 4px 0; padding-left: 12px; border-left: 3px solid #dadce0; }}
  .rec {{ font-size: 15px; margin: 6px 0; }}
</style>
</head>
<body>
{body}
<p class="note">生成时间: {gen_time or datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</body>
</html>"""


def capture_table_screenshots(html_path: Path, output_dir: Path) -> Tuple[str, str]:
    """使用 Chrome headless 截取 HTML 中的表格图片。

    返回: (nasdaq_png_path, sp500_png_path) 相对于 output_dir 的路径
    """
    import re

    output_dir.mkdir(parents=True, exist_ok=True)
    html_content = html_path.read_text(encoding='utf-8')

    # 提取 style 部分和表格部分
    style_match = re.search(r'<style>(.*?)</style>', html_content, re.DOTALL)
    style_css = style_match.group(1) if style_match else ""

    # 找到两个表格（仅 <table>，不含 <h2> 标题）
    tables = []
    for match in re.finditer(r'<h2[^>]*>([^<]*ETF[^<]*)</h2>\s*(<table>.*?</table>)', html_content, re.DOTALL):
        tables.append({
            'name': match.group(1).strip(),
            'html': match.group(2)  # 只取 <table>，不含 <h2>
        })

    if len(tables) < 2:
        print("警告: 未找到两个表格")
        return None, None

    nasdaq_png = None
    sp500_png = None

    for table_info in tables:
        name = table_info['name']
        table_html = table_info['html']

        # 创建完整的 HTML 文件，保留原始样式
        full_html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<style>
{style_css}
  body {{ margin: 0; padding: 8px; background: #fff; max-width: none; }}
  table {{ font-size: 15px; }}
  th, td {{ padding: 6px 10px; }}
</style>
</head>
<body>
{table_html}
</body>
</html>"""

        # 保存临时 HTML 文件
        temp_html = output_dir / f"temp_{name.replace(' ', '_')}.html"
        temp_html.write_text(full_html, encoding='utf-8')

        # 使用 Chrome 截图
        png_name = "table_nasdaq.png" if "纳指" in name else "table_sp500.png"
        png_path = output_dir / png_name

        chrome_cmd = [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '--headless',
            '--disable-gpu',
            '--force-device-scale-factor=2',
            '--window-size=1400,600',
            f'--screenshot={png_path}',
            str(temp_html)
        ]

        try:
            subprocess.run(chrome_cmd, capture_output=True, timeout=15)
            temp_html.unlink()

            # 自动裁剪白边
            try:
                from PIL import Image, ImageChops
                img = Image.open(png_path)
                bg = Image.new(img.mode, img.size, (255, 255, 255))
                diff = ImageChops.difference(img, bg)
                bbox = diff.getbbox()
                if bbox:
                    # 四周留 8px 边距
                    pad = 8
                    bbox = (max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                            min(img.width, bbox[2] + pad), min(img.height, bbox[3] + pad))
                    img.crop(bbox).save(png_path)
            except Exception:
                pass  # 裁剪失败不影响截图

            print(f"表格截图: {png_path}")

            if "纳指" in name:
                nasdaq_png = png_name
            else:
                sp500_png = png_name
        except Exception as e:
            print(f"截图失败: {e}")
            if temp_html.exists():
                temp_html.unlink()

    return nasdaq_png, sp500_png


def generate_wechat_html(md_text: str, title: str, nasdaq_png: str, sp500_png: str, gen_time: str = None) -> str:
    """生成微信公众号版本的 HTML，表格用图片替代。"""
    import re

    lines = []
    in_table = False
    current_section = None

    for line in md_text.split('\n'):
        stripped = line.strip()

        # 检测 ## 标题
        if stripped.startswith('## '):
            current_section = stripped[3:].strip()
            lines.append(f'<h2 style="font-size: 17px; color: #333; font-weight: bold; margin: 20px 0 8px 0;">{current_section}</h2>')
            continue

        # 跳过表格内容
        if stripped.startswith('|'):
            if not in_table:
                in_table = True
                # 插入图片
                if "纳指" in current_section and nasdaq_png:
                    lines.append(f'<img src="{nasdaq_png}" style="max-width: 100%; height: auto; margin: 8px 0;" />')
                elif "标普" in current_section and sp500_png:
                    lines.append(f'<img src="{sp500_png}" style="max-width: 100%; height: auto; margin: 8px 0;" />')
            continue

        # 表格结束
        if in_table and not stripped.startswith('|'):
            in_table = False

        # 非表格内容
        if not in_table:
            # 标题
            if stripped.startswith('# '):
                content = stripped[2:]
                lines.append(f'<h1 style="font-size: 20px; color: #1a73e8; font-weight: bold; line-height: 1.4; margin: 0.8em 0 0.5em 0; padding-bottom: 0.3em; border-bottom: 2px solid #1a73e8;">{content}</h1>')
            # 引用
            elif stripped.startswith('> '):
                content = stripped[2:]
                content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
                lines.append(f'<p style="color: #666; font-size: 12px; margin: 4px 0; padding-left: 12px; border-left: 3px solid #dadce0; line-height: 1.6;">{content}</p>')
            # 列表项（缩进 + 圆点）
            elif stripped.startswith('- '):
                content = stripped[2:]
                content = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color: #1a73e8;">\1</strong>', content)
                lines.append(f'<p style="font-size: 14px; margin: 4px 0 4px 16px; padding-left: 10px; border-left: 2px solid #1a73e8; line-height: 1.6; color: #333;">{content}</p>')
            # **标签**: 内容（评估小节标题）
            elif re.match(r'^\*\*.+?\*\*', stripped):
                content = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color: #1a73e8; font-size: 15px;">\1</strong>', stripped)
                lines.append(f'<p style="font-size: 14px; margin: 12px 0 4px 0; line-height: 1.6;">{content}</p>')
            elif stripped:
                content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped)
                lines.append(f'<p style="font-size: 14px; margin: 4px 0; line-height: 1.6;">{content}</p>')

    body = '\n'.join(lines)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ETF溢价分析报告 {title} - 微信预览</title>
<style>
  body {{
    margin: 0;
    padding: 0;
    background: #f0f0f0;
    display: flex;
    justify-content: center;
  }}
  .phone-frame {{
    width: 375px;
    min-height: 100vh;
    background: #fff;
    box-shadow: 0 0 20px rgba(0,0,0,0.1);
    margin: 20px 0;
  }}
  .wechat-header {{
    background: #ededed;
    padding: 10px 16px;
    font-size: 13px;
    color: #999;
    text-align: center;
    border-bottom: 1px solid #ddd;
  }}
  .wechat-title {{
    padding: 20px 16px 10px;
    font-size: 22px;
    font-weight: bold;
    color: #111;
    line-height: 1.4;
  }}
  .wechat-meta {{
    padding: 0 16px 15px;
    font-size: 12px;
    color: #999;
  }}
  .wechat-content {{
    padding: 0 16px 20px;
  }}
</style>
</head>
<body>
<div class="phone-frame">
  <div class="wechat-header">微信公众号预览</div>
  <div class="wechat-title">ETF溢价分析报告 {title}</div>
  <div class="wechat-meta">千里</div>
  <div class="wechat-content">
{body}
<p style="color: #666; font-size: 12px; margin: 8px 0 4px 0; padding-left: 12px; border-left: 3px solid #dadce0; line-height: 1.6;">生成时间: {gen_time or datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
<p style="color: #999; font-size: 11px; margin: 16px 0 0 0; text-align: center;">以上是大模型瞎分析，不要参考，不构成投资建议。</p>
  </div>
</div>
</body>
</html>"""


def generate_cover_image(output_path: Path, date_str: str,
                         top_nasdaq: Dict = None, top_sp500: Dict = None,
                         nq_ft: Dict = None, es_ft: Dict = None) -> Path:
    """生成微信封面图（900x383px，深蓝渐变背景 + 当日数据）"""
    from PIL import Image, ImageDraw, ImageFont

    W, H = 900, 383
    img = Image.new('RGB', (W, H))
    draw = ImageDraw.Draw(img)

    # 渐变背景：深蓝 → 深青
    for y in range(H):
        r = int(15 + (25 - 15) * y / H)
        g = int(32 + (60 - 32) * y / H)
        b = int(80 + (120 - 80) * y / H)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # 装饰线条
    draw.line([(40, 70), (860, 70)], fill=(80, 140, 220), width=2)
    draw.line([(40, 310), (860, 310)], fill=(80, 140, 220), width=2)

    # 字体
    font_path = '/System/Library/Fonts/STHeiti Medium.ttc'
    font_title = ImageFont.truetype(font_path, 38)
    font_date = ImageFont.truetype(font_path, 24)
    font_data = ImageFont.truetype(font_path, 28)
    font_small = ImageFont.truetype(font_path, 20)

    white = (240, 240, 245)
    accent = (100, 180, 255)
    green = (80, 210, 150)

    # 标题行
    draw.text((50, 22), "ETF 溢价分析", fill=white, font=font_title)
    draw.text((720, 30), date_str, fill=accent, font=font_date)

    # 纳指数据
    y_base = 90
    if top_nasdaq:
        draw.text((50, y_base), "纳指首选", fill=accent, font=font_small)
        draw.text((170, y_base - 5), top_nasdaq['code'], fill=white, font=font_data)
        draw.text((340, y_base), f"分值 {top_nasdaq['score']:.2f}", fill=green, font=font_data)
        draw.text((560, y_base), f"溢价 {top_nasdaq.get('display_premium', 0):+.2f}%", fill=white, font=font_small)

    # 标普数据
    y_base = 145
    if top_sp500:
        draw.text((50, y_base), "标普首选", fill=accent, font=font_small)
        draw.text((170, y_base - 5), top_sp500['code'], fill=white, font=font_data)
        draw.text((340, y_base), f"分值 {top_sp500['score']:.2f}", fill=green, font=font_data)
        draw.text((560, y_base), f"溢价 {top_sp500.get('display_premium', 0):+.2f}%", fill=white, font=font_small)

    # 期货数据（取最近一天的涨跌幅）
    y_base = 220
    nq_change = nq_ft['detail'][-1][1] if nq_ft and nq_ft.get('detail') else None
    es_change = es_ft['detail'][-1][1] if es_ft and es_ft.get('detail') else None
    if nq_change is not None:
        color = green if nq_change >= 0 else (255, 100, 100)
        draw.text((50, y_base), "NQ", fill=accent, font=font_small)
        draw.text((100, y_base - 3), f"{nq_change:+.2f}%", fill=color, font=font_data)
    if es_change is not None:
        color = green if es_change >= 0 else (255, 100, 100)
        draw.text((280, y_base), "ES", fill=accent, font=font_small)
        draw.text((330, y_base - 3), f"{es_change:+.2f}%", fill=color, font=font_data)

    # 底部标识
    draw.text((50, 330), "千里 · 每日报告", fill=(120, 140, 170), font=font_small)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), quality=92)
    return output_path


def save_md_report(nasdaq_results: List[Dict], sp500_results: List[Dict], dow_results: List[Dict] = None,
                   nasdaq_insufficient: List[str] = None, sp500_insufficient: List[str] = None,
                   dow_insufficient: List[str] = None,
                   holdings: List[str] = None, nq_ft: Dict = None, es_ft: Dict = None, ym_ft: Dict = None,
                   nikkei_results: List[Dict] = None, nikkei_insufficient: List[str] = None, nk_ft: Dict = None,
                   dax_results: List[Dict] = None, dax_insufficient: List[str] = None, dax_ft: Dict = None,
                   others_results: List[Dict] = None, others_insufficient: List[str] = None,
                   lof_results: List[Dict] = None, lof_insufficient: List[str] = None):
    """保存分析报告为markdown文件"""
    # 使用当前时间作为报告生成时间（而非数据采集时间）
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    timestamp = now.strftime('%Y%m%d')
    gen_time = now.strftime('%Y-%m-%d %H:%M')

    report_dir = PROJECT_ROOT / "reports"
    report_dir.mkdir(exist_ok=True)

    lines = []
    lines.append(f"# ETF溢价分析报告 {today}\n")

    # 期货行情 + 数据状态
    futures = get_futures_info()
    futures_lines = format_futures_display(futures)
    for fl in futures_lines:
        lines.append(f"> {fl}")

    freshness = detect_data_freshness()
    if freshness:
        lines.append(f"> 数据状态: {freshness}")
    lines.append("")

    # 纳指表格
    lines.append(generate_md_table('NASDAQ', nasdaq_results, nasdaq_insufficient, nq_ft))

    # 标普表格
    lines.append(generate_md_table('SP500', sp500_results, sp500_insufficient, es_ft))

    # 道琼斯表格（如果有数据）
    if dow_results:
        lines.append(generate_md_table('DOW', dow_results, dow_insufficient, ym_ft))

    # 德国DAX表格
    if dax_results:
        lines.append(generate_md_table('DAX', dax_results, dax_insufficient, dax_ft))

    # 日经225表格
    if nikkei_results:
        lines.append(generate_md_table('NIKKEI', nikkei_results, nikkei_insufficient, nk_ft))

    # 其他表格
    if others_results:
        lines.append(generate_md_table('OTHERS', others_results, others_insufficient))

    # LOF表格
    if lof_results:
        lines.append(generate_md_table('LOF', lof_results, lof_insufficient))

    # 公式说明（合并，仅出现一次）
    lines.append(f"> 格式: 超额溢价(历史均值)  按分值排序（越高=越推荐）")
    lines.append(f"> 综合超额 = 1M×35% + 3M×25% + 6M×20% + 1Y×10% + ALL×10%")
    lines.append(f"> 分值 = 溢价偏离历史溢价均值 + 同类跟踪质量差异 + 板块历史溢价水平")
    lines.append(f"> 分值越高，当前溢价越低于历史水平。仅反映溢价位置，不预测板块涨跌。")

    # LLM 评估已移至独立 skill（etf-evaluator），生成 {timestamp}_llm.md 文件
    # 使用 "LLM评估" 或 "评估ETF报告" 触发 etf-evaluator skill

    filepath = report_dir / f"analysis_{timestamp}.md"
    filepath.write_text("\n".join(lines), encoding='utf-8')
    print(f"\n报告已保存: {filepath.resolve()}")

    # 生成 HTML 并用浏览器打开
    html_path = report_dir / f"analysis_{timestamp}.html"
    html_content = md_to_html("\n".join(lines), today, gen_time)
    html_path.write_text(html_content, encoding='utf-8')
    print(f"HTML报告: {html_path.resolve()}")
    subprocess.Popen(['open', str(html_path)])

    # ========== 生成微信公众号版本 ==========
    wechat_dir = PROJECT_ROOT.resolve().parent / "wechat-publisher" / "articles" / f"etf-daily-{timestamp}"
    wechat_dir.mkdir(parents=True, exist_ok=True)

    # 截取表格图片
    nasdaq_png, sp500_png = capture_table_screenshots(html_path, wechat_dir)

    if nasdaq_png and sp500_png:
        # 生成微信 HTML
        wechat_html = generate_wechat_html("\n".join(lines), today, nasdaq_png, sp500_png, gen_time)
        wechat_html_path = wechat_dir / "preview.html"
        wechat_html_path.write_text(wechat_html, encoding='utf-8')
        print(f"微信预览: {wechat_html_path.resolve()}")

        # 同时保存到 reports 目录（截图按日期归档）
        import shutil
        img_dir = report_dir / "img" / timestamp
        img_dir.mkdir(parents=True, exist_ok=True)
        for png_name in [nasdaq_png, sp500_png]:
            src = wechat_dir / png_name
            dst = img_dir / png_name
            if src.exists():
                shutil.copy2(src, dst)

        # reports 版预览 HTML：图片路径指向 img/{date}/ 子目录
        reports_nasdaq = f"img/{timestamp}/{nasdaq_png}"
        reports_sp500 = f"img/{timestamp}/{sp500_png}"
        reports_preview_html = generate_wechat_html("\n".join(lines), today, reports_nasdaq, reports_sp500, gen_time)
        preview_in_reports = report_dir / f"analysis_preview_{timestamp}.html"
        preview_in_reports.write_text(reports_preview_html, encoding='utf-8')
        print(f"预览版本: {preview_in_reports.resolve()}")
    else:
        print("警告: 表格截图失败，未生成微信预览")

    # ========== 生成封面图 ==========
    try:
        cover_path = generate_cover_image(
            wechat_dir / "cover.jpg", today,
            nasdaq_results[0] if nasdaq_results else None,
            sp500_results[0] if sp500_results else None,
            nq_ft, es_ft
        )
        if cover_path:
            print(f"封面图: {cover_path}")
    except Exception as e:
        print(f"封面图: 生成失败（{e}）")

    # ========== 自动加入微信草稿箱 ==========
    wechat_api = PROJECT_ROOT.resolve().parent / "wechat-publisher" / "scripts" / "wechat_api.py"
    if wechat_dir.exists() and wechat_api.exists():
        # 检查是否存在 LLM 评估文件
        llm_md_path = report_dir / f"analysis_{timestamp}_llm.md"

        # 准备摘要
        top1_nq = nasdaq_results[0] if nasdaq_results else None
        top1_sp = sp500_results[0] if sp500_results else None
        parts = []
        if top1_nq:
            parts.append(f"纳指首选{top1_nq['code']}(分值{top1_nq['score']:.2f})")
        if top1_sp:
            parts.append(f"标普首选{top1_sp['code']}(分值{top1_sp['score']:.2f})")
        digest = "，".join(parts) + "，当前溢价均低于历史均值，买入窗口开放。"

        if llm_md_path.exists():
            # LLM 评估 + 完整数据表（合并发布）
            llm_content = llm_md_path.read_text(encoding='utf-8')

            # 组合：LLM评估 + 分隔线 + 主报告（从"纳指ETF 分析"开始）
            main_report_start = False
            combined_lines = [llm_content.strip(), "", "", "---", "", ""]
            for line in lines:
                if line.startswith("## 纳指ETF 分析"):
                    main_report_start = True
                if main_report_start:
                    combined_lines.append(line)

            combined_content = "\n".join(combined_lines)

            # 生成合并后的微信 HTML（包含表格截图）
            combined_html = generate_wechat_html(combined_content, today, nasdaq_png, sp500_png, gen_time)
            preview_path = wechat_dir / "preview.html"
            preview_path.write_text(combined_html, encoding='utf-8')

            # 写入完整的 article.md（包含正文内容），方便手动更新
            article_md = wechat_dir / "article.md"
            article_content = f'''---
title: "ETF溢价分析报告 {today}"
author: "千里"
digest: "{digest}"
---

{combined_content}
'''
            article_md.write_text(article_content, encoding='utf-8')
            print("微信草稿: LLM评估 + 完整数据表")
        else:
            # 仅完整数据报告（无 LLM 评估）
            article_md = wechat_dir / "article.md"
            article_content = f'''---
title: "ETF溢价分析报告 {today}"
author: "千里"
digest: "{digest}"
---

{chr(10).join(lines)}
'''
            article_md.write_text(article_content, encoding='utf-8')
            print("微信草稿: 完整数据报告（无 LLM 评估）")

        try:
            result = subprocess.run(
                [sys.executable, str(wechat_api), 'publish', str(wechat_dir), '--draft-only'],
                capture_output=True, text=True, timeout=60
            )
            if '草稿创建成功' in result.stdout or '草稿创建成功' in result.stderr:
                print("微信草稿: 已加入草稿箱")
            else:
                output = result.stdout + result.stderr
                print(f"微信草稿: 提交失败 — {output.strip()[-100:]}")
        except Exception as e:
            print(f"微信草稿: 跳过（{e}）")

    return filepath


def format_futures_display(futures_list: List[Dict]) -> List[str]:
    """格式化期货行情显示（3天数据）"""
    if not futures_list:
        return []

    lines = []
    for entry in futures_list:
        parts = []
        if entry.get('nq_price') is not None:
            chg = entry.get('nq_change', 0) or 0
            parts.append(f"NQ {entry['nq_price']:.0f} ({chg:+.2f}%)")
        if entry.get('es_price') is not None:
            chg = entry.get('es_change', 0) or 0
            parts.append(f"ES {entry['es_price']:.0f} ({chg:+.2f}%)")
        if entry.get('ym_price') is not None:
            chg = entry.get('ym_change', 0) or 0
            parts.append(f"YM {entry['ym_price']:.0f} ({chg:+.2f}%)")
        if entry.get('nk_price') is not None:
            chg = entry.get('nk_change', 0) or 0
            parts.append(f"NK {entry['nk_price']:.0f} ({chg:+.2f}%)")
        if parts:
            lines.append(f"期货 {entry['date']}: {' | '.join(parts)}")

    return lines


def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(description='ETF推荐分析（基于涨幅偏离）')
    parser.add_argument('--holding', nargs='*', default=[],
                        help='当前持仓ETF代码，如: --holding 513100 159655')
    parser.add_argument('--server', action='store_true',
                        help='Server模式: 仅输出report.json，跳过HTML/PNG/Chrome/微信')
    args = parser.parse_args()

    # 所有支持的指数类型
    INDEX_TYPES = ['NASDAQ', 'SP500', 'DAX', 'NIKKEI', 'LOF', 'OTHERS']

    # 分析各指数ETF
    all_results = {}
    all_insufficient = {}
    all_ft_info = {}
    for idx_type in INDEX_TYPES:
        results, insufficient, ft_info = analyze_etfs(idx_type)
        all_results[idx_type] = results
        all_insufficient[idx_type] = insufficient
        all_ft_info[idx_type] = ft_info

    # Server模式: 输出JSON + HTML，无控制台输出
    if args.server:
        nasdaq_results = all_results.get('NASDAQ', [])
        sp500_results = all_results.get('SP500', [])
        nikkei_results = all_results.get('NIKKEI', [])
        dax_results = all_results.get('DAX', [])
        others_results = all_results.get('OTHERS', [])
        lof_results = all_results.get('LOF', [])
        nasdaq_insufficient = all_insufficient.get('NASDAQ', [])
        sp500_insufficient = all_insufficient.get('SP500', [])
        nikkei_insufficient = all_insufficient.get('NIKKEI', [])
        dax_insufficient = all_insufficient.get('DAX', [])
        others_insufficient = all_insufficient.get('OTHERS', [])
        lof_insufficient = all_insufficient.get('LOF', [])
        generate_report_json(nasdaq_results, sp500_results,
                             nasdaq_insufficient, sp500_insufficient,
                             nq_ft=all_ft_info.get('NASDAQ'),
                             es_ft=all_ft_info.get('SP500'),
                             nikkei_results=nikkei_results,
                             nikkei_insufficient=nikkei_insufficient,
                             nk_ft=all_ft_info.get('NIKKEI'),
                             dax_results=dax_results,
                             dax_insufficient=dax_insufficient,
                             dax_ft=all_ft_info.get('DAX'),
                             others_results=others_results,
                             others_insufficient=others_insufficient,
                             others_ft=all_ft_info.get('OTHERS'),
                             lof_results=lof_results,
                             lof_insufficient=lof_insufficient,
                             lof_ft=all_ft_info.get('LOF'))
        # 同时生成 HTML 供 web 展示
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        gen_time = now.strftime('%Y-%m-%d %H:%M')
        lines = []
        lines.append(f"# ETF溢价分析报告 {today}\n")
        futures = get_futures_info()
        for fl in format_futures_display(futures):
            lines.append(f"> {fl}")
        freshness = detect_data_freshness()
        if freshness:
            lines.append(f"> 数据状态: {freshness}")
        lines.append("")
        for idx_type in INDEX_TYPES:
            idx_results = all_results.get(idx_type, [])
            if idx_results:
                lines.append(generate_md_table(idx_type, idx_results, all_insufficient.get(idx_type, []), all_ft_info.get(idx_type)))
        lines.append(f"> 分值 = 溢价偏离历史溢价均值 + 同类跟踪质量差异 + 板块历史溢价水平")
        lines.append(f"> 分值越高，当前溢价越低于历史水平。仅反映溢价位置，不预测板块涨跌。")
        html_content = md_to_html("\n".join(lines), today, gen_time)
        # 注入刷新栏 + 变化箭头脚本
        inject = r'''<div id="rfbar" style="position:fixed;top:0;left:0;right:0;background:#1a73e8;color:#fff;padding:8px 16px;display:flex;align-items:center;gap:12px;z-index:999;font-size:14px;">
<button onclick="location.reload()" style="background:#fff;color:#1a73e8;border:none;padding:6px 16px;border-radius:4px;cursor:pointer;font-weight:bold;">刷新数据</button>
<span id="rfst">数据每分钟自动更新 (交易时段)</span>
</div>
<style>
body{padding-top:48px !important;}
.arrow-up{color:#e53935;font-size:10px;margin-left:2px;vertical-align:super;}
.arrow-down{color:#43a047;font-size:10px;margin-left:2px;vertical-align:super;}
td.changed{transition:background .5s;background:#fff9c4 !important;}
</style>
<script>
(function(){
  var TRACK=['价格','净值','涨幅','估算溢价','分值'];
  var KEY_VAL='etf_prev',KEY_ARR='etf_arrows';
  var tables=document.querySelectorAll('table'),cur={};
  var cellMap={};
  tables.forEach(function(t,ti){
    var rows=t.querySelectorAll('tr');
    if(rows.length<2)return;
    var hdrs=[];
    rows[0].querySelectorAll('th').forEach(function(h){hdrs.push(h.textContent.trim());});
    for(var r=1;r<rows.length;r++){
      var cells=rows[r].querySelectorAll('td');
      if(!cells.length)continue;
      var code=cells[0].textContent.trim();
      for(var c=1;c<cells.length;c++){
        if(TRACK.indexOf(hdrs[c])<0)continue;
        var k=ti+'_'+code+'_'+hdrs[c],v=cells[c].textContent.trim();
        cur[k]=v;
        cellMap[k]=cells[c];
      }
    }
  });
  var prev={};try{prev=JSON.parse(localStorage.getItem(KEY_VAL)||'{}');}catch(e){}
  var savedArrows={};try{savedArrows=JSON.parse(localStorage.getItem(KEY_ARR)||'{}');}catch(e){}
  var arrows={},n=0;
  for(var k in cur){
    if(!(k in prev)){continue;}
    var ov=prev[k],nv=cur[k];
    if(ov===nv){
      if(savedArrows[k])arrows[k]=savedArrows[k];
      continue;
    }
    var on=parseFloat(ov.replace(/[^0-9.\-+]/g,'')),nn=parseFloat(nv.replace(/[^0-9.\-+]/g,''));
    if(isNaN(on)||isNaN(nn))continue;
    arrows[k]=nn>on?'up':'down';
    n++;
  }
  for(var k in arrows){
    if(!cellMap[k])continue;
    var cls=arrows[k]==='up'?'arrow-up':'arrow-down';
    var sym=arrows[k]==='up'?'↑':'↓';
    cellMap[k].innerHTML+='<span class="'+cls+'">'+sym+'</span>';
  }
  localStorage.setItem(KEY_VAL,JSON.stringify(cur));
  localStorage.setItem(KEY_ARR,JSON.stringify(arrows));
  if(n>0)document.getElementById('rfst').textContent=n+' 个数据已变化';
})();
</script>'''
        html_content = html_content.replace("</body>", inject + "\n</body>")
        html_path = PROJECT_ROOT / "data" / "report.html"
        html_path.write_text(html_content, encoding='utf-8')
        return

    print("=" * 85)
    print("ETF推荐分析（基于涨幅偏离）")
    print("=" * 85)

    # 期货行情（两天）
    futures = get_futures_info()
    futures_lines = format_futures_display(futures)
    if futures_lines:
        print()
        for line in futures_lines:
            print(f"  {line}")

    # 数据时效性
    freshness = detect_data_freshness()
    if freshness:
        print(f"  数据状态: {freshness}")

    # 打印各指数结果
    for idx_type in INDEX_TYPES:
        print_results(idx_type, all_results.get(idx_type, []),
                    all_insufficient.get(idx_type, []),
                    all_ft_info.get(idx_type))

    # 今日推荐（简洁汇总）
    print_actionable_summary(all_results, args.holding)

    # 注意事项

    # 保存MD报告
    nasdaq_results = all_results.get('NASDAQ', [])
    sp500_results = all_results.get('SP500', [])
    dax_results = all_results.get('DAX', [])
    nikkei_results = all_results.get('NIKKEI', [])
    others_results = all_results.get('OTHERS', [])
    lof_results = all_results.get('LOF', [])
    nasdaq_insufficient = all_insufficient.get('NASDAQ', [])
    sp500_insufficient = all_insufficient.get('SP500', [])
    dax_insufficient = all_insufficient.get('DAX', [])
    nikkei_insufficient = all_insufficient.get('NIKKEI', [])
    others_insufficient = all_insufficient.get('OTHERS', [])
    lof_insufficient = all_insufficient.get('LOF', [])
    save_md_report(nasdaq_results, sp500_results, None,
                   nasdaq_insufficient, sp500_insufficient, None,
                   args.holding,
                   nq_ft=all_ft_info.get('NASDAQ'),
                   es_ft=all_ft_info.get('SP500'),
                   dax_results=dax_results,
                   dax_insufficient=dax_insufficient,
                   dax_ft=all_ft_info.get('DAX'),
                   nikkei_results=nikkei_results,
                   nikkei_insufficient=nikkei_insufficient,
                   nk_ft=all_ft_info.get('NIKKEI'),
                   others_results=others_results,
                   others_insufficient=others_insufficient,
                   lof_results=lof_results,
                   lof_insufficient=lof_insufficient)
    print()


if __name__ == '__main__':
    main()
