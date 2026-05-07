#!/usr/bin/env python3
"""Markdown → 微信公众号兼容 HTML 转换器。

将 Markdown 文件转换为微信公众号可直接使用的 HTML（所有 CSS 内联），
并生成模拟微信手机端 375px 宽度的预览文件。
"""

import argparse
import re
import sys
from pathlib import Path

try:
    import markdown
except ImportError:
    print("请安装 markdown 库: pip install markdown", file=sys.stderr)
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR / ".."

# --- 简洁商务风内联样式 ---

STYLES = {
    "body": "margin: 0 auto; padding: 16px; max-width: 375px; font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', 'PingFang SC', 'Microsoft YaHei', sans-serif; background: #fff;",
    "h1": "font-size: 20px; color: #1a1a1a; font-weight: bold; line-height: 1.4; margin: 1.2em 0 0.6em 0; padding-bottom: 0.3em; border-bottom: 2px solid #2b7a78;",
    "h2": "font-size: 18px; color: #1a1a1a; font-weight: bold; line-height: 1.4; margin: 1.2em 0 0.6em 0; padding-bottom: 0.3em; border-bottom: 1px solid #e0e0e0;",
    "h3": "font-size: 16px; color: #1a1a1a; font-weight: bold; line-height: 1.4; margin: 1em 0 0.4em 0;",
    "h4": "font-size: 15px; color: #333; font-weight: bold; line-height: 1.4; margin: 0.8em 0 0.3em 0;",
    "p": "font-size: 15px; color: #333; line-height: 1.75em; margin: 0 0 1em 0;",
    "a": "color: #2b7a78; text-decoration: none; border-bottom: 1px solid #2b7a78;",
    "strong": "color: #1a1a1a; font-weight: bold;",
    "em": "font-style: italic; color: #555;",
    "ul": "margin: 0 0 1em 0; padding-left: 1.5em; font-size: 15px; color: #333; line-height: 1.75em;",
    "ol": "margin: 0 0 1em 0; padding-left: 1.5em; font-size: 15px; color: #333; line-height: 1.75em;",
    "li": "margin-bottom: 0.4em;",
    "blockquote": "margin: 0 0 1em 0; padding: 10px 15px; border-left: 3px solid #2b7a78; background: #f9fafb; color: #666; font-size: 14px; line-height: 1.75em;",
    "code_inline": "background: #f1f3f5; color: #c7254e; padding: 2px 6px; border-radius: 3px; font-size: 13px; font-family: Consolas, Monaco, 'Courier New', monospace;",
    "pre": "background: #f6f8fa; padding: 12px 16px; border-radius: 6px; overflow-x: auto; margin: 0 0 1em 0; border: 1px solid #e8ecef;",
    "code_block": "font-family: Consolas, Monaco, 'Courier New', monospace; font-size: 13px; color: #333; line-height: 1.6; white-space: pre-wrap; word-wrap: break-word;",
    "table": "width: 100%; border-collapse: collapse; margin: 0 0 1em 0; font-size: 14px;",
    "th": "background: #f6f8fa; padding: 8px 12px; border: 1px solid #dde1e5; text-align: left; font-weight: bold; color: #1a1a1a;",
    "td": "padding: 8px 12px; border: 1px solid #dde1e5; color: #333;",
    "img": "max-width: 100%; height: auto; margin: 0.8em 0; border-radius: 4px;",
    "hr": "border: none; border-top: 1px solid #e0e0e0; margin: 1.5em 0;",
}

# 微信预览 HTML 模板
PREVIEW_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - 微信预览</title>
<style>
  body {{
    margin: 0;
    padding: 0;
    background: #f0f0f0;
    display: flex;
    justify-content: center;
  }}
  .phone-frame {{
    width: 375px;
    min-height: 100vh;
    background: #fff;
    box-shadow: 0 0 20px rgba(0,0,0,0.1);
    margin: 20px 0;
  }}
  .wechat-header {{
    background: #ededed;
    padding: 10px 16px;
    font-size: 13px;
    color: #999;
    text-align: center;
    border-bottom: 1px solid #ddd;
  }}
  .wechat-title {{
    padding: 20px 16px 10px;
    font-size: 22px;
    font-weight: bold;
    color: #111;
    line-height: 1.4;
  }}
  .wechat-meta {{
    padding: 0 16px 15px;
    font-size: 12px;
    color: #999;
  }}
  .wechat-content {{
    padding: 0 16px 20px;
  }}
