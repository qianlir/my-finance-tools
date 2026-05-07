#!/bin/bash
# fetch_holdings_api.sh — 通过环境变量传递 curl 命令
# 用法: export API_CURL_CMD="完整的curl命令"; fetch_holdings_api.sh

# 从环境变量获取 curl 命令（包含完整的 Cookie 和 headers）
if [ -n "$API_CURL_CMD" ]; then
    # 直接执行传入的 curl 命令
    eval "$API_CURL_CMD"
else
    # 回退：使用参数方式（可能不完全可靠）
    COOKIE="$1"
    USERID="$2"
    FUND_KEY="${3:-}"

    curl -s 'https://tzzb.10jqka.com.cn/caishen_httpserver/tzzb/caishen_fund/pc/asset/v1/stock_position' \
      -X POST \
      -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:148.0) Gecko/20100101 Firefox/148.0' \
      -H 'Accept: application/json, text/plain, */*' \
      -H 'Accept-Language: zh-CN,ja;q=0.9,zh;q=0.8' \
      -H 'Content-Type: application/x-www-form-urlencoded' \
      -H 'Origin: https://tzzb.10jqka.com.cn' \
      -H 'Connection: keep-alive' \
      -H 'Referer: https://tzzb.10jqka.com.cn/pc/index.html' \
      -H "Cookie: $COOKIE" \
      -H 'Sec-Fetch-Dest: empty' \
      -H 'Sec-Fetch-Mode: cors' \
      -H 'Sec-Fetch-Site: same-origin' \
      --data-raw "terminal=1&version=0.0.0&userid=$USERID&user_id=$USERID&manual_id=&fund_key=$FUND_KEY&rzrq_fund_key="
fi
