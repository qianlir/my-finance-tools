#!/usr/bin/env python3
"""更新五粮液数据到最新"""

import akshare as ak
import pandas as pd
from datetime import datetime

def get_latest_data():
    try:
        df = ak.stock_zh_a_hist(symbol='000858', period='daily',
                               start_date='20250401', end_date='20260502', adjust='qfq')
        return df
    except Exception as e:
        print(f"数据获取失败: {e}")
        return None

if __name__ == "__main__":
    df = get_latest_data()
    if df is not None and not df.empty:
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        print("=== 五粮液最新数据（5月2日）===")
        print(f"交易日: {latest['日期']}")
        print(f"收盘价: {latest['收盘']:.2f}元")
        print(f"今日涨跌: {latest['涨跌幅']:.2f}%")
        print(f"成交量: {latest['成交量']:,}手")
        print(f"成交额: {latest['成交额']/100000000:.2f}亿元")

        print("\n五一前后对比:")
        print(f"4月30日收盘: {prev['收盘']:.2f}元")
        print(f"5月2日收盘: {latest['收盘']:.2f}元")
        print(f"两日涨跌: {((latest['收盘']/prev['收盘']-1)*100):+.2f}%")