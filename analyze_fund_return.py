#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_fund_return.py — 场外基金收益率分析

获取指定基金的历史净值数据，计算过去一年的收益率。
"""

import requests
import re
import json
from datetime import datetime, timedelta
from typing import Dict, Optional


def get_historical_navs(code: str, days: int = 400) -> Dict[str, float]:
    """获取基金历史净值数据
    返回: {nav_date: nav_value} 字典

    Args:
        code: 基金代码
        days: 获取天数（默认400天，确保覆盖一年）
    """
    try:
        url = f"http://fund.eastmoney.com/pingzhongdata/{code}.js"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)

        match = re.search(r'Data_netWorthTrend\s*=\s*(\[.+?\]);', response.text)
        if match:
            data = json.loads(match.group(1))
            nav_map = {}
            end_date = datetime.now()

            for item in data:
                dt = datetime.fromtimestamp(item['x'] / 1000)
                nav_date = dt.strftime('%Y-%m-%d')

                # 只保留指定天数内的数据
                if (end_date - dt).days <= days:
                    nav_map[nav_date] = item['y']

            return nav_map
    except Exception as e:
        print(f"获取 {code} 历史净值失败: {e}")
    return {}


def get_fund_name(code: str) -> Optional[str]:
    """获取基金名称"""
    try:
        url = f"http://fund.eastmoney.com/{code}.html"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)

        # 匹配基金名称
        match = re.search(r'<title>([^<]+)</title>', response.text)
        if match:
            name = match.group(1)
            # 去掉后缀
            return name.split('(')[0].strip()
    except Exception:
        pass
    return None


def calculate_returns(nav_map: Dict[str, float], periods: list[tuple[str, int]]) -> dict:
    """计算不同周期收益率

    Args:
        nav_map: {date: nav_value} 字典
        periods: [(period_name, days), ...]

    Returns:
        {period_name: return_pct}
    """
    if not nav_map:
        return {}

    dates = sorted(nav_map.keys(), reverse=True)
    if len(dates) < 2:
        return {}

    current_nav = nav_map[dates[0]]
    results = {}

    for period_name, days in periods:
        target_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # 找到最接近目标日期的净值
        prev_nav = None
        for date in dates:
            if date <= target_date:
                prev_nav = nav_map[date]
                break

        if prev_nav and prev_nav > 0:
            return_pct = (current_nav - prev_nav) / prev_nav * 100
            results[period_name] = {
                'return_pct': return_pct,
                'current_nav': current_nav,
                'prev_nav': prev_nav,
                'current_date': dates[0],
                'prev_date': date
            }

    return results


def analyze_fund(code: str):
    """分析单个基金"""
    print(f"\n{'='*60}")
    print(f"分析基金: {code}")
    print(f"{'='*60}")

    # 获取基金名称
    name = get_fund_name(code)
    print(f"基金名称: {name}")

    # 获取历史净值
    nav_map = get_historical_navs(code, days=400)
    if not nav_map:
        print("无法获取历史净值数据")
        return None

    print(f"获取到 {len(nav_map)} 条净值数据")

    # 获取最新净值
    dates = sorted(nav_map.keys(), reverse=True)
    latest_date = dates[0]
    latest_nav = nav_map[latest_date]
    print(f"最新净值: {latest_nav:.4f} ({latest_date})")

    # 计算收益率
    periods = [
        ('近1个月', 30),
        ('近3个月', 90),
        ('近6个月', 180),
        ('近1年', 365),
    ]

    results = calculate_returns(nav_map, periods)

    print(f"\n{'周期':<12} {'收益率':>12} {'起止净值':>20}")
    print(f"{'-'*44}")

    for period_name, data in results.items():
        return_pct = data['return_pct']
        current_nav = data['current_nav']
        prev_nav = data['prev_nav']
        prev_date = data['prev_date']

        sign = '+' if return_pct >= 0 else ''
        print(f"{period_name:<12} {sign}{return_pct:>11.2f}% {prev_nav:.4f}→{current_nav:.4f}")

    return {
        'code': code,
        'name': name,
        'latest_nav': latest_nav,
        'latest_date': latest_date,
        'returns': results
    }


def main():
    print("=" * 60)
    print("场外基金收益率分析")
    print("=" * 60)

    funds = ['018044', '019737']

    all_results = []

    for code in funds:
        result = analyze_fund(code)
        if result:
            all_results.append(result)

    # 汇总对比
    if all_results:
        print(f"\n\n{'='*60}")
        print("收益率对比")
        print(f"{'='*60}")

        print(f"\n{'基金代码':<10} {'基金名称':<30} {'近1年':>10}")
        print(f"{'-'*50}")

        for result in all_results:
            code = result['code']
            name = result['name'][:28] if result['name'] else 'N/A'
            year_return = result['returns'].get('近1年', {}).get('return_pct', 0)
            sign = '+' if year_return >= 0 else ''
            print(f"{code:<10} {name:<30} {sign}{year_return:>9.2f}%")


if __name__ == '__main__':
    main()
