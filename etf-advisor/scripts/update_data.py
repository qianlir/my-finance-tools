#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_data.py — ETF数据更新脚本

功能：
1. 获取历史价格数据（腾讯/新浪）
2. 获取历史净值数据（东方财富）
3. 获取实时价格和净值
4. 计算指数涨跌（从多只ETF净值变化）
5. 保存到数据库

Usage:
    python3 update_data.py                    # 更新所有数据
    python3 update_data.py --realtime        # 只更新实时数据
    python3 update_data.py --history         # 只更新历史数据
"""

import sqlite3
import json
import re
import requests
from datetime import datetime, timedelta
from pathlib import Path

# ============= 配置 =============
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR / ".."
DB_PATH = str(PROJECT_ROOT / "data" / "etf_premium.db")

ETF_LIST = [
    # 纳斯达克ETF
    {'code': '513100', 'name': '国泰纳指ETF', 'company': '国泰基金', 'market': 'sh', 'index': 'NASDAQ'},
    {'code': '159941', 'name': '广发纳指ETF', 'company': '广发基金', 'market': 'sz', 'index': 'NASDAQ'},
    {'code': '159660', 'name': '汇添富纳指ETF', 'company': '汇添富基金', 'market': 'sz', 'index': 'NASDAQ'},
    # 159509 纳指科技已移到 OTHERS
    {'code': '159501', 'name': '嘉实纳指ETF', 'company': '嘉实基金', 'market': 'sz', 'index': 'NASDAQ'},
    {'code': '159632', 'name': '华安纳指ETF', 'company': '华安基金', 'market': 'sz', 'index': 'NASDAQ'},
    {'code': '159659', 'name': '招商纳指ETF', 'company': '招商基金', 'market': 'sz', 'index': 'NASDAQ'},
    {'code': '513300', 'name': '华夏纳指ETF', 'company': '华夏基金', 'market': 'sh', 'index': 'NASDAQ'},
    {'code': '513870', 'name': '富国纳指ETF', 'company': '富国基金', 'market': 'sh', 'index': 'NASDAQ'},
    {'code': '513390', 'name': '博时纳指ETF', 'company': '博时基金', 'market': 'sh', 'index': 'NASDAQ'},
    {'code': '513110', 'name': '南方纳指ETF', 'company': '南方基金', 'market': 'sh', 'index': 'NASDAQ'},
    {'code': '161130', 'name': '纳斯达克100LOF', 'company': '易方达', 'market': 'sz', 'index': 'NASDAQ'},
    # 标普500ETF
    {'code': '513500', 'name': '博时标普ETF', 'company': '博时基金', 'market': 'sh', 'index': 'SP500'},
    {'code': '159655', 'name': '华夏标普ETF', 'company': '华夏基金', 'market': 'sz', 'index': 'SP500'},
    {'code': '513650', 'name': '南方标普ETF', 'company': '南方基金', 'market': 'sh', 'index': 'SP500'},
    {'code': '159612', 'name': '国泰标普ETF', 'company': '国泰基金', 'market': 'sz', 'index': 'SP500'},
    {'code': '161125', 'name': '标普500LOF', 'company': '易方达', 'market': 'sz', 'index': 'SP500'},
    # 道琼斯ETF
    {'code': '513400', 'name': '国泰道琼斯ETF', 'company': '国泰基金', 'market': 'sh', 'index': 'DOW'},
    # 德国DAX ETF
    {'code': '513030', 'name': '德国ETF华安', 'company': '华安基金', 'market': 'sh', 'index': 'DAX'},
    {'code': '159561', 'name': '德国ETF嘉实', 'company': '嘉实基金', 'market': 'sz', 'index': 'DAX'},
    # 日经225ETF
    {'code': '159866', 'name': '日经ETF工银', 'company': '工银瑞信', 'market': 'sz', 'index': 'NIKKEI'},
    {'code': '513000', 'name': '日经225ETF易方达', 'company': '易方达', 'market': 'sh', 'index': 'NIKKEI'},
    {'code': '513520', 'name': '日经ETF华夏', 'company': '华夏基金', 'market': 'sh', 'index': 'NIKKEI'},
    {'code': '513880', 'name': '日经225ETF华安', 'company': '华安基金', 'market': 'sh', 'index': 'NIKKEI'},
    # OTHERS（持仓估算 + 道琼斯期货）
    # OTHERS ETF
    {'code': '159509', 'name': '纳指科技ETF', 'company': '景顺长城', 'market': 'sz', 'index': 'OTHERS'},
    {'code': '159529', 'name': '标普消费ETF', 'company': '华夏基金', 'market': 'sz', 'index': 'OTHERS'},
    {'code': '513290', 'name': '美国生物ETF', 'company': '国泰基金', 'market': 'sh', 'index': 'OTHERS'},
    {'code': '513080', 'name': '法国CAC40ETF', 'company': '华安基金', 'market': 'sh', 'index': 'OTHERS'},
    # LOF
    {'code': '501312', 'name': '海外科技LOF', 'company': '国泰基金', 'market': 'sh', 'index': 'LOF'},
    {'code': '162415', 'name': '美国消费LOF', 'company': '华宝基金', 'market': 'sz', 'index': 'LOF'},
    {'code': '161128', 'name': '标普科技LOF', 'company': '易方达', 'market': 'sz', 'index': 'LOF'},
    {'code': '160140', 'name': '美国REIT LOF', 'company': '诺安基金', 'market': 'sz', 'index': 'LOF'},
    {'code': '161126', 'name': '标普医药LOF', 'company': '易方达', 'market': 'sz', 'index': 'LOF'},
    {'code': '161127', 'name': '标普生物LOF', 'company': '易方达', 'market': 'sz', 'index': 'LOF'},
    {'code': '162411', 'name': '华宝油气LOF', 'company': '华宝基金', 'market': 'sz', 'index': 'LOF'},
    {'code': '164824', 'name': '印度LOF', 'company': '工银瑞信', 'market': 'sz', 'index': 'LOF'},
    {'code': '160719', 'name': '嘉实黄金LOF', 'company': '嘉实基金', 'market': 'sz', 'index': 'LOF'},
    {'code': '161116', 'name': '易方达黄金LOF', 'company': '易方达', 'market': 'sz', 'index': 'LOF'},
    {'code': '160723', 'name': '嘉实原油LOF', 'company': '嘉实基金', 'market': 'sz', 'index': 'LOF'},
    {'code': '161129', 'name': '易方达原油LOF', 'company': '易方达', 'market': 'sz', 'index': 'LOF'},
    {'code': '160216', 'name': '国泰商品LOF', 'company': '国泰基金', 'market': 'sz', 'index': 'LOF'},
    {'code': '161715', 'name': '招商大宗商品LOF', 'company': '招商基金', 'market': 'sz', 'index': 'LOF'},
    {'code': '161810', 'name': '银华内需LOF', 'company': '银华基金', 'market': 'sz', 'index': 'LOF'},
    {'code': '160644', 'name': '港美互联网LOF', 'company': '景顺长城', 'market': 'sz', 'index': 'LOF'},
    {'code': '501225', 'name': '全球芯片LOF', 'company': '景顺长城', 'market': 'sh', 'index': 'OTHERS'},
]


# ============= 数据获取函数 =============
def get_sina_history(code, market, days=90):
    """从新浪获取历史数据"""
    try:
        market_code = 'sh' if market == 'sh' else 'sz'
        url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
        params = {'symbol': market_code + code, 'scale': '240', 'ma': 'no', 'datalen': str(days)}
        response = requests.get(url, params=params, timeout=30)

        if response.status_code == 200 and '[' in response.text:
            data = json.loads(response.text)
            if isinstance(data, list):
                return [[d.get('day', ''), d.get('open', '0'), d.get('close', '0'),
                        d.get('high', '0'), d.get('low', '0'), d.get('volume', '0')] for d in data]
    except Exception:
        pass
    return None


def get_tencent_history(code, market, days=90):
    """从腾讯获取历史数据"""
    try:
        url = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days*2)

        params = {
            'param': f'{market}{code},day,{start_date.strftime("%Y-%m-%d")},{end_date.strftime("%Y-%m-%d")},640,qfq',
            '_var': 'minq',
            'r': str(end_date.timestamp())
        }

        response = requests.get(url, params=params, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)

        if response.status_code == 200 and response.text.startswith('minq='):
            data = json.loads(response.text[5:])
            if data.get('code') == 0 and 'data' in data:
                etf_data = data['data'].get(f'{market}{code}', {})
                if etf_data and 'qfqday' in etf_data:
                    return etf_data['qfqday']
    except Exception:
        pass
    return None


def get_realtime_price(code, market):
    """获取实时价格、昨收、涨跌幅

    腾讯API格式:
    - parts[3]: 当前价格
    - parts[4]: 今开
    - parts[5]: 昨收
    - parts[32]: API报告的涨跌幅(%)
    - parts[43]: 振幅

    返回: {'price': float, 'prev_close': float, 'change_pct': float, 'source': 'tencent'}
    """
    try:
        url = f"http://qt.gtimg.cn/q={market}{code}"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        response.encoding = 'gbk'

        if '~' in response.text and 'none_match' not in response.text:
            data = response.text.split('"')[1]
            parts = data.split('~')
            if len(parts) > 32 and parts[3]:
                price = float(parts[3])
                prev_close = float(parts[5]) if len(parts) > 5 and parts[5] else None
                # API报告的涨跌幅 (parts[32])
                change_pct = float(parts[32]) if len(parts) > 32 and parts[32] else None
                return {
                    'price': price,
                    'prev_close': prev_close,
                    'change_pct': change_pct,
                    'source': 'tencent'
                }
    except Exception:
        pass
    return None


def get_historical_navs(code):
    """获取历史净值数据
    返回: {nav_date: nav_value} 字典
    注意: 返回的日期是净值实际日期(美股收盘日),不是爬取日期
    """
    try:
        url = f"http://fund.eastmoney.com/pingzhongdata/{code}.js"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)

        match = re.search(r'Data_netWorthTrend\s*=\s*(\[.+?\]);', response.text)
        if match:
            data = json.loads(match.group(1))
            nav_map = {}
            for item in data:
                dt = datetime.fromtimestamp(item['x'] / 1000)
                nav_date = dt.strftime('%Y-%m-%d')
                nav_map[nav_date] = item['y']
            return nav_map
    except Exception:
        pass
    return {}


def get_historical_prices(code, days=30):
    """获取历史价格数据(东方财富K线API)
    返回: {date: close_price} 字典
    """
    try:
        # ETF在东方财富的secid格式: 0.{code} 或 1.{code}
        # 上海基金: 1.xxxxxxx, 深圳基金: 0.xxxxxxx
        secid_prefix = '1' if code.startswith('51') else '0'
        url = (f"http://push2.eastmoney.com/api/qt/cl/klt?lcltt=1&secid={secid_prefix}.{code}"
               f"&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
               f"&klt=1&fqt=0&end=20500101&beg=19900101")

        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get('data') and data['data'].get('diff'):
                price_map = {}
                for item in data['data']['diff']:
                    # 格式: date=20240326, open/close/high/low等
                    date_str = str(item.get('date', ''))
                    if len(date_str) == 8:
                        formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                        price_map[formatted_date] = item.get('f2', 0)  # f2=收盘价
                return price_map
    except Exception:
        pass
    return {}


def get_current_nav(code, fallback_to_db=True):
    """获取当前净值"""
    try:
        url = f"http://fund.eastmoney.com/{code}.html"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        match = re.search(r'fix_dwjz[^>]*>([\d.]+)</span>', response.text)
        if match:
            return float(match.group(1))
    except Exception:
        pass

    # 如果API获取失败，从数据库获取最近NAV
    if fallback_to_db:
        return get_latest_nav_from_db(code)
    return None


def get_current_nav_with_date(code):
    """获取当前净值及其日期
    返回: {'nav': float, 'nav_date': str} 或 None

    优先从历史API获取最新净值及日期，如果失败则从数据库获取
    """
    # 先尝试从历史API获取（包含日期）
    nav_map = get_historical_navs(code)
    if nav_map:
        # 按日期排序，获取最新的
        sorted_dates = sorted(nav_map.keys(), reverse=True)
        latest_nav_date = sorted_dates[0]
        latest_nav = nav_map[latest_nav_date]
        return {'nav': latest_nav, 'nav_date': latest_nav_date}

    # 回退到数据库获取
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT nav, nav_date
            FROM etf_data
            WHERE code = ? AND nav IS NOT NULL
            ORDER BY date DESC
            LIMIT 1
        """, (code,))

        row = cursor.fetchone()
        conn.close()

        if row:
            nav = row['nav']
            nav_date = row['nav_date']  # 可能为NULL
            return {'nav': nav, 'nav_date': nav_date}
    except Exception:
        pass

    return None


