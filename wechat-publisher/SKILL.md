---
name: wechat-publisher
description: |
  微信公众号自动发帖工具。支持从 Markdown 写作到微信公众号发布的端到端流程：
  创建/润色文章 → 转换为微信排版 HTML 并预览 → 确认后自动发布到公众号。
  当用户说"发公众号"、"写公众号文章"、"发微信文章"、"公众号发帖"时触发。
user-invocable: true
argument-hint: "[主题/内容] 或留空进入交互模式"
---

# 微信公众号自动发帖

## 任务描述

帮助用户完成从内容创作到微信公众号发布的全流程：写文章 → 排版预览 → 发布。

## 前置条件

发布功能需要：
1. 环境变量 `WECHAT_APP_SECRET` 已设置
2. 微信公众平台 IP 白名单已配置当前机器公网 IP
3. 账号配置已存在: `memory/knowledge/wechat/account-config.json`

如果用户未完成配置，引导完成：
- 获取 AppSecret: 前往微信开发者平台 → 我的业务 → 公众号/服务号 → 详情页
- 配置 IP 白名单: 微信公众平台 → 设置与开发 → 基本配置
- 获取公网 IP: `curl ifconfig.me`
- 测试连通性: `cd wechat-publisher && python3 scripts/wechat_api.py test`

## 交互流程

### Phase 1: 创建 Markdown 文章

1. 判断内容来源：
   - 用户口述主题/要点 → 撰写完整文章
   - 用户提供现成文本/文件 → 整理润色
   - 如果不明确 → 询问"请告诉我文章主题，或提供已有的文稿"

2. 文章保存为 Markdown，包含 YAML frontmatter：
   ```markdown
   ---
   title: "文章标题"
   author: "作者名"
   digest: "摘要（显示在文章列表中）"
   ---

   正文内容...
   ```

3. 保存到 `wechat-publisher/articles/<标题缩写-日期>/article.md`
   - 目录名示例: `etf-analysis-20260325`

### Phase 2: 转换 + 预览确认

1. 执行转换脚本：
   ```bash
   cd wechat-publisher && python3 scripts/md_to_wechat_html.py articles/<dir>/article.md
   ```
   生成 `articles/<dir>/preview.html`（模拟 375px 手机宽度）

2. 打开浏览器预览：
   ```bash
   open wechat-publisher/articles/<dir>/preview.html
   ```

3. 询问用户确认：
   - "预览效果满意吗？可以修改内容或直接发布。"
   - 用户要求修改 → 编辑 article.md → 重新执行转换 → 再次预览
   - 用户确认 → 进入 Phase 3

### Phase 3: 发布到微信公众号

1. 询问发布方式：
   - 直接发布（freepublish）→ 文章公开可见
   - 仅存草稿（--draft-only）→ 保存到微信草稿箱，手动决定发布时机

2. 执行发布：
   ```bash
   cd wechat-publisher && python3 scripts/wechat_api.py publish articles/<dir>/
   # 或仅存草稿:
   cd wechat-publisher && python3 scripts/wechat_api.py publish articles/<dir>/ --draft-only
   ```

3. 报告结果：
   - 成功 → 告知 publish_id，提醒"发布为异步处理，可在微信后台查看状态"
   - 失败 → 展示错误信息，引导排查（token 过期？IP 白名单？）

### Phase 4: 追问处理

- "加一张封面图" → 引导用户将图片保存为 `articles/<dir>/cover.jpg`，重新发布
- "修改文章" → 编辑 article.md，重走 Phase 2-3
- "查看发布记录" → 读取 `data/publish_log.json`
- "测试 API 连通" → 执行 `python3 scripts/wechat_api.py test`

## 封面图

- 推荐尺寸: 900x383px（2.35:1 比例）
- 格式: JPG 或 PNG，不超过 1MB
- 放置在文章目录: `articles/<dir>/cover.jpg`
- 如果不提供封面图，文章将以无封面模式发布

## 注意事项

1. 通过 API 发布的文章不会触发微信系统推荐，可通过菜单或链接分享
2. 文章正文中的图片必须上传到微信 CDN，外部 URL 会被微信过滤
3. 发布是异步操作，提交成功不等于发布完成
4. AppSecret 仅通过环境变量传递，不存入文件

## 脚本声明

```yaml
scripts:
  - path: wechat-publisher/scripts/wechat_api.py
    description: 微信 API 操作（认证、上传、草稿、发布）
    args: [test, "publish <article_dir>", "--draft-only"]
  - path: wechat-publisher/scripts/md_to_wechat_html.py
    description: Markdown → 微信排版 HTML 转换
    args: ["<input.md>", "-o <output.html>"]
```

## 知识库引用

- `wechat-publisher/memory/knowledge/wechat/account-config.json`: 公众号配置
- `wechat-publisher/data/publish_log.json`: 发布记录
- `wechat-publisher/references/wechat_api.md`: API 文档速查
