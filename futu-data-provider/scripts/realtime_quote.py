#!/usr/bin/env python3
"""实时报价订阅 — 监控持仓标的的盘中变化。

用法:
    python3 realtime_quote.py --from-portfolio sectors.csv
    python3 realtime_quote.py --codes SZ.000858 HK.09988 SH.513100

按 Ctrl+C 退出。
"""
import argparse
import csv
import sys
import time

try:
    from futu import OpenQuoteContext, RET_OK, SubType
except ImportError:
    sys.exit('❌ 请先安装: pip install futu-api')


def code_to_futu(code: str) -> str:
    code = str(code).strip()
    if '.' in code: return code
    if not code.isdigit(): return ''
    if len(code) == 5: return f'HK.{code}'
    code = code.zfill(6)
    if code[0] == '6': return f'SH.{code}'
    if code[:2] in ('51', '56', '58', '50', '11', '17', '18', '20', '68', '60'):
        return f'SH.{code}'
    return f'SZ.{code}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from-portfolio', help='从 sectors.csv 读标的')
    ap.add_argument('--codes', nargs='+', help='指定富途代码')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=11111)
    ap.add_argument('--interval', type=int, default=10, help='刷新间隔(秒)')
    args = ap.parse_args()

    if args.from_portfolio:
        codes = []
        with open(args.from_portfolio) as f:
            for r in csv.DictReader(f):
                c = code_to_futu(r['code'])
                if c: codes.append(c)
    elif args.codes:
        codes = args.codes
    else:
        sys.exit('请指定 --from-portfolio 或 --codes')

    # 富途订阅限制: 免费用户最多 100 个标的
    if len(codes) > 100:
        print(f'⚠️ 标的 {len(codes)} 个超过免费额度 100,只取前 100 个')
        codes = codes[:100]

    ctx = OpenQuoteContext(host=args.host, port=args.port)
    ret, _ = ctx.get_global_state()
    if ret != RET_OK:
        ctx.close()
        sys.exit('❌ Futu OpenD 未连接')

    print(f'订阅 {len(codes)} 个标的实时报价,每 {args.interval} 秒刷新...')
    print('按 Ctrl+C 退出\n')

    try:
        while True:
            ret, quotes = ctx.get_market_snapshot(codes)
            if ret == RET_OK:
                print(f'\033[2J\033[H')  # 清屏
                print(f'{"代码":>14} {"名称":<10} {"最新价":>8} {"涨跌幅":>8} {"成交额(万)":>10}')
                print('-' * 58)
                for _, row in quotes.sort_values('change_rate', ascending=False).iterrows():
                    chg = row['change_rate']
                    color = '\033[31m' if chg > 0 else '\033[32m' if chg < 0 else ''
                    reset = '\033[0m' if color else ''
                    turnover = row.get('turnover', 0) / 10000
                    print(f'{row["code"]:>14} {row["name"]:<10} '
                          f'{row["last_price"]:>8.3f} '
                          f'{color}{chg:>+7.2f}%{reset} '
                          f'{turnover:>10,.0f}')
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print('\n退出')
    finally:
        ctx.close()


if __name__ == '__main__':
    main()
