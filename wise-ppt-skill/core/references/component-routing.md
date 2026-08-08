# 组件路由：版式与 renderer 的正交组合

Layout 决定空间关系，renderer 决定某个 slot 如何呈现数据。两者可以自由组合：同一个非对称分栏可以承载图表、截图或表格；同一个图表也可以进入不同的 layout。不要把“用了某组件”误当成“已经完成页面表达”。

## 1. 路由顺序

严格按以下顺序决策：

`页面任务 → takeaway → 证据形态 → relation → spatial_primitive → density → layout → slot renderer → theme adapter`

如果跳过前半段，AI 很容易把所有信息降级为同构卡片。每个 `render-plan.json` 页面必须把 deck 的 `spatial_primitive` 原样记录为 `core_primitive`，把主题 layout 的具体组合记录为 `theme_primitives`，并写 `rationale` 解释 layout 如何支持关系、为何当前 renderer 比纯文本更有效。

## 2. Renderer Provider

| provider | 适用内容 | 关键约束 |
|---|---|---|
| `typography` | 单一判断、引用、大数字、短 CTA | 文字本身就是主角；不伪装成图表 |
| `table` | 需要逐行逐列精确查值 | 保留表头、单位和来源；列多时不缩成不可读 |
| `image` | 真实截图、照片、扫描件、图像证据 | 标记来源；裁切不能改变证据含义 |
| `native-html` | UI mock、终端、代码、密集信息面板 | 保持语义 DOM；不要截图替代可读文本 |
| `echarts` | 多序列趋势、坐标编码、可比量级、统计分布 | 必须有 `data_ref` 与 `encode`；主题适配不可改变数据 |
| `atlas` | 本地组件目录中的精确结构骨架 | 先精确查询名称与 variant；不让 atlas 替代语义选择 |
| `svg` | 关系图、流程、网络、空间标注和定制示意 | 图元必须编码语义，不做纯装饰 |

## 3. ECharts 的进入条件

满足任一条件时优先考虑 ECharts：

- 需要共同坐标轴比较 4 个以上量值；
- 需要表达趋势、分布、相关性或多序列差异；
- 数据更新后应由同一结构自动重绘；
- tooltip、图例或轴编码对理解有实际帮助。

一个 KPI、三条短柱、简单比例或纯流程通常无需 ECharts。选用时：

- `data_ref` 指向权威数据；
- `encode` 明确维度、指标、系列、单位和排序；
- 禁止把数字直接散落在脚本配置里而失去来源；
- theme adapter 只改视觉，不得改数值、排序或轴尺度含义。

## 4. Atlas 的正确位置

Atlas 是组件目录，不是语义规划器。先由 core 确定“需要循环、金字塔还是时间线”，再按精确中文或英文名查询：

1. 唯一命中：可以进入 adapt 或 compose；
2. 多候选：比较 variant 和 slot capacity，不静默取第一个；
3. 无命中：回到 SVG / native HTML 或 novel，不把相似名称硬套；
4. 不修改 atlas 源目录，适配发生在当前 deck 或主题 adapter 中。

## 5. 模板复用是首选能力

模板复制没有问题；没有理由地复制才有问题。`reuse_mode` 的决策是：

- `copy`：关系、容量、slot 和组件组合完全匹配，直接复用已验证样例；
- `adapt`：主结构匹配，只替换内容、密度或单个 renderer；
- `compose`：一个 layout 需要多个已验证组件共同完成；
- `novel`：目录没有可用结构，按原语新建。

前三种必须填写 `reuse_source`。所有模式都必须写 rationale；copy 的 rationale 应明确“哪些条件完全匹配”，不能只写“参考模板”。

## 6. DOM 契约

页面根节点必须写：

```html
<main
  data-page-id="page.example"
  data-page-role="explain"
  data-theme="example-theme"
  data-layout="example-theme.flow.sequence"
  data-density="balanced"
  data-reuse-mode="adapt">
</main>
```

每个组件包装节点必须写：

```html
<section
  data-block-id="block.process"
  data-provider="svg"
  data-component="sequence-path"
  data-content-ref="atom.one atom.two">
</section>
```

`data-content-ref` 用空格分隔稳定 ID。实际 DOM 属性必须与 render plan 一致；这让覆盖检查能从事实一直追到最终像素载体。

## 7. 选择结果的最低质量

- 一页恰好一个 primary visual role；
- 每个 slot 都有对应 block 和 content refs；
- 组件不是纯装饰；
- 图表有数据引用与编码；
- layout 和 slot 容量均为 fit；
- 模板复用来源和理由可复查；
- 主题适配不会修改事实语义。