def get_fundgz_nav(code):
    """从东方财富 fundgz API 获取盘中估值（A 股基金实时估算净值）

    返回: {'estimated_nav': float, 'change_pct': float} 或 None
    仅在 A 股交易时段有效，盘后返回最后一次估值。
    """
    import re as _re
    url = f'https://fundgz.1234567.com.cn/js/{code}.js'

    # 尝试 requests
    try:
        resp = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0', 'Referer': 'https://fund.eastmoney.com/'
        }, timeout=8)
        m = _re.search(r'jsonpgz\((.+)\)', resp.text)
        if m:
            data = json.loads(m.group(1))
            gsz = float(data.get('gsz', 0))
            gszzl = float(data.get('gszzl', 0))
            if gsz > 0:
                return {'estimated_nav': gsz, 'change_pct': gszzl}
    except Exception:
        pass

    # fallback: curl
    try:
        import subprocess as _sp
        r = _sp.run(['curl', '-s', '--noproxy', '*', '--max-time', '8', url],
                     capture_output=True, text=True, timeout=12)
        if r.returncode == 0 and r.stdout.strip():
            m = _re.search(r'jsonpgz\((.+)\)', r.stdout)
            if m:
                data = json.loads(m.group(1))
                gsz = float(data.get('gsz', 0))
                gszzl = float(data.get('gszzl', 0))
                if gsz > 0:
                    return {'estimated_nav': gsz, 'change_pct': gszzl}
    except Exception:
        pass

    return None


