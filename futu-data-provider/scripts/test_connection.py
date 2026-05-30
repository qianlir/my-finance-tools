#!/usr/bin/env python3
"""测试 Futu OpenD 连接 + 基本行情查询。

前置: Futu OpenD 正在运行(默认 localhost:11111)。

用法:
    python3 test_connection.py
    python3 test_connection.py --host 127.0.0.1 --port 11111
"""
import argparse
import sys

try:
    from futu import OpenQuoteContext, RET_OK, KLType, KL_FIELD
except ImportError:
    sys.exit('❌ 请先安装: pip install futu-api')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=11111)
    args = ap.parse_args()

    print(f'连接 Futu OpenD {args.host}:{args.port} ...')
    ctx = OpenQuoteContext(host=args.host, port=args.port)

    # 1. 测试连接: 获取全局状态
    ret, data = ctx.get_global_state()
    if ret != RET_OK:
        ctx.close()
        sys.exit(f'❌ 连接失败: {data}')
    print(f'✅ 连接成功')
    print(f'   市场状态: {data}')

    # 2. 测试实时报价: 几个代表性标的
    test_codes = ['SZ.000858', 'HK.09988', 'SH.513100']
    print(f'\n获取实时报价: {test_codes}')
    ret, data = ctx.get_stock_basicinfo('SH', 'STOCK')

    ret, quotes = ctx.get_market_snapshot(test_codes)
    if ret == RET_OK:
        for _, row in quotes.iterrows():
            print(f'  {row["code"]:>12} {row["name"]:<10} '
                  f'最新: {row["last_price"]:.3f}  '
                  f'涨跌: {row["price_change"]:.3f} ({row["change_rate"]:.2f}%)')
    else:
        print(f'  ⚠️ 报价失败: {quotes}')

    # 3. 测试历史 K 线: 平安银行最近 5 日
    print(f'\n获取日 K 线: SZ.000001 最近 5 日')
    ret, kline, _ = ctx.request_history_kline(
        'SZ.000001', ktype=KLType.K_DAY,
        start='2026-05-20', end='2026-05-30',
        max_count=5,
        fields=[KL_FIELD.DATE_TIME, KL_FIELD.CLOSE, KL_FIELD.VOLUME])
    if ret == RET_OK:
        for _, row in kline.iterrows():
            print(f'  {row["time_key"][:10]}  收盘: {row["close"]:.3f}  成交量: {row["volume"]:,.0f}')
    else:
        print(f'  ⚠️ K 线失败: {kline}')

    ctx.close()
    print('\n✅ 测试完成')


if __name__ == '__main__':
    main()
