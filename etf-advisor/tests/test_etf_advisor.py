#!/usr/bin/env python3
"""ETF Advisor 黑盒测试套件

验证: 数据采集 → 分析推荐 → 报告输出 → Admin API 全流程
"""

import json
import sqlite3
import sys
import os
import requests
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent / "scripts"
DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = str(DATA_DIR / "etf_premium.db")
REPORT_PATH = DATA_DIR / "report.json"
ADMIN_URL = "http://127.0.0.1:8090"

sys.path.insert(0, str(SCRIPT_DIR))

passed = 0
failed = 0
errors = []

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        errors.append(f"{name}: {detail}")
        print(f"  ✗ {name} — {detail}")


# ============================================================
print("=== 1. 数据库结构 ===")
# ============================================================
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

test("fund_config 表存在", "fund_config" in tables)
test("fund_holdings 表存在", "fund_holdings" in tables)
test("stock_prices 表存在", "stock_prices" in tables)
test("admin_config 表存在", "admin_config" in tables)
test("etf_data 表存在", "etf_data" in tables)
test("futures_data 表存在", "futures_data" in tables)

# ============================================================
print("\n=== 2. fund_config 完整性 ===")
# ============================================================
funds = conn.execute("SELECT * FROM fund_config WHERE enabled=1").fetchall()
cats = {}
for f in funds:
    cats.setdefault(f['category'], []).append(f)

test("总基金数 >= 27", len(funds) >= 27, f"实际 {len(funds)}")
test("有 NASDAQ 类别", "NASDAQ" in cats)
test("有 SP500 类别", "SP500" in cats)
test("有 DAX 类别", "DAX" in cats)
test("有 NIKKEI 类别", "NIKKEI" in cats)
test("有 OTHERS 类别", "OTHERS" in cats)
test("有 LOF 类别", "LOF" in cats)
test("NASDAQ >= 10只", len(cats.get("NASDAQ", [])) >= 10, f"实际 {len(cats.get('NASDAQ', []))}")
test("SP500 >= 4只", len(cats.get("SP500", [])) >= 4)
test("LOF >= 10只", len(cats.get("LOF", [])) >= 10, f"实际 {len(cats.get('LOF', []))}")
test("OTHERS >= 3只", len(cats.get("OTHERS", [])) >= 3)

# 估算方式检查
for f in funds:
    test(f"{f['code']} 有估算方式", f['estimate_method'] in ('futures', 'index', 'holdings'),
         f"{f['code']} estimate_method={f['estimate_method']}")

# ============================================================
print("\n=== 3. 持仓数据 ===")
# ============================================================
holdings_funds = conn.execute(
    "SELECT DISTINCT fund_code FROM fund_holdings"
).fetchall()
holdings_codes = [r['fund_code'] for r in holdings_funds]

test("159509 纳指科技有持仓", "159509" in holdings_codes)
test("159529 标普消费有持仓", "159529" in holdings_codes)
test("161128 标普科技有持仓", "161128" in holdings_codes)
test("501312 海外科技有持仓", "501312" in holdings_codes)

# 持仓权重合理性
for code in ["159509", "161128"]:
    rows = conn.execute("SELECT SUM(weight_pct) as total FROM fund_holdings WHERE fund_code=?", (code,)).fetchone()
    total = rows['total'] or 0
    test(f"{code} 持仓权重 > 50%", total > 50, f"实际 {total:.1f}%")

# ============================================================
print("\n=== 4. 美股价格 ===")
# ============================================================
prices = conn.execute("SELECT * FROM stock_prices").fetchall()
test("美股价格 >= 20只", len(prices) >= 20, f"实际 {len(prices)}")

# 关键股票有价格
for ticker in ["AAPL", "NVDA", "MSFT"]:
    row = conn.execute("SELECT price, change_pct FROM stock_prices WHERE ticker=?", (ticker,)).fetchone()
    test(f"{ticker} 有价格", row is not None and row['price'] > 0,
         f"price={row['price'] if row else 'None'}")

# ============================================================
print("\n=== 5. 历史数据深度 ===")
# ============================================================
for code, name in [("513100", "国泰纳指"), ("159612", "国泰标普"), ("161128", "标普科技"), ("160719", "嘉实黄金")]:
    count = conn.execute("SELECT COUNT(*) FROM etf_data WHERE code=?", (code,)).fetchone()[0]
    test(f"{code} {name} 历史 >= 200天", count >= 200, f"实际 {count}天")

conn.close()

# ============================================================
print("\n=== 6. report.json 结构 ===")
# ============================================================
report = json.loads(REPORT_PATH.read_text())

