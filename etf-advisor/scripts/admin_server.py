#!/usr/bin/env python3
"""Admin API server for ETF Advisor.

Provides REST API for fund management, holdings sync, and stock prices.
Runs on 127.0.0.1:8090, proxied by nginx at /admin/api/.

Usage:
    python admin_server.py
    python admin_server.py --port 8090
"""

import atexit
import hashlib
import json
import os
import secrets
import sqlite3
import sys
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR / ".."
DB_PATH = str(PROJECT_ROOT / "data" / "etf_premium.db")

# Import data functions
sys.path.insert(0, str(SCRIPT_DIR))
from update_data import (
    fetch_holdings_from_eastmoney, save_holdings,
    fetch_us_stock_prices, save_stock_prices,
    init_database
)

# Active tokens (in-memory, cleared on restart)
_tokens = {}

# --- Visitor tracking (memory-buffered, periodic flush) ---
DATA_DIR = str(PROJECT_ROOT / "data")
_DATA_FILES = {'report.json', 'rotation_index.json',
               'rotation_nasdaq.json', 'rotation_sp500.json',
               'rotation_nikkei.json', 'rotation_dax.json'}

_visitor_lock = threading.Lock()
_visitor_buf = {}  # {device_id: {'ip': str, 'ua': str, 'visits': int, 'last_seen': str}}
_FLUSH_INTERVAL = 60


