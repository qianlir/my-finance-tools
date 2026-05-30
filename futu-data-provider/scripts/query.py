#!/usr/bin/env python3
"""通用行情查询 CLI — 支持 A 股 / 港股 / 美股，单日或区间查询。

数据源优先级: Futu OpenD → 腾讯财经 API(降级)

用法:
    # 查某只股票某一天
    python3 query.py 000858 --date 2026-05-30

    # 查一段时间
    python3 query.py 000858 --start 2026-01-01 --end 2026-05-30

    # 多只股票
    python3 query.py 000858 09988 513100 --start 2026-05-01

    # 不指定日期 = 最近 20 个交易日
    python3 query.py 000858

    # 输出格式: table(默认) / csv / json
    python3 query.py 000858 --start 2026-01-01 --format csv
"""
import argparse
import csv
import json
import sqlite3
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB_PATH = HERE.parent / 'data' / 'futu_kline.db'
SECTOR_CSV = Path(__file__).resolve().parent.parent.parent / '.claude' / 'skills' / 'portfolio-pnl-analyzer' / 'references' / 'sector-overrides.csv'

# ── 代码转换 ──────────────────────────────────────────────

def code_to_futu(code: str) -> str:
    """纯数字代码 → 富途格式"""
    code = str(code).strip()
    if '.' in code: return code.upper()
    if not code.isdigit(): return ''
    if len(code) == 5: return f'HK.{code}'
    code = code.zfill(6)
    if code[0] == '6': return f'SH.{code}'
    if code[:2] in ('51', '56', '58', '50', '11', '17', '18', '20', '68', '60'):
        return f'SH.{code}'
    return f'SZ.{code}'


def load_name_map():
    """从 sector-overrides.csv 构建 中文名 → code 映射"""
    name_map = {}
    if not SECTOR_CSV.exists(): return name_map
    with open(SECTOR_CSV, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r.get('name'):
                name_map[r['name']] = r['code']
    return name_map


def resolve_code(input_str: str, name_map: dict = None) -> tuple:
    """智能识别代码 → (futu_code, display_name)
    支持: 000858 / SZ.000858 / 五粮液"""
    s = input_str.strip()
    # 已是富途格式
    if '.' in s and s.split('.')[0] in ('SH', 'SZ', 'HK', 'US'):
        return s.upper(), s
    # 纯数字
    if s.isdigit():
        futu = code_to_futu(s)
        return futu, s
    # 中文名查找
    if name_map:
        code = name_map.get(s)
        if code:
            return code_to_futu(code), s
    return '', s


def futu_to_tencent(futu_code: str) -> str:
    """SZ.000858 → sz000858 (腾讯格式)"""
    if '.' not in futu_code: return ''
    prefix, num = futu_code.split('.', 1)
    p = prefix.lower()
    if p in ('sh', 'sz'): return f'{p}{num}'
    if p == 'hk': return f'hk{num}'
    return ''


# ── 数据源: Futu OpenD ───────────────────────────────────

def _opend_reachable(host='127.0.0.1', port=11111, timeout=1) -> bool:
    """快速检测 Futu OpenD 端口是否开放"""
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError):
        return False


def fetch_futu(futu_code: str, start: str, end: str):
    """通过 Futu OpenD 拉日 K 线。返回 [{date,open,close,high,low,volume}]"""
    # 先快速检测端口,避免 SDK 漫长重试
    if not _opend_reachable():
        return None

    try:
        from futu import OpenQuoteContext, RET_OK, KLType, KL_FIELD
    except ImportError:
        return None

    try:
        ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        ret, _ = ctx.get_global_state()
        if ret != RET_OK:
            ctx.close()
            return None

        ret, kline, _ = ctx.request_history_kline(
            futu_code, ktype=KLType.K_DAY,
            start=start, end=end,
            fields=[KL_FIELD.DATE_TIME, KL_FIELD.OPEN, KL_FIELD.CLOSE,
                    KL_FIELD.HIGH, KL_FIELD.LOW, KL_FIELD.VOLUME])
        ctx.close()

        if ret != RET_OK or kline is None or len(kline) == 0:
            return None

        # 获取股票名称
        name = ''
        try:
            ctx2 = OpenQuoteContext(host='127.0.0.1', port=11111)
            ret2, snap = ctx2.get_market_snapshot([futu_code])
            if ret2 == RET_OK and len(snap) > 0:
                name = snap.iloc[0]['name']
            ctx2.close()
        except Exception:
            pass

        rows = []
        for _, row in kline.iterrows():
            rows.append({
                'date': row['time_key'][:10],
                'open': float(row['open']),
                'close': float(row['close']),
                'high': float(row['high']),
                'low': float(row['low']),
                'volume': float(row['volume']),
            })
        return {'name': name, 'rows': rows}
    except Exception:
        return None


