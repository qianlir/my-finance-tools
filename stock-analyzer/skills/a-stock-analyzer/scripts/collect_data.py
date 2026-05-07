#!/usr/bin/env python3
"""Astock analyzer — 个股数据采集与分析脚本"""

import argparse
import json
import sys
from datetime import datetime, timedelta

import akshare as ak
import numpy as np
import pandas as pd


def collect_realtime(code: str, market: str = "A股") -> dict:
    """采集实时行情"""
    result = {}
    if market == "A股":
        try:
            df = ak.stock_individual_info_em(symbol=code)
            for _, row in df.iterrows():
                result[row["item"]] = row["value"]
        except Exception as e:
            result["error"] = str(e)
    return result


def collect_financials(code: str) -> pd.DataFrame:
    """采集近5年年度财务数据"""
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按年度")
        recent = df.tail(5)
        return recent
    except Exception as e:
        print(f"财务数据采集失败: {e}")
        return pd.DataFrame()


def collect_dividends(code: str) -> pd.DataFrame:
    """采集分红记录"""
    try:
        df = ak.stock_dividend_cninfo(symbol=code)
        return df.tail(10)
    except Exception as e:
        print(f"分红数据采集失败: {e}")
        return pd.DataFrame()


def collect_daily(code: str, days: int = 365, market: str = "A股") -> pd.DataFrame:
    """采集日线数据并计算技术指标"""
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days + 120)).strftime("%Y%m%d")

    try:
        if market == "A股":
            df = ak.stock_zh_a_hist(
                symbol=code, period="daily",
                start_date=start_date, end_date=end_date, adjust="qfq"
            )
        else:
            df = ak.stock_hk_hist(
                symbol=code, period="daily",
                start_date=start_date, end_date=end_date, adjust="qfq"
            )

        if df.empty:
            return df

        # 计算均线
        for w in [5, 10, 20, 60, 120, 250]:
            df[f"MA{w}"] = df["收盘"].rolling(w).mean()

        # MACD
        ema12 = df["收盘"].ewm(span=12, adjust=False).mean()
        ema26 = df["收盘"].ewm(span=26, adjust=False).mean()
        df["DIF"] = ema12 - ema26
        df["DEA"] = df["DIF"].ewm(span=9, adjust=False).mean()
        df["MACD"] = 2 * (df["DIF"] - df["DEA"])

        # RSI(14)
        delta = df["收盘"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        df["RSI14"] = 100 - (100 / (1 + rs))

        return df

    except Exception as e:
        print(f"日线数据采集失败: {e}")
        return pd.DataFrame()


def calc_valuation(financials: pd.DataFrame, current_price: float, total_shares: float) -> dict:
    """计算估值指标"""
    if financials.empty or not current_price:
        return {}

    latest = financials.iloc[-1]
    eps = latest.get("基本每股收益", 0)
    bvps = latest.get("每股净资产", 0)

    pe = current_price / eps if eps and eps > 0 else None
    pb = current_price / bvps if bvps and bvps > 0 else None

    return {
        "PE_TTM": round(pe, 2) if pe else None,
        "PB": round(pb, 2) if pb else None,
        "EPS": eps,
        "BVPS": bvps,
    }


def calc_support_resistance(daily: pd.DataFrame) -> dict:
    """计算支撑压力位"""
    if daily.empty or len(daily) < 20:
        return {}

    recent = daily.tail(60)
    last_price = daily["收盘"].iloc[-1]

    support_levels = []
    resistance_levels = []

    # 近60日的局部低点和高点
    for i in range(2, len(recent) - 2):
        if (recent["最低"].iloc[i] < recent["最低"].iloc[i - 1] and
                recent["最低"].iloc[i] < recent["最低"].iloc[i - 2] and
                recent["最低"].iloc[i] < recent["最低"].iloc[i + 1] and
                recent["最低"].iloc[i] < recent["最低"].iloc[i + 2]):
            support_levels.append(recent["最低"].iloc[i])
        if (recent["最高"].iloc[i] > recent["最高"].iloc[i - 1] and
                recent["最高"].iloc[i] > recent["最高"].iloc[i - 2] and
                recent["最高"].iloc[i] > recent["最高"].iloc[i + 1] and
                recent["最高"].iloc[i] > recent["最高"].iloc[i + 2]):
            resistance_levels.append(recent["最高"].iloc[i])

    # 加入均线作为支撑/压力
    last_row = daily.iloc[-1]
    for ma in ["MA20", "MA60", "MA120"]:
        val = last_row.get(ma)
        if val and not pd.isna(val):
            if val < last_price:
                support_levels.append(val)
            else:
                resistance_levels.append(val)

    support_levels = sorted(set([round(s, 2) for s in support_levels if s < last_price]), reverse=True)[:3]
    resistance_levels = sorted(set([round(r, 2) for r in resistance_levels if r > last_price]))[:3]

    return {
        "current": round(last_price, 2),
        "supports": support_levels,
        "resistances": resistance_levels,
    }


def analyze_technical(daily: pd.DataFrame) -> dict:
    """技术面综合分析"""
    if daily.empty or len(daily) < 120:
        return {"error": "数据不足"}

    last = daily.iloc[-1]
    price = last["收盘"]

    # 均线状态
    ma_status = {}
    for ma in ["MA5", "MA10", "MA20", "MA60", "MA120"]:
        val = last.get(ma)
        if val and not pd.isna(val):
            ma_status[ma] = {
                "value": round(val, 2),
                "diff_pct": round((price / val - 1) * 100, 2),
                "position": "上方" if price > val else "下方",
            }

    # 趋势判断
    ma20 = last.get("MA20", 0)
    ma60 = last.get("MA60", 0)
    ma120 = last.get("MA120", 0)

    if ma20 and ma60 and ma120 and not any(pd.isna([ma20, ma60, ma120])):
        if price > ma20 > ma60 > ma120:
            trend = "多头排列(强势上涨)"
        elif price < ma20 < ma60 < ma120:
            trend = "空头排列(弱势下跌)"
        elif ma20 > ma60 and price < ma20:
            trend = "中短期回调"
        elif ma20 < ma60 and price > ma20:
            trend = "中短期反弹"
        else:
            trend = "震荡整理"
    else:
        trend = "数据不足"

    # MACD状态
    dif = last.get("DIF", 0)
    dea = last.get("DEA", 0)
    macd = last.get("MACD", 0)
    if dif and dea:
        macd_status = "金叉(看多)" if dif > dea else "死叉(看空)"
        if dif > 0 and dea > 0:
            macd_zone = "零轴上方(多头区域)"
        elif dif < 0 and dea < 0:
            macd_zone = "零轴下方(空头区域)"
        else:
            macd_zone = "零轴附近(方向不明)"
    else:
        macd_status = "N/A"
        macd_zone = "N/A"

    # RSI
    rsi = last.get("RSI14", 50)
    if rsi > 70:
        rsi_status = "超买"
    elif rsi < 30:
        rsi_status = "超卖"
    else:
        rsi_status = "中性"

    return {
        "trend": trend,
        "ma_status": ma_status,
        "macd": {"DIF": round(dif, 3), "DEA": round(dea, 3), "MACD": round(macd, 3),
                 "signal": macd_status, "zone": macd_zone},
        "rsi14": {"value": round(rsi, 1), "status": rsi_status},
    }


def main():
    parser = argparse.ArgumentParser(description="A股/港股通个股数据采集")
    parser.add_argument("--code", required=True, help="股票代码 (如 000858)")
    parser.add_argument("--market", default="A股", choices=["A股", "港股"], help="市场类型")
    parser.add_argument("--output", default=None, help="输出JSON文件路径")
    args = parser.parse_args()

    print(f"采集 {args.code} ({args.market}) 数据...")

    # 1. 基本信息
    info = collect_realtime(args.code, args.market)

    # 2. 财务数据
    financials = collect_financials(args.code)

    # 3. 分红数据
    dividends = collect_dividends(args.code)

    # 4. 日线+技术指标
    daily = collect_daily(args.code, days=365, market=args.market)

    # 5. 计算
    current_price = daily["收盘"].iloc[-1] if not daily.empty else 0
    total_shares = info.get("总股本", 0)
    valuation = calc_valuation(financials, current_price, total_shares)
    support_resist = calc_support_resistance(daily)
    technical = analyze_technical(daily)

    # 股息率
    dividend_yield = None
    if not dividends.empty and current_price > 0:
        latest_div = dividends.iloc[-1]
        div_per_10 = latest_div.get("派息比例", 0)
        if div_per_10 and div_per_10 > 0:
            dividend_yield = round((div_per_10 / 10) / current_price * 100, 2)

    # 52周高低
    year_high = daily["最高"].max() if not daily.empty else 0
    year_low = daily["最低"].min() if not daily.empty else 0

    result = {
        "code": args.code,
        "market": args.market,
        "timestamp": datetime.now().isoformat(),
        "info": info,
        "valuation": valuation,
        "dividend_yield_pct": dividend_yield,
        "year_high": round(year_high, 2) if year_high else None,
        "year_low": round(year_low, 2) if year_low else None,
        "dist_high_pct": round((current_price / year_high - 1) * 100, 2) if year_high else None,
        "dist_low_pct": round((current_price / year_low - 1) * 100, 2) if year_low else None,
        "support_resistance": support_resist,
        "technical": technical,
        "financials_summary": financials.tail(3).to_dict("records") if not financials.empty else [],
        "recent_daily": daily.tail(15)[["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额"]].to_dict("records") if not daily.empty else [],
    }

    output_path = args.output or f"data_{args.code}_{datetime.now().strftime('%Y%m%d')}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print(f"数据已保存到 {output_path}")

    # 打印摘要
    print(f"\n{'='*50}")
    print(f"股票代码: {args.code} ({args.market})")
    print(f"当前价格: {current_price:.2f}")
    print(f"52周最高: {year_high:.2f} (距{result['dist_high_pct']:.1f}%)")
    print(f"52周最低: {year_low:.2f} (距{result['dist_low_pct']:.1f}%)")
    if valuation.get("PE_TTM"):
        print(f"PE(TTM): {valuation['PE_TTM']}")
    if dividend_yield:
        print(f"股息率: {dividend_yield}%")
    print(f"趋势判断: {technical.get('trend', 'N/A')}")
    print(f"MACD: {technical.get('macd', {}).get('signal', 'N/A')}")
    print(f"RSI(14): {technical.get('rsi14', {}).get('value', 'N/A')} ({technical.get('rsi14', {}).get('status', 'N/A')})")
    if support_resist.get("supports"):
        print(f"支撑位: {', '.join([str(s) for s in support_resist['supports']])}")
    if support_resist.get("resistances"):
        print(f"压力位: {', '.join([str(r) for r in support_resist['resistances']])}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
