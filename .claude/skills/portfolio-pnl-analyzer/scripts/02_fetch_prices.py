#!/usr/bin/env python3
"""通过腾讯财经 API 拉 prior_year-12-31 / cur_year-12-31 收盘价 (不复权)。

环境变量:
  PORTFOLIO_WORK_DIR   工作目录
  PORTFOLIO_PRIOR_YEAR 去年
  PORTFOLIO_CUR_YEAR   今年
"""
import os
import csv
import json
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

WORK = Path(os.environ['PORTFOLIO_WORK_DIR']).expanduser()
PRIOR = int(os.environ['PORTFOLIO_PRIOR_YEAR'])
CUR = int(os.environ['PORTFOLIO_CUR_YEAR'])
DATA = WORK / 'data'

D_PRIOR = f'{PRIOR-1}-12-31'   # 期初 = 去年的上一年 12-31
D_CUR_END = f'{PRIOR}-12-31'    # 去年期末 = 去年 12-31


def to_symbol(code: str):
    if not code: return None
    code = str(code).strip()
    if not code.isdigit(): return None
    if len(code) == 5:
        return f'hk{code}'
    if len(code) != 6:
        return None
    if code[0] == '6': return f'sh{code}'
    if code[:2] in ('51','56','58','50','11','17','18','20','68','60'): return f'sh{code}'
    if code[0] in '03': return f'sz{code}'
    if code[:2] in ('00','30','15','16','12','39'): return f'sz{code}'
    if code[0] in '8' or code[:2] in ('92','83'): return f'sz{code}'
    return f'sh{code}'


def fetch_kline_end(symbol: str, end: str, count: int = 3):
    url = (f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
           f'?param={symbol},day,,{end},{count},')
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            if data.get('code') != 0: return {}
            sym_data = data['data'].get(symbol, {})
            if not isinstance(sym_data, dict): return {}
            klines = sym_data.get('day') or sym_data.get('qfqday') or []
            result = {}
            for row in klines:
                if isinstance(row, list) and len(row) >= 3:
                    result[row[0]] = float(row[2])
            return result
        except Exception:
            if attempt < 2:
                time.sleep(1.0); continue
            return {}
    return {}


def fetch_one(code, name):
    sym = to_symbol(code)
    if not sym:
        return {'code': code, 'name': name, 'sym': None,
                f'price_{D_PRIOR}': None, f'price_{D_CUR_END}': None}
    kl_prior = fetch_kline_end(sym, D_PRIOR, count=3)
    kl_cur = fetch_kline_end(sym, D_CUR_END, count=3)

    def pick(kl, target):
        if target in kl: return kl[target]
        cands = sorted([d for d in kl if d <= target])
        return kl[cands[-1]] if cands else None

    return {'code': code, 'name': name, 'sym': sym,
            f'price_{D_PRIOR}': pick(kl_prior, D_PRIOR),
            f'price_{D_CUR_END}': pick(kl_cur, D_CUR_END)}


def load_cache():
    """读已有 prices.csv 作为缓存。两个时点都有有效价的代码 = 已缓存,不再拉。"""
    cache = {}
    p = DATA / 'prices.csv'
    if not p.exists():
        return cache
    with open(p) as f:
        for r in csv.DictReader(f):
            # 只接受两个时点都有的(避免半成品 cache)
            if r.get(f'price_{D_PRIOR}') and r.get(f'price_{D_CUR_END}'):
                cache[r['code']] = r
    return cache


def main():
    needed = {}
    for snap_date in [D_PRIOR, D_CUR_END]:
        path = DATA / f'snapshot_{snap_date.replace("-","")}.csv'
        if not path.exists(): continue
        with open(path) as f:
            next(f)
            for row in csv.reader(f):
                if row[0] and row[0] not in needed:
                    needed[row[0]] = row[1]

    cache = load_cache()
    to_fetch = {c: n for c, n in needed.items() if c not in cache}
    print(f'共 {len(needed)} 个代码,缓存命中 {len(cache)},需新拉 {len(to_fetch)} 个')

    results = list(cache.values())  # 缓存先入
    if to_fetch:
        with ThreadPoolExecutor(max_workers=12) as ex:
            futs = {ex.submit(fetch_one, c, n): (c, n) for c, n in to_fetch.items()}
            for i, fut in enumerate(as_completed(futs), 1):
                results.append(fut.result())
                if i % 20 == 0:
                    print(f'  进度 {i}/{len(to_fetch)}')

    results.sort(key=lambda x: x['code'])
    fields = ['code','name','sym', f'price_{D_PRIOR}', f'price_{D_CUR_END}']
    with open(DATA / 'prices.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(results)

    ok_prior = sum(1 for r in results if r.get(f'price_{D_PRIOR}'))
    ok_cur = sum(1 for r in results if r.get(f'price_{D_CUR_END}'))
    print(f'完成: {len(results)}, 有 {D_PRIOR} 价: {ok_prior}, 有 {D_CUR_END} 价: {ok_cur}')


if __name__ == '__main__':
    main()
