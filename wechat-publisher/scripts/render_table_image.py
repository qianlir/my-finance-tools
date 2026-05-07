#!/usr/bin/env python3
"""将分析报告数据渲染为精美的表格图片，用于微信公众号发布。"""

import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# --- 配色方案 ---
COLORS = {
    "header_bg": (26, 115, 232),       # #1a73e8 蓝色表头
    "header_text": (255, 255, 255),     # 白色
    "top_bg": (220, 240, 225),          # 浅绿 强推荐行
    "good_bg": (255, 248, 225),         # 浅黄 推荐行
    "normal_bg": (255, 255, 255),       # 白色 普通行
    "alt_bg": (248, 249, 250),          # 微灰 交替行
    "text": (51, 51, 51),              # #333 正文
    "text_bold": (26, 26, 26),         # #1a1a1a 加粗
    "text_green": (30, 130, 76),       # 绿色 正值
    "text_red": (200, 50, 50),         # 红色 负值
    "border": (224, 224, 224),         # #e0e0e0 边框
    "check": (52, 168, 83),            # 绿色勾
}

# --- 字体 ---
def load_font(size, bold=False):
    """加载系统字体。"""
    paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for p in paths:
        try:
            # PingFang.ttc: index 0=Regular, 1=Medium, 2=Semibold, 3=Bold (approx)
            return ImageFont.truetype(p, size, index=3 if bold else 0)
        except (OSError, IndexError):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def parse_report_md(md_path):
    """从分析报告 MD 文件中解析表格数据。"""
    content = Path(md_path).read_text(encoding="utf-8")

    sections = {}
    current_section = None
    current_rows = []
    headers = []

    for line in content.split("\n"):
        if line.startswith("## ") and "ETF" in line:
            if current_section and current_rows:
                sections[current_section] = {"headers": headers, "rows": current_rows}
            current_section = line.strip("# ").strip()
            current_rows = []
            headers = []
        elif line.startswith("|") and current_section:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if not headers:
                headers = cells
            elif not all(c.startswith("-") for c in cells):
                current_rows.append(cells)

    if current_section and current_rows:
        sections[current_section] = {"headers": headers, "rows": current_rows}

    return sections


def filter_columns(headers, rows, keep_cols):
    """只保留指定列名的列。"""
    indices = []
    new_headers = []
    for i, h in enumerate(headers):
        for k in keep_cols:
            if k in h:
                indices.append(i)
                new_headers.append(keep_cols[k])
                break

    # 找出所有 "超额(均值)" 列的索引，用于提取括号内的均值
    mean_col_indices = {i for i, h in enumerate(headers) if "超额" in h and "综合" not in h}

    new_rows = []
    for row in rows:
        new_row = []
        for i in indices:
            if i < len(row):
                cell = row[i]
                # 对于 "超额(均值)" 列，只取均值部分
                if i in mean_col_indices and "(" in cell:
                    match = re.search(r'\(([^)]+)\)', cell)
                    cell = match.group(1) if match else cell
                new_row.append(cell)
            else:
                new_row.append("")
        new_rows.append(new_row)

    return new_headers, new_rows


def get_row_style(row, headers):
    """根据推荐列确定行样式。"""
    rec_idx = None
    for i, h in enumerate(headers):
        if "推荐" in h:
            rec_idx = i
            break

    if rec_idx is not None and rec_idx < len(row):
        rec = row[rec_idx]
        check_count = rec.count("✅")
        if check_count >= 3:
            return "top"
        elif check_count >= 2:
            return "good"
    return "normal"


