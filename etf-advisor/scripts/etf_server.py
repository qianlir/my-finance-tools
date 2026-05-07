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


def is_market_hours():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    hour, minute = now.hour, now.minute
    t = hour * 60 + minute
    return 9 * 60 + 15 <= t <= 15 * 60 + 5


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

    print(f"Daemon mode: interval={args.interval}s, market hours only", flush=True)
    while True:
        time.sleep(args.interval)
        if is_market_hours():
            run_update()


if __name__ == "__main__":
    main()
