#!/usr/bin/env python3
"""Portfolio P&L Analyzer · 一键入口

最简用法 — 自动找 Excel + 用今天日期:
    python3 run_analysis.py

或指定 Excel:
    python3 run_analysis.py --xlsx ~/Downloads/汇总持仓.xlsx

或指定年份 / 工作目录:
    python3 run_analysis.py --xlsx ~/Downloads/汇总持仓.xlsx --prior-year 2024
"""
import argparse
import glob
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _utils import validate_excel


def auto_find_xlsx():
    """从 ~/Downloads 找最新的同花顺导出 Excel(文件名含'汇总持仓')"""
    home = Path.home()
    candidates = []
    for pat in ['汇总持仓*.xlsx', 'portfolio*.xlsx', '持仓*.xlsx']:
        candidates.extend(glob.glob(str(home / 'Downloads' / pat)))
    if not candidates:
        return None
    # 取修改时间最新的
    candidates.sort(key=lambda p: Path(p).stat().st_mtime, reverse=True)
    return candidates[0]


def run(cmd, env):
    print(f'\n>>> {cmd}')
    r = subprocess.run(cmd, shell=True, env=env)
    if r.returncode != 0:
        sys.exit(f'FAILED: {cmd}')


def main():
    ap = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                  description=__doc__)
    ap.add_argument('--xlsx', help='同花顺导出 Excel 路径(留空 = 自动找 ~/Downloads/汇总持仓*.xlsx)')
    today_default = date.today().isoformat()
    ap.add_argument('--today', default=today_default, help=f'当前日期(默认 {today_default})')
    ap.add_argument('--prior-year', type=int, help='去年(默认 = today 年 - 1)')
    ap.add_argument('--cur-year', type=int, help='今年(默认 = today 年)')
    ap.add_argument('--work-dir', help='工作目录(默认 ~/gei-workspace/output/portfolio-pnl-{today}/)')
    ap.add_argument('--open', action='store_true', help='跑完自动在 Chrome 打开 HTML')
    args = ap.parse_args()

    # 1. xlsx 推断
    xlsx = args.xlsx or auto_find_xlsx()
    if not xlsx:
        sys.exit('❌ 找不到 Excel。请指定 --xlsx,或把同花顺导出文件放到 ~/Downloads/ 下,名字含"汇总持仓"。')
    xlsx = str(Path(xlsx).expanduser().resolve())
    if not Path(xlsx).exists():
        sys.exit(f'❌ Excel 不存在: {xlsx}')
    print(f'✓ Excel: {xlsx}')

    # 2. Schema 验证
    errors = validate_excel(xlsx)
    if errors:
        print('❌ Excel schema 错误:')
        for e in errors: print(f'  · {e}')
        sys.exit('请检查 Excel 是否同花顺标准导出(必需 sheet: 持仓数据/已清仓/交易记录)。')
    print('✓ Excel schema OK(3 个 sheet + 必需列齐全)')

    # 3. 年份推断
    today_year = int(args.today[:4])
    cur_year = args.cur_year or today_year
    prior_year = args.prior_year or (cur_year - 1)
    print(f'✓ 期间: {prior_year} 全年 + {cur_year} YTD(至 {args.today})')

    # 4. work_dir 推断
    work_dir = args.work_dir or f'~/gei-workspace/output/portfolio-pnl-{args.today}/'
    work = Path(work_dir).expanduser().resolve()
    (work / 'data').mkdir(parents=True, exist_ok=True)
    (work / 'reports').mkdir(parents=True, exist_ok=True)
    print(f'✓ 工作目录: {work}')

    # 5. 环境变量 + 跑 4 步
    env = os.environ.copy()
    env['PORTFOLIO_XLSX'] = xlsx
    env['PORTFOLIO_WORK_DIR'] = str(work)
    env['PORTFOLIO_PRIOR_YEAR'] = str(prior_year)
    env['PORTFOLIO_CUR_YEAR'] = str(cur_year)
    env['PORTFOLIO_TODAY'] = args.today

    print('\n══════════════════════════════════════════')
    print('  Pipeline 启动 · 6 步')
    print('══════════════════════════════════════════')
    run(f'python3 "{HERE}/01_build_snapshots.py"', env)
    run(f'python3 "{HERE}/02_fetch_prices.py"', env)
    run(f'python3 "{HERE}/03b_generate_registry.py"', env)
    run(f'python3 "{HERE}/04_calc_pnl.py"', env)
    run(f'python3 "{HERE}/06_build_monthly_db.py"', env)
    run(f'python3 "{HERE}/05_report.py"', env)

    md = work / 'reports' / f'analysis-{args.today}.md'
    html = work / 'reports' / f'analysis-{args.today}.html'

    print(f'\n══════════════════════════════════════════')
    print(f'  ✓ 完成')
    print(f'══════════════════════════════════════════')
    print(f'  📄 MD:   {md}')
    print(f'  🌐 HTML: {html}')
    print(f'  📊 资产清单: {work}/data/asset-registry.md')

    if args.open or sys.platform == 'darwin':
        os.system(f'open -a "Google Chrome" "{html}"')
        print(f'  → 已在 Chrome 打开')


if __name__ == '__main__':
    main()
