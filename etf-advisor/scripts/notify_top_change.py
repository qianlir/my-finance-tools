#!/usr/bin/env python3
"""
ETF 首位切换飞书提醒

检测 NASDAQ/SP500/DAX/NIKKEI 四个指数的首位 ETF 变化：
- 首位切换（code 变了）→ 立即发送提醒
- 旧首位仍在列表但非首位，且新首位分值 - 旧首位分值 ≥ 1.0 → 发送切换持仓建议

用法:
  python3 notify_top_change.py              # 正常检测+通知
  python3 notify_top_change.py --init       # 初始化缓存（不发消息）
  python3 notify_top_change.py --test       # 发送测试消息

集成: 由 etf_server.py 在每次 recommend_by_change.py --server 之后调用
"""

import hashlib
import hmac
import base64
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
REPORT_PATH = PROJECT_DIR / "data" / "report.json"
CACHE_PATH = PROJECT_DIR / "data" / "top1_cache.json"

# 飞书 webhook（仅飞书，不发 Lark）
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/6f917305-9516-48be-a3ef-f4fc9d92870c"
FEISHU_SECRET = "19gZpflvGPL0TeCsUSDvJ"

WATCHED_INDEX_TYPES = ["NASDAQ", "SP500", "DAX", "NIKKEI"]