def _init_visitor_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS visitors (
        device_id TEXT PRIMARY KEY,
        ip TEXT,
        user_agent TEXT,
        visits INTEGER DEFAULT 0,
        first_seen TEXT,
        last_seen TEXT
    )""")
    conn.commit()
    conn.close()


def _flush_visitors():
    with _visitor_lock:
        buf = _visitor_buf.copy()
        _visitor_buf.clear()
    if buf:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect(DB_PATH)
        for did, info in buf.items():
            conn.execute("""
                INSERT INTO visitors (device_id, ip, user_agent, visits, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    ip = excluded.ip,
                    user_agent = excluded.user_agent,
                    visits = visits + excluded.visits,
                    last_seen = excluded.last_seen
            """, (did, info['ip'], info['ua'], info['visits'], now_str, info['last_seen']))
        conn.commit()
        conn.close()


def _start_flush_timer():
    _flush_visitors()
    t = threading.Timer(_FLUSH_INTERVAL, _start_flush_timer)
    t.daemon = True
    t.start()


def _record_visit(device_id, ip, ua):
    if not device_id:
        return
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with _visitor_lock:
        if device_id in _visitor_buf:
            _visitor_buf[device_id]['visits'] += 1
            _visitor_buf[device_id]['last_seen'] = now_str
            _visitor_buf[device_id]['ip'] = ip
        else:
            _visitor_buf[device_id] = {'ip': ip, 'ua': ua, 'visits': 1, 'last_seen': now_str}


# --- File cache (avoid disk reads on every request) ---
_file_cache = {}  # {filename: {'mtime': float, 'data': bytes}}


def _read_cached_file(filename):
    """Read file with mtime-based cache. Returns bytes or None."""
    filepath = os.path.join(DATA_DIR, filename)
    try:
        mtime = os.path.getmtime(filepath)
    except OSError:
        return None
    cached = _file_cache.get(filename)
    if cached and cached['mtime'] == mtime:
        return cached['data']
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
        _file_cache[filename] = {'mtime': mtime, 'data': data}
        return data
    except OSError:
        return None


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def check_password(password):
    conn = get_db()
    row = conn.execute("SELECT value FROM admin_config WHERE key='password_hash'").fetchone()
    conn.close()
    if not row:
        return False
    return hashlib.sha256(password.encode()).hexdigest() == row['value']


def verify_token(token):
    return token in _tokens and _tokens[token] > time.time()


class AdminHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self._cors_headers()
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        # --- Public: serve data JSON + track visitors ---
        if path.startswith('/data/'):
            filename = path[len('/data/'):]
            if filename in _DATA_FILES:
                device_id = self.headers.get('X-Device-Id', '')
                ip = self.headers.get('X-Real-IP', self.client_address[0])
                ua = self.headers.get('User-Agent', '')
                _record_visit(device_id, ip, ua)
                return self._serve_file(filename)
            return self._json(404, {"error": "not found"})

        # --- Admin: require auth ---
        token = self.headers.get('Authorization', '').replace('Bearer ', '')

        if not verify_token(token):
            return self._json(401, {"error": "未登录"})

        if path == '/admin/api/funds':
            return self._get_funds()
        elif path.startswith('/admin/api/fund/') and path.endswith('/holdings'):
            code = path.split('/')[4]
            return self._get_holdings(code)
        elif path == '/admin/api/stock-prices':
            return self._get_stock_prices()
        elif path == '/admin/api/visitors':
            return self._get_visitors()
        else:
            return self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()

        if path == '/admin/api/login':
            return self._login(body)

        token = self.headers.get('Authorization', '').replace('Bearer ', '')
        if not verify_token(token):
            return self._json(401, {"error": "未登录"})

        if path == '/admin/api/funds':
            return self._add_fund(body)
        elif path.startswith('/admin/api/fund/') and path.endswith('/sync'):
            code = path.split('/')[4]
            return self._sync_holdings(code)
        else:
            return self._json(404, {"error": "not found"})

    def do_PUT(self):
        path = urlparse(self.path).path
        token = self.headers.get('Authorization', '').replace('Bearer ', '')
        if not verify_token(token):
            return self._json(401, {"error": "未登录"})

        body = self._read_body()

        if path.startswith('/admin/api/fund/') and path.endswith('/holdings'):
            code = path.split('/')[4]
            return self._update_holdings(code, body)
        elif path.startswith('/admin/api/fund/'):
            code = path.split('/')[4]
            return self._update_fund(code, body)
        elif path == '/admin/api/settings/password':
            return self._change_password(body)
        else:
            return self._json(404, {"error": "not found"})

    def do_DELETE(self):
        path = urlparse(self.path).path
        token = self.headers.get('Authorization', '').replace('Bearer ', '')
        if not verify_token(token):
            return self._json(401, {"error": "未登录"})

        if path.startswith('/admin/api/fund/'):
            code = path.split('/')[4]
            return self._delete_fund(code)
        return self._json(404, {"error": "not found"})

    # === API Handlers ===

    def _login(self, body):
        if check_password(body.get('password', '')):
            token = secrets.token_hex(32)
            _tokens[token] = time.time() + 86400 * 7  # 7 days
            return self._json(200, {"token": token})
        return self._json(401, {"error": "密码错误"})

    def _get_funds(self):
        conn = get_db()
        rows = conn.execute("SELECT * FROM fund_config ORDER BY category, sort_order").fetchall()
        conn.close()
        return self._json(200, [dict(r) for r in rows])

    def _add_fund(self, body):
        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO fund_config (code, name, company, category, market, estimate_method, estimate_symbol, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (body['code'], body['name'], body.get('company', ''),
                  body.get('category', 'OTHERS'), body.get('market', 'sz'),
                  body.get('estimate_method', 'holdings'), body.get('estimate_symbol'),
                  body.get('sort_order', 99)))
            conn.commit()
            conn.close()
            return self._json(200, {"ok": True})
        except Exception as e:
            conn.close()
            return self._json(400, {"error": str(e)})

    def _update_fund(self, code, body):
        conn = get_db()
        fields = []
        values = []
        for k in ['name', 'company', 'category', 'market', 'estimate_method',
                   'estimate_symbol', 'enabled', 'sort_order', 'rotation_pool', 'rotation_bonus', 'sub_category',
                   'subscription_status', 'subscription_limit']:
            if k in body:
                fields.append(f"{k}=?")
                values.append(body[k])
        if not fields:
            conn.close()
            return self._json(400, {"error": "no fields"})
        values.append(code)
        conn.execute(f"UPDATE fund_config SET {','.join(fields)} WHERE code=?", values)
        conn.commit()
        conn.close()
        return self._json(200, {"ok": True})

    def _delete_fund(self, code):
        conn = get_db()
        conn.execute("DELETE FROM fund_config WHERE code=?", (code,))
        conn.execute("DELETE FROM fund_holdings WHERE fund_code=?", (code,))
        conn.commit()
        conn.close()
        return self._json(200, {"ok": True})

    def _get_holdings(self, code):
        conn = get_db()
        rows = conn.execute("SELECT * FROM fund_holdings WHERE fund_code=? ORDER BY weight_pct DESC", (code,)).fetchall()
        conn.close()
        return self._json(200, [dict(r) for r in rows])

    def _update_holdings(self, code, body):
        holdings = body.get('holdings', [])
        conn = get_db()
        conn.execute("DELETE FROM fund_holdings WHERE fund_code=?", (code,))
        for h in holdings:
            conn.execute("""
                INSERT INTO fund_holdings (fund_code, ticker, stock_name, weight_pct, report_date)
                VALUES (?, ?, ?, ?, ?)
            """, (code, h['ticker'], h.get('stock_name', ''), h.get('weight_pct', 0),
                  h.get('report_date', datetime.now().strftime('%Y-%m-%d'))))
        conn.commit()
        conn.close()
        return self._json(200, {"ok": True, "count": len(holdings)})

    def _sync_holdings(self, code):
        holdings = fetch_holdings_from_eastmoney(code)
        if not holdings:
            return self._json(400, {"error": "无法获取持仓"})
        saved = save_holdings(code, holdings)
        # Also update stock prices
        tickers = [h['ticker'] for h in holdings]
        prices = fetch_us_stock_prices(tickers)
        if prices:
            save_stock_prices(prices)
        return self._json(200, {"ok": True, "holdings": len(holdings), "prices": len(prices)})

    def _get_stock_prices(self):
        conn = get_db()
        rows = conn.execute("SELECT * FROM stock_prices ORDER BY ticker").fetchall()
        conn.close()
        return self._json(200, [dict(r) for r in rows])

    def _serve_file(self, filename):
        body = _read_cached_file(filename)
        if body is None:
            return self._json(404, {"error": "file not found"})
        self.send_response(200)
        self._cors_headers()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _get_visitors(self):
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM visitors ORDER BY last_seen DESC"
        ).fetchall()
        conn.close()
        return self._json(200, [dict(r) for r in rows])

    def _change_password(self, body):
        new_pw = body.get('password', '')
        if len(new_pw) < 4:
            return self._json(400, {"error": "密码太短"})
        pw_hash = hashlib.sha256(new_pw.encode()).hexdigest()
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO admin_config (key, value) VALUES ('password_hash', ?)", (pw_hash,))
        conn.commit()
        conn.close()
        _tokens.clear()
        return self._json(200, {"ok": True})

    # === Helpers ===

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except:
            return {}

    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self._cors_headers()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')

    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}", flush=True)


if __name__ == "__main__":
    init_database()
    _init_visitor_table()
    atexit.register(_flush_visitors)
    _start_flush_timer()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    server = HTTPServer(('127.0.0.1', port), AdminHandler)
    print(f"Admin API server on 127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()
