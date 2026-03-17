---
name: wechat-draftbox
description: 当需要将 HTML 图文写入微信公众号订阅号草稿箱（含永久封面素材与可选图文内图片上传）时应使用此技能。
---

# Wechat Draftbox

## 概述

将本地 HTML/Markdown 图文写入微信公众号草稿箱。
- `news`：图文消息（支持封面永久素材 `thumb_media_id`、可自动上传正文本地图片并替换为微信 URL）
- `newspic`：图片消息（最多 20 张图片，走永久素材上传）
- 支持更新草稿：提供 `--media-id` 时调用更新接口

## 适用场景

- 新增草稿 / 写入草稿箱
- 更新已存在草稿（同一 `media_id`）
- Markdown 到草稿（自动转 HTML）
- 自动上传正文内本地图片并替换 URL

## 工作流程

1) 准备环境

- 配置环境变量（多账号支持）：
  ```bash
  # 主公众号（歪斯Wise）
  export WECHAT_APPID_MAIN=your_main_appid
  export WECHAT_APPSECRET_MAIN=your_main_secret

  # 副业公众号（人类）
  export WECHAT_APPID_SUB=your_sub_appid
  export WECHAT_APPSECRET_SUB=your_sub_secret
  ```
- 确认出网 IP 在公众号后台白名单中（否则会报 `40164 invalid ip`）
- 如需 Markdown 转换：`pip install markdown`

2) 准备内容

- 内容源（二选一）：`--content-html` 或 `--markdown`
- `news` 类型封面（二选一）：`--cover-image` 或 `--thumb-media-id`
- `newspic` 类型图片（二选一）：`--images` 或 `--image-media-ids`

3) 执行

```bash
SKILL_DIR="$HOME/.codex/skills/wechat-draftbox"  # 也可用 ~/.claude/skills/wechat-draftbox

# 1) 创建草稿：Markdown -> HTML（news）
python3 "$SKILL_DIR/scripts/wechat_draftbox.py" \
  --account main \
  --title "草稿标题" \
  --markdown /abs/path/to/article.md \
  --cover-image /abs/path/to/cover.jpg \
  --out /abs/path/to/wechat_draft.json

# 2) 创建草稿：HTML（news）
python3 "$SKILL_DIR/scripts/wechat_draftbox.py" \
  --account main \
  --title "草稿标题" \
  --content-html /abs/path/to/article.html \
  --cover-image /abs/path/to/cover.jpg

# 3) 更新草稿（news）：提供 --media-id
python3 "$SKILL_DIR/scripts/wechat_draftbox.py" \
  --account main \
  --media-id MEDIA_ID \
  --title "更新后的标题" \
  --markdown /abs/path/to/article.md \
  --thumb-media-id THUMB_MEDIA_ID \
  --verbose

# 4) 创建图片消息（newspic）
python3 "$SKILL_DIR/scripts/wechat_draftbox.py" \
  --account sub \
  --article-type newspic \
  --title "图片消息" \
  --content-html /abs/path/to/article.html \
  --images /path/to/img1.jpg /path/to/img2.png

# 5) 不上传正文内本地图片（news）
python3 "$SKILL_DIR/scripts/wechat_draftbox.py" \
  --account main \
  --title "草稿标题" \
  --markdown /abs/path/to/article.md \
  --cover-image /abs/path/to/cover.jpg \
  --no-upload-images
```

4) 校验输出

- 命令会输出 JSON 到 stdout
- `draft_media_id`：草稿箱素材 ID（`media_id`）
- `thumb_media_id`：封面永久素材 ID（news）
- `image_media_ids`：图片永久素材 ID 列表（newspic）
- `content_image_urls`：正文图片替换记录（如有）

## 参数说明

| 参数 | 必填 | 说明 |
|------|------|------|
| `--account` | 是 | 公众号账号：`main` 或 `sub` |
| `--title` | 是 | 文章标题 |
| `--content-html` | 二选一 | HTML 文件路径 |
| `--markdown` | 二选一 | Markdown 文件路径（自动转换为 HTML；需安装 `markdown`） |
| `--media-id` | 否 | 草稿 ID（提供时更新草稿，否则创建草稿） |
| `--article-type` | 否 | `news`（默认）或 `newspic` |
| `--author` | 否 | 作者（默认：main=Wise Wong，sub=吃粿条） |
| `--digest` | 否 | 摘要（news 有效，未提供时自动从正文第一段提取） |
| `--content-source-url` | 否 | 原文链接（news 有效） |
| `--cover-image` | news 二选一 | 封面图片路径（上传为永久素材生成 `thumb_media_id`） |
| `--thumb-media-id` | news 二选一 | 已有封面永久素材 media_id |
| `--pic-crop-235-1` | 否 | 封面裁剪为 2.35:1 的坐标 X1_Y1_X2_Y2（news） |
| `--pic-crop-1-1` | 否 | 封面裁剪为 1:1 的坐标 X1_Y1_X2_Y2（news） |
| `--images` | newspic 二选一 | 图片文件路径列表（最多 20 张） |
| `--image-media-ids` | newspic 二选一 | 已有图片永久素材 media_id 列表 |
| `--need-open-comment` | 否 | 开启评论（默认开启） |
| `--no-open-comment` | 否 | 关闭评论 |
| `--only-fans-can-comment` | 否 | 仅粉丝可评论（需开启评论） |
| `--no-upload-images` | 否 | 不上传正文中的本地图片（默认自动上传；仅 news 生效） |
| `--verbose` | 否 | 显示详细日志 |
| `--out` | 否 | 将 JSON 结果额外保存到文件 |

## 文件

- `scripts/wechat_draftbox.py`：草稿箱创建/更新脚本
- `README.md`：更完整的使用说明
- `references/wechat_api.md`：草稿箱/素材 API 要点与错误码

## Handoff 落盘协议

**当作为 article-workflow 子技能调用时：**

1. 接收来自 article-workflow 的输入参数
2. 执行草稿箱上传
3. 生成 handoff.yaml：
```yaml
step_id: "12_draftbox"
inputs:
  - "wechat/11_article.html"
  - "wechat/09_images/cover_16x9.jpg"
  - "wechat/03_title_selected.md"
outputs:
  - "wechat/12_draft.json"
  - "wechat/12_handoff.yaml"
summary: "上传 HTML 和封面到公众号草稿箱"
next_instructions:
  - "工作流完成：可以在公众号后台编辑和发布"
open_questions: []
```
4. 保存到 `{run_dir}/wechat/12_handoff.yaml`
