# 微信订阅号草稿箱管理工具

微信订阅号草稿箱管理工具，支持创建草稿、更新草稿、自动上传图片等功能。

## 功能特性

- ✅ **创建草稿**：支持图文消息（news）和图片消息（newspic）
- ✅ **更新草稿**：通过 `--media-id` 参数更新已存在的草稿
- ✅ **Markdown 支持**：自动将 Markdown 转换为 HTML
- ✅ **自动图片上传**：自动检测并上传正文中的本地图片
- ✅ **多账号支持**：支持主公众号（歪斯Wise）和副业公众号（人类）
- ✅ **封面处理**：支持上传封面图片并生成永久素材
- ✅ **图片消息**：支持创建图片消息（最多20张图片）

## 安装依赖

```bash
pip install markdown  # 如果需要 Markdown 转换功能
```

## 环境变量配置

在使用前，需要配置微信公众号的 AppID 和 AppSecret：

```bash
# 主公众号（歪斯Wise）
export WECHAT_APPID_MAIN=your_main_appid
export WECHAT_APPSECRET_MAIN=your_main_secret

# 副业公众号（人类）
export WECHAT_APPID_SUB=your_sub_appid
export WECHAT_APPSECRET_SUB=your_sub_secret
```

## 使用示例

### 1. 从 Markdown 创建草稿（推荐）

```bash
python wechat_draftbox.py \
  --account sub \
  --title "文章标题" \
  --markdown article.md \
  --cover-image cover.png
```

工具会自动：
- 将 Markdown 转换为 HTML
- 上传封面图片为永久素材
- 检测并上传正文中的所有本地图片
- 替换图片 URL 为微信临时 URL

### 2. 从 HTML 创建草稿

```bash
python wechat_draftbox.py \
  --account sub \
  --title "文章标题" \
  --content-html article.html \
  --cover-image cover.png
```

### 3. 更新已存在的草稿

```bash
python wechat_draftbox.py \
  --account sub \
  --media-id MEDIA_ID \
  --title "更新后的标题" \
  --markdown article.md \
  --cover-image new_cover.png
```

### 4. 创建图片消息

```bash
python wechat_draftbox.py \
  --account sub \
  --article-type newspic \
  --title "图片消息标题" \
  --images img1.jpg img2.jpg img3.jpg
```

### 5. 使用已有封面素材

```bash
python wechat_draftbox.py \
  --account sub \
  --title "文章标题" \
  --markdown article.md \
  --thumb-media-id THUMB_MEDIA_ID
```

### 6. 开启评论并设置仅粉丝可评论

```bash
python wechat_draftbox.py \
  --account sub \
  --title "文章标题" \
  --markdown article.md \
  --cover-image cover.png \
  --need-open-comment \
  --only-fans-can-comment
```

### 7. 查看详细日志

```bash
python wechat_draftbox.py \
  --account sub \
  --title "文章标题" \
  --markdown article.md \
  --cover-image cover.png \
  --verbose
```

### 8. 保存结果到文件

```bash
python wechat_draftbox.py \
  --account sub \
  --title "文章标题" \
  --markdown article.md \
  --cover-image cover.png \
  --out result.json
```

## 参数说明

### 基础参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `--account` | 是 | 公众号账号：`main`（歪斯Wise）或 `sub`（人类） |
| `--title` | 是 | 文章标题 |
| `--author` | 否 | 作者（默认：公众号名称） |
| `--digest` | 否 | 摘要（news类型有效） |
| `--content-source-url` | 否 | 原文链接（news类型有效） |

### 内容源（二选一）

| 参数 | 说明 |
|------|------|
| `--content-html` | HTML 文件路径 |
| `--markdown` | Markdown 文件路径（自动转换为HTML） |

### 操作模式

| 参数 | 说明 |
|------|------|
| `--media-id` | 草稿ID（用于更新现有草稿） |

### 文章类型

| 参数 | 说明 |
|------|------|
| `--article-type` | 文章类型：`news`（图文消息，默认）或 `newspic`（图片消息） |

### 评论设置

| 参数 | 说明 |
|------|------|
| `--need-open-comment` | 开启评论（默认） |
| `--no-open-comment` | 关闭评论 |
| `--only-fans-can-comment` | 仅粉丝可评论（需开启评论） |

