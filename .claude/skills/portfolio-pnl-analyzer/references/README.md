# Skill 级归类基线

## 文件

- **`sector-overrides.csv`** — 248+ 个标的的权威归类(用户累积的知识)
  格式: `code,name,sector`
  合法 sector 值: `A股 / H股 / 美股(QDII) / 海外其他 / 可转债 / 国债+短融货基 / 商品(黄金/REITs)`

## 优先级链(归类决策时)

1. **基线 `sector-overrides.csv`** ← 用户累积权威(本文件)
2. **脚本内 `EXPLICIT_SECTOR` 字典** ← 代码硬编码的边界标的
3. **关键词规则**(美股/海外/可转债/国债/商品 关键词匹配)
4. **代码模式**(5 位 0 开头=H 股,11/12 开头=转债,6/0/3 开头 6 位=A 股 ...)
5. **兜底** → `A股`

## 如何更新基线

当你在某个 work_dir 手工调整了归类(`data/sectors.csv`)并满意结果,用以下命令把它**升级回 skill 基线**,以后跑就自动带:

```bash
python3 /Users/cmwang/work/money/.claude/skills/portfolio-pnl-analyzer/scripts/sync_overrides.py \
  /path/to/work_dir/data/sectors.csv
```

或一行版:

```bash
cp <work_dir>/data/sectors.csv \
   /Users/cmwang/work/money/.claude/skills/portfolio-pnl-analyzer/references/sector-overrides.csv
```

后者会**全量覆盖**;脚本版会**合并**(新代码追加,已有代码用最新归类覆盖)。

## 添加新代码的归类

如果某次跑 skill 时有新标的没在基线里,03b 会:
1. 跑默认规则给出一个归类
2. 写入当前 work_dir 的 `data/sectors.csv`
3. **不**自动写回 skill 基线 — 等用户审完再决定要不要 sync

## 不同账户?

如果这个 skill 要给其他账户用(归类规则不同),建议:
- fork 一份 skill 改 references/sector-overrides.csv
- 或者把 sector-overrides.csv 改成多文件(`sector-overrides-{account}.csv`)+ 加环境变量切换

当前实现只支持单账户(默认基线)。
