#!/usr/bin/env python3
"""重建 prior_year-12-31 / cur_year-12-31 / today 三个时点持仓快照 + 期间现金流。

环境变量:
  PORTFOLIO_XLSX       同花顺导出的 Excel 路径
  PORTFOLIO_WORK_DIR   工作目录(会写 data/snapshot_*.csv 和 data/cashflow_*.csv)
  PORTFOLIO_PRIOR_YEAR 去年(如 2025)
  PORTFOLIO_CUR_YEAR   今年(如 2026)
  PORTFOLIO_TODAY      当前日期 YYYY-MM-DD
"""
import os
import openpyxl
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SRC = Path(os.environ['PORTFOLIO_XLSX']).expanduser()
WORK = Path(os.environ['PORTFOLIO_WORK_DIR']).expanduser()
PRIOR = int(os.environ['PORTFOLIO_PRIOR_YEAR'])
CUR = int(os.environ['PORTFOLIO_CUR_YEAR'])
TODAY = os.environ['PORTFOLIO_TODAY']

OUT = WORK / 'data'
OUT.mkdir(exist_ok=True, parents=True)

# 真买卖:影响 qty + 影响现金流
BUY_SIDE = {'买入', '新股入帐', '融资买入'}
SELL_SIDE = {'卖出', '卖券还款'}
# 账户间调拨:只影响 qty,不算现金流入流出
# (用户在子账户间转股,或转债场内换股,无外部现金变动)
TRANSFER_IN = {'股份转入', '转债转入', '调帐转入'}
TRANSFER_OUT = {'股份转出', '转债转出'}
SKIP_QTY = {'银行转证券', '证券转银行', '银证转入', '银证转出', '收入',
            '股息个税征收',
            '融券', '融券回购', '融券购回',
            '上海债券质押逆回购初始交易', '上海债券质押逆回购购回交易',
            '深圳债券质押逆回购初始交易', '深圳债券质押逆回购购回交易',
            '通用回购逆回购', '通用回购逆回购购回',
            '除权除息'}
REVERSE_REPO_CODES = {'131810','131811','131800','131801',
                       '204001','204002','204003','204004','204007','204014','204028','204091','204182'}


def to_str_date(v):
    if v is None: return None
    if isinstance(v, str):
        return v[:10]
    if isinstance(v, datetime) or hasattr(v, 'strftime'):
        return v.strftime('%Y-%m-%d')
    return str(v)[:10]


def main():
    wb = openpyxl.load_workbook(SRC, data_only=True)
    ws = wb['交易记录']

    SNAP_DATES = [f'{PRIOR-1}-12-31', f'{PRIOR}-12-31', TODAY]
    PERIODS = {
        str(PRIOR): (f'{PRIOR}-01-01', f'{PRIOR}-12-31'),
        str(CUR):   (f'{CUR}-01-01', TODAY),
    }

    snapshots = {d: defaultdict(lambda: {'qty':0.0, 'name':None,
                                          'buy_qty':0.0, 'buy_cost':0.0}) for d in SNAP_DATES}
    cashflows = {p: defaultdict(lambda: {
        'name':None, 'buy_amt':0.0, 'sell_amt':0.0, 'dividend':0.0, 'tax':0.0, 'fee':0.0,
        'buy_qty':0.0, 'sell_qty':0.0,
    }) for p in PERIODS}
    cash_in_out = defaultdict(float)

    for r in range(2, ws.max_row+1):
        d = to_str_date(ws.cell(r, 1).value)
        code = ws.cell(r, 3).value
        name = ws.cell(r, 4).value
        t = ws.cell(r, 5).value
        qty = float(ws.cell(r, 6).value or 0)
        amt = float(ws.cell(r, 8).value or 0)
        fee = float(ws.cell(r, 10).value or 0)

        if not d: continue
        if code and str(code) in REVERSE_REPO_CODES: continue
        if not code:
            for p, (s, e) in PERIODS.items():
                if s <= d <= e:
                    cash_in_out[p] += amt
            continue

        if len(str(code)) == 5 and str(code).isdigit():
            code_s = str(code).zfill(5)
        elif str(code).isdigit():
            code_s = str(code).zfill(6)
        else:
            code_s = str(code)

        if t == '除权除息':
            for p, (s, e) in PERIODS.items():
                if s <= d <= e:
                    cf = cashflows[p][code_s]
                    cf['name'] = name or cf['name']
                    cf['dividend'] += amt
            continue
        if t == '股息个税征收':
            for p, (s, e) in PERIODS.items():
                if s <= d <= e:
                    cf = cashflows[p][code_s]
                    cf['name'] = name or cf['name']
                    cf['tax'] += amt
            continue
        if t in SKIP_QTY: continue

        # qty 变化:真买卖 + 账户间调拨都影响 qty
        if t in BUY_SIDE or t in TRANSFER_IN:
            signed_qty = qty
        elif t in SELL_SIDE or t in TRANSFER_OUT:
            signed_qty = -qty
        else:
            continue

        for snap in SNAP_DATES:
            if d <= snap:
                ss = snapshots[snap][code_s]
                ss['name'] = name or ss['name']
                ss['qty'] += signed_qty
                # 成本基础:仅真买入,转入不算(转入是已有持仓的调拨)
                if t in BUY_SIDE and qty > 0:
                    cost = -amt if amt < 0 else abs(amt) + fee
                    ss['buy_qty'] += qty
                    ss['buy_cost'] += cost

        # 现金流:仅真买卖算,账户间调拨不算
        for p, (s, e) in PERIODS.items():
            if s <= d <= e:
                cf = cashflows[p][code_s]
                cf['name'] = name or cf['name']
                if t in BUY_SIDE:
                    cf['buy_amt'] += (-amt if amt < 0 else amt)
                    cf['buy_qty'] += qty
                    cf['fee'] += fee
                elif t in SELL_SIDE:
                    cf['sell_amt'] += (amt if amt > 0 else -amt)
                    cf['sell_qty'] += qty
                    cf['fee'] += fee
                # TRANSFER_IN / TRANSFER_OUT: 不算 cash flow

    for snap in SNAP_DATES:
        path = OUT / f'snapshot_{snap.replace("-","")}.csv'
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['code','name','qty','buy_qty','buy_total_cost','avg_cost_est'])
            keep = 0
            for code, d in sorted(snapshots[snap].items()):
                if d['qty'] > 0.5:
                    avg = d['buy_cost'] / d['buy_qty'] if d['buy_qty']>0 else 0
                    w.writerow([code, d['name'], round(d['qty'],4), round(d['buy_qty'],4),
                                round(d['buy_cost'],2), round(avg,6)])
                    keep += 1
            print(f'snapshot {snap}: {keep} positions')

    for p in PERIODS:
        path = OUT / f'cashflow_{p}.csv'
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['code','name','buy_qty','buy_amt','sell_qty','sell_amt','dividend','tax','fee'])
            for code, d in sorted(cashflows[p].items()):
                w.writerow([code, d['name'], round(d['buy_qty'],4),
                            round(d['buy_amt'],2), round(d['sell_qty'],4),
                            round(d['sell_amt'],2), round(d['dividend'],2),
                            round(d['tax'],2), round(d['fee'],2)])
        print(f'cashflow {p}: {len(cashflows[p])} codes')


if __name__ == '__main__':
    main()