### 图文消息参数（news）

| 参数 | 说明 |
|------|------|
| `--cover-image` | 封面图片路径（用于生成永久素材） |
| `--thumb-media-id` | 已有封面永久素材 media_id |
| `--pic-crop-235-1` | 封面裁剪为2.35:1的坐标 X1_Y1_X2_Y2 |
| `--pic-crop-1-1` | 封面裁剪为1:1的坐标 X1_Y1_X2_Y2 |

### 图片消息参数（newspic）

| 参数 | 说明 |
|------|------|
| `--images` | 图片文件路径列表（最多20张） |
| `--image-media-ids` | 已有图片永久素材 media_id 列表 |

### 图片处理

| 参数 | 说明 |
|------|------|
| `--no-upload-images` | 不上传正文中的本地图片（默认自动上传） |

### 输出

| 参数 | 说明 |
|------|------|
| `--out` | 输出结果 JSON 文件 |
| `--verbose` | 显示详细日志 |

## 返回结果

执行成功后，工具会返回 JSON 格式的结果：

```json
{
  "action": "created",           // 操作类型：created 或 updated
  "article_type": "news",         // 文章类型
  "draft_media_id": "MEDIA_ID",   // 草稿ID
  "thumb_media_id": "THUMB_ID",   // 封面素材ID（news类型）
  "content_image_urls": {         // 正文图片上传记录
    "/path/to/image1.png": "http://mmbiz.qpic.cn/...",
    "/path/to/image2.png": "http://mmbiz.qpic.cn/..."
  },
  "result": {                      // 微信API返回的原始结果
    "media_id": "MEDIA_ID",
    "item": [...]
  }
}
```

## 工作流示例

### 完整的工作流程

```bash
# 步骤 1：准备 Markdown 文件和图片
# article.md
# cover.png
# images/
#   ├── image1.png
#   └── image2.png

# 步骤 2：创建草稿
python wechat_draftbox.py \
  --account sub \
  --title "我的文章" \
  --markdown article.md \
  --cover-image cover.png \
  --verbose \
  --out draft.json

# 步骤 3：获取草稿ID
DRAFT_ID=$(cat draft.json | jq -r '.draft_media_id')
echo "草稿ID: $DRAFT_ID"

# 步骤 4：（可选）更新草稿
python wechat_draftbox.py \
  --account sub \
  --media-id $DRAFT_ID \
  --title "更新后的标题" \
  --markdown article_v2.md \
  --cover-image new_cover.png \
  --verbose
```

## 注意事项

1. **图片上传**：正文中的本地图片会自动上传为微信临时 URL，有效期为 3 天
2. **封面图片**：封面图片会上传为永久素材，可重复使用
3. **草稿限制**：每个公众号最多保存 500 个草稿
4. **素材限制**：图片素材总大小不超过 10MB，单个图片不超过 2MB
5. **IP 白名单**：确保运行环境的 IP 地址已在公众号后台的 IP 白名单中

## 常见问题

### Q: 上传图片失败怎么办？

A: 检查以下几点：
- 图片文件是否存在
- 图片格式是否支持（jpg、png、bmp、gif）
- 图片大小是否超过限制（2MB）
- 运行环境的 IP 是否在白名单中

### Q: 如何获取已上传图片的 media_id？

A: 使用 `newspic` 类型上传的图片会返回永久素材 media_id，可在返回结果中查看。

### Q: 可以更新草稿的封面吗？

A: 可以，更新草稿时重新指定 `--cover-image` 或 `--thumb-media-id` 即可。

### Q: Markdown 支持哪些语法？

A: 支持标准 Markdown 语法，包括：
- 标题、段落、列表
- 粗体、斜体、删除线
- 链接、图片
- 代码块、行内代码
- 引用、水平线
- 表格

## 更新日志

### v2.0.0（当前版本）

- ✅ 支持更新草稿（`--media-id`）
- ✅ 支持 Markdown 直接输入（`--markdown`）
- ✅ 自动上传正文图片（默认开启）
- ✅ 添加详细日志（`--verbose`）
- ✅ 优化错误提示和用户体验

### v1.0.0

- ✅ 创建草稿（news 和 newspic 类型）
- ✅ 上传封面和图片
- ✅ 多账号支持
