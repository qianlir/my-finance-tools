# ETF 数据库 is_fixed 字段修复任务

## 背景

项目：纳指/标普ETF智能换仓顾问
数据库：`/Users/cmwang/work/money/nasdaq-etf-advisor/data/etf_premium.db`

## 问题描述

原有数据库 `etf_data` 表缺少两个字段来区分数据来源和净值实际日期：
1. `nav_date` - 净值实际日期（美股收盘日），区别于爬取日期
2. `is_fixed` - 标记数据是否为历史确认数据

## 时区问题

**关键理解**：
- A股交易时间：北京时间 9:30-15:00
- 美股交易时间：北京时间 21:30-次日4:00（冬令时）或 22:30-次日5:00（夏令时）

因此：A股T日收盘时，美股T日还没收盘，所以A股T日无法获取美股T日的净值。

## 数据来源

### 历史API（update_history_fixed）
- **价格**：腾讯/新浪历史API
- **净值**：东方财富历史API `http://fund.eastmoney.com/pingzhongdata/{code}.js`
- **特点**：返回的日期是净值实际日期（美股收盘日）
- **is_fixed = 1**

### 实时API（update_realtime）
- **价格**：腾讯/新浪实时API
- **净值**：东方财富当前页面API `http://fund.eastmoney.com/{code}.html`
- **特点**：净值来自历史API的最新值
- **is_fixed = 0**

## 数据库Schema

```sql
CREATE TABLE etf_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,              -- A股交易日/爬取日期
    timestamp TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    company TEXT NOT NULL,
    price REAL,
    nav REAL,
    premium_rate REAL,
    nav_type TEXT,
    nav_date TEXT,                   -- 净值实际日期(美股收盘日) [新增]
    is_fixed INTEGER DEFAULT 0,      -- 1=历史确认数据, 0=实时数据 [新增]
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, code)
);
```

## 已完成的修改

### 1. 数据库Schema更新（update_data.py）

添加了 `nav_date` 和 `is_fixed` 字段：
```python
# init_database() 中添加
ALTER TABLE etf_data ADD COLUMN nav_date TEXT
ALTER TABLE etf_data ADD COLUMN is_fixed INTEGER DEFAULT 0
```

### 2. save_etf_records 函数

修改为支持新字段：
```python
cursor.execute("""
    INSERT OR REPLACE INTO etf_data
    (date, timestamp, code, name, company, price, nav, premium_rate, nav_type, nav_date, is_fixed)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (..., r.get('nav_date'), r.get('is_fixed', 0)))
```

### 3. 新增 get_current_nav_with_date 函数

获取当前净值及其日期：
```python
def get_current_nav_with_date(code):
    """返回: {'nav': float, 'nav_date': str} 或 None"""
    # 从历史API获取最新净值及日期
    nav_map = get_historical_navs(code)
    if nav_map:
        sorted_dates = sorted(nav_map.keys(), reverse=True)
        latest_nav_date = sorted_dates[0]
        latest_nav = nav_map[latest_nav_date]
        return {'nav': latest_nav, 'nav_date': latest_nav_date}
    # 回退到数据库...
```

### 4. update_history_fixed 函数

简化逻辑：所有历史API获取的数据标记为 `is_fixed=1`
```python
all_records.append({
    'date': trade_date,
    'nav_date': nav_date,
    'is_fixed': 1,  # 历史API获取 = fixed
    'price': price,  # 历史价格（腾讯/新浪）
    'nav': nav_value,  # 历史净值（东方财富）
    'premium_rate': premium,
    ...
})
```

### 5. update_realtime 函数

简化逻辑：所有实时API获取的数据标记为 `is_fixed=0`
```python
records.append({
    'date': today,
    'nav_date': nav_date,
    'is_fixed': 0,  # 实时API获取 = not fixed
    'price': realtime['price'],
    'nav': nav,
    ...
})
```

### 6. recommend_by_change.py 的修改

#### get_nav_info 函数

更新为使用 `nav_date` 字段，并跳过重复净值值：
```python
def get_nav_info(code: str) -> Dict:
    # 优先获取有nav_date的记录（历史确认数据）
    cursor.execute("""
        SELECT date, nav, nav_date, is_fixed FROM etf_data
        WHERE code = ? AND nav IS NOT NULL
        ORDER BY date DESC LIMIT 20
    """, (code,))

    # 筛选有nav_date的记录
    valid_rows = [r for r in all_rows if r['nav_date']]

    # 找到第一个不同的净值值作为前一日净值
    for row in valid_rows[1:]:
        if row['nav'] and row['nav'] != latest_nav:
            prev_nav = row['nav']
            break
```

#### 报告生成中的净值日期显示

修正了净值日期显示逻辑（不再减1天）：
```python
# nav_date 已经是美股收盘日，不需要再减1天
if results and results[0].get('nav_date'):
    nav_date_str = results[0]['nav_date'][-5:]
    nav_dt = datetime.strptime(nav_date_str, '%m-%d')
    lines.append(f"> 净值日期: {nav_dt.strftime('%-m/%-d')}（美股收盘）")
```

## 当前数据状态

```
 date       | nav_date   | is_fixed | 说明
------------|------------|----------|--------
 2026-03-26 | 2026-03-24 | 0        | 实时API获取
 2026-03-25 | 2026-03-24 | 1        | 历史API获取
 2026-03-24 | 2026-03-24 | 1        | 历史API获取
 2026-03-23 | 2026-03-23 | 1        | 历史API获取
```

## 命令行参数

```bash
# 获取历史确认数据并标记为 fixed
python3 scripts/update_data.py --fixed --days 120

# 获取实时数据（not fixed）
python3 scripts/update_data.py --realtime

# 完整更新（历史+实时）
python3 scripts/update_data.py
```

## 关键文件

| 文件 | 修改内容 |
|------|----------|
| `scripts/update_data.py` | 数据库schema、get_current_nav_with_date、update_history_fixed、update_realtime |
| `scripts/recommend_by_change.py` | get_nav_info、报告生成中的净值日期显示 |

## 待验证事项

1. **溢价计算**：确认使用 `is_fixed=1` 的数据计算溢价是否准确
2. **报告显示**：确认净值日期和涨跌幅显示正确
3. **边缘情况**：周末、节假日前后数据的处理

## 测试命令

```bash
# 1. 获取历史数据
python3 scripts/update_data.py --fixed --days 120

# 2. 查看数据状态
sqlite3 data/etf_premium.db "
SELECT date, nav_date, nav, is_fixed
FROM etf_data
WHERE code='159660'
ORDER BY date DESC LIMIT 10"

# 3. 生成报告
python3 scripts/recommend_by_change.py --holding 159660

# 4. 查看报告中的净值日期
grep "净值日期" reports/analysis_$(date +%Y%m%d).md
```

## 注意事项

1. **nav_date vs date**：
   - `date` = A股交易日/爬取日期
   - `nav_date` = 净值实际日期（美股收盘日）
   - 通常 `nav_date` 会早于或等于 `date`

2. **is_fixed 的定义**：
   - `is_fixed=1` = 通过历史API获取的确认数据
   - `is_fixed=0` = 通过实时API获取的数据

3. **T+1 机制**：
   - A股T日收盘时，美股T日还没收盘
   - 所以A股T日只能获取到T-1或更早的美股净值
