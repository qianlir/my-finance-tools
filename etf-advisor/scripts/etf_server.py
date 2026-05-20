#!/usr/bin/env python3
"""
ETF report update daemon.

Runs update_data.py --realtime + recommend_by_change.py --server
at a configurable interval (default 60s) during A-share market hours.

nginx serves the generated static files (report.html / report.json) directly.
This script is ONLY for data refresh, not for serving HTTP requests.

Usage:
    python etf_server.py              # 60s interval
    python etf_server.py --interval 120
    python etf_server.py --once       # run once and exit
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR / ".."


def is_us_dst():
    """判断当前是否美国夏令时 (3月第二个周日 ~ 11月第一个周日)"""
    now = datetime.now()
    year = now.year
    # 3月第二个周日
    mar1 = datetime(year, 3, 1)
    dst_start = mar1.replace(day=(14 - mar1.weekday()) % 7 + 8)
    # 11月第一个周日
    nov1 = datetime(year, 11, 1)
    dst_end = nov1.replace(day=(7 - nov1.weekday()) % 7 + 1)
    return dst_start <= now.replace(hour=0, minute=0, second=0) < dst_end


def get_anchor_hour():
    """美股盘后结束对应的北京时间小时: 夏令时=8, 冬令时=9"""
    return 8 if is_us_dst() else 9


def is_market_hours():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    hour, minute = now.hour, now.minute
    t = hour * 60 + minute
    return 9 * 60 + 15 <= t <= 15 * 60 + 5


def try_capture_anchor():
    """在美股盘后结束时刻采集 NQ/ES 锚点价 (每天一次)"""
    now = datetime.now()
    anchor_hour = get_anchor_hour()
    # 在锚点时间 ± 30 分钟内采集
    if now.weekday() >= 5:
        return
    if not (anchor_hour * 60 - 30 <= now.hour * 60 + now.minute <= anchor_hour * 60 + 30):
        return
    venv_python = Path(sys.prefix) / "bin" / "python3"
    python_cmd = str(venv_python) if venv_python.exists() else sys.executable
    try:
        subprocess.run(
            [python_cmd, "-c",
             "import sys; sys.path.insert(0, 'scripts'); "
             "from update_data import init_database, capture_futures_anchor; "
             "init_database(); capture_futures_anchor()"],
            cwd=str(PROJECT_ROOT), timeout=15, check=False,
            capture_output=True
        )
    except Exception:
        pass


def run_update():
    venv_python = Path(sys.prefix) / "bin" / "python3"
    python_cmd = str(venv_python) if venv_python.exists() else sys.executable

    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] Running update...", flush=True)

    try:
        subprocess.run(
            [python_cmd, str(SCRIPT_DIR / "update_data.py"), "--realtime"],
            cwd=str(PROJECT_ROOT), timeout=60, check=True,
            capture_output=True
        )
        subprocess.run(
            [python_cmd, str(SCRIPT_DIR / "recommend_by_change.py"), "--server"],
            cwd=str(PROJECT_ROOT), timeout=60, check=True,
            capture_output=True
        )
        subprocess.run(
            [python_cmd, str(SCRIPT_DIR / "calc_rotation_index.py"), "--index", "all"],
            cwd=str(PROJECT_ROOT), timeout=180, check=True,
            capture_output=True
        )
        subprocess.run(
            [python_cmd, str(SCRIPT_DIR / "notify_top_change.py")],
            cwd=str(PROJECT_ROOT), timeout=15, check=False,
            capture_output=True
        )
        print(f"[{ts}] Update OK", flush=True)
    except Exception as e:
        print(f"[{ts}] Update FAILED: {e}", flush=True)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    run_update()
    if args.once:
        return

    print(f"Daemon mode: market={args.interval}s, idle=600s", flush=True)
    while True:
        interval = args.interval if is_market_hours() else 600
        time.sleep(interval)
        try_capture_anchor()  # 在美股盘后结束时采集锚点价 (每天一次)
        run_update()


if __name__ == "__main__":
    main()
