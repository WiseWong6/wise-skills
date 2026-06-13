---
name: image-to-pages
description: 将图片拼接成3:4白色容器的HTML和PDF页面，支持打印PDF和下载容器截图。当用户说"拼成3:4"、"拼成3比4"、"做成打印页面"、"整理成3:4容器"、"已有3:4图片"、"打印图片"、"图片排版"、"做成PDF"等时需要使用此技能。
license: MIT
---

# 图片布局打印机

将图片自动拼接成 3:4 比例的白色容器，生成可直接双击打开的独立 HTML 页面和 PDF 文件（图片以 base64 嵌入，无需服务器）。

支持**两种模式**：

## 模式对比

| 模式 | 适用场景 | 效果 |
|------|---------|------|
| `auto`（默认） | 任意比例图片 → 拼成统一3:4容器 | 每容器放1-2张图，各占50%高度 |
| `full` | 图片本身已是3:4比例 → 直接排列展示 | 每张图独占一个完整容器 |

## 输入

用户可提供：
1. **文件夹路径** - 包含图片的文件夹
2. **图片文件列表** - 具体的图片文件路径

支持的图片格式：jpg, jpeg, png, gif, webp

## 工作流程

### 步骤 1: 收集图片

- 如果用户提供文件夹路径，扫描该文件夹获取所有图片
- 如果用户提供图片列表，直接使用
- 按文件名**自然排序**（1.png, 2.png, ..., 10.png，而非 1.png, 10.png, 2.png）
- 自动检测每张图片的实际宽高比例

### 步骤 2: 生成 HTML

使用脚本一步生成图片以 base64 嵌入的独立 HTML：

```bash
# 模式1（默认）：任意比例图片 → 每容器2张拼成3:4
python3 scripts/generate_html.py <图片文件夹> [输出文件名]

# 模式2：已有3:4比例图片 → 每张独占完整容器
python3 scripts/generate_html.py <图片文件夹> [输出文件名] --mode full

# 仅生成 HTML，不生成 PDF
python3 scripts/generate_html.py <图片文件夹> [输出文件名] --no-pdf
```

**自动模式检测**：脚本会自动分析图片比例。如果超过70%的图片接近3:4，会自动建议并使用 `full` 模式。

**非3:4图片处理**：在 `full` 模式下，如果图片比例偏离3:4超过8%，会自动使用 `object-fit: cover` 填满容器，避免打印时出现白边。

**打印页面优化**：打印时页面尺寸自动设为 150mm × 200mm（3:4比例），导出PDF时不会出现A4纸的白边。

输出的 HTML 文件可直接双击打开，打印和下载功能完全正常，无需启动任何服务器。

### 模式 1: auto（默认）

将任意比例的图片放入 3:4 白色容器中：

- 计算需要的容器数量：`ceil(图片总数 / 2)`
- 每个容器放 2 张图片（最后可能只有 1 张）
- **单张图片时占满整个容器高度**（100%），不留空白
- 图片以 `object-fit: contain` 方式显示

### 模式 2: full

图片本身已经是 3:4 比例，直接按原样排列展示：

- 每张图片独占一个完整容器
- 图片占满整个容器（`height: 100%`）
- **自动检测图片比例**：接近3:4用 `contain`，偏离较大用 `cover` 避免白边
- 不做任何不必要的裁剪或缩放

### 备选方案：手动生成 HTML

如果图片来自不同目录或需要自定义布局，可以直接用 Write 工具生成 HTML，图片路径使用 base64 data URI 或相对路径。模板规范见下方。

## HTML 模板规范

### 容器结构

**模式 1 (auto)**
```html
<div class="page" id="page-N">
    <img src="..." alt="...">
    <img src="..." alt="...">  <!-- 可选 -->
</div>
```

**模式 2 (full)**
```html
<div class="page full" id="page-N">
    <img src="..." alt="..." style="object-fit: cover;">  <!-- 非3:4图片自动加cover -->
</div>
```

### CSS 关键属性
- `.page`: `aspect-ratio: 3/4`, `background: white`
- `.page img`: `height: 50%`, `object-fit: contain`
- `.page.full img`: `height: 100%`
- `@media print`: `@page { size: 150mm 200mm; margin: 0; }` —— 3:4打印页面，无A4白边

### JavaScript 功能
- `downloadAllPages()`: 使用 html2canvas 逐个下载容器为 PNG
- `window.print()`: 打印/导出 PDF（页面自动为3:4比例）

## 输出文件

| 文件 | 说明 | 条件 |
|------|------|------|
| `<name>_layout.html` | 独立 HTML 文件，图片已嵌入，双击即可用 | 始终生成 |
| `<name>_layout.pdf` | PDF 文件，可直接用于打印/分享 | 需安装 Chrome/Chromium（可选） |

> PDF 生成需要系统安装 Chrome、Chromium、Edge 或 Arc 浏览器之一。如未安装，仍可通过 HTML 文件的"打印/导出PDF"按钮手动生成。

### PDF 自动生成

脚本会自动检测系统中的 Chromium 内核浏览器（Chrome > Chromium > Edge > Arc），使用 headless 模式将 HTML 渲染为 PDF。

- PDF 尺寸与 HTML 打印完全一致（150mm × 200mm，3:4 比例，无白边）
- 如不想生成 PDF，可使用 `--no-pdf` 参数
- 如未检测到浏览器，仅生成 HTML 并给出提示

## 注意事项

1. **文件体积**: 图片以 base64 嵌入，HTML 文件体积约为原图总和的 1.33 倍
2. **文件名**: 容器截图命名为 `page_01.png`, `page_02.png`...
3. **打印白边**: 若使用浏览器"打印"功能，由于页面已设为3:4比例，导出PDF时不会有A4纸的白边。如仍有白边，请使用"下载所有容器"按钮生成精确3:4的PNG。
4. **排序**: 文件名中的数字按数值排序（1,2,3...10），而非字符串排序（1,10,2...）
5. **PDF生成**: 自动调用 Chrome headless，无需手动操作。大文件（>20MB）可能需要较长时间。

## 示例

### 示例 1: 模式1 - 任意图片拼成3:4

用户："/path/to/images 帮我做成打印页面"

助手：
1. 扫描 /path/to/images 获取图片
2. 运行 `python3 scripts/generate_html.py /path/to/images`
3. 生成 `/path/to/images_layout.html` 和 `/path/to/images_layout.pdf`

### 示例 2: 模式2 - 已有3:4图片直接排列

用户："/path/to/xhs_images 这些已经是3:4的图，直接排列展示"

助手：
1. 扫描 /path/to/xhs_images 获取图片
2. 运行 `python3 scripts/generate_html.py /path/to/xhs_images output --mode full`
3. 生成 `/path/to/output_layout.html` 和 `/path/to/output_layout.pdf`，每张图独占一个完整容器