# ── 数据源: 腾讯财经(降级) ────────────────────────────────

def fetch_tencent(futu_code: str, end: str, count: int = 400):
    """腾讯财经 API 降级。只有 A 股和港股。"""
    symbol = futu_to_tencent(futu_code)
    if not symbol: return None

    url = (f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
           f'?param={symbol},day,,{end},{count},')
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        if data.get('code') != 0: return None
        sym_data = data['data'].get(symbol, {})
        if not isinstance(sym_data, dict): return None
        klines = sym_data.get('day') or sym_data.get('qfqday') or []
        rows = []
        for row in klines:
            if isinstance(row, list) and len(row) >= 6:
                rows.append({
                    'date': row[0],
                    'open': float(row[1]),
                    'close': float(row[2]),
                    'high': float(row[3]),
                    'low': float(row[4]),
                    'volume': float(row[5]) if len(row) > 5 else 0,
                })
        return {'name': '', 'rows': rows} if rows else None
    except Exception:
        return None


# ── SQLite 缓存 ──────────────────────────────────────────

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute('''CREATE TABLE IF NOT EXISTS daily_kline (
        code TEXT, date TEXT, open REAL, close REAL, high REAL, low REAL, volume REAL,
        PRIMARY KEY(code, date))''')
    return conn


def cache_get(conn, futu_code: str, start: str, end: str):
    rows = conn.execute(
        'SELECT date, open, close, high, low, volume FROM daily_kline '
        'WHERE code=? AND date>=? AND date<=? ORDER BY date',
        (futu_code, start, end)).fetchall()
    if not rows: return None
    return [{'date': r[0], 'open': r[1], 'close': r[2],
             'high': r[3], 'low': r[4], 'volume': r[5]} for r in rows]


def cache_put(conn, futu_code: str, rows: list):
    conn.executemany(
        'INSERT OR REPLACE INTO daily_kline VALUES(?,?,?,?,?,?,?)',
        [(futu_code, r['date'], r['open'], r['close'],
          r['high'], r['low'], r['volume']) for r in rows])
    conn.commit()


# ── 统一查询入口 ──────────────────────────────────────────

def query_kline(futu_code: str, start: str, end: str):
    """查询日 K 线。优先缓存 → Futu → 腾讯降级。
    返回 {'name': str, 'rows': [...], 'source': str}"""
    conn = init_db()

    # 1. 缓存
    cached = cache_get(conn, futu_code, start, end)
    if cached and len(cached) >= 1:
        # 检查覆盖度: 缓存的最早/最晚日期是否覆盖请求范围
        if cached[0]['date'] <= start and cached[-1]['date'] >= end:
            conn.close()
            return {'name': '', 'rows': cached, 'source': 'cache'}

    # 2. Futu OpenD
    result = fetch_futu(futu_code, start, end)
    if result and result['rows']:
        cache_put(conn, futu_code, result['rows'])
        conn.close()
        return {**result, 'source': 'futu'}

    # 3. 腾讯降级
    result = fetch_tencent(futu_code, end, count=400)
    if result and result['rows']:
        # 过滤日期范围
        filtered = [r for r in result['rows'] if start <= r['date'] <= end]
        if filtered:
            cache_put(conn, futu_code, result['rows'])  # 全量缓存
            conn.close()
            return {'name': '', 'rows': filtered, 'source': 'tencent'}

    # 4. 缓存兜底(不管覆盖度)
    if cached:
        filtered = [r for r in cached if start <= r['date'] <= end]
        if filtered:
            conn.close()
            return {'name': '', 'rows': filtered, 'source': 'cache(partial)'}

    conn.close()
    return None


# ── 输出格式化 ────────────────────────────────────────────

def print_single_day(futu_code: str, name: str, row: dict, source: str):
    """单日输出"""
    title = f'{name} ({futu_code})' if name else futu_code
    print(f'\n{title} · {row["date"]}  [{source}]')
    prev_close = row['open']  # 近似(无法知道昨收)
    chg = row['close'] - prev_close
    chg_pct = chg / prev_close * 100 if prev_close else 0
    print(f'  开盘: {row["open"]:<10.3f} 最高: {row["high"]:<10.3f} 最低: {row["low"]:.3f}')
    color = '\033[31m' if chg >= 0 else '\033[32m'
    reset = '\033[0m'
    print(f'  收盘: {color}{row["close"]:<10.3f}{reset} '
          f'涨跌: {color}{chg:+.3f} ({chg_pct:+.2f}%){reset}')
    if row['volume']:
        print(f'  成交量: {row["volume"]:,.0f}')


