#!/bin/bash
set -e

REMOTE="root@qianli_vm"
REMOTE_DIR="/opt/etf-advisor"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Syncing $LOCAL_DIR → $REMOTE:$REMOTE_DIR ==="

ssh $REMOTE "mkdir -p $REMOTE_DIR/{data,web,memory/knowledge/etf,deploy}"

rsync -avz --delete --exclude='__pycache__' --exclude='venv' \
  "$LOCAL_DIR/scripts/" "$REMOTE:$REMOTE_DIR/scripts/"

rsync -avz --delete "$LOCAL_DIR/web/" "$REMOTE:$REMOTE_DIR/web/"
rsync -avz "$LOCAL_DIR/deploy/" "$REMOTE:$REMOTE_DIR/deploy/"
rsync -avz "$LOCAL_DIR/memory/knowledge/etf/" "$REMOTE:$REMOTE_DIR/memory/knowledge/etf/"
rsync -avz "$LOCAL_DIR/data/etf_premium.db" "$REMOTE:$REMOTE_DIR/data/"
[ -f "$LOCAL_DIR/data/report.json" ] && rsync -avz "$LOCAL_DIR/data/report.json" "$REMOTE:$REMOTE_DIR/data/"
[ -f "$LOCAL_DIR/data/rotation_index.json" ] && rsync -avz "$LOCAL_DIR/data/rotation_index.json" "$REMOTE:$REMOTE_DIR/data/"

echo "=== Setting up venv + deps ==="
ssh $REMOTE "cd $REMOTE_DIR && python3 -m venv venv && venv/bin/pip install -q requests"

echo "=== Installing systemd service (update daemon, 60s interval) ==="
ssh $REMOTE "cp $REMOTE_DIR/deploy/etf-advisor.service /etc/systemd/system/ && \
  systemctl daemon-reload && \
  systemctl enable etf-advisor && \
  systemctl restart etf-advisor"

echo "=== Installing nginx config (static file serving on :8088) ==="
ssh $REMOTE "cp $REMOTE_DIR/deploy/nginx-etf.conf /etc/nginx/sites-enabled/etf-advisor && \
  nginx -t && systemctl reload nginx"

echo "=== Verifying ==="
ssh $REMOTE "systemctl status etf-advisor --no-pager -l | head -10"
echo ""
IP=$(ssh $REMOTE 'hostname -I | awk "{print \$1}"')
echo "Done! Visit http://${IP}:8088/"
