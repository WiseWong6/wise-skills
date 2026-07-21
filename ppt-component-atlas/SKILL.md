---
name: ppt-component-atlas
description: 按中文或英文 PPT 组件名从本地 catalog 直接生成裸 HTML 文件；如果用户只是要看图册、预览或浏览组件，则只提供线上图册地址。
---

# ppt-component-atlas

`ppt-component-atlas` 只有一个职责：**把用户输入的中文或英文组件名转换为本地裸 `.html` 文件**。

本 Skill 以本地 catalog 为可信源，可以直接导出；线上图册只是快捷预览和多候选确认入口，不是导出的必经步骤。

源码口径来自：

```text
https://github.com/WiseWong6/wise-labs/tree/main/html-ppt-components
```

本地 `public/catalog-data.js` 必须与 GitHub raw catalog 对齐；维护时用脚本的 `--verify-source` 检查。

## 需求路由

当用户只是要看图册、预览、浏览组件、查看有哪些组件或要组件目录时，回复线上图册地址即可：

```text
https://wisewong.com/#tab=html-ppt-components
```

当用户要某个组件的 HTML 文件、HTML 代码文件、下载文件，或输入中文/英文组件名要求取代码时，调用导出脚本生成本地 `.html` 文件：

```bash
node ~/.codex/skills/ppt-component-atlas/scripts/export-component-html.mjs --query "<组件名>" --out-dir outputs/ppt-components
```

生成成功后，在回复里给生成文件的链接。不要在聊天里粘贴完整 HTML 源码。

导出默认为**动态版**：catalog 的 `componentMotionCss` 动效层已注入文件，与线上图册的动态预览一致——纯 CSS 实现，不含 JS；打开页面时入场动画播放一次，之后箭头轻推、雷达点脉冲等微动效持续循环。用户明确要「静态」「无动画」「不要动效」时，加 `--static` 重新导出静态版；用户未指明时默认动态，不要主动追问。

导出的文件必须是裸 HTML：只包含可独立打开所需的最小 `html/head/style/body`、组件 CSS、组件动效层和组件 DOM。不要导出 public 图册页、预览页、筛选器、分页、复制按钮、代码面板、返回按钮或说明 UI。

动效层随 catalog 的 `componentMotionCss` 一并注入：入场动画只播放一次，微动效持续循环，系统开启 `prefers-reduced-motion` 时全部自动关闭。不要手动删除生成文件里的动效样式，除非用户明确要求静态版本。

成功导出后，回复必须包含：

- 本地文件绝对路径和可点击文件链接
- `fileUrl`
- 线上详情 `detailUrl`
- 当前组件可见文字 `editableText`
- 说明这些文字只是当前参考内容，用户可以要求改文案、换色、增删元素或调整布局
- 如果用户需要预览，询问是否帮他打开浏览器预览本地 `fileUrl` 或线上 `detailUrl`

不要要求用户打开 `public/index.html` 后再自己定位组件；必须给准确的生成文件路径和准确的预览 URL。

如果 catalog 中没有完全满足用户需求的样式，先给最接近的组件作为参考 HTML；后续改文案、换色、加多个元素、改布局时，直接编辑生成出的 `.html` 文件。不要把这些二次修改强行塞回 catalog 或脚本参数。

## 数据口径

- 唯一数据源是 `public/catalog-data.js`
- 当前数据来自 `WiseWong6/wise-labs/html-ppt-components/catalog-data.js`
- 当前只保留 61 个组件 entry
- catalog 同时携带 `componentMotionCss` 动效层，导出时随组件 CSS 一并注入
- 旧 catalog 中多出来的组件口径不保留、不兼容、不做 alias

## 匹配规则

- 支持中文 `label`
- 支持英文 `name`
- 支持 `name + variant`
- 支持编号
- 精确命中唯一组件时直接导出
- 多候选时只输出候选列表和线上详情链接，让用户选择具体组件；不要自动取第一个
- 无命中时提示未找到，并给出可参考候选

## 脚本接口

```bash
# 列出全部组件
node ~/.codex/skills/ppt-component-atlas/scripts/export-component-html.mjs --list

# 按中文名导出（默认动态版，含动效）
node ~/.codex/skills/ppt-component-atlas/scripts/export-component-html.mjs --query "封面" --out-dir outputs/ppt-components

# 导出静态版（无动效）
node ~/.codex/skills/ppt-component-atlas/scripts/export-component-html.mjs --query "封面" --static --out-dir outputs/ppt-components

# 按英文名或英文名 + 变体导出
node ~/.codex/skills/ppt-component-atlas/scripts/export-component-html.mjs --query "process wrapped" --out-dir outputs/ppt-components

# 检查本地 catalog 是否对齐 GitHub 源码
node ~/.codex/skills/ppt-component-atlas/scripts/export-component-html.mjs --verify-source
```

脚本输出 JSON：

- `status: "ok"`：已生成文件，读取 `file`、`fileUrl`、`detailUrl`、`editableText`；`motion: true` 表示动态版（含动效层），`false` 为静态版
- `status: "ambiguous"`：多候选，读取 `candidates` 中的 `detailUrl` 辅助确认样式
- `status: "not_found"`：无命中，读取 `candidates` 中的 `detailUrl` 作为参考
- `status: "mismatch"`：`--verify-source` 发现本地 catalog 与 GitHub raw 不一致
- `status: "error"`：脚本调用或数据错误

## 后续修改

本 Skill 生成的是参考组件文件，不负责覆盖所有视觉变化。用户要改组件时，按普通 HTML 文件继续编辑生成结果：

- 改文字：直接改生成文件里的可见文案
- 换色：直接改生成文件里的 CSS 变量、颜色值或局部样式
- 加元素：直接改生成文件里的 HTML 结构
- 当前 catalog 样式不满足：用最接近组件作为参考，再直接改生成文件

二次修改只作用于 `outputs/ppt-components/` 里的生成文件；不要改 `public/catalog-data.js`，除非用户明确要求更新 catalog 源数据。

## 禁止事项

- 不输出组件卡片
- 不输出 public 图册页或图册包装 HTML
- 不输出带筛选器、分页、复制按钮、代码面板、返回按钮的预览页
- 不让用户自己打开 public 目录再手动查找组件
- 不把用户的二次修改写回 catalog，除非用户明确要求
- 不做 PPT Host Skill 协同
- 不提供 Host 适配建议
- 不把组件语义映射到其它 PPT/Slides 渲染器
- 不生成整份 PPT 或 deck
- 不把旧 catalog 口径作为 fallback