def print_range_table(futu_code: str, name: str, rows: list, source: str):
    """区间表格输出"""
    title = f'{name} ({futu_code})' if name else futu_code
    print(f'\n{title} · {rows[0]["date"]} ~ {rows[-1]["date"]}  [{source}]  共 {len(rows)} 个交易日')
    print(f'{"日期":<12} {"开盘":>8} {"收盘":>8} {"最高":>8} {"最低":>8} {"涨跌幅":>8} {"成交量":>12}')
    print('-' * 72)

    prev_close = None
    for r in rows:
        if prev_close and prev_close > 0:
            chg_pct = (r['close'] - prev_close) / prev_close * 100
            color = '\033[31m' if chg_pct >= 0 else '\033[32m'
            reset = '\033[0m'
            chg_s = f'{color}{chg_pct:>+7.2f}%{reset}'
        else:
            chg_s = f'{"—":>8}'
        vol_s = f'{r["volume"]:>12,.0f}' if r['volume'] else f'{"—":>12}'
        print(f'{r["date"]:<12} {r["open"]:>8.3f} {r["close"]:>8.3f} '
              f'{r["high"]:>8.3f} {r["low"]:>8.3f} {chg_s} {vol_s}')
        prev_close = r['close']

    # 区间统计
    first_open = rows[0]['open']
    last_close = rows[-1]['close']
    range_chg = (last_close - first_open) / first_open * 100 if first_open else 0
    highest = max(r['high'] for r in rows)
    lowest = min(r['low'] for r in rows)
    h_date = next(r['date'] for r in rows if r['high'] == highest)
    l_date = next(r['date'] for r in rows if r['low'] == lowest)
    avg_vol = sum(r['volume'] for r in rows) / len(rows) if rows else 0

    # 最大回撤
    peak = 0; max_dd = 0
    for r in rows:
        if r['close'] > peak: peak = r['close']
        dd = (r['close'] - peak) / peak * 100 if peak else 0
        if dd < max_dd: max_dd = dd

    color = '\033[31m' if range_chg >= 0 else '\033[32m'
    reset = '\033[0m'
    print(f'\n区间统计:')
    print(f'  起始: {first_open:.3f} → 收盘: {last_close:.3f} '
          f'({color}区间涨幅 {range_chg:+.2f}%{reset})')
    print(f'  最高: {highest:.3f} ({h_date[5:]})  最低: {lowest:.3f} ({l_date[5:]})')
    print(f'  最大回撤: {max_dd:.2f}%')
    if avg_vol > 0:
        print(f'  日均成交量: {avg_vol:,.0f}')


def print_csv(rows: list):
    """CSV 输出"""
    print('date,open,close,high,low,volume')
    for r in rows:
        print(f'{r["date"]},{r["open"]:.3f},{r["close"]:.3f},'
              f'{r["high"]:.3f},{r["low"]:.3f},{r["volume"]:.0f}')


def print_json(futu_code: str, name: str, rows: list, source: str):
    """JSON 输出"""
    print(json.dumps({
        'code': futu_code, 'name': name, 'source': source,
        'count': len(rows), 'data': rows,
    }, ensure_ascii=False, indent=2))


# ── Main ──────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('codes', nargs='+', help='股票代码(纯数字/富途格式/中文名)')
    ap.add_argument('--date', '-d', help='查单日 YYYY-MM-DD')
    ap.add_argument('--start', '-s', help='开始日期')
    ap.add_argument('--end', '-e', help='结束日期(默认今天)')
    ap.add_argument('--format', '-f', default='table', choices=['table', 'csv', 'json'])
    args = ap.parse_args()

    # 日期处理
    today = date.today().isoformat()
    if args.date:
        start = end = args.date
    elif args.start:
        start = args.start
        end = args.end or today
    else:
        # 默认最近 20 个交易日(约 30 自然日)
        start = (date.today() - timedelta(days=30)).isoformat()
        end = today

    # 代码解析
    name_map = load_name_map()
    targets = []
    for c in args.codes:
        futu_code, display = resolve_code(c, name_map)
        if not futu_code:
            print(f'⚠️ 无法识别代码: {c}', file=sys.stderr)
            continue
        targets.append((futu_code, display))

    if not targets:
        sys.exit('❌ 没有有效代码')

    # 查询
    for futu_code, display in targets:
        result = query_kline(futu_code, start, end)
        if not result:
            print(f'\n⚠️ {display} ({futu_code}): 无数据 ({start} ~ {end})')
            continue

        name = result['name'] or display
        rows = result['rows']
        source = result['source']

        if args.format == 'csv':
            print_csv(rows)
        elif args.format == 'json':
            print_json(futu_code, name, rows, source)
        elif len(rows) == 1:
            print_single_day(futu_code, name, rows[0], source)
        else:
            print_range_table(futu_code, name, rows, source)


if __name__ == '__main__':
    main()
