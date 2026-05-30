#!/usr/bin/env python3
"""批量拉历史日 K 线 → SQLite。可替代 portfolio-pnl-analyzer 的腾讯 API。

用法:
    # 从 portfolio 的 sectors.csv 读标的列表,拉 18 个月 K 线
    python3 fetch_kline.py --from-portfolio ~/gei-workspace/output/portfolio-pnl-2026-05-30/data/sectors.csv

    # 指定标的
    python3 fetch_kline.py --codes SZ.000858 HK.09988 SH.513100

    # 指定日期范围
    python3 fetch_kline.py --from-portfolio sectors.csv --start 2024-12-01 --end 2026-05-30

前置: Futu OpenD 正在运行。
"""
import argparse
import csv
import sqlite3
import sys
import time
from pathlib import Path

try:
    from futu import OpenQuoteContext, RET_OK, KLType, KL_FIELD
except ImportError:
    sys.exit('❌ 请先安装: pip install futu-api')

HERE = Path(__file__).resolve().parent
DB_DEFAULT = HERE.parent / 'data' / 'futu_kline.db'


def code_to_futu(code: str) -> str:
    """portfolio 的 6 位代码 → 富途格式
    000858 → SZ.000858, 600941 → SH.600941, 09988 → HK.09988"""
    code = str(code).strip()
    if '.' in code:
        return code  # 已是富途格式
    if not code.isdigit():
        return ''
    if len(code) == 5:
        return f'HK.{code}'
    code = code.zfill(6)
    if code[0] == '6':
        return f'SH.{code}'
    if code[:2] in ('51', '56', '58', '50', '11', '17', '18', '20', '68', '60'):
        return f'SH.{code}'
    return f'SZ.{code}'


def load_portfolio_codes(csv_path: str) -> list:
    """从 sectors.csv 读标的列表"""
    codes = []
    with open(csv_path) as f:
        for r in csv.DictReader(f):
            futu_code = code_to_futu(r['code'])
            if futu_code:
                codes.append((futu_code, r.get('name', '')))
    return codes


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--from-portfolio', help='从 sectors.csv 读标的')
    ap.add_argument('--codes', nargs='+', help='指定富途代码')
    ap.add_argument('--start', default='2024-12-01', help='开始日期')
    ap.add_argument('--end', default='2026-05-30', help='结束日期')
    ap.add_argument('--db', default=str(DB_DEFAULT), help='SQLite 路径')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=11111)
    args = ap.parse_args()

    # 构建标的列表
    if args.from_portfolio:
        targets = load_portfolio_codes(args.from_portfolio)
    elif args.codes:
        targets = [(c, '') for c in args.codes]
    else:
        sys.exit('请指定 --from-portfolio 或 --codes')

    print(f'标的: {len(targets)} 个, 日期: {args.start} ~ {args.end}')

    # SQLite
    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    conn.execute('''CREATE TABLE IF NOT EXISTS daily_kline (
        code TEXT, date TEXT, open REAL, close REAL, high REAL, low REAL, volume REAL,
        PRIMARY KEY(code, date))''')

    # 检查已缓存
    cached = set()
    for r in conn.execute('SELECT DISTINCT code FROM daily_kline'):
        cached.add(r[0])
    to_fetch = [(c, n) for c, n in targets if c not in cached]
    print(f'已缓存: {len(cached)}, 需拉: {len(to_fetch)}')

    if not to_fetch:
        print('全部命中缓存,无需拉取')
        conn.close()
        return

    # 连接 OpenD
    ctx = OpenQuoteContext(host=args.host, port=args.port)
    ret, _ = ctx.get_global_state()
    if ret != RET_OK:
        ctx.close()
        sys.exit('❌ Futu OpenD 未连接')

    # 逐个拉取(富途频率限制: 30 次/30 秒)
    success = 0
    for i, (code, name) in enumerate(to_fetch, 1):
        ret, kline, _ = ctx.request_history_kline(
            code, ktype=KLType.K_DAY,
            start=args.start, end=args.end,
            fields=[KL_FIELD.DATE_TIME, KL_FIELD.OPEN, KL_FIELD.CLOSE,
                    KL_FIELD.HIGH, KL_FIELD.LOW, KL_FIELD.VOLUME])

        if ret == RET_OK and len(kline) > 0:
            rows = [(code, row['time_key'][:10], row['open'], row['close'],
                     row['high'], row['low'], row['volume'])
                    for _, row in kline.iterrows()]
            conn.executemany('INSERT OR REPLACE INTO daily_kline VALUES(?,?,?,?,?,?,?)', rows)
            success += 1
            if i % 10 == 0:
                conn.commit()
                print(f'  进度 {i}/{len(to_fetch)} ({name or code}: {len(rows)} 条)')
        else:
            print(f'  ⚠️ {code} {name}: {kline if ret != RET_OK else "空数据"}')

        # 频率控制: 每 29 次暂停 30 秒
        if i % 29 == 0:
            print(f'  频率控制: 暂停 30 秒...')
            time.sleep(30)

    conn.commit()
    ctx.close()

    total = conn.execute('SELECT COUNT(DISTINCT code) FROM daily_kline').fetchone()[0]
    print(f'\n✅ 完成: 本次成功 {success}/{len(to_fetch)}, 数据库共 {total} 个标的')
    conn.close()


if __name__ == '__main__':
    main()