def get_latest_nav_from_db(code):
    """从数据库获取最近的NAV"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT nav
            FROM etf_data
            WHERE code = ? AND nav IS NOT NULL
            ORDER BY date DESC
            LIMIT 1
        """, (code,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return row['nav']
    except Exception:
        pass
    return None


def get_us_trading_date(china_time=None):
    """根据中国时间推算当前美股交易日

    规则：
    - 中国时间 08:00 前 → 美股尚未开盘，归属到前一日
    - 中国时间 08:00 后 → 美股前一交易日收盘（如周二早上 = 周一美股数据）

    夏令时（3月第二个周日-11月第一个周日）：美东比中国慢 12 小时
    冬令时：美东比中国慢 13 小时

    简化处理：用 08:00 作为分界线（保守估计，覆盖绝大多数情况）

    Args:
        china_time: datetime对象，默认使用当前时间

    Returns:
        str: 美股交易日，格式 YYYY-MM-DD
    """
    from datetime import datetime, timedelta

    if china_time is None:
        china_time = datetime.now()

    # 早8点前 → 数据归属到前一个美股交易日
    if china_time.hour < 8:
        us_date = (china_time - timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        # 早8点后 → 数据归属到当前美股交易日
        us_date = china_time.strftime('%Y-%m-%d')

    # 进一步修正：如果推算出的 us_date 是周末，回退到周五
    # （周末无交易，数据实际来自周五）
    date_obj = datetime.strptime(us_date, '%Y-%m-%d')
    if date_obj.weekday() == 5:  # 周六
        return (date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
    elif date_obj.weekday() == 6:  # 周日
        return (date_obj - timedelta(days=2)).strftime('%Y-%m-%d')

    return us_date


def get_futures_from_sina(symbol):
    """从新浪财经获取期货实时数据
    返回: {change_pct, price, prev_close, source} 或 None
    """
    try:
        url = f"https://hq.sinajs.cn/list=hf_{symbol}"
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://finance.sina.com.cn'
        }, timeout=10)
        response.encoding = 'gbk'

        # 格式: var hq_str_hf_NQ="最新价,,卖价,最高,?,最低,时间,昨收,开盘,...";
        match = re.search(r'"([^"]+)"', response.text)
        if match:
            fields = match.group(1).split(',')
            if len(fields) >= 9 and fields[0] and fields[7]:
                price = float(fields[0])
                prev_close = float(fields[7])
                change_pct = (price - prev_close) / prev_close * 100
                return {
                    'price': price,
                    'prev_close': prev_close,
                    'change_pct': change_pct,
                    'source': 'sina'
                }
        return None
    except Exception:
        return None


def get_realtime_futures():
    """获取实时期货涨跌数据（新浪财经）"""
    futures_data = {}

    # NQ期货 (纳斯达克100)
    nq_data = get_futures_from_sina('NQ')
    if nq_data:
        futures_data['NQ'] = nq_data

    # ES期货 (标普500)
    es_data = get_futures_from_sina('ES')
    if es_data:
        futures_data['ES'] = es_data

    # YM期货 (道琼斯)
    ym_data = get_futures_from_sina('YM')
    if ym_data:
        futures_data['YM'] = ym_data

    # GC期货 (黄金)
    gc_data = get_futures_from_sina('GC')
    if gc_data:
        futures_data['GC'] = gc_data

    # CL期货 (原油)
    cl_data = get_futures_from_sina('CL')
    if cl_data:
        futures_data['CL'] = cl_data

    # NK期货 (日经225)
    nk_data = get_futures_from_sina('NK')
    if nk_data:
        futures_data['NK'] = nk_data

    # 日经225指数（东方财富，用于估算净值，比期货更准确）
    nk_idx = get_nikkei_index_realtime()
    if nk_idx:
        futures_data['NK_IDX'] = nk_idx

    # 德国DAX指数（东方财富 + 新浪 b_DAX fallback）
    dax_idx = get_dax_index_realtime()
    if dax_idx:
        futures_data['DAX_IDX'] = dax_idx

    # 法国CAC40指数（东方财富 + 新浪 b_CAC fallback）
    cac_idx = get_cac_index_realtime()
    if cac_idx:
        futures_data['CAC_IDX'] = cac_idx

    # 印度SENSEE指数（东方财富 + 新浪 b_SENSEX fallback）
    sensex_idx = get_sensex_index_realtime()
    if sensex_idx:
        futures_data['SENSEX_IDX'] = sensex_idx

    # SOX 半导体指数（新浪 gb_$sox，美股格式）
    sox_data = _get_sox_realtime()
    if sox_data:
        futures_data['SOX_IDX'] = sox_data

    return futures_data


def get_nikkei_index_realtime():
    """获取日经225指数实时数据（多源 fallback）

    优先级:
      1. 东方财富 push2 API (requests)
      2. 东方财富 push2 API (curl, 绕过代理)
      3. 东方财富历史K线最新一条
      4. NK期货变动率 × DB中最近的指数收盘价（需要已有锚点）

    返回: {price, prev_close, change_pct, source} 或 None
    """
    for fn in [_nk_idx_from_eastmoney, _nk_idx_from_eastmoney_curl,
               _nk_idx_from_eastmoney_kline, _nk_idx_from_futures_extrapolate]:
        result = fn()
        if result:
            return result
    return None


def _parse_eastmoney_nk_idx(data: dict) -> dict:
    """解析东方财富 N225 API 返回的 f43/f60/f170 字段"""
    if not data or not data.get('f43'):
        return None
    price = data['f43'] / 100
    prev_close = data['f60'] / 100 if data.get('f60') else None
    change_pct = data['f170'] / 100 if data.get('f170') is not None else None
    if not prev_close or prev_close <= 0:
        return None
    if change_pct is None:
        change_pct = (price - prev_close) / prev_close * 100
    return {'price': price, 'prev_close': prev_close,
            'change_pct': change_pct, 'source': 'eastmoney'}


def _nk_idx_from_eastmoney():
    """源1: 东方财富 push2 实时 API"""
    try:
        url = 'https://push2.eastmoney.com/api/qt/stock/get?secid=100.N225&fields=f43,f60,f170'
        resp = requests.get(url, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
        return _parse_eastmoney_nk_idx(resp.json().get('data', {}))
    except Exception:
        return None


def _nk_idx_from_eastmoney_curl():
    """源2: 用 curl 调东方财富（绕过 Python 代理设置）"""
    try:
        import subprocess as _sp
        url = 'https://push2.eastmoney.com/api/qt/stock/get?secid=100.N225&fields=f43,f60,f170'
        r = _sp.run(['curl', '-s', '--noproxy', '*', '--max-time', '8', url],
                     capture_output=True, text=True, timeout=12)
        if r.returncode == 0 and r.stdout.strip():
            return _parse_eastmoney_nk_idx(json.loads(r.stdout).get('data', {}))
    except Exception:
        pass
    return None


def _nk_idx_from_eastmoney_kline():
    """源3: 东方财富历史K线最新一条（不同服务器，可能可用）"""
    try:
        url = ('https://push2his.eastmoney.com/api/qt/stock/kline/get'
               '?secid=100.N225&fields1=f1&fields2=f51,f52,f53&klt=101&fqt=0&beg=0&end=0&lmt=2')
        resp = requests.get(url, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
        klines = resp.json().get('data', {}).get('klines', [])
        if len(klines) >= 2:
            today = klines[-1].split(',')
            yesterday = klines[-2].split(',')
            price = float(today[2])
            prev_close = float(yesterday[2])
            change_pct = (price - prev_close) / prev_close * 100
            return {'price': price, 'prev_close': prev_close,
                    'change_pct': change_pct, 'source': 'eastmoney_kline'}
    except Exception:
        pass
    return None


def _nk_idx_from_futures_extrapolate():
    """源4: 用NK期货变动率 × DB最近的指数锚点（精度较低）

    原理: 虽然期货和指数的绝对值差 ~5%，但日涨跌幅高度相关。
    如果 DB 中有最近的 nk_idx_close，用期货的变动率外推。
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT nk_idx_close, nk_close, date
            FROM futures_data
            WHERE nk_idx_close IS NOT NULL AND nk_idx_close > 0
            ORDER BY date DESC LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        anchor_idx, anchor_fut, anchor_date = row[0], row[1], row[2]
        # 获取当前 NK 期货
        nk = get_futures_from_sina('NK')
        if not nk or not anchor_fut or anchor_fut <= 0:
            return None
        futures_change = nk['price'] / anchor_fut
        price = anchor_idx * futures_change
        prev_close = anchor_idx
        change_pct = (futures_change - 1) * 100
        return {'price': price, 'prev_close': prev_close,
                'change_pct': change_pct, 'source': f'futures_extrapolate({anchor_date})'}
    except Exception:
        return None


def get_dax_index_realtime():
    """获取德国DAX指数实时数据（多源 fallback）

    优先级:
      1. 东方财富 push2 API (100.GDAXI)
      2. 东方财富 via curl
      3. 新浪 b_DAX
    """
    for fn in [_dax_idx_from_eastmoney, _dax_idx_from_eastmoney_curl, _dax_idx_from_sina]:
        result = fn()
        if result:
            return result
    return None


def _dax_idx_from_eastmoney():
    """东方财富 DAX 指数 (requests)"""
    try:
        url = 'https://push2.eastmoney.com/api/qt/stock/get?secid=100.GDAXI&fields=f43,f60,f170'
        resp = requests.get(url, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
        return _parse_eastmoney_nk_idx(resp.json().get('data', {}))
    except Exception:
        return None


def _dax_idx_from_eastmoney_curl():
    """东方财富 DAX via curl"""
    try:
        import subprocess as _sp
        url = 'https://push2.eastmoney.com/api/qt/stock/get?secid=100.GDAXI&fields=f43,f60,f170'
        r = _sp.run(['curl', '-s', '--noproxy', '*', '--max-time', '8', url],
                     capture_output=True, text=True, timeout=12)
        if r.returncode == 0 and r.stdout.strip():
            return _parse_eastmoney_nk_idx(json.loads(r.stdout).get('data', {}))
    except Exception:
        pass
    return None


def _dax_idx_from_sina():
    """新浪 b_DAX 指数"""
    try:
        url = 'https://hq.sinajs.cn/list=b_DAX'
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn'
        }, timeout=10)
        response.encoding = 'gbk'
        m = re.search(r'"([^"]+)"', response.text)
        if m:
            fields = m.group(1).split(',')
            if len(fields) >= 12 and fields[1]:
                price = float(fields[1])
                high = float(fields[10]) if fields[10] else price
                low = float(fields[11]) if fields[11] else price
                # b_DAX 没有可靠的昨收，用东方财富的 f60 逻辑代替
                # 先用 (today_high + today_low) / 2 近似不行，放弃 prev_close
                # 返回 price，prev_close 由 DB 历史补充
                return {'price': price, 'prev_close': None,
                        'change_pct': None, 'source': 'sina_b_DAX'}
    except Exception:
        pass
    return None


def get_cac_index_realtime():
    """获取法国CAC40指数实时数据（多源 fallback）"""
    for fn in [_cac_idx_from_eastmoney, _cac_idx_from_eastmoney_curl, _cac_idx_from_sina]:
        result = fn()
        if result:
            return result
    return None


def _cac_idx_from_eastmoney():
    """东方财富 CAC40 指数 (requests)"""
    try:
        url = 'https://push2.eastmoney.com/api/qt/stock/get?secid=100.FCHI&fields=f43,f60,f170'
        resp = requests.get(url, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
        return _parse_eastmoney_nk_idx(resp.json().get('data', {}))
    except Exception:
        return None


def _cac_idx_from_eastmoney_curl():
    """东方财富 CAC40 via curl"""
    try:
        import subprocess as _sp
        url = 'https://push2.eastmoney.com/api/qt/stock/get?secid=100.FCHI&fields=f43,f60,f170'
        r = _sp.run(['curl', '-s', '--noproxy', '*', '--max-time', '8', url],
                     capture_output=True, text=True, timeout=12)
        if r.returncode == 0 and r.stdout.strip():
            return _parse_eastmoney_nk_idx(json.loads(r.stdout).get('data', {}))
    except Exception:
        pass
    return None


def _cac_idx_from_sina():
    """新浪 b_CAC 指数"""
    try:
        url = 'https://hq.sinajs.cn/list=b_CAC'
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn'
        }, timeout=10)
        response.encoding = 'gbk'
        m = re.search(r'"([^"]+)"', response.text)
        if m:
            fields = m.group(1).split(',')
            if len(fields) >= 4 and fields[1]:
                price = float(fields[1])
                change_amt = float(fields[2]) if fields[2] else None
                prev_close = (price - change_amt) if change_amt is not None else None
                change_pct = float(fields[3]) if fields[3] else None
                return {'price': price, 'prev_close': prev_close,
                        'change_pct': change_pct, 'source': 'sina_b_CAC'}
    except Exception:
        pass
    return None


def get_sensex_index_realtime():
    """获取印度SENSEX指数实时数据（多源 fallback）"""
    for fn in [_sensex_idx_from_eastmoney, _sensex_idx_from_eastmoney_curl, _sensex_idx_from_sina]:
        result = fn()
        if result:
            return result
    return None


def _sensex_idx_from_eastmoney():
    """东方财富 SENSEX 指数 (requests)"""
    try:
        url = 'https://push2.eastmoney.com/api/qt/stock/get?secid=100.SENSEX&fields=f43,f60,f170'
        resp = requests.get(url, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
        return _parse_eastmoney_nk_idx(resp.json().get('data', {}))
    except Exception:
        return None


def _sensex_idx_from_eastmoney_curl():
    """东方财富 SENSEX via curl"""
    try:
        import subprocess as _sp
        url = 'https://push2.eastmoney.com/api/qt/stock/get?secid=100.SENSEX&fields=f43,f60,f170'
        r = _sp.run(['curl', '-s', '--noproxy', '*', '--max-time', '8', url],
                     capture_output=True, text=True, timeout=12)
        if r.returncode == 0 and r.stdout.strip():
            return _parse_eastmoney_nk_idx(json.loads(r.stdout).get('data', {}))
    except Exception:
        pass
    return None


def _sensex_idx_from_sina():
    """新浪 b_SENSEX 指数"""
    try:
        url = 'https://hq.sinajs.cn/list=b_SENSEX'
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn'
        }, timeout=10)
        response.encoding = 'gbk'
        m = re.search(r'"([^"]+)"', response.text)
        if m:
            fields = m.group(1).split(',')
            if len(fields) >= 4 and fields[1]:
                price = float(fields[1])
                change_amt = float(fields[2]) if fields[2] else None
                prev_close = (price - change_amt) if change_amt is not None else None
                change_pct = float(fields[3]) if fields[3] else None
                return {'price': price, 'prev_close': prev_close,
                        'change_pct': change_pct, 'source': 'sina_b_SENSEX'}
    except Exception:
        pass
    return None


def _get_sox_realtime():
    """获取SOX半导体指数实时数据（新浪 gb_$sox，美股行情格式）"""
    try:
        url = 'https://hq.sinajs.cn/list=gb_$sox'
        resp = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://finance.sina.com.cn'
        }, timeout=10)
        resp.encoding = 'gbk'
        m = re.search(r'"([^"]+)"', resp.text)
        if not m:
            return None
        f = m.group(1).split(',')
        if len(f) < 27 or not f[1]:
            return None
        price = float(f[1])
        prev_close = float(f[26]) if f[26] else price
        change_pct = ((price - prev_close) / prev_close * 100) if prev_close > 0 else 0
        return {'price': price, 'prev_close': prev_close, 'change_pct': change_pct, 'source': 'sina_gb_sox'}
    except Exception:
        return None


def get_futures_history_from_sina(symbol):
    """从新浪获取期货历史日K线（真实美股收盘价）
    返回: [{date, close}, ...] 按日期升序
    """
    try:
        url = f"https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_{symbol}=/GlobalFuturesService.getGlobalFuturesDailyKLine?symbol={symbol}"
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://finance.sina.com.cn'
        }, timeout=15)
        response.encoding = 'utf-8'
        m = re.search(r'=\((\[.*\])\)', response.text)
        if not m:
            return []
        import json as _json
        data = _json.loads(m.group(1))
        return [{'date': d['date'], 'close': float(d['close'])} for d in data if d.get('close')]
    except Exception:
        return []


def backfill_futures_history(days=30):
    """从新浪回补历史期货收盘价 (真实美股收盘价)。

    为最近 N 天的每个交易日回写 futures_data:
      - us_date = Sina 日期
      - nq_close / es_close / ym_close = 当日真收盘价
      - nq_prev_close / es_prev_close / ym_prev_close = 前一交易日真收盘价
    只回补字段为空的历史行，今日实时数据不覆盖。
    """
    all_hist = {}
    for sym in ['NQ', 'ES', 'YM', 'NK']:
        all_hist[sym] = get_futures_history_from_sina(sym)

    if not any(all_hist.values()):
        return 0

    merged = {}
    for sym, hist in all_hist.items():
        col = sym.lower()
        for i, d in enumerate(hist):
            merged.setdefault(d['date'], {})[f'{col}_close'] = d['close']
            if i > 0:
                merged[d['date']][f'{col}_prev_close'] = hist[i - 1]['close']

    # 只保留最近 days 个交易日
    recent_dates = sorted(merged.keys())[-days:]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    today_str = datetime.now().strftime('%Y-%m-%d')
    updated = 0
    for date_str in recent_dates:
        if date_str >= today_str:
            continue  # 不覆盖今日实时数据
        rec = merged[date_str]
        cursor.execute("SELECT date FROM futures_data WHERE date = ?", (date_str,))
        if cursor.fetchone():
            cursor.execute("""
                UPDATE futures_data
                SET us_date = ?,
                    nq_close = COALESCE(?, nq_close), nq_prev_close = COALESCE(?, nq_prev_close),
                    es_close = COALESCE(?, es_close), es_prev_close = COALESCE(?, es_prev_close),
                    ym_close = COALESCE(?, ym_close), ym_prev_close = COALESCE(?, ym_prev_close),
                    nk_close = COALESCE(?, nk_close), nk_prev_close = COALESCE(?, nk_prev_close)
                WHERE date = ?
            """, (date_str,
                  rec.get('nq_close'), rec.get('nq_prev_close'),
                  rec.get('es_close'), rec.get('es_prev_close'),
                  rec.get('ym_close'), rec.get('ym_prev_close'),
                  rec.get('nk_close'), rec.get('nk_prev_close'),
                  date_str))
        else:
            cursor.execute("""
                INSERT INTO futures_data
                (date, us_date, nq_close, nq_prev_close, es_close, es_prev_close,
                 ym_close, ym_prev_close, nk_close, nk_prev_close,
                 nq_source, es_source, ym_source, nk_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'sina_hist', 'sina_hist', 'sina_hist', 'sina_hist')
            """, (date_str, date_str,
                  rec.get('nq_close'), rec.get('nq_prev_close'),
                  rec.get('es_close'), rec.get('es_prev_close'),
                  rec.get('ym_close'), rec.get('ym_prev_close'),
                  rec.get('nk_close'), rec.get('nk_prev_close')))
        updated += 1

    conn.commit()
    conn.close()
    return updated


def backfill_nikkei_index_history(days=30):
    """从东方财富回补日经225指数历史收盘价到 futures_data 的 nk_idx_close 列"""
    try:
        url = ('https://push2his.eastmoney.com/api/qt/stock/kline/get'
               '?secid=100.N225&fields1=f1&fields2=f51,f52,f53&klt=101&fqt=0'
               f'&beg=0&end=0&lmt={days + 5}')
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        klines = resp.json().get('data', {}).get('klines', [])
    except Exception:
        try:
            import subprocess as _sp
            r = _sp.run(['curl', '-s', '--noproxy', '*', '--max-time', '15', url],
                        capture_output=True, text=True, timeout=20)
            klines = json.loads(r.stdout).get('data', {}).get('klines', []) if r.returncode == 0 else []
        except Exception:
            return 0

    if len(klines) < 2:
        return 0

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    today_str = datetime.now().strftime('%Y-%m-%d')
    updated = 0
    for i, kl in enumerate(klines):
        parts = kl.split(',')
        date_str, close = parts[0], float(parts[2])
        prev_close = float(klines[i - 1].split(',')[2]) if i > 0 else None
        if date_str >= today_str:
            continue
        cursor.execute("SELECT date FROM futures_data WHERE date = ?", (date_str,))
        if cursor.fetchone():
            cursor.execute("""
                UPDATE futures_data
                SET nk_idx_close = COALESCE(?, nk_idx_close),
                    nk_idx_prev_close = COALESCE(?, nk_idx_prev_close)
                WHERE date = ?
            """, (close, prev_close, date_str))
        else:
            cursor.execute("""
                INSERT INTO futures_data (date, us_date, nk_idx_close, nk_idx_prev_close)
                VALUES (?, ?, ?, ?)
            """, (date_str, date_str, close, prev_close))
        updated += 1

    conn.commit()
    conn.close()
    return updated


def backfill_dax_index_history(days=30):
    """从东方财富回补DAX指数历史收盘价到 futures_data 的 dax_idx_close 列"""
    try:
        url = ('https://push2his.eastmoney.com/api/qt/stock/kline/get'
               '?secid=100.GDAXI&fields1=f1&fields2=f51,f52,f53&klt=101&fqt=0'
               f'&beg=0&end=0&lmt={days + 5}')
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        klines = resp.json().get('data', {}).get('klines', [])
    except Exception:
        try:
            import subprocess as _sp
            r = _sp.run(['curl', '-s', '--noproxy', '*', '--max-time', '15', url],
                        capture_output=True, text=True, timeout=20)
            klines = json.loads(r.stdout).get('data', {}).get('klines', []) if r.returncode == 0 else []
        except Exception:
            return 0

    if len(klines) < 2:
        return 0

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    today_str = datetime.now().strftime('%Y-%m-%d')
    updated = 0
    for i, kl in enumerate(klines):
        parts = kl.split(',')
        date_str, close = parts[0], float(parts[2])
        prev_close = float(klines[i - 1].split(',')[2]) if i > 0 else None
        if date_str >= today_str:
            continue
        cursor.execute("SELECT date FROM futures_data WHERE date = ?", (date_str,))
        if cursor.fetchone():
            cursor.execute("""
                UPDATE futures_data
                SET dax_idx_close = COALESCE(?, dax_idx_close),
                    dax_idx_prev_close = COALESCE(?, dax_idx_prev_close)
                WHERE date = ?
            """, (close, prev_close, date_str))
        else:
            cursor.execute("""
                INSERT INTO futures_data (date, us_date, dax_idx_close, dax_idx_prev_close)
                VALUES (?, ?, ?, ?)
            """, (date_str, date_str, close, prev_close))
        updated += 1

    conn.commit()
    conn.close()
    return updated


def backfill_cac_index_history(days=30):
    """从东方财富回补CAC40指数历史收盘价到 futures_data 的 cac_idx_close 列"""
    try:
        url = ('https://push2his.eastmoney.com/api/qt/stock/kline/get'
               '?secid=100.FCHI&fields1=f1&fields2=f51,f52,f53&klt=101&fqt=0'
               f'&beg=0&end=0&lmt={days + 5}')
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        klines = resp.json().get('data', {}).get('klines', [])
    except Exception:
        try:
            import subprocess as _sp
            r = _sp.run(['curl', '-s', '--noproxy', '*', '--max-time', '15', url],
                        capture_output=True, text=True, timeout=20)
            klines = json.loads(r.stdout).get('data', {}).get('klines', []) if r.returncode == 0 else []
        except Exception:
            return 0

    if len(klines) < 2:
        return 0

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    today_str = datetime.now().strftime('%Y-%m-%d')
    updated = 0
    for i, kl in enumerate(klines):
        parts = kl.split(',')
        date_str, close = parts[0], float(parts[2])
        prev_close = float(klines[i - 1].split(',')[2]) if i > 0 else None
        if date_str >= today_str:
            continue
        cursor.execute("SELECT date FROM futures_data WHERE date = ?", (date_str,))
        if cursor.fetchone():
            cursor.execute("""
                UPDATE futures_data
                SET cac_idx_close = COALESCE(?, cac_idx_close),
                    cac_idx_prev_close = COALESCE(?, cac_idx_prev_close)
                WHERE date = ?
            """, (close, prev_close, date_str))
        else:
            cursor.execute("""
                INSERT INTO futures_data (date, us_date, cac_idx_close, cac_idx_prev_close)
                VALUES (?, ?, ?, ?)
            """, (date_str, date_str, close, prev_close))
        updated += 1

    conn.commit()
    conn.close()
    return updated


def backfill_sensex_index_history(days=30):
    """从东方财富回补SENSEX指数历史收盘价到 futures_data 的 sensex_idx_close 列"""
    try:
        url = ('https://push2his.eastmoney.com/api/qt/stock/kline/get'
               '?secid=100.SENSEX&fields1=f1&fields2=f51,f52,f53&klt=101&fqt=0'
               f'&beg=0&end=0&lmt={days + 5}')
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        klines = resp.json().get('data', {}).get('klines', [])
    except Exception:
        try:
            import subprocess as _sp
            r = _sp.run(['curl', '-s', '--noproxy', '*', '--max-time', '15', url],
                        capture_output=True, text=True, timeout=20)
            klines = json.loads(r.stdout).get('data', {}).get('klines', []) if r.returncode == 0 else []
        except Exception:
            return 0

    if len(klines) < 2:
        return 0

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    today_str = datetime.now().strftime('%Y-%m-%d')
    updated = 0
    for i, kl in enumerate(klines):
        parts = kl.split(',')
        date_str, close = parts[0], float(parts[2])
        prev_close = float(klines[i - 1].split(',')[2]) if i > 0 else None
        if date_str >= today_str:
            continue
        cursor.execute("SELECT date FROM futures_data WHERE date = ?", (date_str,))
        if cursor.fetchone():
            cursor.execute("""
                UPDATE futures_data
                SET sensex_idx_close = COALESCE(?, sensex_idx_close),
                    sensex_idx_prev_close = COALESCE(?, sensex_idx_prev_close)
                WHERE date = ?
            """, (close, prev_close, date_str))
        else:
            cursor.execute("""
                INSERT INTO futures_data (date, us_date, sensex_idx_close, sensex_idx_prev_close)
                VALUES (?, ?, ?, ?)
            """, (date_str, date_str, close, prev_close))
        updated += 1

    conn.commit()
    conn.close()
    return updated


def backfill_sox_index_history(days=30):
    """回补SOX半导体指数历史数据到 futures_data

    数据源优先级:
    1. 东方财富 SOXX ETF K线 (SOX 指数无直接API，用 SOXX ETF 近似)
    2. NQ 比率推算 (fallback)

    注: SOX 与 SOXX 高度相关（相关系数 > 0.99），用 SOXX 的涨跌率反推 SOX
    """
    # 用当前 SOX 实时价格作为锚点，回推历史
    sox_current = _get_sox_realtime()
    if not sox_current:
        return 0

    sox_price_today = sox_current['price']
    sox_prev_today = sox_current.get('prev_close')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 获取有 NQ 数据但没有 SOX 数据的日期
    cursor.execute("""
        SELECT date, nq_close, nq_prev_close FROM futures_data
        WHERE nq_close IS NOT NULL AND (sox_idx_close IS NULL OR sox_idx_close = 0)
        ORDER BY date DESC LIMIT ?
    """, (days + 5,))

    rows = cursor.fetchall()
    if not rows:
        conn.close()
        return 0

    # 获取最新 NQ 作为锚点比率
    cursor.execute("SELECT nq_close FROM futures_data WHERE nq_close IS NOT NULL ORDER BY date DESC LIMIT 1")
    nq_latest = cursor.fetchone()
    if not nq_latest:
        conn.close()
        return 0

    nq_latest_close = nq_latest[0]
    sox_nq_ratio = sox_price_today / nq_latest_close

    updated = 0
    for row in rows:
        date_str, nq_close, nq_prev = row
        est_sox = nq_close * sox_nq_ratio
        est_sox_prev = nq_prev * sox_nq_ratio if nq_prev else None

        cursor.execute("""
            UPDATE futures_data
            SET sox_idx_close = COALESCE(sox_idx_close, ?),
                sox_idx_prev_close = COALESCE(sox_idx_prev_close, ?)
            WHERE date = ?
        """, (est_sox, est_sox_prev, date_str))
        updated += 1

    conn.commit()
    conn.close()
    return updated


def save_futures_data(date, nq_change, es_change, ym_change=None,
                      nq_close=None, es_close=None, ym_close=None,
                      nq_prev_close=None, es_prev_close=None, ym_prev_close=None,
                      us_date=None, nq_source='sina', es_source='sina', ym_source='sina',
                      nk_change=None, nk_close=None, nk_prev_close=None, nk_source='sina',
                      nk_idx_close=None, nk_idx_prev_close=None, nk_idx_change=None,
                      dax_idx_close=None, dax_idx_prev_close=None, dax_idx_change=None,
                      gc_close=None, gc_prev_close=None, gc_change=None, gc_source='sina',
                      cl_close=None, cl_prev_close=None, cl_change=None, cl_source='sina',
                      cac_idx_close=None, cac_idx_prev_close=None, cac_idx_change=None,
                      sensex_idx_close=None, sensex_idx_prev_close=None, sensex_idx_change=None,
                      sox_idx_close=None, sox_idx_prev_close=None, sox_idx_change=None):
    """保存期货数据到数据库（NQ/ES/YM/NK/GC/CL期货用 INSERT OR REPLACE）"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 美股 + NK/GC/CL期货：INSERT OR REPLACE
        cursor.execute("""
            INSERT OR REPLACE INTO futures_data
            (date, us_date, nq_close, nq_prev_close, nq_change_pct,
             es_close, es_prev_close, es_change_pct,
             ym_close, ym_prev_close, ym_change_pct,
             nk_close, nk_prev_close, nk_change_pct,
             gc_close, gc_prev_close, gc_change_pct,
             cl_close, cl_prev_close, cl_change_pct,
             nq_source, es_source, ym_source, nk_source, gc_source, cl_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (date, us_date, nq_close, nq_prev_close, nq_change,
              es_close, es_prev_close, es_change,
              ym_close, ym_prev_close, ym_change,
              nk_close, nk_prev_close, nk_change,
              gc_close, gc_prev_close, gc_change,
              cl_close, cl_prev_close, cl_change,
              nq_source, es_source, ym_source, nk_source, gc_source, cl_source))

        # 日经指数 + DAX指数 + CAC指数 + SENSEX指数：单独 UPDATE + COALESCE
        if nk_idx_close is not None:
            cursor.execute("""
                UPDATE futures_data
                SET nk_idx_close = COALESCE(nk_idx_close, ?),
                    nk_idx_prev_close = COALESCE(nk_idx_prev_close, ?),
                    nk_idx_change_pct = COALESCE(nk_idx_change_pct, ?)
                WHERE date = ?
            """, (nk_idx_close, nk_idx_prev_close, nk_idx_change, date))
        if dax_idx_close is not None:
            cursor.execute("""
                UPDATE futures_data
                SET dax_idx_close = COALESCE(dax_idx_close, ?),
                    dax_idx_prev_close = COALESCE(dax_idx_prev_close, ?),
                    dax_idx_change_pct = COALESCE(dax_idx_change_pct, ?)
                WHERE date = ?
            """, (dax_idx_close, dax_idx_prev_close, dax_idx_change, date))
        if cac_idx_close is not None:
            cursor.execute("""
                UPDATE futures_data
                SET cac_idx_close = COALESCE(cac_idx_close, ?),
                    cac_idx_prev_close = COALESCE(cac_idx_prev_close, ?),
                    cac_idx_change_pct = COALESCE(cac_idx_change_pct, ?)
                WHERE date = ?
            """, (cac_idx_close, cac_idx_prev_close, cac_idx_change, date))
        if sensex_idx_close is not None:
            cursor.execute("""
                UPDATE futures_data
                SET sensex_idx_close = COALESCE(sensex_idx_close, ?),
                    sensex_idx_prev_close = COALESCE(sensex_idx_prev_close, ?),
                    sensex_idx_change_pct = COALESCE(sensex_idx_change_pct, ?)
                WHERE date = ?
            """, (sensex_idx_close, sensex_idx_prev_close, sensex_idx_change, date))
        if sox_idx_close is not None:
            cursor.execute("""
                UPDATE futures_data
                SET sox_idx_close = COALESCE(sox_idx_close, ?),
                    sox_idx_prev_close = COALESCE(sox_idx_prev_close, ?),
                    sox_idx_change_pct = COALESCE(sox_idx_change_pct, ?)
                WHERE date = ?
            """, (sox_idx_close, sox_idx_prev_close, sox_idx_change, date))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"保存期货数据失败: {e}")
        return False


# ============= 持仓 + 美股价格 =============

def fetch_holdings_from_eastmoney(fund_code):
    """从东方财富获取基金持仓 Top10
    返回: [{'ticker': 'AAPL', 'stock_name': '苹果', 'weight_pct': 12.31}, ...]
    """
    try:
        url = f'https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc&code={fund_code}&topline=10&year=&month=&rt=0.123'
        resp = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://fundf10.eastmoney.com/'
        }, timeout=15)
        resp.encoding = 'utf-8'

        from html.parser import HTMLParser
        class _P(HTMLParser):
            def __init__(self):
                super().__init__()
                self.rows = []; self.cur = []; self.in_td = False; self.in_tbody = False; self.td = ""
            def handle_starttag(self, t, a):
                if t == 'tbody': self.in_tbody = True
                if t == 'td' and self.in_tbody: self.in_td = True; self.td = ""
            def handle_endtag(self, t):
                if t == 'td': self.in_td = False; self.cur.append(self.td.strip())
                if t == 'tr' and self.cur: self.rows.append(self.cur[:]); self.cur = []
                if t == 'tbody': self.in_tbody = False
            def handle_data(self, d):
                if self.in_td: self.td += d.strip()

        start = resp.text.find('content:"') + 9
        end = resp.text.find('",aression')
        p = _P()
        p.feed(resp.text[start:end])

        holdings = []
        for r in p.rows:
            if len(r) >= 7 and r[0].isdigit():
                ticker = r[1].strip()
                name = r[2].strip()
                try:
                    weight = float(r[6].rstrip('%'))
                except ValueError:
                    continue
                holdings.append({'ticker': ticker, 'stock_name': name, 'weight_pct': weight})
        return holdings
    except Exception as e:
        print(f"  获取持仓失败 {fund_code}: {e}")
        return []


def save_holdings(fund_code, holdings, report_date=None):
    """保存持仓到 fund_holdings 表"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM fund_holdings WHERE fund_code = ?", (fund_code,))
    rd = report_date or datetime.now().strftime('%Y-%m-%d')
    for h in holdings:
        c.execute("""
            INSERT INTO fund_holdings (fund_code, ticker, stock_name, weight_pct, report_date)
            VALUES (?, ?, ?, ?, ?)
        """, (fund_code, h['ticker'], h['stock_name'], h['weight_pct'], rd))
    conn.commit()
    conn.close()
    return len(holdings)


def fetch_us_stock_prices(tickers):
    """新浪批量获取美股价格
    返回: {'AAPL': {'price': 293.32, 'prev_close': 287.44, 'after_hours': 0, 'change_pct': 2.05}, ...}
    """
    if not tickers:
        return {}
    symbols = ','.join(f'gb_{t.lower()}' for t in tickers)
    try:
        resp = requests.get(f'https://hq.sinajs.cn/list={symbols}', headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://finance.sina.com.cn'
        }, timeout=15)
        resp.encoding = 'gbk'

        result = {}
        for line in resp.text.strip().split('\n'):
            m = re.search(r'gb_(\w+)="([^"]+)"', line)
            if not m:
                continue
            sym = m.group(1).upper()
            f = m.group(2).split(',')
            if len(f) < 27 or not f[1]:
                continue
            try:
                price = float(f[1])
                prev_close = float(f[26]) if f[26] else price
                after_hours = float(f[17]) if len(f) > 17 and f[17] and float(f[17]) > 0 else 0
                change_pct = ((price - prev_close) / prev_close * 100) if prev_close > 0 else 0
                result[sym] = {
                    'price': price, 'prev_close': prev_close,
                    'after_hours': after_hours, 'change_pct': change_pct
                }
            except (ValueError, ZeroDivisionError):
                continue
        return result
    except Exception as e:
        print(f"  获取美股价格失败: {e}")
        return {}


def save_stock_prices(prices):
    """保存美股价格到 stock_prices 表"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for ticker, p in prices.items():
        c.execute("""
            INSERT OR REPLACE INTO stock_prices (ticker, price, prev_close, after_hours, change_pct, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ticker, p['price'], p['prev_close'], p['after_hours'], p['change_pct'], now))
    conn.commit()
    conn.close()


def _is_hk_ticker(ticker):
    """判断是否为港股代码（5位纯数字，如 00700/09988/00883）"""
    return len(ticker) == 5 and ticker.isdigit()


def _fetch_hk_from_sina(tickers):
    """新浪 rt_hk 批量获取港股价格"""
    symbols = ','.join(f'rt_hk{t}' for t in tickers)
    resp = requests.get(f'https://hq.sinajs.cn/list={symbols}', headers={
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://finance.sina.com.cn'
    }, timeout=15)
    resp.encoding = 'gbk'

    result = {}
    for line in resp.text.strip().split('\n'):
        m = re.search(r'rt_hk(\d+)="([^"]+)"', line)
        if not m:
            continue
        code = m.group(1)
        f = m.group(2).split(',')
        if len(f) < 10 or not f[6]:
            continue
        price = float(f[6])
        prev_close = float(f[3]) if f[3] else price
        change_pct = ((price - prev_close) / prev_close * 100) if prev_close > 0 else 0
        result[code] = {
            'price': price, 'prev_close': prev_close,
            'after_hours': 0, 'change_pct': change_pct
        }
    return result


def _fetch_hk_from_tencent(tickers):
    """腾讯 r_hk 批量获取港股价格"""
    symbols = ','.join(f'r_hk{t}' for t in tickers)
    resp = requests.get(f'http://qt.gtimg.cn/q={symbols}', headers={
        'User-Agent': 'Mozilla/5.0'
    }, timeout=15)
    resp.encoding = 'gbk'

    result = {}
    for line in resp.text.strip().split(';'):
        if '~' not in line or 'none_match' in line:
            continue
        parts = line.split('~')
        if len(parts) < 33 or not parts[3]:
            continue
        code = parts[2]
        try:
            price = float(parts[3])
            prev_close = float(parts[4]) if parts[4] else price
            change_pct = float(parts[32]) if parts[32] else ((price - prev_close) / prev_close * 100)
            result[code] = {
                'price': price, 'prev_close': prev_close,
                'after_hours': 0, 'change_pct': change_pct
            }
        except (ValueError, ZeroDivisionError):
            continue
    return result


def fetch_hk_stock_prices(tickers):
    """批量获取港股价格（新浪 → 腾讯 fallback）
    返回: {'00700': {'price': 465.0, 'prev_close': 471.4, 'change_pct': -1.36}, ...}
    """
    if not tickers:
        return {}
    for fn in [_fetch_hk_from_sina, _fetch_hk_from_tencent]:
        try:
            result = fn(tickers)
            if result:
                return result
        except Exception:
            continue
    return {}


def update_all_holdings_prices():
    """更新所有 holdings 型基金的持仓股票价格（美股 + 港股）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 获取所有需要持仓估算的基金
    holdings_funds = conn.execute(
        "SELECT code FROM fund_config WHERE estimate_method='holdings' AND enabled=1"
    ).fetchall()

    if not holdings_funds:
        conn.close()
        return

    # 收集所有唯一的 ticker，分 US / HK
    us_tickers = set()
    hk_tickers = set()
    for f in holdings_funds:
        rows = conn.execute("SELECT ticker FROM fund_holdings WHERE fund_code=?", (f['code'],)).fetchall()
        for r in rows:
            t = r['ticker']
            if _is_hk_ticker(t):
                hk_tickers.add(t)
            else:
                us_tickers.add(t)
    conn.close()

    all_prices = {}

    # 美股
    if us_tickers:
        prices = fetch_us_stock_prices(list(us_tickers))
        if prices:
            all_prices.update(prices)
            print(f"  美股价格: 更新 {len(prices)} 只 ({', '.join(list(prices.keys())[:5])}...)")

    # 港股
    if hk_tickers:
        prices = fetch_hk_stock_prices(list(hk_tickers))
        if prices:
            all_prices.update(prices)
            print(f"  港股价格: 更新 {len(prices)} 只 ({', '.join(list(prices.keys())[:5])}...)")

    if all_prices:
        save_stock_prices(all_prices)


def estimate_nav_by_holdings(fund_code, confirmed_nav):
    """用持仓股票涨跌估算 NAV
    返回: (estimated_nav, change_pct) 或 (confirmed_nav, 0)
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    holdings = conn.execute(
        "SELECT ticker, weight_pct FROM fund_holdings WHERE fund_code=?", (fund_code,)
    ).fetchall()
    prices = {r['ticker']: r for r in conn.execute("SELECT * FROM stock_prices").fetchall()}
    conn.close()

    if not holdings:
        return confirmed_nav, 0

    total_weight = sum(h['weight_pct'] for h in holdings)
    matched_weight = 0
    weighted_change = 0

    for h in holdings:
        p = prices.get(h['ticker'])
        if p and p['change_pct'] is not None:
            weighted_change += h['weight_pct'] * p['change_pct']
            matched_weight += h['weight_pct']

    if matched_weight == 0:
        return confirmed_nav, 0

    # 归一化：用匹配到的权重占比
    est_change = weighted_change / matched_weight
    est_nav = confirmed_nav * (1 + est_change / 100)
    return est_nav, est_change


def update_subscription_status():
    """查询所有LOF的申购/赎回状态（每天12点后查一次）"""
    now = datetime.now()
    if now.hour < 12:
        return
    conn = sqlite3.connect(DB_PATH)
    today = now.strftime('%Y-%m-%d')
    last = conn.execute("SELECT value FROM admin_config WHERE key='sub_status_date'").fetchone()
    if last and last[0] == today:
        conn.close()
        return
    lofs = conn.execute("SELECT code FROM fund_config WHERE category IN ('LOF','OTHERS') AND enabled=1").fetchall()
    conn.close()
    if not lofs:
        return

    updated = 0
    for row in lofs:
        code = row[0]
        try:
            url = f'https://fund.eastmoney.com/{code}.html'
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
            resp.encoding = 'utf-8'
            text = resp.text

            status = 'unknown'
            limit_text = None
            # 从"交易状态"区域提取，避免新闻标题中的关键词干扰
            trade_section = ''
            m_trade = re.search(r'交易状态[：:](.*?)(?:</div>|</td>)', text)
            if m_trade:
                trade_section = m_trade.group(1)

            if '暂停申购' in trade_section:
                status = 'closed'
            elif '限大额' in trade_section:
                status = 'limited'
                m = re.search(r'限大额.*?([\d,.]+万?元?)', trade_section)
                if m:
                    limit_text = m.group(1)
                m2 = re.search(r'上限([\d,.]+万?元?)', trade_section)
                if m2 and not limit_text:
                    limit_text = m2.group(1)
            elif '开放申购' in trade_section or '正常申购' in trade_section:
                status = 'open'
            elif '暂停申购' in text and '限大额' not in text:
                # fallback: 全文匹配但排除"限大额"（限大额≠暂停）
                status = 'closed'

            conn = sqlite3.connect(DB_PATH)
            conn.execute("UPDATE fund_config SET subscription_status=?, subscription_limit=? WHERE code=?",
                         (status, limit_text, code))
            conn.commit()
            conn.close()
            updated += 1
        except Exception:
            pass

    if updated:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT OR REPLACE INTO admin_config (key, value) VALUES ('sub_status_date', ?)", (today,))
        conn.commit()
        conn.close()
        print(f"  申购状态: 更新 {updated} 只LOF")


# ============= 数据库操作 =============
def init_database():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ETF数据表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS etf_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            company TEXT NOT NULL,
            price REAL,
            prev_close REAL,
            nav REAL,
            premium_rate REAL,
            change_pct REAL,
            nav_type TEXT,
            nav_date TEXT,
            is_fixed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, code)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_date_code ON etf_data(date, code)")

    # 为已存在的数据库添加新字段（向后兼容）
    try:
        cursor.execute("ALTER TABLE etf_data ADD COLUMN nav_date TEXT")
    except Exception:
        pass  # 字段已存在
    try:
        cursor.execute("ALTER TABLE etf_data ADD COLUMN is_fixed INTEGER DEFAULT 0")
    except Exception:
        pass  # 字段已存在
    try:
        cursor.execute("ALTER TABLE etf_data ADD COLUMN prev_close REAL")
    except Exception:
        pass  # 字段已存在
    try:
        cursor.execute("ALTER TABLE etf_data ADD COLUMN change_pct REAL")
    except Exception:
        pass  # 字段已存在

    # 期货/指数数据表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS futures_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            us_date TEXT,
            nq_close REAL,
            nq_prev_close REAL,
            nq_change_pct REAL,
            es_close REAL,
            es_prev_close REAL,
            es_change_pct REAL,
            nq_source TEXT,
            es_source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 添加 prev_close 字段（如果不存在）
    try:
        cursor.execute("ALTER TABLE futures_data ADD COLUMN nq_prev_close REAL")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE futures_data ADD COLUMN es_prev_close REAL")
    except Exception:
        pass

    # 添加 us_date 字段（如果不存在）- 美股交易日
    try:
        cursor.execute("ALTER TABLE futures_data ADD COLUMN us_date TEXT")
    except Exception:
        pass

    # 创建 us_date 索引以提高查询效率
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_us_date ON futures_data(us_date)")
    except Exception:
        pass

    # 添加 NK (日经期货) 字段
    for col in ['nk_close', 'nk_prev_close', 'nk_change_pct', 'nk_source']:
        try:
            col_type = 'TEXT' if 'source' in col else 'REAL'
            cursor.execute(f"ALTER TABLE futures_data ADD COLUMN {col} {col_type}")
        except Exception:
            pass

    # 添加日经225指数 + DAX指数字段
    for col in ['nk_idx_close', 'nk_idx_prev_close', 'nk_idx_change_pct',
                'dax_idx_close', 'dax_idx_prev_close', 'dax_idx_change_pct']:
        try:
            cursor.execute(f"ALTER TABLE futures_data ADD COLUMN {col} REAL")
        except Exception:
            pass

    # 添加 GC/CL 期货字段
    for col in ['gc_close', 'gc_prev_close', 'gc_change_pct', 'gc_source',
                'cl_close', 'cl_prev_close', 'cl_change_pct', 'cl_source']:
        try:
            col_type = 'TEXT' if 'source' in col else 'REAL'
            cursor.execute(f"ALTER TABLE futures_data ADD COLUMN {col} {col_type}")
        except Exception:
            pass

    # 添加 CAC40 + SENSEX 指数字段
    for col in ['cac_idx_close', 'cac_idx_prev_close', 'cac_idx_change_pct',
                'sensex_idx_close', 'sensex_idx_prev_close', 'sensex_idx_change_pct']:
        try:
            cursor.execute(f"ALTER TABLE futures_data ADD COLUMN {col} REAL")
        except Exception:
            pass

    # 添加 SOX 半导体指数字段
    for col in ['sox_idx_close', 'sox_idx_prev_close', 'sox_idx_change_pct']:
        try:
            cursor.execute(f"ALTER TABLE futures_data ADD COLUMN {col} REAL")
        except Exception:
            pass

    # V2: 新表
    for ddl in [
        """CREATE TABLE IF NOT EXISTS fund_config (
            code TEXT PRIMARY KEY, name TEXT NOT NULL, company TEXT,
            category TEXT NOT NULL, market TEXT DEFAULT 'sz',
            estimate_method TEXT NOT NULL, estimate_symbol TEXT,
            enabled INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0,
            rotation_pool INTEGER DEFAULT 0, rotation_bonus REAL DEFAULT 0,
            sub_category TEXT,
            subscription_status TEXT,
            subscription_limit TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS fund_holdings (
            fund_code TEXT NOT NULL, ticker TEXT NOT NULL,
            stock_name TEXT, weight_pct REAL,
            market TEXT DEFAULT 'US', report_date TEXT,
            PRIMARY KEY (fund_code, ticker))""",
        """CREATE TABLE IF NOT EXISTS stock_prices (
            ticker TEXT PRIMARY KEY, price REAL, prev_close REAL,
            after_hours REAL, change_pct REAL, updated_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS admin_config (
            key TEXT PRIMARY KEY, value TEXT)""",
    ]:
        cursor.execute(ddl)

    conn.commit()
    conn.close()


