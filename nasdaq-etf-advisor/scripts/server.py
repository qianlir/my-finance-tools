#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server.py — 本地 Flask 服务器，代理 10jqka API 解决 CORS 问题

Usage:
    python server.py              # 启动服务器，默认 http://127.0.0.1:8080
    python server.py --port 9000  # 指定端口
"""

import os
import sys
import json
import re
import subprocess
import sqlite3
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, Response

# 配置
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / ".." / "data"
DB_PATH = DATA_DIR / "etf_premium.db"
HOLDINGS_FILE = DATA_DIR / "holdings.txt"
HOLDINGS_JSON_FILE = DATA_DIR / "holdings_detail.json"
PORT = 8080

app = Flask(__name__, static_folder=str(DATA_DIR))


def get_etf_info(codes):
    """从数据库获取 ETF 信息"""
    if not DB_PATH.exists():
        return {}

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        placeholders = ','.join(['?' for _ in codes])
        # 获取最新日期的数据
        query = f"""
            SELECT code, name, price, premium_rate, nav
            FROM etf_data
            WHERE code IN ({placeholders})
            AND date = (SELECT MAX(date) FROM etf_data)
        """
        cursor.execute(query, codes)

        result = {row['code']: dict(row) for row in cursor.fetchall()}
        conn.close()
        return result
    except Exception as e:
        print(f"数据库查询错误: {e}")
        return {}


def read_holdings_file():
    """读取 holdings.txt 文件"""
    if not HOLDINGS_FILE.exists():
        return []

    content = HOLDINGS_FILE.read_text()
    lines = [line.strip() for line in content.split('\n')
             if line.strip() and not line.startswith('#')]

    if lines:
        return lines[0].split()
    return []


@app.route('/')
@app.route('/<path:path>')
def serve_static(path="home.html"):
    """服务静态 HTML 文件"""
    if path and (DATA_DIR / path).exists():
        return send_from_directory(DATA_DIR, path)
    return send_from_directory(DATA_DIR, "home.html")


@app.route('/api/holdings-local', methods=['GET'])
def get_local_holdings():
    """获取本地持仓数据（优先从 holdings_detail.json，回退到 holdings.txt + 数据库）"""
    try:
        # 优先尝试读取 JSON 详情文件（包含完整数量、市值信息）
        if HOLDINGS_JSON_FILE.exists():
            try:
                data = json.loads(HOLDINGS_JSON_FILE.read_text())
                stock_list = data.get('data', {}).get('stock_list', [])
                updated_at = data.get('updated_at', '')

                # 从数据库补充实时价格和溢价率
                codes = [item.get('stock_code') for item in stock_list if item.get('stock_code')]
                etf_info = get_etf_info(codes)

                # 合并数据库信息
                for item in stock_list:
                    code = item.get('stock_code')
                    if code in etf_info:
                        item['price'] = etf_info[code].get('price', 0)
                        item['premium_rate'] = etf_info[code].get('premium_rate', 0)

                return jsonify({
                    'data': {'stock_list': stock_list},
                    '_debug': {
                        'total_stocks': len(stock_list),
                        'source': 'holdings_detail.json',
                        'update_time': updated_at,
                        'has_full_data': True
                    }
                })
            except Exception as e:
                print(f"读取 JSON 文件失败: {e}，回退到 txt 文件")

        # 回退：读取 txt 文件
        codes = read_holdings_file()

        if not codes:
            return jsonify({
                'data': {'stock_list': []},
                '_debug': {
                    'total_stocks': 0,
                    'source': 'local_file',
                    'message': 'holdings.txt 不存在或为空'
                }
            })

        # 从数据库获取详细信息
        etf_info = get_etf_info(codes)

        # 构造响应格式（与 API 格式兼容）
        stock_list = []
        for code in codes:
            info = etf_info.get(code, {})
            stock_list.append({
                'stock_code': code,
                'stock_name': info.get('name', ''),
                'current_amount': 0,  # txt 文件没有数量信息
                'market_value': 0,   # txt 文件没有市值信息
                'income_profit': 0,   # txt 文件没有盈亏信息
                'income_profit_rate': 0,
                # 额外的实时数据
                'price': info.get('price', 0),
                'premium_rate': info.get('premium_rate', 0)
            })

        # 读取文件更新时间
        update_time = ''
        if HOLDINGS_FILE.exists():
            for line in HOLDINGS_FILE.read_text().split('\n'):
                if line.startswith('# 更新时间:'):
                    update_time = line.replace('# 更新时间:', '').strip()
                    break

        return jsonify({
            'data': {'stock_list': stock_list},
            '_debug': {
                'total_stocks': len(stock_list),
                'source': 'holdings.txt',
                'update_time': update_time,
                'with_db_info': len(etf_info),
                'has_full_data': False
            }
        })

    except Exception as e:
        return jsonify({
            'error': str(e),
            'data': {'stock_list': []}
        }), 500


@app.route('/api/holdings', methods=['POST'])
def proxy_holdings():
    """代理 10jqka 持仓 API"""
    data = request.json
    cookie = data.get('cookie', '')

    if not cookie:
        return jsonify({'error': '缺少 cookie'}), 400

    # 提取 userid
    userid_match = re.search(r'userid=(\d+)', cookie)
    userid = userid_match.group(1) if userid_match else None

    if not userid:
        return jsonify({'error': 'Cookie 中未找到 userid'}), 400

    # 构造请求
    headers = {
        'Cookie': cookie,
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://tzzb.10jqka.com.cn',
        'Referer': 'https://tzzb.10jqka.com.cn/pc/index.html'
    }

    # 从请求中获取 fund_key（如果有）
    fund_key = data.get('fund_key', '')

    post_data = {
        'terminal': '1',
        'version': '0.0.0',
        'userid': userid,
        'user_id': userid,
        'manual_id': '',
        'fund_key': fund_key,
        'rzrq_fund_key': ''
    }

    try:
        # 使用 shell 脚本调用 API（绕过 Python 环境限制）
        script_path = SCRIPT_DIR / "fetch_holdings_api.sh"
        cmd = [str(script_path), cookie, userid, fund_key]

        result_proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

        if result_proc.returncode != 0:
            return jsonify({'error': f'curl 执行失败: {result_proc.stderr[:200]}'}), 500

        response_text = result_proc.stdout.strip()
        if not response_text:
            return jsonify({'error': 'API 无响应'}), 500

        result = json.loads(response_text)

        # 统一响应格式：将 ex_data.position 转换为 data.stock_list
        # (网页期望 data.stock_list 格式)
        if result.get('ex_data') and result['ex_data'].get('position'):
            # 新格式：ex_data.position
            position_items = result['ex_data']['position']

            # 转换为旧格式（注意：API 字段名是 count/value/hold_profit/hold_rate）
            stock_list = []
            for item in position_items:
                # 处理字符串类型的数值
                def safe_float(val, default=0):
                    try:
                        return float(val) if val else default
                    except (ValueError, TypeError):
                        return default

                def safe_int(val, default=0):
                    try:
                        return int(float(val)) if val else default
                    except (ValueError, TypeError):
                        return default

                stock_list.append({
                    'stock_code': item.get('code', ''),
                    'stock_name': item.get('name', ''),
                    'current_amount': safe_int(item.get('count')),
                    'market_value': safe_float(item.get('value')),
                    'income_profit': safe_float(item.get('hold_profit')),
                    'income_profit_rate': safe_float(item.get('hold_rate'))
                })

            # 构造统一响应格式
            result = {
                'data': {
                    'stock_list': stock_list
                },
                '_debug': {
                    'total_stocks': len(stock_list),
                    'fund_key_used': fund_key or '(empty)',
                    'original_format': 'ex_data.position'
                }
            }

        elif result.get('data') and result['data'].get('stock_list'):
            # 旧格式：data.stock_list（已经是网页期望的格式）
            if '_debug' not in result:
                result['_debug'] = {}
            result['_debug']['total_stocks'] = len(result['data']['stock_list'])
            result['_debug']['fund_key_used'] = fund_key or '(empty)'
            result['_debug']['original_format'] = 'data.stock_list'
        else:
            # 无数据
            result = {
                'data': {'stock_list': []},
                '_debug': {'total_stocks': 0, 'fund_key_used': fund_key or '(empty)'}
            }

        return jsonify(result)

    except subprocess.TimeoutExpired:
        return jsonify({'error': '请求超时'}), 500
    except json.JSONDecodeError as e:
        return jsonify({'error': f'JSON 解析失败: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'请求失败: {str(e)}'}), 500


@app.route('/api/parse-curl', methods=['POST'])
def parse_curl():
    """解析 curl 命令，提取 cookie"""
    data = request.json
    curl_cmd = data.get('curl', '')

    # 提取 -H 'Cookie: ...' 中的内容
    cookie_match = re.search(r"-H\s+'(?:Cookie:\s*)?([^']+)'", curl_cmd)
    if cookie_match:
        cookie = cookie_match.group(1)
        # 提取 userid
        userid_match = re.search(r'userid=(\d+)', cookie)
        userid = userid_match.group(1) if userid_match else None
        return jsonify({'cookie': cookie, 'userid': userid})

    return jsonify({'error': '无法解析 curl 命令'}), 400


def main():
    import argparse
    parser = argparse.ArgumentParser(description='ETF 投资助手本地服务器')
    parser.add_argument('--port', type=int, default=PORT, help='端口号')
    parser.add_argument('--host', default='127.0.0.1', help='主机地址')
    args = parser.parse_args()

    print(f"启动服务器: http://{args.host}:{args.port}")
    print(f"数据目录: {DATA_DIR}")
    print("按 Ctrl+C 停止")

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()
