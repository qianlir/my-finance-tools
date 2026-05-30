#!/usr/bin/env python3
"""构建月频持仓 SQLite — v2.0

重放交易记录在每个月末生成持仓快照,批量拉腾讯日 K 线取月末收盘价,
计算月度市值 + 累计 P&L → 存 SQLite + 导出 JSON(给 05_report 画折线图)。

环境变量:
  PORTFOLIO_XLSX       同花顺导出 Excel
  PORTFOLIO_WORK_DIR   工作目录
  PORTFOLIO_PRIOR_YEAR 去年(如 2025)
  PORTFOLIO_CUR_YEAR   今年(如 2026)
  PORTFOLIO_TODAY      当前日期 YYYY-MM-DD

产出:
  data/portfolio_monthly.db   — SQLite(daily_price 缓存 + 3 张月度表)
  data/monthly_curve.json     — 月度 P&L 曲线(给报告用)
  data/avg_mv.json            — 月度平均市值(更精确的收益率分母)
"""
import os
import csv
import json
import sqlite3
import time
import calendar
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date
from pathlib import Path
import openpyxl

SRC = Path(os.environ['PORTFOLIO_XLSX']).expanduser()
WORK = Path(os.environ['PORTFOLIO_WORK_DIR']).expanduser()
PRIOR = int(os.environ['PORTFOLIO_PRIOR_YEAR'])
CUR = int(os.environ['PORTFOLIO_CUR_YEAR'])
TODAY = os.environ['PORTFOLIO_TODAY']
DATA = WORK / 'data'

# 交易类型(同 01_build_snapshots.py)
BUY_SIDE = {'买入', '新股入帐', '融资买入'}
SELL_SIDE = {'卖出', '卖券还款'}
TRANSFER_IN = {'股份转入', '转债转入', '调帐转入'}
TRANSFER_OUT = {'股份转出', '转债转出'}
SKIP_QTY = {'银行转证券', '证券转银行', '银证转入', '银证转出', '收入',
            '股息个税征收', '融券', '融券回购', '融券购回',
            '上海债券质押逆回购初始交易', '上海债券质押逆回购购回交易',
            '深圳债券质押逆回购初始交易', '深圳债券质押逆回购购回交易',
            '通用回购逆回购', '通用回购逆回购购回',
            '除权除息'}
REVERSE_REPO_CODES = {'131810', '131811', '131800', '131801',
                      '204001', '204002', '204003', '204004',
                      '204007', '204014', '204028', '204091', '204182'}


# ── 工具函数 ──────────────────────────────────────────────

def generate_month_ends(start_year, start_month, end_date_str):
    """生成 [start_year-start_month 月末, ..., end_date] 的日期列表"""
    end = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    dates = []
    y, m = start_year, start_month
    while True:
        last_day = calendar.monthrange(y, m)[1]
        d = date(y, m, last_day)
        if d > end:
            # 当月未结束 → 用 today 代替月末
            if date(y, m, 1) <= end:
                dates.append(end_date_str)
            break
        dates.append(d.isoformat())
        m += 1
        if m > 12:
            m = 1; y += 1
    return dates


def to_str_date(v):
    if v is None: return None
    if isinstance(v, str): return v[:10]
    if hasattr(v, 'strftime'): return v.strftime('%Y-%m-%d')
    return str(v)[:10]


def normalize_code(c):
    if c is None: return ''
    s = str(c).strip()
    if not s.isdigit(): return s
    if len(s) == 5: return s
    if len(s) <= 6: return s.zfill(6)
    return s


def to_symbol(code: str):
    if not code or not code.isdigit(): return None
    if len(code) == 5: return f'hk{code}'
    if len(code) != 6: return None
    if code[0] == '6': return f'sh{code}'
    if code[:2] in ('51', '56', '58', '50', '11', '17', '18', '20', '68', '60'): return f'sh{code}'
    if code[0] in '03': return f'sz{code}'
    if code[:2] in ('00', '30', '15', '16', '12', '39'): return f'sz{code}'
    if code[0] in '8' or code[:2] in ('92', '83'): return f'sz{code}'
    return f'sh{code}'


# ── Step 1: 重放交易记录,构建月末快照 ──────────────────────

