---
name: md-to-wxhtml
description: 将 Markdown 转换为微信编辑器/富文本平台兼容的 HTML（保留 data-* 属性与原始 HTML 片段），用于生成公众号文章、狗狗/96/135 编辑器样式输出。优先用于文章发布链路；当输入是公众号正文、图文稿、草稿箱前 HTML 时，使用 `--content-mode article` 以获得文章友好的默认参数。
---

# md-to-wxhtml

## 适用场景

- 需要把 Markdown 直接转成可粘贴到微信编辑器的 HTML。
- 文档中混有原始 HTML（尤其 `data-*` 属性）并要求原样保留。
- 需要稳定输出：章节头、5 列目录、代码块、图片容器、引用块。

## 默认风格（2026-03）

- 主色：`#0052FF`
- 浅色：`#E6F0FF`
- 字体：
  - **全局字体：`Noto Serif SC / Noto Sans SC /苹方简细体`**
  - 回退字体：`Noto Serif SC / 思源宋体`
- 字号：17px，font-weight: 300，line-height: 2.0
- 强调规则：
  - `**加粗**` 和 `*强调*`：简洁粗体 `<span textstyle=””><strong>...</strong></span>`
  - `[超链接](url)`：蓝色 + 强下边线 + 渐变底
- 引用块：浅底 `#F8FAFC` + 左侧蓝线（非透明背景，避免暗色模式变灰）
- **顶部/底部引导文案**：
  - 歪斯Wise号：⭐️ 关注星标，收看AI实战
  - 人类号：⭐️ 关注星标，收看AI、商业新知
  - 通过 `--account-type` 参数切换

## 关键布局规律（从最终成型 HTML 提炼）

1. 章节头（`## 01 标题`）：
   - 简洁粗体风格：`20px <strong>序号 标题</strong>`
   - 使用 `<section>` 标签包裹
2. 目录（TOC）：
   - 默认 `none`（无目录，匹配 4.html 风格）
   - 可通过 `--toc-mode fixed5-single` 手动开启
3. 正文分隔线：
   - Markdown `---` 默认输出微信兼容 `<hr>`（`--divider-policy wechat-hr`）
4. 代码块：
   - 保留 macOS 三色圆点 + 语言标签。
   - 默认启用 `smart-url`，自动断开”标签+URL+标签+URL”粘连。
   - `pre` 使用 `white-space: pre-wrap` 保留换行。
5. 图片：
   - 默认 `full`：外层容器等宽，内层图片 `width:100%`，避免粘贴后宽度漂移。
6. 段落：
   - 使用 `<section data-layout-id=”N”>` 替代 `<p>`（微信兼容）

## 快速开始

```bash
python3 scripts/convert_md_to_wx_html.py input.md -o output.html
```

## 推荐模式

### 文章模式（新增，推荐给 article-workflow / 公众号正文）

```bash
python3 scripts/convert_md_to_wx_html.py input.md -o output.html \
  --content-mode article \
  --account-type human
```

`--content-mode article` 会把输出收敛到公众号正文更友好的默认值：
- 列表使用 `html`，不再转成深色代码块
- 不输出预览页壳，适合直接进入草稿箱
- 保持 `wechat-hr`、`full` 图片容器等文章默认项

## 常用命令

1. 默认（带预览页面外壳）

```bash
python3 scripts/convert_md_to_wx_html.py input.md -o output.html
```

2. 不带预览外壳（纯内容，给 wechat-draftbox 用）

```bash
python3 scripts/convert_md_to_wx_html.py input.md -o output.html \
  --page-shell none
```

3. 目录改为滚动卡片（章节很多时）

```bash
python3 scripts/convert_md_to_wx_html.py input.md -o output.html \
  --toc-mode fixed5-scroll
```

4. 关闭代码 URL 智能断行

```bash
python3 scripts/convert_md_to_wx_html.py input.md -o output.html \
  --code-wrap none
```

5. 使用人类号账号类型（底部文案不同）

```bash
python3 scripts/convert_md_to_wx_html.py input.md -o output.html \
  --account-type human
```

6. 保留 Markdown 分割线为普通线

```bash
python3 scripts/convert_md_to_wx_html.py input.md -o output.html \
  --divider-policy line
```

## 参数约定（当前默认）

- `--content-mode default`：保留原有脚本默认值。
- `--content-mode article`：文章模式，建议用于公众号图文正文。
- `--list-style code`：列表默认转代码块风格；**文章模式下自动切为 `html`**。
- `--toc-mode none`：无目录（匹配 4.html 风格），可通过 `--toc-mode fixed5-single` 开启目录。
- `--divider-policy wechat-hr`：Markdown `---` 输出微信兼容 `<hr>`。
- `--image-container full`：图片容器与正文等宽。
- `--code-wrap smart-url`：代码块 URL 智能断行。
- `--highlight-direction ltr`：强调渐变从左到右。
- `--account-type wise`：账号类型，控制顶部/底部引导文案。
  - `wise`：歪斯Wise号 - ⭐️ 关注星标，收看AI实战
  - `human`：人类号 - ⭐️ 关注星标，收看AI、商业新知
- `--page-shell preview`：是否带预览页面外壳（`preview`=带工具栏，`none`=纯内容）

## 原始 HTML 保留

- 使用 `<!--RAW-->` 与 `<!--/RAW-->` 包裹需要原样透传的片段。
- 对于以 `<` 开头的单行 HTML，脚本会直接透传。

## 资源路径

- 脚本：`scripts/convert_md_to_wx_html.py`
- 规则映射：`references/mapping.md`
- 分割线模板：`assets/divider.html`
- 图片模板：`assets/image_template.html`

## Handoff 落盘协议（article-workflow 子步骤）

1. 读取 `--run-dir` 和 `--output-path`
2. 输出 HTML 到 `{run_dir}/{output_path}`
3. 生成 `{run_dir}/wechat/11_handoff.yaml`：

```yaml
step_id: "11_wx_html"
inputs:
  - "wechat/10_handoff.yaml"
  - "wechat/07_final_final.md"
  - "wechat/10_image_mapping.json"
outputs:
  - "wechat/11_article.html"
  - "wechat/11_handoff.yaml"
summary: "Markdown 转换为微信编辑器兼容 HTML（图片使用 CDN URL）"
next_instructions:
  - "下一步：wechat-draftbox 上传到草稿箱"
open_questions: []
```
