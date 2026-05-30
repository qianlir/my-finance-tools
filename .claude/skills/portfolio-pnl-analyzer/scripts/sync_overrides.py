#!/usr/bin/env python3
"""把指定 work_dir 的 sectors.csv 合并/同步回 skill 基线 sector-overrides.csv。

Usage:
  python3 sync_overrides.py <work_dir>/data/sectors.csv
  python3 sync_overrides.py <work_dir>/data/sectors.csv --mode replace

模式:
  merge (默认)  -- 新代码追加,已有代码用 sectors.csv 的最新归类覆盖
  replace      -- 全量替换 skill 基线
"""
import csv
import shutil
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
BASELINE = SKILL_DIR / 'references' / 'sector-overrides.csv'


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = Path(sys.argv[1]).expanduser().resolve()
    mode = 'replace' if '--mode' in sys.argv and 'replace' in sys.argv else 'merge'

    if not src.exists():
        sys.exit(f'找不到输入: {src}')

    # 备份当前基线
    if BASELINE.exists():
        bk = BASELINE.with_suffix(f'.csv.bak')
        shutil.copy(BASELINE, bk)
        print(f'已备份基线 → {bk}')

    if mode == 'replace':
        shutil.copy(src, BASELINE)
        print(f'replace: {src} → {BASELINE}')
        return

    # merge
    existing = {}
    if BASELINE.exists():
        with open(BASELINE, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                if r.get('code'):
                    existing[r['code']] = {'name': r.get('name',''), 'sector': r['sector']}

    new_count = 0
    upd_count = 0
    with open(src, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if not r.get('code'): continue
            c = r['code']
            if c not in existing:
                existing[c] = {'name': r.get('name',''), 'sector': r['sector']}
                new_count += 1
            elif existing[c]['sector'] != r['sector']:
                old = existing[c]['sector']
                existing[c]['sector'] = r['sector']
                existing[c]['name'] = r.get('name', existing[c]['name'])
                upd_count += 1
                print(f'  改归类: {c} {existing[c]["name"]}  {old} → {r["sector"]}')

    with open(BASELINE, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['code','name','sector'])
        for c in sorted(existing.keys()):
            w.writerow([c, existing[c]['name'], existing[c]['sector']])

    print(f'\nmerge 完成: 新增 {new_count} 条, 改归类 {upd_count} 条, 基线现有 {len(existing)} 条')
    print(f'基线: {BASELINE}')


if __name__ == '__main__':
    main()