def parse_trades():
    """解析交易记录 → 列表 [{date, code, name, signed_qty, net_in}]
    net_in = 卖出收入 - 买入支出(正=资金流出账户,负=资金流入账户)
    仅真买卖产生 net_in,转入/转出只影响 qty"""
    wb = openpyxl.load_workbook(SRC, data_only=True, read_only=True)
    ws = wb['交易记录']
    trades = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        d = to_str_date(r[0])
        code = r[2]; name = r[3]; t = r[4]
        qty = float(r[5] or 0)
        amt = float(r[7] or 0)
        fee = float(r[9] or 0)
        if not d or not code: continue
        code_s = normalize_code(code)
        if code_s in REVERSE_REPO_CODES: continue

        # 分红 / 个税 → 只影响 net_in,不影响 qty
        if t == '除权除息':
            trades.append({'date': d, 'code': code_s, 'name': name,
                           'signed_qty': 0, 'net_in': amt})
            continue
        if t == '股息个税征收':
            trades.append({'date': d, 'code': code_s, 'name': name,
                           'signed_qty': 0, 'net_in': amt})
            continue
        if t in SKIP_QTY: continue

        # qty 变化
        if t in BUY_SIDE or t in TRANSFER_IN:
            signed_qty = qty
        elif t in SELL_SIDE or t in TRANSFER_OUT:
            signed_qty = -qty
        else:
            continue

        # net_in: 仅真买卖产生(转入转出不算现金流)
        # 买入: amt 通常是负数(付出), net_in = amt - fee (大负数)
        # 卖出: amt 通常是正数(收到), net_in = amt - fee (正数)
        if t in BUY_SIDE or t in SELL_SIDE:
            net_in = amt - fee
        else:
            net_in = 0  # 转入/转出不产生现金流

        trades.append({'date': d, 'code': code_s, 'name': name or '',
                       'signed_qty': signed_qty, 'net_in': net_in})
    wb.close()
    return sorted(trades, key=lambda x: x['date'])


def build_monthly_snapshots(trades, month_ends):
    """用 01_build_snapshots 的逻辑:遍历交易,对每个 month_end 累加 d<=me 的交易。

    返回:
      snapshots: {date: {code: {qty, name}}}
      cf_prior:  {date: {code: cumulative_net_in from PRIOR-01-01}}
      cf_cur:    {date: {code: cumulative_net_in from CUR-01-01}}
    """
    # 初始化
    snapshots = {me: defaultdict(lambda: {'qty': 0.0, 'name': ''}) for me in month_ends}
    cf_prior = {me: defaultdict(float) for me in month_ends}
    cf_cur = {me: defaultdict(float) for me in month_ends}

    prior_start = f'{PRIOR}-01-01'
    cur_start = f'{CUR}-01-01'

    for t in trades:
        d, code = t['date'], t['code']
        for me in month_ends:
            if d <= me:
                snapshots[me][code]['qty'] += t['signed_qty']
                snapshots[me][code]['name'] = t['name'] or snapshots[me][code]['name']
                if d >= prior_start:
                    cf_prior[me][code] += t['net_in']
                if d >= cur_start:
                    cf_cur[me][code] += t['net_in']

    # 过滤 qty <= 0 的
    clean = {}
    for me in month_ends:
        clean[me] = {c: v for c, v in snapshots[me].items() if v['qty'] > 0.5}
    return clean, cf_prior, cf_cur


# ── Step 2: 批量拉价格(SQLite 缓存) ─────────────────────

def fetch_daily_kline(symbol, end, count=400):
    """拉一个标的截至 end 的 count 条日 K 线(不复权收盘价)。
    腾讯 API 不支持同时传 start+end,用 end+count 模式。
    count=400 ≈ 18 个月交易日。"""
    url = (f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
           f'?param={symbol},day,,{end},{count},')
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            if data.get('code') != 0: return {}
            sym_data = data['data'].get(symbol, {})
            if not isinstance(sym_data, dict): return {}
            klines = sym_data.get('day') or sym_data.get('qfqday') or []
            return {row[0]: float(row[2]) for row in klines
                    if isinstance(row, list) and len(row) >= 3}
        except Exception:
            if attempt < 2: time.sleep(1.0); continue
            return {}
    return {}


