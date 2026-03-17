---
name: wechat-uploadimg
description: 上传图片到微信 CDN 获取 URL。当用户需要上传图片到微信公众号、获取图片 CDN URL、准备草稿箱素材时触发。支持批量上传和封面单独上传，自动分类封面和正文图片。支持 SSH 中继模式解决 IP 白名单问题。
---

# 微信图片上传技能

上传本地图片到微信 CDN，获取可用于正文的图片 URL。

## 功能

- **批量上传模式**：扫描指定目录，上传所有图片文件
- **单独上传模式**：上传单个封面图片
- **SSH 中继模式**：通过固定 IP 服务器转发请求，解决本地 IP 变化导致的白名单问题
- 自动分类：以 `cover` 开头的文件识别为封面，其他为正文图片
- 输出映射文件：保存本地文件名到微信 URL 的映射关系

## 使用方法

### 批量上传所有图片

```bash
wechat-uploadimg --account main --images-dir /path/to/images --output image_mapping.json
```

### 单独上传封面图片

```bash
wechat-uploadimg --account main --cover-image /path/to/cover.jpg --output cover_url.json
```

### 通过 SSH 中继上传（解决 IP 白名单问题）

```bash
wechat-uploadimg --account main --images-dir /path/to/images --output image_mapping.json --relay
```

## 参数说明

| 参数 | 说明 | 必填 |
|------|------|-------|
| `--account` | 公众号账号：main=歪斯Wise, sub=人类 | 是 |
| `--images-dir` | 图片目录路径（批量上传） | 否 |
| `--cover-image` | 封面图片路径（单独上传） | 否 |
| `--output` | 输出文件路径（JSON格式） | 是 |
| `--relay` | 使用 SSH 中继（通过固定 IP 服务器转发） | 否 |
| `--no-relay` | 禁用 SSH 中继 | 否 |
| `--verbose` | 显示详细日志 | 否 |

## 输出格式

### 批量上传

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

### 单独上传封面

```json
{
  "cover_url": "http://mmbiz.qpic.cn/mmbiz_jpg/...",
  "cover_filename": "cover.jpg"
}
```

## 限制

- 图片大小：必须小于 **1MB**
- 支持格式：jpg, jpeg, png, gif, bmp
- 账号 IP 必须在公众号后台白名单中

## SSH 中继配置

当本地 IP 经常变化时，可通过固定 IP 的云服务器转发请求：

**配置文件路径**：`~/.claude/skills/wechat-relay/config.yaml`

```yaml
relay:
  enabled: true
  host: "115.191.35.152"
  user: "root"
  key_path: "/Users/xxx/.ssh/id_rsa"
  work_dir: "/tmp/wechat_relay"
```

**使用方式**：

1. **命令行指定**：`--relay` 参数
2. **配置文件默认启用**：设置 `enabled: true`

**工作原理**：

```
本地执行                         云服务器（固定IP）
    │                                  │
    ▼                                  ▼
┌─────────────┐    SCP 上传     ┌─────────────────┐
│ 收集图片    │ ──────────────▶ │ 执行 Python     │
│ 打包脚本    │                 │ 调用微信 API    │
│             │ ◀────────────── │ 返回 JSON 结果  │
└─────────────┘    SCP 下载     └─────────────────┘
```

## article-workflow 集成

在 article-workflow 中的使用流程：

1. `image-gen` 生成本地图片到 `wechat/13_images/`
2. `wechat-uploadimg` 批量上传所有图片，生成 `image_mapping.json`
3. `md-to-wxhtml` 读取映射，替换 Markdown 中的图片引用为微信 URL
4. `wechat-draftbox` 上传草稿（无需再处理图片）

## 环境变量

| 变量 | 说明 | 必填 |
|------|------|-------|
| `WECHAT_APPID_MAIN` | 主公众号 AppID（歪斯Wise） | 是 |
| `WECHAT_APPSECRET_MAIN` | 主公众号 AppSecret | 是 |
| `WECHAT_APPID_SUB` | 副业公众号 AppID（人类） | 否 |
| `WECHAT_APPSECRET_SUB` | 副业公众号 AppSecret | 否 |
