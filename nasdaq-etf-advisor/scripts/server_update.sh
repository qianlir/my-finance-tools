#!/bin/bash
# server_update.sh — 服务器定时任务：采集数据 + 生成JSON报告
# crontab: */5 9-15 * * 1-5 /path/to/server_update.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON=python3
LOG_FILE="$PROJECT_DIR/data/server.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') Starting update..." >> "$LOG_FILE"

# Step 1: 采集实时数据 (~4秒)
$PYTHON "$SCRIPT_DIR/update_data.py" --realtime >> "$LOG_FILE" 2>&1

# Step 2: 生成 report.json（仅计算，无 Chrome/PNG/微信）
$PYTHON "$SCRIPT_DIR/recommend_by_change.py" --server >> "$LOG_FILE" 2>&1

echo "$(date '+%Y-%m-%d %H:%M:%S') Update complete." >> "$LOG_FILE"
echo "---" >> "$LOG_FILE"