def save_etf_records(records):
    """保存ETF数据
    records: 每个record可包含:
        - date: 爬取日期(A股交易日)
        - nav_date: 净值实际日期(美股收盘日), 可选
        - is_fixed: 是否为历史API确认数据, 可选(默认0)
        - prev_close: 昨收价, 可选
        - change_pct: API报告的涨跌幅, 可选
        - 其他字段: code, name, company, price, nav, premium_rate
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    saved = 0

    for r in records:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO etf_data
                (date, timestamp, code, name, company, price, prev_close, nav, premium_rate, change_pct, nav_type, nav_date, is_fixed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (r['date'], f"{r['date']}T15:00:00", r['code'], r['name'],
                  r['company'], r['price'], r.get('prev_close'), r.get('nav'), r.get('premium_rate'),
                  r.get('change_pct'), r.get('nav_type', 'actual'),
                  r.get('nav_date'),  # 净值实际日期
                  r.get('is_fixed', 0)))  # 是否为fixed数据
            saved += 1
        except Exception as e:
            print(f"保存记录失败 {r.get('code')}: {e}")

    conn.commit()
    conn.close()
    return saved


def calculate_index_changes():
    """从ETF净值变化计算指数涨跌"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 纳斯达克ETF
    nasdaq_codes = ['513100', '159941', '159660', '159501', '159632', '159659', '513300', '513870', '513390', '513110']
    # 标普500ETF
    sp500_codes = ['513500', '159655', '513650', '159612']

    # 获取所有日期
    cursor.execute("SELECT DISTINCT date FROM etf_data WHERE nav IS NOT NULL ORDER BY date")
    all_dates = [row[0] for row in cursor.fetchall()]

    futures_records = []

    for i, date in enumerate(all_dates):
        if i == 0:
            continue

        prev_date = all_dates[i - 1]

        # 获取NAV数据
        cursor.execute("SELECT code, nav FROM etf_data WHERE date = ?", (date,))
        current_navs = {row['code']: row['nav'] for row in cursor.fetchall()}
        cursor.execute("SELECT code, nav FROM etf_data WHERE date = ?", (prev_date,))
        prev_navs = {row['code']: row['nav'] for row in cursor.fetchall()}

        # 计算变化
        nasdaq_changes = []
        for code in nasdaq_codes:
            if code in current_navs and code in prev_navs and prev_navs[code] > 0:
                change = (current_navs[code] - prev_navs[code]) / prev_navs[code] * 100
                nasdaq_changes.append(change)

        sp500_changes = []
        for code in sp500_codes:
            if code in current_navs and code in prev_navs and prev_navs[code] > 0:
                change = (current_navs[code] - prev_navs[code]) / prev_navs[code] * 100
                sp500_changes.append(change)

        nq_change = sorted(nasdaq_changes)[len(nasdaq_changes)//2] if nasdaq_changes else None
        es_change = sorted(sp500_changes)[len(sp500_changes)//2] if sp500_changes else None

        if nq_change or es_change:
            futures_records.append({'date': date, 'nq_change_pct': nq_change, 'es_change_pct': es_change})

    # 保存期货数据
    for rec in futures_records:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO futures_data
                (date, nq_change_pct, es_change_pct, nq_source, es_source)
                VALUES (?, ?, ?, ?, ?)
            """, (rec['date'], rec['nq_change_pct'], rec['es_change_pct'], 'NAV_PROXY', 'NAV_PROXY'))
        except Exception:
            pass

    conn.commit()
    conn.close()

    return len(futures_records)


# ============= 主流程 =============
def update_history(days=90):
    """更新历史数据"""
    print("=" * 60)
    print(f"获取历史数据（{days}天）")
    print("=" * 60)

    all_records = []

    for etf in ETF_LIST:
        code, name, market = etf['code'], etf['name'], etf['market']

        print(f"\n{code} {name}...")

        # 尝试腾讯，失败则新浪
        history = get_tencent_history(code, market, days=days)
        source = "腾讯"

        if not history or len(history) == 0:
            history = get_sina_history(code, market, days=days)
            source = "新浪"

        if not history:
            print(f"  无历史数据")
            continue

        print(f"  获取 {len(history)} 条 (来源: {source})")

        # 获取历史NAV
        nav_map = get_historical_navs(code)
        print(f"  获取 {len(nav_map)} 条NAV")

        # 解析数据
        last_nav = None  # 用于继承最近的NAV
        for item in history:
            try:
                date_str = item[0]
                price = float(item[2]) if item[2] else None

                if not price:
                    continue

                nav = nav_map.get(date_str)

                # 如果当天没有NAV，使用最近一天的NAV
                if nav is None:
                    nav = last_nav
                    nav_source = 'inherited'
                else:
                    last_nav = nav
                    nav_source = 'actual'
                premium = ((price - nav) / nav * 100) if nav else None

                all_records.append({
                    'date': date_str, 'code': code, 'name': name,
                    'company': etf['company'], 'price': price,
                    'nav': nav, 'premium_rate': premium
                })
            except Exception:
                pass

    if all_records:
        saved = save_etf_records(all_records)
        print(f"\n历史数据: 保存 {saved} 条")

        # 计算指数涨跌
        futures_count = calculate_index_changes()
        print(f"指数涨跌: 更新 {futures_count} 条")


def update_history_fixed(days=120):
    """使用历史API获取数据并标记为fixed
    特点:
    - 价格使用腾讯/新浪API
    - 净值使用东方财富历史API(有实际日期)
    - nav_date存储净值实际日期(美股收盘日)
    - is_fixed=1标记为确认数据
    - 正确处理T+1机制(净值日期可能早于交易日)
    """
    print("=" * 60)
    print(f"获取历史确认数据（{days}天）")
    print("=" * 60)

    all_records = []
    today = datetime.now().date()

    for etf in ETF_LIST:
        code, name, market = etf['code'], etf['name'], etf['market']
        print(f"\n{code} {name}...")

        # 获取历史净值 {nav_actual_date: nav_value}
        # 注意: 东方财富API返回的日期是净值实际日期(美股收盘日)
        nav_map = get_historical_navs(code)
        print(f"  NAV: {len(nav_map)} 条")

        # 获取历史价格 [(date, ..., price, ...), ...]
        # 腾讯优先，失败则新浪
        history = get_tencent_history(code, market, days=days)
        source = "腾讯"
        if not history or len(history) == 0:
            history = get_sina_history(code, market, days=days)
            source = "新浪"

        if not history:
            print(f"  无历史价格数据")
            continue

        print(f"  价格: {len(history)} 条 (来源: {source})")

        # 净值日期排序(用于查找)
        nav_dates = sorted(nav_map.keys(), reverse=True)

        for item in history:
            try:
                trade_date = item[0]  # A股交易日
                price = float(item[2]) if item[2] else None

                if not price or price < 0.01:
                    continue

                # 限制天数范围
                dt = datetime.strptime(trade_date, '%Y-%m-%d').date()
                if (today - dt).days > days:
                    continue

                # 找到该交易日对应的最新可用净值
                # 规则: 使用 <= trade_date 的最新净值
                # 只有 date - nav_date >= 2 才是fixed(净值已公布)
                nav_date = None
                nav_value = None

                for nd in nav_dates:
                    if nd <= trade_date:  # 净值日期不能晚于交易日
                        nav_date = nd
                        nav_value = nav_map[nd]
                        break

                if not nav_value or nav_value < 0.01:
                    continue

                # 计算溢价率
                premium = ((price - nav_value) / nav_value * 100) if nav_value else None

                all_records.append({
                    'date': trade_date,       # A股交易日
                    'nav_date': nav_date,     # 净值实际日期(美股收盘日)
                    'is_fixed': 1,            # 历史API获取 = fixed
                    'code': code,
                    'name': name,
                    'company': etf['company'],
                    'price': price,           # 历史价格（腾讯/新浪）
                    'nav': nav_value,         # 历史净值（东方财富）
                    'premium_rate': premium,  # 计算的溢价率
                    'nav_type': 'actual'
                })
            except Exception as e:
                print(f"  处理日期 {item[0]} 失败: {e}")

    if all_records:
        saved = save_etf_records(all_records)
        print(f"\n确认数据: 保存 {saved} 条")

        # 计算指数涨跌
        futures_count = calculate_index_changes()
        print(f"指数涨跌: 更新 {futures_count} 条")
        return saved
    print(f"\n无数据保存")
    return 0


def _backfill_missing_days():
    """检查 DB 中最后一条记录的日期，如果距今超过 1 个交易日则补齐历史数据。"""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute('SELECT MAX(date) FROM etf_data').fetchone()
    conn.close()

    if not row or not row[0]:
        return

    last_date = datetime.strptime(row[0], '%Y-%m-%d').date()
    today = datetime.now().date()
    gap_days = (today - last_date).days

    if gap_days <= 1:
        return

    print(f"\n检测到数据缺口: 最后记录 {last_date}，距今 {gap_days} 天")
    print(f"自动补齐历史数据...\n")
    update_history_fixed(days=gap_days + 5)  # 多取几天确保覆盖，使用fixed版本保留nav_date


def update_realtime():
    """更新实时数据"""
    print()
    print("=" * 60)
    print("更新实时数据")
    print("=" * 60)

    # 先检查并补齐缺失的历史数据
    _backfill_missing_days()

    today = datetime.now().strftime('%Y-%m-%d')
    records = []

    for etf in ETF_LIST:
        code, name, market = etf['code'], etf['name'], etf['market']

        realtime = get_realtime_price(code, market)
        if not realtime:
            print(f"  {code} {name}: 获取失败")
            continue

        nav_info = get_current_nav_with_date(code)
        nav = nav_info['nav'] if nav_info else None
        nav_date = nav_info['nav_date'] if nav_info else None

        premium = ((realtime['price'] - nav) / nav * 100) if nav else None

        nav_str = f"{nav:.3f}" if nav else "N/A"
        nav_date_str = f"({nav_date})" if nav_date else ""
        change_pct_str = f" ({realtime.get('change_pct'):+.2f}%)" if realtime.get('change_pct') is not None else ""
        print(f"  {code} {name}: {realtime['price']:.3f}{change_pct_str} (净值:{nav_str}{nav_date_str})")

        records.append({
            'date': today, 'code': code, 'name': name,
            'company': etf['company'], 'price': realtime['price'],
            'prev_close': realtime.get('prev_close'),  # 昨收价
            'nav': nav, 'premium_rate': premium,
            'change_pct': realtime.get('change_pct'),  # API报告的涨跌幅
            'nav_date': nav_date,  # 保存净值实际日期
            'is_fixed': 0         # 实时API获取 = not fixed
        })

    if records:
        saved = save_etf_records(records)
        print(f"\n实时数据: 保存 {saved} 条")

        # 获取期货数据
        print("\n获取期货数据...")
        futures = get_realtime_futures()

        nq = futures.get('NQ', {})
        es = futures.get('ES', {})
        ym = futures.get('YM', {})
        nk = futures.get('NK', {})
        gc = futures.get('GC', {})
        cl = futures.get('CL', {})
        nq_change = nq.get('change_pct')
        es_change = es.get('change_pct')
        ym_change = ym.get('change_pct')
        nk_change = nk.get('change_pct')
        nq_close = nq.get('price')
        es_close = es.get('price')
        ym_close = ym.get('price')
        nk_close = nk.get('price')
        nq_prev_close = nq.get('prev_close')
        es_prev_close = es.get('prev_close')
        ym_prev_close = ym.get('prev_close')
        nk_prev_close = nk.get('prev_close')
        gc_close = gc.get('price')
        gc_prev_close = gc.get('prev_close')
        gc_change = gc.get('change_pct')
        cl_close = cl.get('price')
        cl_prev_close = cl.get('prev_close')
        cl_change = cl.get('change_pct')
        nk_idx = futures.get('NK_IDX', {})
        nk_idx_close = nk_idx.get('price')
        nk_idx_prev_close = nk_idx.get('prev_close')
        nk_idx_change = nk_idx.get('change_pct')
        dax_idx = futures.get('DAX_IDX', {})
        dax_idx_close = dax_idx.get('price')
        dax_idx_prev_close = dax_idx.get('prev_close')
        dax_idx_change = dax_idx.get('change_pct')
        cac_idx = futures.get('CAC_IDX', {})
        cac_idx_close = cac_idx.get('price')
        cac_idx_prev_close = cac_idx.get('prev_close')
        cac_idx_change = cac_idx.get('change_pct')
        sensex_idx = futures.get('SENSEX_IDX', {})
        sensex_idx_close = sensex_idx.get('price')
        sensex_idx_prev_close = sensex_idx.get('prev_close')
        sensex_idx_change = sensex_idx.get('change_pct')
        sox_idx = futures.get('SOX_IDX', {})
        sox_idx_close = sox_idx.get('price')
        sox_idx_prev_close = sox_idx.get('prev_close')
        sox_idx_change = sox_idx.get('change_pct')

        if nq_change is not None or es_change is not None or ym_change is not None or nk_change is not None:
            us_date = get_us_trading_date()
            if save_futures_data(today, nq_change, es_change, ym_change,
                                 nq_close=nq_close, es_close=es_close, ym_close=ym_close,
                                 nq_prev_close=nq_prev_close, es_prev_close=es_prev_close, ym_prev_close=ym_prev_close,
                                 us_date=us_date,
                                 nk_change=nk_change, nk_close=nk_close, nk_prev_close=nk_prev_close,
                                 nk_idx_close=nk_idx_close, nk_idx_prev_close=nk_idx_prev_close,
                                 nk_idx_change=nk_idx_change,
                                 dax_idx_close=dax_idx_close, dax_idx_prev_close=dax_idx_prev_close,
                                 dax_idx_change=dax_idx_change,
                                 gc_close=gc_close, gc_prev_close=gc_prev_close, gc_change=gc_change,
                                 cl_close=cl_close, cl_prev_close=cl_prev_close, cl_change=cl_change,
                                 cac_idx_close=cac_idx_close, cac_idx_prev_close=cac_idx_prev_close,
                                 cac_idx_change=cac_idx_change,
                                 sensex_idx_close=sensex_idx_close, sensex_idx_prev_close=sensex_idx_prev_close,
                                 sensex_idx_change=sensex_idx_change,
                                 sox_idx_close=sox_idx_close, sox_idx_prev_close=sox_idx_prev_close,
                                 sox_idx_change=sox_idx_change):
                for sym, chg in [('NQ', nq_change), ('ES', es_change), ('YM', ym_change), ('NK', nk_change)]:
                    print(f"  {sym}涨跌: {chg:+.2f}%" if chg is not None else f"  {sym}涨跌: N/A")
                if nk_idx_change is not None:
                    print(f"  日经指数: {nk_idx_close:.0f} ({nk_idx_change:+.2f}%)")
                if dax_idx_change is not None:
                    print(f"  DAX指数: {dax_idx_close:.0f} ({dax_idx_change:+.2f}%)")
                if gc_change is not None:
                    print(f"  黄金GC: {gc_close:.1f} ({gc_change:+.2f}%)")
                if cl_change is not None:
                    print(f"  原油CL: {cl_close:.2f} ({cl_change:+.2f}%)")
                if cac_idx_change is not None:
                    print(f"  CAC40: {cac_idx_close:.0f} ({cac_idx_change:+.2f}%)")
                if sensex_idx_change is not None:
                    print(f"  SENSEX: {sensex_idx_close:.0f} ({sensex_idx_change:+.2f}%)")
                if sox_idx_change is not None:
                    print(f"  SOX半导体: {sox_idx_close:.1f} ({sox_idx_change:+.2f}%)")
                print(f"期货数据: 已保存 (美股日: {us_date})")
            else:
                print("期货数据: 保存失败")
        else:
            print("期货数据: 获取失败")

        # 回补最近 30 天真实期货收盘价（用于估算溢价价格比值法）
        try:
            back_n = backfill_futures_history(days=30)
            if back_n:
                print(f"历史期货收盘价: 回补 {back_n} 天")
        except Exception as e:
            print(f"历史期货回补失败: {e}")

        # 回补日经225 + DAX指数历史收盘价
        for name, fn in [('日经指数', backfill_nikkei_index_history),
                          ('DAX指数', backfill_dax_index_history),
                          ('CAC指数', backfill_cac_index_history),
                          ('SENSEX指数', backfill_sensex_index_history),
                          ('SOX半导体', backfill_sox_index_history)]:
            try:
                n = fn(days=30)
                if n:
                    print(f"{name}历史: 回补 {n} 天")
            except Exception as e:
                print(f"{name}回补失败: {e}")

        # 更新持仓型基金的美股价格
        print("\n获取持仓股票价格...")
        update_all_holdings_prices()

        # 更新LOF申购状态
        print("\n更新LOF申购状态...")
        update_subscription_status()

    # 写入快照文件
    write_snapshot(records)


def write_snapshot(records):
    """将采集结果写入快照文件"""
    snapshot_path = PROJECT_ROOT / "memory" / "knowledge" / "etf" / "latest-snapshot.json"
    premiums = [r['premium_rate'] for r in records if r.get('premium_rate') is not None]

    snapshot = {
        "date": datetime.now().strftime('%Y-%m-%d'),
        "timestamp": datetime.now().isoformat(),
        "etfs": [{
            "code": r['code'], "name": r['name'],
            "price": r['price'], "nav": r.get('nav'),
            "premium_rate": r.get('premium_rate')
        } for r in records],
        "summary": {
            "total": len(records),
            "success": len(premiums),
            "avg_premium": sum(premiums) / len(premiums) if premiums else None,
            "min_premium": min(premiums) if premiums else None,
            "max_premium": max(premiums) if premiums else None
        }
    }

    try:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        with open(snapshot_path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        print(f"\n快照已写入: {snapshot_path.name}")
    except Exception as e:
        print(f"\n快照写入失败: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='ETF数据更新')
    parser.add_argument('--realtime', '-r', action='store_true', help='只更新实时数据')
    parser.add_argument('--history', action='store_true', help='只更新历史数据')
    parser.add_argument('--fixed', action='store_true', help='使用东方财富API获取确认历史数据(标记is_fixed=1)')
    parser.add_argument('--days', type=int, default=90, help='历史数据天数（默认90）')
    args = parser.parse_args()

    init_database()

    if args.fixed:
        # 使用东方财富API获取确认历史数据
        update_history_fixed(days=args.days)
    elif args.realtime:
        update_realtime()
    elif args.history:
        update_history(days=args.days)
    else:
        update_history(days=args.days)
        update_realtime()

    print()
    print("=" * 60)
    print("数据更新完成!")
    print(f"数据库: {DB_PATH}")
    print("=" * 60)


if __name__ == '__main__':
    main()
