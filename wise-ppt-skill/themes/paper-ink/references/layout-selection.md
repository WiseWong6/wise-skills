# 纸墨主题版式选择

`layout-manifest.json` 是 63 个纸墨版式的唯一权威源。本文件解释如何读 manifest，不另建一套编号或坐标表。

## 先决定表达，再决定皮肤

Core 应先完成页面主张、受众问题、证据引用、关系形状和密度，再进入主题。纸墨主题只做以下匹配：

1. 用 `roles` 筛掉不承担该页面任务的版式。
2. 用 `relations` 匹配信息之间的关系，不按行业关键词匹配。
3. 用 `core_primitives` 匹配 deck page 已确定的 `spatial_primitive`；这一步回答“该版式能否承载这种通用空间关系”。
4. 用 `densities` 与 `capacity.semantic_units` 检查承载量。
5. 用 `slots[].allowed_providers` 检查所需组件能否落位。
6. 比较 `selection_notes` 与 `anti_patterns`，写出选择理由。

`display_code` 只服务画册浏览；render plan 必须写稳定的 `layout_id`，例如 `paper-ink.data.chart-wall`。

Manifest 中两套原语不可混用：

- `core_primitives` 只能取 Core 定义的 12 个通用原语，是 layout 的语义承载能力；render page 的 `core_primitive` 必须命中其中一项。
- `primitives` 是纸墨主题的具体实现部件，例如 `chart-grid`、`figure-caption`、`kpi-band`；render page 的 `theme_primitives` 从这里选择。

前者解释“为什么这样排”，后者解释“纸墨主题具体怎么画”。

## 复用强度

- `copy`：结构、容量、插槽完全匹配，直接复制样张骨架并换内容。模板复制是优先的高质量路径。
- `adapt`：关系一致，但数量、主次或比例有轻微变化；保留原语，调整轨道、列数或插槽比例。
- `compose`：一个现有版式能承载主关系，再叠加一个辅助原语或支持组件，例如流程 + KPI 带。
- `novel`：没有版式满足关系或容量。先用现有 primitives 组合，并在 render plan 解释为什么已有版式都不适用。

禁止因“想显得原创”而拒绝精确匹配的模板，也禁止为了快速套模板而改写事实关系。

## 三档密度

- `breathing`：1–2 个语义单元，留白不低于 60%。适合封面、章节、金句、单一隐喻和收尾。
- `balanced`：3–5 个语义单元。65/35 只是纸墨主题的起始构图比例。
- `dense`：6–12 个语义单元，或一张完整表格、数据、UI、架构复合。无固定留白比例，但必须通过字号、安全区、遮挡与溢出门禁。

容量超出 `capacity.semantic_units.max` 时拆页；低于最小值时换版式或明确接受 `underfill`，不得靠装饰填满。

## 居中与网格

- Grid 是矩阵、同级并列和证据墙的正确表达，不是默认骨架。
- 只有 `centered-type`、`particle-field`、`concentric-rings` 等中心型原语要求几何居中。
- 非对称分栏、证据墙、时间轴、章节轨、UI、流程和架构页按结构线定位，以视觉配平收尾。
- 同页可以一行两列、三列、六格或不使用格子；列数来自信息单元和关系，不来自固定模板偏好。

## 组件是插槽，不是版式

布局决定区域、比例、顺序和层级；组件决定某个 slot 如何绘制。一个布局可分别装 ECharts、atlas、截图、表格、SVG 或原生 HTML。每页只允许一个主要视觉角色，但可有多个支持组件。

六个跨组件组合例见 `themes/paper-ink/examples/`。它们都是 render plan 示例，不新增 layout ID。
