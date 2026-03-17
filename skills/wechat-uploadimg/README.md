# wechat-uploadimg

上传本地图片到微信 CDN，获取可用于正文的图片 URL。

## 功能

- **批量上传模式**：扫描指定目录，上传所有图片文件
- **单独上传模式**：上传单个封面图片
- 自动分类：以 `cover` 开头的文件识别为封面，其他为正文图片
- 输出映射文件：保存本地文件名到微信 URL 的映射关系

## 使用方法

### 批量上传所有图片

```bash
python3 wechat_uploadimg.py \
  --account main \
  --images-dir /path/to/images/ \
  --output image_mapping.json
```

输出示例：
```json
{
  "cover_urls": {
    "cover_16_9.jpg": "http://mmbiz.qpic.cn/mmbiz_jpg/..."
  },
  "poster_urls": {
    "poster_01_16_9.jpg": "http://mmbiz.qpic.cn/mmbiz_jpg/...",
    "poster_02_16_9.jpg": "http://mmbiz.qpic.cn/mmbiz_jpg/..."
  },
  "total": 3
}
```

### 单独上传封面图片

```bash
python3 wechat_uploadimg.py \
  --account main \
  --cover-image /path/to/cover.jpg \
  --output cover_url.json
```

输出示例：
```json
{
  "cover_url": "http://mmbiz.qpic.cn/mmbiz_jpg/...",
  "cover_filename": "cover.jpg"
}
```

## 环境变量

| 变量 | 说明 | 必填 |
|-------|------|-------|
| `WECHAT_APPID_MAIN` | 主公众号 AppID（歪斯Wise） | 是）|
| `WECHAT_APPSECRET_MAIN` | 主公众号 AppSecret | 是 |
| `WECHAT_APPID_SUB` | 副业公众号 AppID（人类） | 否 |
| `WECHAT_APPSECRET_SUB` | 副业公众号 AppSecret | 否 |

## 限制

- 图片大小：必须小于 **1MB**
- 支持格式：jpg, jpeg, png, gif, bmp
- 账号 IP 必须在公众号后台白名单中

## 微信 API 文档

- [上传图文消息内的图片获取URL](https://developers.weixin.qq.com/doc/subscription/api/material/permanent/api_uploadimage.html)

## article-workflow 集成

在 article-workflow 中的使用流程：

1. `image-gen` 生成本地图片到 `wechat/09_images/`
2. `wechat-uploadimg` 批量上传所有图片，生成 `image_mapping.json`
3. `orchestrator` 读取映射，替换 Markdown 中的图片引用为微信 URL
4. `md-to-wxhtml` 转换为 HTML（图片已是 CDN URL）
5. `wechat-draftbox` 上传草稿（无需再处理图片）
