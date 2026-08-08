# 组件路由：布局需求与 renderer 的正交组合

Layout 决定空间关系，renderer 决定某个 slot 如何呈现内容。Gallery、PPT Component Atlas 与 ECharts 都只是可选参考源；AI 可以完全使用 HTML、CSS、SVG、Typography、Table 或 Image 构建页面。

## 1. 固定决策链

严格按以下顺序决策：

`内容语义 → 所需空间结构与组件 → 查询 Gallery → 严格判断是否满足 → 选择组件来源 → 渲染与验证`

在查询 Gallery 前必须先写清：页面任务、takeaway、证据形态、relation、`spatial_primitive`、density、所需 regions、reading order、capacity 和各区域的组件角色。Gallery 不能反过来定义内容。

只有角色、关系、核心原语、密度、容量、slot 集合与顺序全部满足时，才能采用 Gallery。确认采用后才读取对应样张 HTML。查询为空或候选全部被拒绝不是失败，直接进入 `custom`。

## 2. Renderer 是渲染机制

| provider | 来源 | 适用内容 | 关键约束 |
|---|---|---|---|
| `typography` | 原生 | 单一判断、引用、大数字、短 CTA | 文字本身就是主角；不伪装成图表 |
| `table` | 原生 | 需要逐行逐列精确查值 | 保留表头、单位和来源 |
| `image` | 原生 | 真实截图、照片、扫描件、图像证据 | 标记来源；裁切不能改变证据含义 |
| `native-html` | 原生 | UI、终端、代码、密集信息面板 | 保持语义 DOM；可直接用 HTML/CSS 构建 |
| `svg` | 原生 | 关系图、流程、网络、空间标注和定制示意 | 图元必须编码语义，不做纯装饰 |
| `echarts` | 可选参考源 | 定量图表与复杂坐标编码 | 按官方 option 文档选择能力；必须有 `data_ref` 与非空 `encode` |
| `atlas` | 可选参考源 | 本地目录中可精确命名的结构组件 | 只按精确名称查询；不让 Atlas 替代语义选择 |

页面可以完全不使用 Atlas 或 ECharts。provider 是否可用仍受当前主题 `providers` 声明约束。

## 3. ECharts 的进入条件

满足任一条件时考虑 ECharts：

- 需要共同坐标轴比较多个量值；
- 需要表达趋势、分布、相关性、多序列差异或复杂关系；
- 数据更新后应由同一结构自动重绘；
- tooltip、图例或轴编码对理解有实际帮助。

一个 KPI、三条短柱、简单比例或纯流程通常无需 ECharts。选用时：

- 按 [ECharts 官方 option 文档](https://echarts.apache.org/en/option.html)选择 `component` 或 `series.type`，不受本地有限目录约束；
- 所选配置必须兼容当前主题声明的 ECharts runtime major；具体版本由主题配置提供；
- `data_ref` 指向权威数据，`encode` 明确维度、指标、系列、单位和排序；
- 禁止把业务数据只散落在 option 中而失去来源；
- theme adapter 只改视觉，不得改数值、排序或轴尺度含义；
- `radar`、`sankey`、`custom` 等类型只要数据契约和真实渲染通过，就不因本地未枚举而失败。

## 4. Atlas 的正确位置

Atlas 是可选组件目录，不是语义规划器。只有页面实际选择 `provider=atlas` 时才加载 Atlas catalog：

1. 唯一精确命中：可作为 slot renderer；
2. 多候选：比较 variant 和 slot capacity，不静默取第一个；
3. 无命中：明确返回 `render.unknown_component`，然后重新选择原生 HTML/SVG 或其他 renderer；
4. 不修改 Atlas 源目录，适配发生在当前 deck 或主题 adapter 中。

`python3 scripts/catalog.py components` 只查询 PPT Component Atlas。ECharts 直接查询官方 option 文档；原生能力不需要 catalog。

## 5. Layout 与组件决策

每页使用 `layout_decision`：

- `source=gallery, reuse_mode=copy`：Gallery 结构不变，所有 slot 的 `component_decision.action` 都是 `keep`；
- `source=gallery, reuse_mode=adapt`：Gallery 结构不变，至少一个 slot 是 `replace`，其余为 `keep`；
- `source=custom, reuse_mode=custom`：Gallery 不满足，使用页内 `custom_contract`，所有 slot 都是 `select`。

Gallery 一旦需要增减区域、调整 slot 顺序、改变 reading order 或主结构，必须切换为 `custom`。Custom 不修改 Gallery manifest，不新增样张，也不需要注册；提升为 Gallery 是独立主题维护流程。

## 6. DOM 契约

页面根节点必须写：

```html
<section class="slide"
  data-page-id="page.example"
  data-page-role="explain"
  data-theme="example-theme"
  data-layout="custom.page.example"
  data-layout-source="custom"
  data-density="balanced"
  data-reuse-mode="custom"
  data-page-title="页面结论"
  data-page-summary="观众应记住的结论"
  data-section-id="section.example"
  data-section-title="章节标题"
  data-emphasis-mode="none">
</section>
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

`data-content-ref` 用空格分隔稳定 ID。页面属性由 Deck Plan、主题、`layout_decision` 和 `emphasis` 派生；组件属性由 Render Plan 的 slot 派生。语义焦点页还必须声明 `data-emphasis-ref`、`data-emphasis-roles`，并在同一内容载体写 `data-emphasis-role`。HTML 必须与这些权威字段严格一致。

## 7. 最低质量门禁

- 一页恰好一个 primary visual role；
- 每个 slot 都有唯一 block、component decision 和 content refs；
- Gallery 的 slot 集合与规范顺序不得被 copy/adapt 改写；
- Custom 的 reading order 覆盖全部 regions，每个 block 恰好映射一次；
- 组件不是纯装饰；图表有数据引用与编码；
- layout 与 slot 容量均为 fit；
- 主题适配不会修改事实语义；
- 纯原生 HTML/SVG 页面能够在没有 Atlas/ECharts 时通过。
