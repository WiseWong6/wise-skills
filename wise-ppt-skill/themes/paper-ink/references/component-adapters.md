# 纸墨主题组件适配

组件选择由 Core 的语义路由完成；本文件只说明组件落入纸墨 slot 后如何变成同一套视觉语言。Atlas 与 ECharts 都是可选参考源，页面可以完全使用原生 HTML、CSS 或 SVG。

## 通用契约

每个组件根节点必须声明：

```html
<section
  data-block-id="block.metric"
  data-provider="echarts"
  data-component="line"
  data-content-ref="item.metric-retention">
</section>
```

- `data-content-ref` 必须能追到 `content.json`，不能把事实只写死在绘制代码里。
- 页面只能有一个主要视觉角色；表格、标注、KPI、来源注可作为支持组件。
- 不允许 decoration-only 组件。每个组件必须承载主张、证据或导航。
- `render_plan` 中的 provider、component、data_ref、encode 与 HTML 属性必须一致。

## Typography 与 Table

- 大字、金句、结论走宋体或文楷；正文、数据、UI 走黑体或 mono，具体字阶查 `design-tokens.md`。
- 表格必须保留真实行列关系；不要把表格拆成同构卡片以追求“好看”。
- dense 表格可缩到 16–18px 正文，但不得低于 16px；超过安全区就拆页或裁列。

## Image

- 真实截图、原件、照片属于证据，优先完整呈现并标来源；只为版式需要时才裁切。
- 图像外可加 1px 墨线、图题和局部批注；禁止用纸纹滤镜把关键信息盖住。
- 生成图必须在 `content.json` 标明 `inferred` 或 `placeholder`，不得冒充来源证据。

## Native HTML

- 适合产品 UI、表格、筛选器、规格单和高密度界面。
- 统一移除圆角、渐变、彩色状态底和重阴影；状态差异改用线型、hatch、字阶和受控强调色。
- 交互不是交付依赖；PDF/PNG 导出时关键状态必须静态可见。

## ECharts

满足以下任一条件才选 ECharts：连续数值尺度、真实坐标轴、复杂比较、多系列、地理编码，或手写 SVG 会削弱数据正确性。仅有 1–4 个 KPI 时用 Typography/SVG。

render plan 至少声明：

```json
{
  "provider": "echarts",
  "component": "line",
  "content_refs": ["item.metric-retention-series"],
  "data_ref": "item.metric-retention-series",
  "encode": {
    "x": "week",
    "y": "retention_rate",
    "series": "cohort",
    "focus": "latest"
  },
  "theme_adapter": "paper-ink.echarts"
}
```

- 图表类型按 [ECharts 官方 option 文档](https://echarts.apache.org/en/option.html)选择，不维护本地 series 白名单；`radar`、`sankey`、`custom` 等可正常使用。
- 当前纸墨主题运行时为 ECharts 5；所选配置必须兼容该 major，本次不升级运行时。
- 色板只用墨色阶梯；`?accent` 只染 encode 指定的唯一主角。
- 轴线与网格 0.6–1px；去渐变、圆角、面积重填充和阴影。
- 图例、刻度、单位永不使用强调色；图表必须有来源或数据口径。
- 异步图表页先在 `<html>` 写 `data-render-pending="true"`；字体、图片和图表全部完成后调用 `markRenderReady()`，由它在页面根节点写唯一的 `data-render-ready="true"`。不要另造 `data-page-ready` 协议。

## Atlas

`ppt-component-atlas` 只负责“精确组件名 + variant → 裸 HTML”。仅在页面实际使用 `provider=atlas` 时加载。Core 负责语义选择；不得要求 Atlas 猜概念。

- render plan 必须写可唯一命中的精确 `component` 和可选 `variant`，例如 `流程-默认变体(4步)` / `default`；不要只写会命中多条记录的 `process`。
- 导出后保留结构，套用 `theme_adapter: paper-ink.atlas`：去色、直角、细线、字体替换、静态化。
- Atlas 是 slot renderer，不是整页布局；不得让组件自带画布覆盖主题安全区。
- 候选不唯一时停止该 slot 的渲染并返回候选，不自动取第一个。

## SVG

- 自由 SVG 用于关系图、工程制图、标注、具象线稿和粒子形态。
- 线型必须编码语义：实/虚代表确定性，线宽代表权重，断口代表缺失，hatch 代表实体或选中。
- 能由真实数据直接生成的图形要从 `data_ref` 读取；不得在路径代码里另造一套数值。
