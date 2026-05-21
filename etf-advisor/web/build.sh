#!/bin/bash
# build.sh — 编译 app.js
#
# 流程:
#   1. 编译 4 个 JSX (shared + pc + mobile + tweaks-panel)
#   2. 追加 app-bootstrap.js (parseRoute + App + createRoot)
#   3. 验证关键符号 + 语法检查
#
# 用法:
#   bash web/build.sh          # 从项目根目录
#   bash build.sh              # 从 web/ 目录
#   bash build.sh --deploy     # 编译 + 部署到服务器

set -e
cd "$(dirname "$0")"

echo "=== Building app.js ==="

node -e '
const fs = require("fs");
const { transform } = require("@babel/standalone");

const jsxFiles = ["shared.jsx", "pc.jsx", "mobile.jsx", "tweaks-panel.jsx"];
const parts = [];

for (const file of jsxFiles) {
  if (!fs.existsSync(file)) { console.error("MISSING: " + file); process.exit(1); }
  const result = transform(fs.readFileSync(file, "utf8"), { presets: ["react"] }).code;
  parts.push("// --- " + file + " ---\n" + result);
  console.log("  " + file + ": " + result.length + " chars");
}

if (!fs.existsSync("app-bootstrap.js")) {
  console.error("MISSING: app-bootstrap.js"); process.exit(1);
}
parts.push("// --- app-bootstrap.js ---\n" + fs.readFileSync("app-bootstrap.js", "utf8"));
console.log("  app-bootstrap.js: appended");

const app = parts.join("\n\n");
fs.writeFileSync("app.js", app);

// 验证
const checks = {
  parseRoute: (app.match(/function parseRoute/g) || []).length,
  createRoot: (app.match(/ReactDOM.createRoot/g) || []).length,
  setSelFund: (app.match(/setSelFund/g) || []).length,
  TweaksPanel: (app.match(/TweaksPanel/g) || []).length,
  estimated_nav: (app.match(/estimated_nav/g) || []).length,
};

let ok = true;
if (checks.parseRoute !== 1) { console.error("FAIL: parseRoute=" + checks.parseRoute + " (want 1)"); ok = false; }
if (checks.createRoot !== 1) { console.error("FAIL: createRoot=" + checks.createRoot + " (want 1)"); ok = false; }
if (checks.setSelFund < 1) { console.error("FAIL: setSelFund=0"); ok = false; }
if (checks.TweaksPanel < 1) { console.error("FAIL: TweaksPanel=0"); ok = false; }
if (!ok) process.exit(1);

try { new Function(app); } catch(e) { console.error("SYNTAX ERROR: " + e.message); process.exit(1); }

console.log("  app.js: " + app.length + " chars ✓");
console.log("  checks:", JSON.stringify(checks));
console.log("=== Build OK ===");
'

# 可选: --deploy 参数时自动部署
if [ "$1" = "--deploy" ]; then
  echo "=== Deploying ==="
  scp app.js root@qianli_vm:/opt/etf-advisor/web/app.js
  ssh root@qianli_vm 'cp /opt/etf-advisor/web/app.js /opt/etf-advisor/web/app.js.server-backup'
  echo "=== Deploy OK ==="
fi
