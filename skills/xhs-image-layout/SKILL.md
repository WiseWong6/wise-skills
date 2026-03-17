---
name: xhs-image-layout
description: 将图片拼接成 3:4 白色容器的 HTML 页面，支持打印 PDF 和下载容器截图。当用户说"拼成3:4"、"拼成3比4"、"做成打印页面"、"整理成3:4容器"等时需要使用此技能。
license: MIT
---

# 图片布局打印机

将图片自动拼接成 3:4 比例的白色容器，每个容器可放 1-2 张图片垂直排列。生成可直接打印或下载的 HTML 页面。

## 使用场景

- 将多张截图/图片整理成统一格式的展示页面
- 需要打印或导出拼接后的图片容器
- 生成带打印样式的 HTML 便于分享

## 输入

用户可提供：
1. **文件夹路径** - 包含图片的文件夹
2. **图片文件列表** - 具体的图片文件路径

支持的图片格式：jpg, jpeg, png, gif, webp

## 工作流程

### 步骤 1: 收集图片

- 如果用户提供文件夹路径，扫描该文件夹获取所有图片
- 如果用户提供图片列表，直接使用
- 按文件名排序图片

### 步骤 2: 规划布局

- 计算需要的容器数量：`ceil(图片总数 / 2)`
- 每个容器放 2 张图片（最后可能只有 1 张）
- 单张图片时只在上半部分显示，保持视觉统一

### 步骤 3: 生成 HTML

使用模板生成 HTML 文件，包含：
- 3:4 白色容器（`aspect-ratio: 3/4`）
- 图片垂直拼接（每张 50% 高度）
- 打印样式（`@media print`）
- html2canvas 下载功能
- 右上角操作按钮（打印、下载所有容器）

### 步骤 4: 生成独立版本（推荐）

将图片嵌入 HTML，生成无需服务器的独立版本：

```bash
python3 ~/.claude/skills/xhs-image-layout/scripts/embed_images.py <filename>.html
```

这会生成 `<filename>_embedded.html`，图片以 base64 形式嵌入，**可直接双击打开，下载功能完全正常**。

### 备选方案：启动服务器

如果不方便生成 embed 版本，可以启动 CORS 服务器：

```bash
cd <output_dir> && python3 start_cors_server.py
# 访问 http://localhost:8080/<filename>.html
```

## HTML 模板规范

### 容器结构
```html
<div class="page" id="page-N">
    <img src="..." alt="...">
    <img src="..." alt="...">  <!-- 可选 -->
</div>
```

### CSS 关键属性
- `.page`: `aspect-ratio: 3/4`, `background: white`
- `.page img`: `height: 50%`, `object-fit: contain`
- `.page.single img`: `height: 50%` (保持统一)

### JavaScript 功能
- `downloadAllPages()`: 使用 html2canvas 逐个下载容器为 PNG
- `window.print()`: 打印/导出 PDF

## 输出文件

| 文件 | 说明 |
|------|------|
| `<name>.html` | 主 HTML 文件 |
| `start_cors_server.py` | CORS 服务器启动脚本 |

## 注意事项

1. **CORS 限制**: 本地文件直接用浏览器打开时，html2canvas 下载会因跨域失败。必须启动服务器或使用嵌入 base64 版本
2. **图片路径**: 使用相对路径 `./folder/image.jpg`
3. **文件名**: 容器截图命名为 `page_01.png`, `page_02.png`...

## 示例

用户："/path/to/images 帮我做成打印页面"

Claude：
1. 扫描 /path/to/images 获取图片
2. 生成 image_collage.html
3. 创建 start_cors_server.py
4. 提供访问链接 http://localhost:8080/image_collage.html
