# 微信公众号 API 速查

## 认证

### 获取 access_token
```
GET https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=APPID&secret=APPSECRET
```
- 有效期 7200s，需缓存
- 响应: `{"access_token": "...", "expires_in": 7200}`

## 素材上传

### 上传封面图（永久素材）
```
POST https://api.weixin.qq.com/cgi-bin/material/add_material?access_token=TOKEN&type=image
```
- Multipart form: `media` 字段
- 限制: JPG/PNG, < 1MB, 推荐 900x383px (2.35:1)
- 响应: `{"media_id": "...", "url": "..."}`

### 上传正文图片
```
POST https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token=TOKEN
```
- Multipart form: `media` 字段
- 限制: JPG/PNG/GIF, < 2MB
- 响应: `{"url": "http://mmbiz.qpic.cn/..."}`
- 返回的 URL 可直接用于文章 HTML 的 img src

## 草稿管理

### 新建草稿
```
POST https://api.weixin.qq.com/cgi-bin/draft/add?access_token=TOKEN
```
请求体:
```json
{
  "articles": [{
    "article_type": "news",
    "title": "标题（最多32字）",
    "author": "作者（最多16字）",
    "digest": "摘要（最多128字）",
    "content": "<p>HTML正文</p>",
    "content_source_url": "原文链接",
    "thumb_media_id": "封面图media_id",
    "need_open_comment": 1,
    "only_fans_can_comment": 0,
    "show_cover_pic": 1
  }]
}
```
- 响应: `{"media_id": "DRAFT_MEDIA_ID"}`
- content 中的图片必须用微信 CDN URL
- 注意: `json.dumps(payload, ensure_ascii=False).encode('utf-8')`

## 发布

### 发布草稿
```
POST https://api.weixin.qq.com/cgi-bin/freepublish/submit?access_token=TOKEN
```
请求体: `{"media_id": "DRAFT_MEDIA_ID"}`
响应: `{"errcode": 0, "errmsg": "ok", "publish_id": "..."}`

异步操作 — errcode=0 仅表示任务提交成功。

## 常见错误码

| 错误码 | 含义 | 解决方案 |
|--------|------|----------|
| 40001 | access_token 无效 | 重新获取 token |
| 40164 | IP 不在白名单 | 添加 IP 到微信后台白名单 |
| 48001 | 接口未授权 | 检查公众号权限 |
| 53503 | 草稿审核未通过 | 检查内容合规性 |
| 53504 | 需手动发布 | 登录微信后台手动操作 |
