#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_holdings.py — 调用系统 curl 获取持仓

Usage:
    python fetch_holdings.py
"""

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
SHELL_SCRIPT = SCRIPT_DIR / "fetch_holdings.sh"

def fetch_holdings():
    """调用 shell 脚本获取持仓"""
    try:
        result = subprocess.run(
            [str(SHELL_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # 读取生成的文件
        holdings_file = SCRIPT_DIR / ".." / "data" / "holdings.txt"
        if holdings_file.exists():
            content = holdings_file.read_text()
            # 提取代码（跳过注释行）
            codes = [line for line in content.split('\n')
                     if line and not line.startswith('#')]
            if codes:
                return codes[0].split()
        return []
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return []

def main():
    codes = fetch_holdings()
    if codes:
        print(" ".join(codes))
        return 0
    return 1

if __name__ == "__main__":
    sys.exit(main())
