#!/bin/bash
# local_scheduled_update.sh — 本地定时任务：采集数据 + 生成报告 + 提交微信
# 仅在交易时间执行：工作日 9:30-15:00

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON=python3
LOG_FILE="$PROJECT_DIR/data/scheduled.log"

# 检查是否在交易时间
# 工作日 9:30-15:00
DAY_OF_WEEK=$(date '+%u')  # 1-5 (周一到周五)
HOUR=$(date '+%H')
MINUTE=$(date '+%M')
# 去除前导零（避免八进制解释）
HOUR=$((10#$HOUR))
MINUTE=$((10#$MINUTE))

# 周末不执行
if [ "$DAY_OF_WEEK" -ge 6 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') Weekend, skipping." >> "$LOG_FILE"
    exit 0
fi

# 非交易时间不执行 (9:30前, 15:00后)
TOTAL_MINUTES=$((HOUR * 60 + MINUTE))
if [ "$TOTAL_MINUTES" -lt 570 ] || [ "$TOTAL_MINUTES" -ge 900 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') Outside trading hours, skipping." >> "$LOG_FILE"
    exit 0
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') Starting scheduled update..." >> "$LOG_FILE"

# Step 1: 采集实时数据
$PYTHON "$SCRIPT_DIR/update_data.py" --realtime >> "$LOG_FILE" 2>&1

# Step 2: 生成 report.json（小程序数据）
$PYTHON "$SCRIPT_DIR/recommend_by_change.py" --server >> "$LOG_FILE" 2>&1

# Step 3: 生成报告并自动提交微信草稿
$PYTHON "$SCRIPT_DIR/recommend_by_change.py" >> "$LOG_FILE" 2>&1

echo "$(date '+%Y-%m-%d %H:%M:%S') Scheduled update complete." >> "$LOG_FILE"
echo "---" >> "$LOG_FILE"
