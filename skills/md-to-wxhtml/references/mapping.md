# Markdown -> WeChat HTML 映射（v2026-03）

## 1) Block 级映射

- 段落：普通文本 -> `<section data-layout-id="N">`（17px、2.0 行高、思源宋体族）
- 空行：空行 -> 不渲染（靠 margin-bottom 自然分隔）
- 章节头：`## 01 标题`
  - 简洁粗体风格：`20px <strong>序号 标题</strong>`
  - 使用 `<section>` 标签包裹
- 标题：`###`~`######`
  - `###` 及以上：下边线标题
  - `####`~`######`：左侧蓝线标题
- 分割线：`---`/`***`/`___`
  - 默认 `wechat-hr`（微信兼容 `<hr>`）
  - 可选 `remove`（不输出）、`line`（普通横线）
- 引用：`>` -> 浅底引用块（非透明）
- 代码围栏：```lang -> 终端风代码块（含三色圆点+语言标签）
- 列表：`-/*/1.` -> 默认按代码块风格渲染（`--list-style code`）
- 图片：`![alt](url)` -> 默认 `full`（外层容器等宽 + 内层 `width:100%`）
- 原始 HTML：
  - 以 `<` 开头行：直接透传
  - `<!--RAW-->...<!--/RAW-->`：整块透传

## 2) Inline 映射

- `**text**` / `__text__`：简洁粗体 `<span textstyle=""><strong>...</strong></span>`（无渐变底）
- `*text*` / `_text_`：同款简洁粗体 `<span textstyle=""><strong>...</strong></span>`
- `[text](url)`：蓝色链接 + 强下边线 + 渐变底
- `` `code` ``：`<code>`
- `{{{ raw_html }}}`：行内原样插入（不转义）

## 3) 目录（TOC）策略

- 默认：`none`
  - 不输出目录（匹配 4.html 风格）
- `fixed5-single`
  - 微信兼容优先的 float 列方案（最多 5 列）
  - 章节不足 5 个时自动均分宽度，不补空白列
  - 每列顶部短分隔线
  - 底部一条整宽分隔线
- `fixed5-scroll`
  - 横向滚动卡片样式，适用于章节过多
- `text`
  - 纯文本目录

## 4) 代码块 URL 智能断行（`--code-wrap smart-url`）

自动拆分以下粘连场景：

- `URLURL` 连写
- `URL中文` 紧贴
- `标签 URL`（如"下载地址 https://..."）
- `URL 标签`（如"... https://... 即梦图片生成接口文档"）
- `文本https://...` 紧贴

目标：粘贴到微信后仍保留清晰换行结构。

## 5) 当前默认参数

```bash
--list-style code \
--toc-mode none \
--divider-policy wechat-hr \
--image-container full \
--code-wrap smart-url \
--highlight-direction ltr \
--page-shell preview
```