test("report.json 有 date", "date" in report)
test("report.json 有 sections", "sections" in report)
test("sections 数量 = 6", len(report['sections']) == 6, f"实际 {len(report['sections'])}")

section_types = [s['index_type'] for s in report['sections']]
test("sections 顺序正确", section_types == ['NASDAQ', 'SP500', 'DAX', 'NIKKEI', 'LOF', 'OTHERS'],
     f"实际 {section_types}")

total_etfs = sum(len(s['etfs']) for s in report['sections'])
test("总ETF数 >= 27", total_etfs >= 27, f"实际 {total_etfs}")

# 每个 ETF 有必要字段
required_fields = ['code', 'name', 'price', 'nav', 'display_premium', 'score', 'recommendation', 'stars']
for s in report['sections']:
    for e in s['etfs']:
        for field in required_fields:
            if field not in e:
                test(f"{e.get('code','?')} 有 {field}", False, f"缺失")
                break
        else:
            continue
        break
    else:
        test(f"{s['index_name']} 所有ETF字段完整", True)

# OTHERS/LOF 持仓数据
for s in report['sections']:
    if s['index_type'] in ('OTHERS', 'LOF'):
        holdings_etfs = [e for e in s['etfs'] if e.get('holdings')]
        test(f"{s['index_name']} 有持仓详情的ETF >= 1", len(holdings_etfs) >= 1,
             f"实际 {len(holdings_etfs)}")

# ============================================================
print("\n=== 7. 推荐逻辑 ===")
# ============================================================
nq = [s for s in report['sections'] if s['index_type'] == 'NASDAQ'][0]
nq_etfs = nq['etfs']

test("纳指 ETF 按分值降序", all(nq_etfs[i]['score'] >= nq_etfs[i+1]['score'] for i in range(len(nq_etfs)-1)))

# rotation pool
pool_etfs = [e for e in nq_etfs if e.get('rotation_pool')]
test("纳指推荐池 = 4只", len(pool_etfs) == 4, f"实际 {len(pool_etfs)}")
test("推荐池有 rotation_bonus", all(e.get('rotation_bonus', 0) > 0 for e in pool_etfs))

# LOF 不在 NASDAQ
nq_codes = [e['code'] for e in nq_etfs]
test("161130 纳斯达克100LOF 在纳指tab", "161130" in nq_codes)
test("159509 纳指科技不在纳指tab", "159509" not in nq_codes)

# ============================================================
print("\n=== 8. 估算溢价合理性 ===")
# ============================================================
for s in report['sections']:
    for e in s['etfs']:
        prem = e['display_premium']
        test(f"{e['code']} 溢价在 [-30%, +50%]", -30 <= prem <= 50,
             f"{e['name']} 溢价={prem:.2f}%")

# ============================================================
print("\n=== 9. Admin API ===")
# ============================================================
try:
    # 登录
    r = requests.post(f"{ADMIN_URL}/admin/api/login", json={"password": "admin"}, timeout=5)
    test("Admin 登录成功", r.status_code == 200 and r.json().get("token"))
    token = r.json().get("token", "")

    # 获取基金列表
    r = requests.get(f"{ADMIN_URL}/admin/api/funds", headers={"Authorization": f"Bearer {token}"}, timeout=5)
    test("获取基金列表", r.status_code == 200 and len(r.json()) >= 27)

    # 获取持仓
    r = requests.get(f"{ADMIN_URL}/admin/api/fund/159509/holdings", headers={"Authorization": f"Bearer {token}"}, timeout=5)
    test("获取159509持仓", r.status_code == 200 and len(r.json()) >= 5)

    # 获取股票价格
    r = requests.get(f"{ADMIN_URL}/admin/api/stock-prices", headers={"Authorization": f"Bearer {token}"}, timeout=5)
    test("获取股票价格", r.status_code == 200 and len(r.json()) >= 10)

    # 未授权
    r = requests.get(f"{ADMIN_URL}/admin/api/funds", timeout=5)
    test("未授权拒绝", r.status_code == 401)

    # 错误密码
    r = requests.post(f"{ADMIN_URL}/admin/api/login", json={"password": "wrong"}, timeout=5)
    test("错误密码拒绝", r.status_code == 401)

except requests.ConnectionError:
    test("Admin API 可连接", False, "连接失败，admin_server 未运行？")

# ============================================================
print(f"\n{'=' * 50}")
print(f"结果: {passed} 通过, {failed} 失败")
if errors:
    print(f"\n失败详情:")
    for e in errors:
        print(f"  ✗ {e}")
print(f"{'=' * 50}")
sys.exit(0 if failed == 0 else 1)