def _lark_sign(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    h = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(h).decode("utf-8")


def send_feishu(text: str) -> bool:
    """发送飞书文本消息，成功返回 True。"""
    timestamp = str(int(time.time()))
    payload = {
        "timestamp": timestamp,
        "sign": _lark_sign(timestamp, FEISHU_SECRET),
        "msg_type": "text",
        "content": {"text": text},
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        FEISHU_WEBHOOK, data=data, method="POST",
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("code") == 0 or result.get("StatusCode") == 0
    except Exception as e:
        print(f"[notify] 飞书发送失败: {e}", file=sys.stderr)
        return False


def load_cache() -> dict:
    """加载上次首位缓存。返回 {index_type: {code, name, score}}。"""
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_cache(cache: dict):
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def get_current_tops(report: dict) -> dict:
    """从 report.json 提取各指数首位 ETF。返回 {index_type: {code, name, score, premium, change}}。"""
    tops = {}
    for section in report.get("sections", []):
        idx_type = section.get("index_type", "")
        if idx_type not in WATCHED_INDEX_TYPES:
            continue
        etfs = section.get("etfs", [])
        if not etfs:
            continue
        top = etfs[0]
        tops[idx_type] = {
            "code": top["code"],
            "name": top["name"],
            "score": top["score"],
            "premium": top.get("display_premium", 0),
            "change": top.get("change", 0),
            "price": top.get("price", 0),
        }
    return tops


def get_etf_by_code(report: dict, index_type: str, code: str) -> dict | None:
    """在指定 section 中按 code 查找 ETF。"""
    for section in report.get("sections", []):
        if section.get("index_type") != index_type:
            continue
        for e in section.get("etfs", []):
            if e["code"] == code:
                return {
                    "code": e["code"], "name": e["name"], "score": e["score"],
                    "premium": e.get("display_premium", 0), "change": e.get("change", 0),
                    "price": e.get("price", 0),
                }
    return None


def check_and_notify():
    """主检测逻辑。"""
    if not REPORT_PATH.exists():
        print("[notify] report.json 不存在，跳过")
        return

    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    current = get_current_tops(report)
    prev = load_cache()

    if not prev:
        # 首次运行，仅初始化缓存
        save_cache(current)
        print(f"[notify] 缓存已初始化: {list(current.keys())}")
        return

    alerts = []  # 收集所有变化

    for idx_type in WATCHED_INDEX_TYPES:
        cur_top = current.get(idx_type)
        prev_top = prev.get(idx_type)
        if not cur_top or not prev_top:
            continue

        if cur_top["code"] != prev_top["code"]:
            # 首位切换
            old_score_info = ""
            # 查旧首位在当前列表的分数
            old_in_list = get_etf_by_code(report, idx_type, prev_top["code"])
            if old_in_list:
                diff = cur_top["score"] - old_in_list["score"]
                old_score_info = f"（旧首位 {prev_top['code']} 当前分值 {old_in_list['score']:.2f}，差 {diff:+.2f}）"

            alerts.append({
                "type": "A",
                "index_type": idx_type,
                "title": "首位切换",
                "old_code": prev_top["code"],
                "old_name": prev_top["name"],
                "old_score": prev_top.get("score", 0),
                "old_premium": prev_top.get("premium", 0),
                "old_change": prev_top.get("change", 0),
                "new_code": cur_top["code"],
                "new_name": cur_top["name"],
                "new_score": cur_top["score"],
                "new_premium": cur_top["premium"],
                "new_change": cur_top["change"],
                "new_price": cur_top.get("price", 0),
                "extra": old_score_info,
            })

        elif cur_top["code"] == prev_top["code"] and cur_top["score"] != prev_top.get("score"):
            # 首位没变但分值变了，检查是否有分差≥1的切换持仓建议
            pass

        # 类型 B: 旧首位还在列表里但不是首位，分差≥1
        if cur_top["code"] == prev_top["code"]:
            # 首位没变，不需要检查类型 B
            continue

        # 此时首位已切换（已触发类型 A）
        # 额外检查：旧首位还在列表里且新首位比它高 ≥1.0
        if prev_top["code"] != cur_top["code"]:
            old_in_list = get_etf_by_code(report, idx_type, prev_top["code"])
            if old_in_list and (cur_top["score"] - old_in_list["score"]) >= 1.0:
                # 已在类型 A 消息中包含分差信息，如果分差≥1则标注建议切换
                for a in alerts:
                    if a["type"] == "A" and a["index_type"] == idx_type:
                        a["type"] = "B"  # 升级为切换持仓建议

    if not alerts:
        # 无变化，静默更新缓存中的分值
        save_cache(current)
        return

    # 构建消息
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = ["【ETF首位变化提醒】", ""]

    def fmt_pct(v):
        return f"{v:+.2f}%" if v else f"{v:.2f}%"

    for a in alerts:
        if a["type"] == "B":
            lines.append(f"🔔 {a['index_type']} 建议切换持仓")
        else:
            lines.append(f"📢 {a['index_type']} 首位切换")

        lines.append(f"   {a['old_code']} {a['old_name']}（分值 {a['old_score']:.2f} 溢价 {fmt_pct(a['old_premium'])} 涨幅 {fmt_pct(a['old_change'])}）")
        chg_arrow = "↑" if a["new_change"] >= 0 else "↓"
        lines.append(f"   → {a['new_code']} {a['new_name']}")
        lines.append(f"     价格 {a['new_price']:.3f} | 涨幅 {fmt_pct(a['new_change'])} | 溢价 {fmt_pct(a['new_premium'])} | 分值 {a['new_score']:.2f}")
        if a["extra"]:
            lines.append(f"     {a['extra']}")
        lines.append("")

    # 附加当前各指数首位概览
    lines.append("📊 当前各指数首位:")
    for idx_type in WATCHED_INDEX_TYPES:
        t = current.get(idx_type)
        if t:
            chg_icon = "🔴" if t["change"] < 0 else "🟢"
            lines.append(f"   {idx_type}: {t['code']} {t['name']}")
            lines.append(f"     {t['price']:.3f} {chg_icon}{fmt_pct(t['change'])} | 溢价{fmt_pct(t['premium'])} | 分值{t['score']:.2f}")

    lines.append("")
    lines.append(f"⏰ {now}")

    msg = "\n".join(lines)
    ok = send_feishu(msg)
    if ok:
        print(f"[notify] 已发送 {len(alerts)} 条提醒")
    else:
        print(f"[notify] 发送失败，缓存不更新（下次重试）")
        return

    save_cache(current)


if __name__ == "__main__":
    if "--test" in sys.argv:
        print("[notify] 发送测试消息...")
        ok = send_feishu("【ETF测试】飞书通知连通测试 ✓")
        print("成功" if ok else "失败")
    elif "--init" in sys.argv:
        if not REPORT_PATH.exists():
            print("[notify] report.json 不存在")
            sys.exit(1)
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        tops = get_current_tops(report)
        save_cache(tops)
        print(f"[notify] 缓存已初始化: {json.dumps(tops, ensure_ascii=False, indent=2)}")
    else:
        check_and_notify()