def render_table(headers, rows, title, output_path, width=780, footnote=""):
    """渲染一张精美的表格图片。"""
    font_header = load_font(15, bold=True)
    font_cell = load_font(14)
    font_cell_bold = load_font(14, bold=True)
    font_title = load_font(18, bold=True)
    font_note = load_font(11)

    row_height = 38
    header_height = 42
    title_height = 44
    padding_x = 12
    corner_radius = 10
    footnote_height = 36 if footnote else 0

    n_cols = len(headers)
    n_rows = len(rows)
    img_height = title_height + header_height + row_height * n_rows + footnote_height + 16

    # 计算列宽 — 根据内容自适应
    col_widths = []
    for i in range(n_cols):
        max_w = font_header.getbbox(headers[i])[2] + padding_x * 2
        for row in rows:
            if i < len(row):
                text = row[i].replace("✅", "V")
                w = font_cell.getbbox(text)[2] + padding_x * 2
                max_w = max(max_w, w)
        col_widths.append(max_w)

    # 按比例缩放到目标宽度
    total = sum(col_widths)
    col_widths = [int(w * width / total) for w in col_widths]
    # 修正舍入误差
    col_widths[-1] += width - sum(col_widths)

    img = Image.new("RGB", (width, img_height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    y = 0

    # 标题
    draw.text((16, (title_height - 18) // 2), title, fill=COLORS["header_bg"], font=font_title)
    y += title_height

    # 表头背景（圆角矩形顶部）
    draw.rounded_rectangle(
        [0, y, width, y + header_height],
        radius=corner_radius,
        fill=COLORS["header_bg"],
    )
    # 补平底部圆角（让表头底部是直角）
    draw.rectangle([0, y + header_height - corner_radius, width, y + header_height], fill=COLORS["header_bg"])

    # 表头文字
    x = 0
    for i, h in enumerate(headers):
        bbox = font_header.getbbox(h)
        tw = bbox[2] - bbox[0]
        tx = x + (col_widths[i] - tw) // 2
        ty = y + (header_height - (bbox[3] - bbox[1])) // 2
        draw.text((tx, ty), h, fill=COLORS["header_text"], font=font_header)
        x += col_widths[i]
    y += header_height

    # 数据行
    for r_idx, row in enumerate(rows):
        style = get_row_style(row, headers)
        if style == "top":
            bg = COLORS["top_bg"]
        elif style == "good":
            bg = COLORS["good_bg"]
        elif r_idx % 2 == 1:
            bg = COLORS["alt_bg"]
        else:
            bg = COLORS["normal_bg"]

        # 最后一行加底部圆角
        if r_idx == n_rows - 1:
            draw.rounded_rectangle([0, y, width, y + row_height], radius=corner_radius, fill=bg)
            draw.rectangle([0, y, width, y + corner_radius], fill=bg)
        else:
            draw.rectangle([0, y, width, y + row_height], fill=bg)

        # 行底部边线
        if r_idx < n_rows - 1:
            draw.line([(12, y + row_height - 1), (width - 12, y + row_height - 1)], fill=COLORS["border"], width=1)

        # 单元格文字
        x = 0
        for i, cell in enumerate(row):
            if i >= n_cols:
                break
            font = font_cell_bold if style == "top" else font_cell

            # 颜色处理
            color = COLORS["text_bold"] if style == "top" else COLORS["text"]
            if "%" in cell:
                if cell.startswith("+"):
                    color = COLORS["text_red"]
                elif cell.startswith("-"):
                    color = COLORS["text_green"]

            # 推荐列：用绿色圆点表示评级
            if ("推荐" in headers[i] or "✅" in cell) and "✅" in cell:
                check_count = cell.count("✅")
                dot_r = 5
                dot_gap = 14
                total_w = check_count * dot_gap - (dot_gap - dot_r * 2)
                dot_x = x + (col_widths[i] - total_w) // 2
                dot_y = y + row_height // 2
                for d in range(check_count):
                    cx = dot_x + d * dot_gap + dot_r
                    draw.ellipse(
                        [cx - dot_r, dot_y - dot_r, cx + dot_r, dot_y + dot_r],
                        fill=COLORS["check"],
                    )
                x += col_widths[i]
                continue

            bbox = font.getbbox(cell)
            tw = bbox[2] - bbox[0]
            tx = x + (col_widths[i] - tw) // 2
            ty = y + (row_height - (bbox[3] - bbox[1])) // 2
            draw.text((tx, ty), cell, fill=color, font=font)
            x += col_widths[i]

        y += row_height

    # 脚注
    if footnote:
        y += 8
        draw.text((16, y), footnote, fill=(153, 153, 153), font=font_note)
        y += footnote_height

    # 裁剪到实际内容高度
    img = img.crop((0, 0, width, y + 8))
    img.save(output_path, "PNG", optimize=True)
    return output_path


def main():
    if len(sys.argv) < 3:
        print("用法: render_table_image.py <analysis.md> <output_dir>")
        sys.exit(1)

    md_path = sys.argv[1]
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    # 要保留的列及其显示名称（有序）
    keep_cols = {
        "代码": "代码",
        "价格": "价格",
        "涨幅": "涨幅",
        "估算溢价": "估算溢价",
        "3M超额": "3M平均",
        "6M超额": "6M平均",
        "1Y超额": "1Y平均",
        "综合超额": "综合超额",
        "1Y最高": "最高溢价",
        ">7%天": ">7%天",
        "推荐": "推荐",
    }

    sections = parse_report_md(md_path)

    footnote = "按综合超额排序（越负=越便宜=越推荐）"

    for name, data in sections.items():
        headers, rows = filter_columns(data["headers"], data["rows"], keep_cols)

        if "纳指" in name:
            out = output_dir / "table_nasdaq.png"
            title = "纳指ETF 分析"
        elif "标普" in name:
            out = output_dir / "table_sp500.png"
            title = "标普ETF 分析"
        else:
            continue

        render_table(headers, rows, title, str(out), footnote=footnote)
        print(f"已生成: {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
