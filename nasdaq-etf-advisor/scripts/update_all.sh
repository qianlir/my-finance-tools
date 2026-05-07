#!/bin/bash
# update_all.sh — 一键更新所有数据

cd "$(dirname "$0")/.."

echo "=========================================="
echo "更新 ETF 投资助手数据"
echo "=========================================="

# 1. 更新实时数据
echo "[1/2] 采集实时数据..."
python scripts/update_data.py --realtime

# 2. 生成报告
echo "[2/2] 生成分析报告..."
python scripts/recommend_by_change.py --server

echo ""
echo "✓ 更新完成！"
echo "  报告: data/report.json"
echo "  回测: data/backtest.json (如需要)"
echo ""
echo "启动服务器: python scripts/server.py"