def fetch_batch_prices(codes_names, end_date, db_path, count=400):
    """批量拉日 K 线 → SQLite daily_price 表(增量缓存)
    返回 {code: {date: price}}"""
    conn = sqlite3.connect(db_path)
    conn.execute('''CREATE TABLE IF NOT EXISTS daily_price
                     (code TEXT, date TEXT, price REAL,
                      PRIMARY KEY(code, date))''')

    cached = {r[0] for r in conn.execute('SELECT DISTINCT code FROM daily_price')}
    to_fetch = {c: n for c, n in codes_names.items() if c not in cached}
    print(f'价格: 共 {len(codes_names)} 个, 缓存 {len(cached)}, 需拉 {len(to_fetch)} 个')

    if to_fetch:
        def _fetch(code):
            sym = to_symbol(code)
            if not sym: return code, {}
            return code, fetch_daily_kline(sym, end_date, count=400)

        with ThreadPoolExecutor(max_workers=12) as ex:
            futs = {ex.submit(_fetch, c): c for c in to_fetch}
            for i, fut in enumerate(as_completed(futs), 1):
                code, prices = fut.result()
                if prices:
                    conn.executemany(
                        'INSERT OR REPLACE INTO daily_price VALUES(?,?,?)',
                        [(code, d, p) for d, p in prices.items()])
                if i % 30 == 0:
                    conn.commit()
                    print(f'  进度 {i}/{len(to_fetch)}')
        conn.commit()

    # 全量读出
    all_prices = defaultdict(dict)
    for r in conn.execute('SELECT code, date, price FROM daily_price'):
        all_prices[r[0]][r[1]] = r[2]
    conn.close()
    return all_prices


def pick_price(daily, target):
    """取 target 日或之前最近交易日收盘价"""
    if target in daily: return daily[target]
    cands = sorted(d for d in daily if d <= target)
    return daily[cands[-1]] if cands else None


# ── Step 3: 写 SQLite + JSON ──────────────────────────────

