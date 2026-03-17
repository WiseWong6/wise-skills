# 微信订阅号草稿箱 API 要点

## 环境变量（必须）
- `WECHAT_APPID`
- `WECHAT_APPSECRET`

## 1) 获取 access_token
- 接口：`GET https://api.weixin.qq.com/cgi-bin/token`
- 参数：`grant_type=client_credential&appid=APPID&secret=APPSECRET`
- 返回：`{"access_token":"...","expires_in":7200}`

## 2) 上传永久素材（封面）
- 接口：`POST https://api.weixin.qq.com/cgi-bin/material/add_material?access_token=ACCESS_TOKEN&type=thumb`
- 表单字段：`media=@/path/to/cover.png`
- 返回：`{"media_id":"...","url":"..."}`（`media_id` 用作 `thumb_media_id`）

## 3) 上传图文内图片（返回 URL）
- 接口：`POST https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token=ACCESS_TOKEN`
- 表单字段：`media=@/path/to/image.png`
- 返回：`{"url":"https://mmbiz.qpic.cn/..."}`（示例）

## 4) 草稿箱入库
- 接口：`POST https://api.weixin.qq.com/cgi-bin/draft/add?access_token=ACCESS_TOKEN`
- Body 示例：
```json
{
  "articles": [
    {
      "title": "标题",
      "author": "",
      "digest": "",
      "content": "<p>HTML内容</p>",
      "content_source_url": "",
      "thumb_media_id": "MEDIA_ID",
      "need_open_comment": 0,
      "only_fans_can_comment": 0
    }
  ]
}
```

## 常见错误
- `40164 invalid ip`：出网 IP 不在公众号后台白名单
- `40007 invalid media_id`：`thumb_media_id` 不是永久素材
