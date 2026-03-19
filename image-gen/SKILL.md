---
name: image-gen
description: 生成图片支持多提供商：火山 Ark (Doubao Seedream) 或 Gemini 3 Pro Image。支持批量生成、图片编辑、多图合成、自动保存和 Markdown 插入。
metadata:
  {
    "openclaw":
      {
        "emoji": "🎨",
        "requires": { "env": ["ARK_API_KEY", "GEMINI_API_KEY"] },
        "primaryEnv": "ARK_API_KEY"
      },
  }
---

# Image Gen

## 概述

支持多提供商的图片生成工具：
- **火山 Ark**: OpenAI 兼容接口，Doubao Seedream 系列模型
- **Gemini 3 Pro Image**: Google 的 Nano Banana Pro，支持图片编辑和多图合成

默认关闭水印，可输出 URL 或 base64，并按需保存到本地。支持批量生成和多线程并行处理。

## 快速开始

### 火山 Ark (默认)

```bash
python scripts/generate_image.py \
  --prompt "星际穿越，黑洞，复古列车，电影大片感" \
  --model "doubao-seedream-5-0-260128" \
  --size "2K"
```

### Gemini 3 Pro Image

```bash
# 生成图片
python scripts/generate_image.py \
  --provider gemini \
  --prompt "一只可爱的猫咪" \
  --output "./cat.png" \
  --resolution 2K

# 编辑图片（单图）
python scripts/generate_image.py \
  --provider gemini \
  --prompt "给这只猫加上墨镜" \
  --input-image ./cat.png \
  --output "./cool-cat.png"

# 多图合成（最多14张）
python scripts/generate_image.py \
  --provider gemini \
  --prompt "把这些合成为一个场景" \
  --input-image img1.png --input-image img2.png --input-image img3.png \
  --output "./combined.png"
```

## 平台智能识别

脚本会根据输出路径自动识别目标平台并应用固定比例规则：

### 固定比例规则

| 平台 | 图片类型 | 比例 | 说明 |
|------|----------|------|------|
| 公众号（WeChat） | 封面图 | 21:9 | 超宽横版 |
| 公众号（WeChat） | 正文图 | 16:9 | 标准宽屏 |
| 小红书（Xiaohongshu） | 全部 | 3:4 | 竖版 |

### 自动检测逻辑

脚本会检测以下路径中的平台标识：
- `wechat` 或 `公众号` → 公众号
- `xiaohongshu` 或 `小红书` → 小红书

检测顺序：输出文件路径 → 输出目录 → 提示词文件路径

### 示例

```bash
# 自动使用公众号比例：封面 21:9
python scripts/generate_image.py \
  --prompt "保险知识科普" \
  --output "./wechat/cover.jpg"

# 批量生成：第1张=封面21:9，第2+张=正文16:9
python scripts/generate_image.py \
  --prompts-file "./wechat/12_prompts.md" \
  --out-dir "./wechat/13_images/" \
  --insert-into "./wechat/11_final_final.md"  # 关键：自动插入图片到文章

# 自动使用小红书比例：全部 3:4
python scripts/generate_image.py \
  --prompt "今日穿搭分享" \
  --output "./小红书/cover.jpg"
```

### 手动覆盖

如需覆盖自动检测的比例，使用 `--aspect-ratio` 参数：

```bash
python scripts/generate_image.py \
  --prompt "测试" \
  --output "./test.jpg" \
  --aspect-ratio "1:1"
```

## 参数约定

### 通用参数

- `--provider`：提供商选择，`ark`（默认）或 `gemini`
- `--prompt`：图片生成提示词
- `--output`：输出文件路径
- `--aspect-ratio`：手动指定比例，可选 `1:1`、`16:9`、`9:16`、`4:3`、`3:4`、`21:9`

### 火山 Ark 专用参数

- `--base-url`：默认 `https://ark.cn-beijing.volces.com/api/v3`
- `--watermark`：默认 `false`（关闭水印）
- `--response-format`：`url` 或 `b64_json`
- `--model`：模型 ID，如 `doubao-seedream-5-0-260128`
- `--size`：图片尺寸，如 `2K`
- `--prompts-file`：从 Markdown 文件读取提示词（支持 image-prompter 格式）
- `--out-dir`：输出目录（与 `--output` 二选一）
- `--insert-into`：指定 Markdown 文件路径，生成图片后自动插入到合适位置

### Gemini 3 Pro Image 专用参数

