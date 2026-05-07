#!/usr/bin/env python3
"""微信公众号 API 操作脚本 — 认证、上传素材、创建草稿、发布文章。"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR / ".."
REPO_ROOT = PROJECT_ROOT / ".."  # money/
CONFIG_PATH = PROJECT_ROOT / "memory" / "knowledge" / "wechat" / "account-config.json"

# 加载 .env 文件（money/.env）
_env_file = REPO_ROOT / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())
PUBLISH_LOG_PATH = PROJECT_ROOT / "data" / "publish_log.json"

# --- Token 缓存 ---
_token_cache = {"token": None, "expires_at": 0}


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_app_secret():
    secret = os.environ.get("WECHAT_APP_SECRET")
    if not secret:
        print("错误: 未设置环境变量 WECHAT_APP_SECRET", file=sys.stderr)
        print("请执行: export WECHAT_APP_SECRET='你的AppSecret'", file=sys.stderr)
        sys.exit(1)
    return secret


def get_access_token(app_id, app_secret):
    """获取 access_token，带内存缓存（有效期 7200s）。"""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]

    url = "https://api.weixin.qq.com/cgi-bin/token"
    params = {
        "grant_type": "client_credential",
        "appid": app_id,
        "secret": app_secret,
    }
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()

    if "access_token" not in data:
        print(f"获取 access_token 失败: {data}", file=sys.stderr)
        sys.exit(1)

    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 7200) - 60
    return _token_cache["token"]


def upload_thumb_image(token, image_path):
    """上传封面图（永久素材），返回 media_id。"""
    url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type=image"
    with open(image_path, "rb") as f:
        resp = requests.post(url, files={"media": f}, timeout=30)
    data = resp.json()
    if "media_id" not in data:
        print(f"上传封面图失败: {data}", file=sys.stderr)
        sys.exit(1)
    print(f"封面图上传成功: media_id={data['media_id']}")
    return data["media_id"]


def upload_content_image(token, image_path):
    """上传正文内图片，返回微信 CDN URL。"""
    url = f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={token}"
    with open(image_path, "rb") as f:
        resp = requests.post(url, files={"media": f}, timeout=30)
    data = resp.json()
    if "url" not in data:
        print(f"上传正文图片失败: {data}", file=sys.stderr)
        sys.exit(1)
    print(f"正文图片上传成功: {Path(image_path).name} → {data['url'][:60]}...")
    return data["url"]


def replace_local_images(token, html_content, article_dir):
    """将 HTML 中的本地图片路径替换为微信 CDN URL。"""
    img_pattern = re.compile(r'<img\s+[^>]*src="([^"]+)"', re.IGNORECASE)
    matches = img_pattern.findall(html_content)

    for src in matches:
        if src.startswith(("http://", "https://")):
            if "mmbiz.qpic.cn" in src:
                continue  # 已经是微信 CDN URL
            print(f"警告: 外部图片 URL 将被微信过滤: {src}")
            continue

        # 本地图片路径
        img_path = Path(article_dir) / src
        if not img_path.exists():
            img_path = Path(src)  # 尝试绝对路径
        if not img_path.exists():
            print(f"警告: 找不到图片文件: {src}")
            continue

        cdn_url = upload_content_image(token, str(img_path))
        html_content = html_content.replace(src, cdn_url)

    return html_content


def create_draft(token, article):
    """创建草稿，返回 media_id。"""
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}"
    payload = {"articles": [article]}
    resp = requests.post(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    data = resp.json()
    if "media_id" not in data:
        print(f"创建草稿失败: {data}", file=sys.stderr)
        sys.exit(1)
    print(f"草稿创建成功: media_id={data['media_id']}")
    return data["media_id"]


def publish_draft(token, media_id):
    """发布草稿，返回 publish_id。"""
    url = f"https://api.weixin.qq.com/cgi-bin/freepublish/submit?access_token={token}"
    payload = {"media_id": media_id}
    resp = requests.post(url, json=payload, timeout=30)
    data = resp.json()
    if data.get("errcode", 0) != 0:
        print(f"发布失败: {data}", file=sys.stderr)
        sys.exit(1)
    publish_id = data.get("publish_id", "unknown")
    print(f"发布任务已提交: publish_id={publish_id}")
    return publish_id


def log_publish(article_dir, media_id, publish_id, title):
    """记录发布日志。"""
    log = []
    if PUBLISH_LOG_PATH.exists():
        with open(PUBLISH_LOG_PATH, "r", encoding="utf-8") as f:
            log = json.load(f)

    log.append({
        "title": title,
        "article_dir": str(article_dir),
        "media_id": media_id,
        "publish_id": publish_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })

    with open(PUBLISH_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"发布记录已保存到 {PUBLISH_LOG_PATH}")


def read_article_meta(article_dir):
    """从 article.md 的 YAML frontmatter 读取元数据。"""
    md_path = Path(article_dir) / "article.md"
    if not md_path.exists():
        print(f"错误: 找不到 {md_path}", file=sys.stderr)
        sys.exit(1)

    content = md_path.read_text(encoding="utf-8")
    meta = {"title": "", "author": "", "digest": ""}

    # 简单解析 YAML frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key in meta:
                        meta[key] = val

    return meta


def cmd_test(args):
    """测试 API 连通性。"""
    config = load_config()
    secret = get_app_secret()
    token = get_access_token(config["app_id"], secret)
    print(f"连接成功! access_token={token[:20]}...")


def cmd_publish(args):
    """完整发布流程：上传图片 → 创建草稿 → 发布。"""
    article_dir = Path(args.article_dir)
    config = load_config()
    secret = get_app_secret()
    token = get_access_token(config["app_id"], secret)

    # 读取元数据
    meta = read_article_meta(article_dir)
    if not meta["title"]:
        print("错误: article.md 缺少 title", file=sys.stderr)
        sys.exit(1)

    # 读取转换后的 HTML
    preview_path = article_dir / "preview.html"
    if not preview_path.exists():
        print("错误: 找不到 preview.html，请先运行 md_to_wechat_html.py", file=sys.stderr)
        sys.exit(1)

    html_content = preview_path.read_text(encoding="utf-8")

    # 提取 <body> 内容作为文章正文
    body_match = re.search(
        r'<div class="wechat-content">(.*?)</div>\s*</body>',
        html_content,
        re.DOTALL,
    )
    if body_match:
        content_html = body_match.group(1).strip()
    else:
        # fallback: 取 body 内容
        body_match = re.search(r"<body[^>]*>(.*?)</body>", html_content, re.DOTALL)
        content_html = body_match.group(1).strip() if body_match else html_content

    # 替换本地图片为微信 CDN URL
    content_html = replace_local_images(token, content_html, article_dir)

    # 上传封面图
    thumb_media_id = None
    for ext in ("jpg", "jpeg", "png"):
        cover_path = article_dir / f"cover.{ext}"
        if cover_path.exists():
            thumb_media_id = upload_thumb_image(token, str(cover_path))
            break

    if not thumb_media_id:
        print("警告: 未找到封面图 (cover.jpg/png)，将使用无封面模式")

    # 构造文章数据
    article = {
        "article_type": "news",
        "title": meta["title"],
        "content": content_html,
        "need_open_comment": config.get("need_open_comment", 1),
        "only_fans_can_comment": config.get("only_fans_can_comment", 0),
    }
    if meta.get("author"):
        article["author"] = meta["author"]
    elif config.get("default_author"):
        article["author"] = config["default_author"]
    if meta.get("digest"):
        article["digest"] = meta["digest"]
    if thumb_media_id:
        article["thumb_media_id"] = thumb_media_id

    # 创建草稿
    media_id = create_draft(token, article)

    # 发布
    if args.draft_only:
        print("仅创建草稿，跳过发布。可在微信后台查看草稿。")
        log_publish(article_dir, media_id, "draft_only", meta["title"])
    else:
        publish_id = publish_draft(token, media_id)
        log_publish(article_dir, media_id, publish_id, meta["title"])
        print("\n发布任务已提交（异步处理），请在微信后台查看发布状态。")


def main():
    parser = argparse.ArgumentParser(description="微信公众号发布工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # test
    subparsers.add_parser("test", help="测试 API 连通性")

    # publish
    pub_parser = subparsers.add_parser("publish", help="发布文章")
    pub_parser.add_argument("article_dir", help="文章目录路径")
    pub_parser.add_argument("--draft-only", action="store_true", help="仅创建草稿，不发布")

    args = parser.parse_args()

    if args.command == "test":
        cmd_test(args)
    elif args.command == "publish":
        cmd_publish(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