def main():
    db_path = DATA / 'portfolio_monthly.db'

    # 月末日期: PRIOR-1 年 12 月末 → TODAY
    month_ends = generate_month_ends(PRIOR - 1, 12, TODAY)
    print(f'月末日期: {len(month_ends)} 个 ({month_ends[0]} ~ {month_ends[-1]})')

    # 解析交易
    print('解析交易记录...')
    trades = parse_trades()
    print(f'  交易笔数: {len(trades)}')

    # 构建月末快照 + 累计现金流
    print('构建月末快照...')
    snapshots, cf_prior, cf_cur = build_monthly_snapshots(trades, month_ends)

    # 收集所有代码
    all_codes = {}
    for me, snap in snapshots.items():
        for code, info in snap.items():
            all_codes[code] = info['name']
    print(f'涉及标的: {len(all_codes)} 个')

    # 批量拉价格(end=TODAY, count=400 ≈ 18 个月交易日)
    all_prices = fetch_batch_prices(all_codes, TODAY, str(db_path), count=400)

    # 读板块分类
    sectors = {}
    sp = DATA / 'sectors.csv'
    if sp.exists():
        with open(sp) as f:
            for r in csv.DictReader(f):
                sectors[r['code']] = r['sector']

    # 写 SQLite 月度表
    conn = sqlite3.connect(str(db_path))
    for t in ('monthly_position', 'monthly_sector', 'monthly_portfolio'):
        conn.execute(f'DROP TABLE IF EXISTS {t}')
    conn.execute('''CREATE TABLE monthly_position (
        code TEXT, name TEXT, sector TEXT, date TEXT,
        qty REAL, price REAL, mv REAL,
        PRIMARY KEY(code, date))''')
    conn.execute('''CREATE TABLE monthly_sector (
        sector TEXT, date TEXT, mv REAL, position_count INTEGER,
        PRIMARY KEY(sector, date))''')
    conn.execute('''CREATE TABLE monthly_portfolio (
        date TEXT PRIMARY KEY, total_mv REAL, position_count INTEGER)''')

    base_date = month_ends[0]  # PRIOR-1 年 12 月末 = P&L 基准

    for me in month_ends:
        snap = snapshots[me]
        sec_mv = defaultdict(float)
        sec_cnt = defaultdict(int)
        total_mv = 0; total_cnt = 0

        for code, info in snap.items():
            price = pick_price(all_prices.get(code, {}), me)
            mv = info['qty'] * price if (info['qty'] > 0 and price) else 0
            sector = sectors.get(code, 'A股')
            conn.execute('INSERT INTO monthly_position VALUES(?,?,?,?,?,?,?)',
                         (code, info['name'], sector, me,
                          round(info['qty'], 4),
                          round(price, 4) if price else None,
                          round(mv, 2)))
            sec_mv[sector] += mv
            sec_cnt[sector] += 1
            total_mv += mv; total_cnt += 1

        for sec_name in sec_mv:
            conn.execute('INSERT INTO monthly_sector VALUES(?,?,?,?)',
                         (sec_name, me, round(sec_mv[sec_name], 2), sec_cnt[sec_name]))
        conn.execute('INSERT INTO monthly_portfolio VALUES(?,?,?)',
                     (me, round(total_mv, 2), total_cnt))
    conn.commit()

    # ── 计算月度累计 P&L ──
    # P&L(month M, period P) = Σ_code [ MV(code,M) - MV(code,base_P) + net_in(code, start_P→M) ]
    # PRIOR period: base = PRIOR-1-12-31, start = PRIOR-01-01
    # CUR period:   base = PRIOR-12-31,   start = CUR-01-01
    prior_base = f'{PRIOR - 1}-12-31'
    cur_base = f'{PRIOR}-12-31'

    # 取基准日 MV
    def get_mv_map(snap_date):
        """返回 {code: mv} for a given date"""
        snap = snapshots.get(snap_date, {})
        result = {}
        for code, info in snap.items():
            price = pick_price(all_prices.get(code, {}), snap_date)
            result[code] = info['qty'] * price if (info['qty'] > 0 and price) else 0
        return result

    mv_prior_base = get_mv_map(prior_base)
    mv_cur_base = get_mv_map(cur_base)

    # 月度 P&L 曲线
    curve = {
        'dates_prior': [], 'pl_prior_portfolio': [],
        'pl_prior_sectors': defaultdict(list),
        'dates_cur': [], 'pl_cur_portfolio': [],
        'pl_cur_sectors': defaultdict(list),
        'mv_dates': [], 'mv_portfolio': [],
        'mv_sectors': defaultdict(list),
    }

    all_sector_names = sorted(set(sectors.values()) | {'A股'})

    for me in month_ends:
        snap = snapshots[me]
        year_m = int(me[:4])

        # 市值曲线(全时段)
        curve['mv_dates'].append(me)
        total_mv_me = sum(
            info['qty'] * (pick_price(all_prices.get(c, {}), me) or 0)
            for c, info in snap.items() if info['qty'] > 0)
        curve['mv_portfolio'].append(round(total_mv_me, 0))

        sec_mv_me = defaultdict(float)
        for c, info in snap.items():
            p = pick_price(all_prices.get(c, {}), me)
            mv = info['qty'] * p if (info['qty'] > 0 and p) else 0
            sec_mv_me[sectors.get(c, 'A股')] += mv
        for sn in all_sector_names:
            curve['mv_sectors'][sn].append(round(sec_mv_me.get(sn, 0), 0))

        # PRIOR 年 P&L 曲线(PRIOR-01 ~ PRIOR-12)
        if year_m == PRIOR or (me == prior_base):
            if me != prior_base:  # 跳过基准日本身
                curve['dates_prior'].append(me)
                # 逐代码算 P&L
                sec_pl = defaultdict(float)
                total_pl = 0
                all_codes_period = set(snap.keys()) | set(mv_prior_base.keys()) | set(cf_prior[me].keys())
                for code in all_codes_period:
                    mv_now = 0
                    if code in snap:
                        p = pick_price(all_prices.get(code, {}), me)
                        mv_now = snap[code]['qty'] * p if (snap[code]['qty'] > 0 and p) else 0
                    mv_base = mv_prior_base.get(code, 0)
                    net_in = cf_prior[me].get(code, 0)
                    pl = mv_now - mv_base + net_in
                    sec = sectors.get(code, 'A股')
                    sec_pl[sec] += pl
                    total_pl += pl
                curve['pl_prior_portfolio'].append(round(total_pl, 0))
                for sn in all_sector_names:
                    curve['pl_prior_sectors'][sn].append(round(sec_pl.get(sn, 0), 0))

        # CUR YTD P&L 曲线(CUR-01 ~ TODAY)
        if year_m == CUR:
            curve['dates_cur'].append(me)
            sec_pl = defaultdict(float)
            total_pl = 0
            all_codes_period = set(snap.keys()) | set(mv_cur_base.keys()) | set(cf_cur[me].keys())
            for code in all_codes_period:
                mv_now = 0
                if code in snap:
                    p = pick_price(all_prices.get(code, {}), me)
                    mv_now = snap[code]['qty'] * p if (snap[code]['qty'] > 0 and p) else 0
                mv_base = mv_cur_base.get(code, 0)
                net_in = cf_cur[me].get(code, 0)
                pl = mv_now - mv_base + net_in
                sec = sectors.get(code, 'A股')
                sec_pl[sec] += pl
                total_pl += pl
            curve['pl_cur_portfolio'].append(round(total_pl, 0))
            for sn in all_sector_names:
                curve['pl_cur_sectors'][sn].append(round(sec_pl.get(sn, 0), 0))

    with open(DATA / 'monthly_curve.json', 'w', encoding='utf-8') as f:
        json.dump(curve, f, ensure_ascii=False, indent=2)

    # ── 平均市值 ──
    avg_info = {'prior_year': PRIOR, 'cur_year': CUR, 'sectors': {}}

    # PRIOR 平均: PRIOR-1-12 ~ PRIOR-12 的月末 MV 均值
    prior_months = [me for me in month_ends
                    if (int(me[:4]) == PRIOR - 1 and int(me[5:7]) == 12) or int(me[:4]) == PRIOR]
    cur_months = [me for me in month_ends
                  if (int(me[:4]) == PRIOR and int(me[5:7]) == 12) or int(me[:4]) == CUR]

    def avg_mv_for_months(months):
        mvs = []
        for me in months:
            row = conn.execute('SELECT total_mv FROM monthly_portfolio WHERE date=?', (me,)).fetchone()
            mvs.append(row[0] if row else 0)
        return sum(mvs) / len(mvs) if mvs else 0

    avg_info['avg_mv_prior'] = round(avg_mv_for_months(prior_months), 0)
    avg_info['avg_mv_cur'] = round(avg_mv_for_months(cur_months), 0)
    avg_info['prior_months'] = len(prior_months)
    avg_info['cur_months'] = len(cur_months)

    for sn in all_sector_names:
        s_prior, s_cur = [], []
        for me in prior_months:
            row = conn.execute('SELECT mv FROM monthly_sector WHERE sector=? AND date=?',
                               (sn, me)).fetchone()
            s_prior.append(row[0] if row else 0)
        for me in cur_months:
            row = conn.execute('SELECT mv FROM monthly_sector WHERE sector=? AND date=?',
                               (sn, me)).fetchone()
            s_cur.append(row[0] if row else 0)
        avg_info['sectors'][sn] = {
            'avg_mv_prior': round(sum(s_prior) / len(s_prior), 0) if s_prior else 0,
            'avg_mv_cur': round(sum(s_cur) / len(s_cur), 0) if s_cur else 0,
        }

    with open(DATA / 'avg_mv.json', 'w', encoding='utf-8') as f:
        json.dump(avg_info, f, ensure_ascii=False, indent=2)

    # ── 打印摘要 ──
    print(f'\n=== 月度市值 ===')
    for row in conn.execute('SELECT date, total_mv, position_count FROM monthly_portfolio ORDER BY date'):
        print(f'  {row[0]}: ¥{row[1]:,.0f} ({row[2]} 个标的)')

    print(f'\n=== 平均市值(月频) ===')
    print(f'  {PRIOR} 全年: ¥{avg_info["avg_mv_prior"]:,.0f} (基于 {len(prior_months)} 个月)')
    print(f'  {CUR} YTD:  ¥{avg_info["avg_mv_cur"]:,.0f} (基于 {len(cur_months)} 个月)')

    conn.close()
    print(f'\n✓ SQLite: {db_path}')
    print(f'✓ 曲线 JSON: {DATA / "monthly_curve.json"}')
    print(f'✓ 平均市值: {DATA / "avg_mv.json"}')


if __name__ == '__main__':
    main()