- `--input-image`, `-i`：输入图片路径（可多次指定，最多14张），用于图片编辑或多图合成
- `--resolution`, `-r`：输出分辨率，`1K`（默认）、`2K` 或 `4K`
- `--api-key`：Gemini API key（也可用 `GEMINI_API_KEY` 或 `NANO_BANANA_PRO_API_KEY` 环境变量）

## 提示词文件格式

**支持从文件读取多个提示词：**

```text
# 每行一个提示词，格式参考 image-prompter 输出
星际穿越，黑洞，复古列车，电影大片感
治愈系插画，暖色调，温馨氛围
扁平化科普图，清晰信息，简洁设计
```

**使用方式：**

```bash
# 从文件读取提示词
python scripts/generate_image.py \
  --prompts-file /path/to/prompts.md \
  --out-dir "./wechat/09_images/"
```

## 自动插入图片到 Markdown

**新增功能**：使用 `--insert-into` 参数，生成图片后自动插入到 Markdown 文件的合适位置。

```bash
# 生成图片并插入到 Markdown
python scripts/generate_image.py \
  --prompt-file /path/to/prompts.txt \
  --out-dir "./wechat/09_images/" \
  --insert-into "./wechat/07_final_final.md"
```

**插入策略：**
1. 第 1 张图片：插入到主标题（`# 标题`）后
2. 第 2+ 张图片：插入到各章节标题（`## 章节名`）后
3. 图片引用格式：`![alt](09_images/image_XX.jpg)`（相对路径）

**配合工作流使用：**
```bash
# article-workflow 完整流程
python scripts/generate_image.py \
  --prompt-file "wechat/08_prompts.md" \
  --out-dir "wechat/09_images/" \
  --insert-into "wechat/07_final_final.md" \
  --handoff-out "wechat/09_handoff.yaml"
```

## 使用流程

1. 运行脚本时会先显示当前设置的比例
2. 需要用户确认比例是否正确（输入 y/n）
3. 确认后才会开始生成图片

## Handoff 落盘协议

**当作为 article-workflow 子技能调用时：**

1. 读取 `--prompt-file`，逐行读取提示词
2. 为每个提示词生成图片，保存到 `{run_dir}/wechat/09_images/`
3. **如果提供 `--insert-into`**：自动插入图片到 Markdown 文件
4. 生成 handoff.yaml：
```yaml
step_id: "09_images"
inputs:
  - "wechat/08_prompts.md"
outputs:
  - "wechat/09_images/"
  - "wechat/07_final_final.md"  # 如果使用 --insert-into
  - "wechat/09_handoff.yaml"
summary: "生成文章配图并插入到 Markdown"
next_instructions:
  - "下一步：md-to-wxhtml 转换为 HTML"
open_questions: []
```
5. 保存到 `{run_dir}/wechat/09_handoff.yaml`

## 批量生成

### 单 prompt 多图生成

使用 `--num-images` 参数指定生成数量，脚本会自动使用多线程并行生成：

```bash
python scripts/generate_image.py \
  --prompt "抽象艺术，色彩斑斓" \
  --num-images 10 \
  --output "./artworks/"
```

脚本会根据图片数量动态调整线程数（最多 5 个并发），并为每张图片生成带序号的文件名（如 `image_01.jpg`、`image_02.jpg` 等）。

### 输出格式

- **单张生成**：直接输出到指定文件
- **批量生成**：输出到指定目录，文件名格式为 `image_01.jpg`、`image_02.jpg` 等

## 常见任务

### 生成图片并返回 URL

使用 `--response-format url`，脚本会输出 URL。

### 生成图片并保存文件

传入 `--output`，脚本会自动下载或解码到指定路径。

### 批量生成图片

使用 `--num-images` 指定数量，配合 `--output` 指定输出目录。

## 依赖安装

```bash
# 火山 Ark 支持
pip install openai python-dotenv pyyaml

# Gemini 3 Pro Image 支持（可选）
pip install google-genai pillow
```

## 环境变量

| 变量名 | 用途 | 必需 |
|--------|------|------|
| `ARK_API_KEY` | 火山 Ark API Key | Ark 必需 |
| `GEMINI_API_KEY` 或 `NANO_BANANA_PRO_API_KEY` | Gemini API Key | Gemini 必需 |

## 脚本

- `scripts/generate_image.py`：统一入口，支持：
  - **火山 Ark**: 批量生成、多线程并行、平台智能识别、Markdown 自动插入
  - **Gemini 3 Pro**: 图片生成、编辑（单图）、多图合成（最多14张）