</style>
</head>
<body>
<div class="phone-frame">
  <div class="wechat-header">微信公众号预览</div>
  <div class="wechat-title">{title}</div>
  <div class="wechat-meta">{author}</div>
  <div class="wechat-content">
{content}
  </div>
</div>
</body>
</html>"""


def inject_inline_styles(html):
    """对 HTML 标签注入内联 CSS 样式。"""

    # 处理标题 h1-h4
    for tag in ("h1", "h2", "h3", "h4"):
        html = re.sub(
            rf"<{tag}(?:\s[^>]*)?>",
            f'<{tag} style="{STYLES[tag]}">',
            html,
        )

    # 段落
    html = re.sub(r"<p(?:\s[^>]*)?>", f'<p style="{STYLES["p"]}">', html)

    # 链接
    html = re.sub(r"<a\s", f'<a style="{STYLES["a"]}" ', html)

    # 加粗
    html = re.sub(r"<strong>", f'<strong style="{STYLES["strong"]}">', html)

    # 斜体
    html = re.sub(r"<em>", f'<em style="{STYLES["em"]}">', html)

    # 列表
    html = re.sub(r"<ul>", f'<ul style="{STYLES["ul"]}">', html)
    html = re.sub(r"<ol>", f'<ol style="{STYLES["ol"]}">', html)
    html = re.sub(r"<li>", f'<li style="{STYLES["li"]}">', html)

    # 引用块
    html = re.sub(r"<blockquote>", f'<blockquote style="{STYLES["blockquote"]}">', html)

    # 代码块 (pre > code)
    # 先标记 pre 内的 code 为 code_block 样式
    html = re.sub(r"<pre>", f'<pre style="{STYLES["pre"]}">', html)
    html = re.sub(
        r'(<pre[^>]*>)\s*<code(?:\s[^>]*)?>',
        rf'\1<code style="{STYLES["code_block"]}">',
        html,
    )
    # 再处理剩余未被样式化的 <code>（即内联 code）
    html = re.sub(
        r'<code>',
        f'<code style="{STYLES["code_inline"]}">',
        html,
    )

    # 表格
    html = re.sub(r"<table>", f'<table style="{STYLES["table"]}">', html)
    html = re.sub(r"<th(?:\s[^>]*)?>", f'<th style="{STYLES["th"]}">', html)
    html = re.sub(r"<td(?:\s[^>]*)?>", f'<td style="{STYLES["td"]}">', html)

    # 图片
    html = re.sub(r"<img\s", f'<img style="{STYLES["img"]}" ', html)

    # 分割线
    html = re.sub(r"<hr\s*/?>", f'<hr style="{STYLES["hr"]}"/>', html)

    return html


def parse_frontmatter(content):
    """解析 Markdown 的 YAML frontmatter，返回 (meta_dict, body)。"""
    meta = {}
    body = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip()] = val.strip().strip('"').strip("'")
            body = parts[2].strip()

    return meta, body


def convert_md_to_wechat_html(md_path, output_path=None):
    """将 Markdown 文件转换为微信公众号兼容的 HTML。"""
    md_path = Path(md_path)
    if not md_path.exists():
        print(f"错误: 找不到文件 {md_path}", file=sys.stderr)
        sys.exit(1)

    content = md_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(content)

    title = meta.get("title", md_path.stem)
    author = meta.get("author", "")

    # Markdown → HTML
    extensions = ["tables", "fenced_code", "nl2br"]
    html_body = markdown.markdown(body, extensions=extensions)

    # 注入内联样式
    styled_html = inject_inline_styles(html_body)

    # 生成预览 HTML
    preview_html = PREVIEW_TEMPLATE.format(
        title=title,
        author=author,
        content=styled_html,
    )

    # 输出
    if output_path is None:
        output_path = md_path.parent / "preview.html"
    else:
        output_path = Path(output_path)

    output_path.write_text(preview_html, encoding="utf-8")
    print(f"预览文件已生成: {output_path}")
    print(f"标题: {title}")
    if author:
        print(f"作者: {author}")
    print(f"\n用浏览器打开预览: open {output_path}")

    return str(output_path)


def main():
    parser = argparse.ArgumentParser(description="Markdown → 微信公众号 HTML 转换器")
    parser.add_argument("input", help="输入 Markdown 文件路径")
    parser.add_argument("-o", "--output", help="输出 HTML 文件路径（默认同目录 preview.html）")

    args = parser.parse_args()
    convert_md_to_wechat_html(args.input, args.output)


if __name__ == "__main__":
    main()
