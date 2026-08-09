# 纸墨主题组件适配

本文件只定义组件进入 `paper-ink` 后的视觉适配。Renderer、组件来源和稳定组件 ID 由公共能力层登记与校验：

- `capabilities/registry.json`
- `capabilities/references/component-routing.md`
- `capabilities/references/media-contract.md`

Gallery、ECharts、PPT Component Atlas 与 Codex 宿主图片能力都不属于 Theme。主题 adapter 不能改变组件语义、数据、区域、阅读顺序或来源。

## 通用视觉接口

组件根节点使用 v2 属性表达既有决定：

```html
<section
  data-block-id="block.metric"
  data-renderer-kind="svg"
  data-component-source="echarts"
  data-component-id="echarts.retention-line"
  data-theme-adapter-id="paper-ink.echarts"
  data-content-ref="item.metric-retention-series">
</section>
```

纸墨 adapter 只读取这些属性并应用视觉 token。组件仍须由公共校验器证明内容引用、数据绑定、素材血缘和能力组合合法。

所有组件遵守以下视觉边界：

- 纸底、墨色阶梯、番茄红语义焦点和字体角色只从 `design-tokens.css` 读取；
- 去除渐变、大面积彩色填充、重阴影、装饰性圆角和无语义装饰；
- 页面只有一个主视觉角色，辅助表格、标注、KPI 与来源注保持次级；
- 正文、关键结论和必留内容不得使用小字 token；
- PDF 中的关键状态必须静态可见，不能依赖悬停或点击才能理解。

## Typography 与 Table

- 标题、结论、金句和单个大数据按整套 `typography_mode` 映射 serif 或 sans；正文、说明、卡片标题与 UI 按同一模式映射。
- 表格数字、时间、编号和坐标固定使用 Courier Prime；真实手写批注固定使用 LXGW WenKai。
- 表头、行列、单位和来源保持真实查值关系，不把表格拆成同构卡片。
- 16px 的 `micro-secondary` 只用于元信息与次要表格说明；正文下限为 18px。
- 表格超出安全区时由 Core 调整字段、结构或页数，adapter 不缩小正文。

## Image

- 图片进入主题前必须已经通过公共媒体合同，主题不得放宽重构、来源或披露门禁。
- 重构产物使用 1px 墨线、图题、来源和局部批注融入纸墨体系；关键内容不叠加纸纹或装饰滤镜。
- 用于解释原始证据的重构产物必须让“重构示意”清晰可见，样式不得弱化成难以阅读的角注。
- `paper-ink.image` 只处理边框、留白、题注与视觉层级，不决定素材来源或生成方式。

## Native HTML

- 产品 UI、终端、代码、筛选器和规格单使用直角面板、细线分隔、墨色状态和清晰字段层级。
- 状态差异优先使用线型、hatch、字重和受控强调色，不使用彩色状态底或重阴影。
- 输入框、可编辑区域和正文选择状态必须保留公共 runtime 的交互让行规则。

## ECharts

ECharts 的版本、runtime、数据合同和字段映射由公共 Capabilities 管理。`paper-ink.echarts` 只提供视觉参数：

- 图表背景透明，色板使用墨色阶梯；语义焦点才可使用番茄红；
- 轴线与网格使用 0.6–1px 细线，避免渐变、圆角、面积重填充和阴影；
- 图例、刻度、单位与来源保持墨色，不因位置邻近被误染；
- 图表文字通过 `WisePPT.typeSize(role)` 读取正式字阶，数字和坐标使用 Courier Prime；
- readiness、SVG/Canvas 输出和数据消费沿用公共 runtime，不在主题中复制实现。

## PPT Component Atlas

Atlas 的查询、精确组件 ID 和导出由公共 Capabilities 管理。导出的 `native-html` 或 `svg` 使用对应的纸墨 adapter：

- 保留组件结构与语义连线，只替换字体、颜色、线宽、面板和静态状态；
- 移除组件自带的大面积色块、渐变、重阴影和不必要圆角；
- 不让组件自带画布突破页面安全区，也不让 adapter 改变节点顺序或比例含义。

## SVG 与 Canvas

- SVG 主轮廓、构造线、引线和 hatch 使用 `design-tokens.md` 的线型系统；实虚、粗细和断口必须继续表达原有语义。
- Canvas 文字与颜色通过公共 runtime helper 读取主题 token，不在绘制代码中复制字号或色值。
- adapter 只改变外观；组件使用哪份数据、如何追溯内容，仍由公共能力合同决定。
