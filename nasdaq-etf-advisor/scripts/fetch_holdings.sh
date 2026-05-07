#!/bin/bash
# fetch_holdings.sh — 获取持仓，保存代码列表和完整数据 JSON

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_FILE="$SCRIPT_DIR/../data/holdings.txt"
JSON_FILE="$SCRIPT_DIR/../data/holdings_detail.json"

echo "# ETF 持仓配置（自动从同花顺获取）" > "$OUTPUT_FILE"
echo "# 更新时间: $(date '+%Y-%m-%d %H:%M:%S')" >> "$OUTPUT_FILE"

# 使用 curl 获取完整数据
RESPONSE=$(curl -s 'https://tzzb.10jqka.com.cn/caishen_httpserver/tzzb/caishen_fund/pc/asset/v1/stock_position' \
  -X POST \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:148.0) Gecko/20100101 Firefox/148.0' \
  -H 'Accept: application/json, text/plain, */*' \
  -H 'Accept-Language: zh-CN,ja;q=0.9,zh;q=0.8' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -H 'Origin: https://tzzb.10jqka.com.cn' \
  -H 'Referer: https://tzzb.10jqka.com.cn/pc/index.html' \
  -H 'Cookie: v=A7AXEyIQrXUo2XFxCE-9nhSjh38H-ZRDtt3oR6oBfIveZV6rUglk0wbtuNj5; u_ukey=A10702B8689642C6BE607730E11E6E4A; u_uver=1.0.0; u_dpass=Zd3IqxM1lenA24w9N4GZCB7ZrZyLrgzyM9uffiN%2FZkastIpix78%2FpywARHgknTquHi80LrSsTFH9a%2B6rtRvqGg%3D%3D; u_did=64B7A7ECFC67431A95DFFC10F1247F21; u_ttype=WEB; ttype=WEB; user=MDpteF83MDc4Njc5NTY6Ok5vbmU6NTAwOjcxNzg2Nzk1Njo3LDExMTExMTExMTExLDQwOzQ0LDExLDQwOzYsMSw0MDs1LDEsNDA7MSwxMDEsNDA7MiwxLDQwOzMsMSw0MDs1LDEsNDA3OCwwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMSw0MDsxMDIsMSw0MDoxOTo6OjcwNzg2Nzk1NjoxNzc0NTk1MTQ5Ojo6MTcwNzg5ODg2MDoyNjc4NDAwOjA6MTM2NTU4MDAwNTkyMDM3ZGEyOWY5ZjE3Njg5NDQ3MTIwOmRlZmF1bHRfNTox; userid=707867956; u_name=mx_707867956; escapename=mx_707867956; ticket=d536e59307db002be82af0cee8560553; user_status=0; utk=3ec334f873b1b6e48fff10933ed86662; sess_tk=eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiIsImtpZCI6InNlc3NfdGtfMSIsImJ0eSI6InNlc3NfdGsifQ.eyJqdGkiOiIyMDcxNDQ4OTc2ZjFmOTI5ZGEzNzIwNTkwMDgwNTUzNjEiLCJpYXQiOjE3NzQ1OTUxNDksImV4cCI6MTc3NzI3MzU0OSwic3ViIjoiNzA3ODY3OTU2IiwiaXNzIjoidXBhc3MuMTBqcWthLmNvbS5jbiIsImF1ZCI6IjIwMjAxMTE4NTI4ODkwNzIiLCJhY3QiOiJvZmMiLCJjdWhzIjoiZDdmYzlmODUzYmM1ZTMwODYwNGI1ZTEzZjRjMGRiZmJmODUwZmVlYjJhNTljODZhNDA5OWFlNGY3YmJiMjMzNyJ9.PdFxCF2E4dwpHyI8MmssloQhfsTi1t2bO6_eYFfAJdtNSP9InRfbifLu94IrZsnJs5J1DIqpKFPVRucO8Wu0Ag; cuc=ddrzdtn5o91p; shoudNotCookieRefresh=1' \
  -H 'Sec-Fetch-Dest: empty' \
  -H 'Sec-Fetch-Mode: cors' \
  -H 'Sec-Fetch-Site: same-origin' \
  --data-raw 'terminal=1&version=0.0.0&userid=707867956&user_id=707867956&manual_id=&fund_key=104886643%2C104851645%2C117145680%2C117439808%2C104927183%2C105029212&rzrq_fund_key=129322449' \
  2>/dev/null)

# 保存完整 JSON 数据（包含所有持仓，不只是 ETF）
echo "$RESPONSE" | python3 -c "
import sys, json
d = json.load(sys.stdin)
items = d.get('ex_data', {}).get('position', [])
# 过滤 ETF 并合并相同代码的持仓
etf_raw = [
    {
        'stock_code': i.get('code', ''),
        'stock_name': i.get('name', ''),
        'current_amount': int(float(i.get('count', 0))) if i.get('count') else 0,
        'market_value': float(i.get('value', 0)) if i.get('value') else 0,
        'income_profit': float(i.get('hold_profit', 0)) if i.get('hold_profit') else 0,
        'income_profit_rate': float(i.get('hold_rate', 0)) if i.get('hold_rate') else 0,
        'price': float(i.get('price', 0)) if i.get('price') else 0,
        'cost': float(i.get('cost', 0)) if i.get('cost') else 0,
        'hold_days': int(i.get('hold_days', 0)) if i.get('hold_days') else 0
    }
    for i in items
    if i.get('code', '').startswith('5') or i.get('code', '').startswith('159') or i.get('code', '').startswith('160')
]

# 合并相同代码的持仓（相加数量、市值、盈亏）
etf_merged = {}
for item in etf_raw:
    code = item['stock_code']
    if code not in etf_merged:
        etf_merged[code] = item
    else:
        etf_merged[code]['current_amount'] += item['current_amount']
        etf_merged[code]['market_value'] += item['market_value']
        etf_merged[code]['income_profit'] += item['income_profit']
        # 取最新价格、名称等
        etf_merged[code]['price'] = item['price']
        etf_merged[code]['stock_name'] = item['stock_name']

etf_items = list(etf_merged.values())
result = {'data': {'stock_list': etf_items}, 'updated_at': '$(date +%Y-%m-%d %H:%M:%S)'}
print(json.dumps(result, ensure_ascii=False, indent=2))
" > "$JSON_FILE"

# 提取 ETF 代码保存到 TXT 文件
echo "$RESPONSE" | python3 -c "
import sys, json
d = json.load(sys.stdin)
items = d.get('ex_data', {}).get('position', [])
etf_codes = [i['code'] for i in items if i.get('code', '').startswith('5') or i.get('code', '').startswith('159') or i.get('code', '').startswith('160')]
print(' '.join(sorted(set(etf_codes))), end='')
" >> "$OUTPUT_FILE"

echo "✅ 已获取 $(grep -v '^#' "$OUTPUT_FILE" | wc -w) 只持仓"
echo "📄 详细数据已保存到 holdings_detail.json"
