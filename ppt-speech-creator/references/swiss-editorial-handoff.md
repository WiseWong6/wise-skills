# Swiss Editorial Handoff

当 `ppt-speech-creator` 需要把某一页继续交给 HTML 渲染器时，不要直接输出 HTML，也不要依赖目录页里的 DOM/CSS。

统一改为输出 `DocumentSpec v1` 页面描述，再交给 `swiss-editorial`：

```json
{
  "version": "v1",
  "target": "16:9",
  "theme": {
    "scheme": "L",
    "family": "tech-poster"
  },
  "pages": [
    {
      "layout": "title-card",
      "variant": "default",
      "slots": {
        "eyebrow": "PPT",
        "title": "页面骨架 + 组件库",
        "subtitle": "先定页面职责，再选组件"
      },
      "items": []
    }
  ]
}
```

## 规则

- `target` 固定用 `16:9`
- 页面骨架和组件都映射到 `layout`
- 如果当前页是纯文字页，用 `title-card` 或 `quote`
- 如果当前页是“骨架 + 组件”混合页：
  - 先选主布局语义
  - 再把补充信息放进 `slots.subtitle`、`slots.caption` 或 `items`
- `public/index.html` 只用来找布局、看变体、抄示例 JSON
- 不要输出 HTML class 细节
- 不要在 `ppt-speech-creator` 里自定义新的 CSS 命名
- 不要把 `#/layout/...` 目录路由当成渲染接口

## 常用映射

- 纯文字过渡页 -> `title-card`
- 大结论页 -> `quote`
- 左右对比 -> `vs` / `before-after`
- 线性步骤 -> `process`
- 闭环 -> `process-loop`
- 里程碑 -> `timeline`
- 核心到外延 -> `concentric`
- 象限/分类 -> `matrix`
- 分层架构 -> `architecture`
- 指标页 -> `stat-card`
- 风险提醒 -> `alert-box`
- 术语/协议/接口示例 -> `terminal-box` / `code-block`

## 职责边界

- `ppt-speech-creator` 负责故事线、表达任务、页面骨架、区域分工、ASCII 图和布局选择
- `swiss-editorial` 负责 layout registry、变体预览和最终 HTML 渲染
- 如果某一页需要新的可视语义，先补 registry，再回写 handoff 映射，不要在 PPT skill 内部临时造样式
