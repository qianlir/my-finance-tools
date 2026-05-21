#!/bin/bash
# test.sh — 前端+后端 冒烟测试
#
# 用法:
#   bash web/test.sh              # 测试本地
#   bash web/test.sh --server     # 测试生产服务器

set -e
cd "$(dirname "$0")/.."

PASS=0
FAIL=0
SERVER=""

if [ "$1" = "--server" ]; then
  SERVER="root@qianli_vm"
  BASE_URL="https://invest.qianli.wang"
  echo "=== 测试生产服务器 ==="
else
  BASE_URL="http://localhost:8000"
  echo "=== 测试本地 ==="
fi

pass() { PASS=$((PASS + 1)); echo "  ✅ $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  ❌ $1"; }

# ====== 后端测试 ======
echo ""
echo "--- 后端: report.json ---"

REPORT=$(curl -sf "${BASE_URL}/data/report.json" 2>/dev/null || echo "")
if [ -z "$REPORT" ]; then
  fail "report.json 无法加载"
else
  pass "report.json 可加载"

  # 检查必要字段
  for field in estimated_nav display_premium nav_formula; do
    count=$(echo "$REPORT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(sum(1 for s in d.get('sections',[]) for e in s.get('etfs',[]) if e.get('$field') is not None))" 2>/dev/null || echo 0)
    if [ "$count" -gt 0 ]; then
      pass "$field: ${count} 只ETF有值"
    else
      fail "$field: 无数据"
    fi
  done

  # 检查 holdings 有 after_hours
  ah_count=$(echo "$REPORT" | python3 -c "
import json,sys
d=json.load(sys.stdin)
n=0
for s in d.get('sections',[]):
  for e in s.get('etfs',[]):
    for h in (e.get('holdings') or []):
      if h.get('after_hours') and h['after_hours'] > 1: n+=1
print(n)
" 2>/dev/null || echo 0)
  if [ "$ah_count" -gt 0 ]; then
    pass "holdings after_hours: ${ah_count} 只个股有盘后价"
  else
    fail "holdings after_hours: 无盘后价数据"
  fi

  # 检查 estimated_nav != nav (OTHERS ETF)
  nav_diff=$(echo "$REPORT" | python3 -c "
import json,sys
d=json.load(sys.stdin)
n=0
for s in d.get('sections',[]):
  for e in s.get('etfs',[]):
    nav = e.get('nav',0)
    est = e.get('estimated_nav',0)
    if nav and est and abs(est - nav) > 0.001: n+=1
print(n)
" 2>/dev/null || echo 0)
  if [ "$nav_diff" -gt 0 ]; then
    pass "estimated_nav != nav: ${nav_diff} 只ETF有估算差异"
  else
    fail "estimated_nav == nav: 估算净值未生效"
  fi
fi

# ====== 前端测试 ======
echo ""
echo "--- 前端: app.js ---"

APP_JS="${BASE_URL}/app.js"
APP=$(curl -sf "$APP_JS" 2>/dev/null || echo "")
if [ -z "$APP" ]; then
  fail "app.js 无法加载"
else
  pass "app.js 可加载 ($(echo "$APP" | wc -c | tr -d ' ') bytes)"

  for sym in parseRoute "ReactDOM.createRoot" setSelFund TweaksPanel estimated_nav nav_formula; do
    count=$(echo "$APP" | grep -c "$sym" || true)
    if [ "$count" -gt 0 ]; then
      pass "app.js 含 $sym ($count)"
    else
      fail "app.js 缺少 $sym"
    fi
  done
fi

# ====== 页面加载测试 ======
echo ""
echo "--- 页面加载 ---"

if [ -n "$SERVER" ]; then
  # 服务器有 nginx SPA 路由, 测试所有路径
  for path in "/" "/m/" "/premium" "/m/premium" "/rotation" "/m/rotation"; do
    status=$(curl -sf -o /dev/null -w "%{http_code}" "${BASE_URL}${path}" 2>/dev/null || echo "000")
    if [ "$status" = "200" ]; then
      pass "${path} → HTTP ${status}"
    else
      fail "${path} → HTTP ${status}"
    fi
  done
else
  # 本地 python http.server 不支持 SPA 路由, 只测 /
  status=$(curl -sf -o /dev/null -w "%{http_code}" "${BASE_URL}/" 2>/dev/null || echo "000")
  if [ "$status" = "200" ]; then
    pass "/ → HTTP ${status}"
  else
    fail "/ → HTTP ${status}"
  fi
  echo "  (跳过 SPA 路由测试, 本地无 nginx)"
fi

# ====== 轮动数据测试 ======
echo ""
echo "--- 轮动数据 ---"

for idx in nasdaq sp500 nikkei dax; do
  ROT=$(curl -sf "${BASE_URL}/data/rotation_${idx}.json" 2>/dev/null || echo "")
  if [ -z "$ROT" ]; then
    fail "rotation_${idx}.json 无法加载"
  else
    ret=$(echo "$ROT" | python3 -c "import json,sys; print(json.load(sys.stdin)['summary']['rotation_return'])" 2>/dev/null || echo "?")
    pass "rotation_${idx}.json: 收益 ${ret}%"
  fi
done

# ====== 汇总 ======
echo ""
echo "================================"
echo "  通过: ${PASS}  失败: ${FAIL}"
echo "================================"

# ====== 本地 UI 测试 (仅本地模式) ======
if [ -z "$SERVER" ]; then
  echo ""
  echo "--- 本地 UI 测试 ---"

  # 用 node 检查 app.js 能否无错执行（模拟浏览器环境）
  node -e "
    // 模拟最小 DOM 环境
    global.window = global;
    global.document = { getElementById: () => ({ }) };
    global.location = { pathname: '/', search: '', hostname: 'localhost' };
    global.navigator = { userAgent: 'test' };
    global.history = { replaceState: () => {} };
    global.HTMLElement = class {};
    global.localStorage = { getItem: () => null, setItem: () => {} };

    // 模拟 React (只检查 app.js 的函数定义不报错)
    global.React = {
      createElement: () => null,
      useState: (v) => [v, () => {}],
      useEffect: () => {},
      useRef: () => ({ current: null }),
      useMemo: (fn) => fn(),
      useCallback: (fn) => fn,
      Fragment: 'Fragment',
    };
    global.ReactDOM = { createRoot: () => ({ render: () => {} }) };
    global.Chart = function() { return { destroy: () => {} }; };

    try {
      require('./web/app.js');
      console.log('OK');
    } catch(e) {
      console.log('FAIL: ' + e.message);
      process.exit(1);
    }
  " 2>&1
  result=$?
  if [ $result -eq 0 ]; then
    pass "app.js 模拟加载无错误"
  else
    fail "app.js 模拟加载失败"
  fi

  # 检查 data.js 语法
  node -e "new Function(require('fs').readFileSync('web/data.js','utf8')); console.log('OK')" 2>&1
  result=$?
  if [ $result -eq 0 ]; then
    pass "data.js 语法正确"
  else
    fail "data.js 语法错误"
  fi

  # 检查 rotation.js 语法
  node -e "new Function(require('fs').readFileSync('web/rotation.js','utf8')); console.log('OK')" 2>&1
  result=$?
  if [ $result -eq 0 ]; then
    pass "rotation.js 语法正确"
  else
    fail "rotation.js 语法错误"
  fi
fi

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
