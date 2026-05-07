#!/bin/bash
cd /opt/etf-advisor
source venv/bin/activate
python3 scripts/update_data.py --realtime >> data/cron.log 2>&1
python3 scripts/recommend_by_change.py --server >> data/cron.log 2>&1
