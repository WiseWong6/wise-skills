# 纸墨主题版式选择

`layout-manifest.json` 保存 63 个已验证的纸墨 Gallery 版式，但不是合法布局全集。本文件解释如何把 Gallery 作为可选参考库，不另建一套编号、坐标表或隐藏模板。

## 先决定表达，再查询 Gallery

Core 先完成页面主张、受众问题、证据形态、关系形状、核心原语、密度，并明确所需 regions、reading order、capacity 与组件角色。之后才能查询纸墨 Gallery：

1. 用 `roles` 检查页面任务；
2. 用 `relations` 检查信息关系；
3. 用 `core_primitives` 检查通用空间原语；
4. 用 `densities` 与 `capacity.semantic_units` 检查承载量；
5. 用 `slots[]` 检查区域集合、规范阅读顺序、角色、容量和 `allowed_providers`；
6. 比较 `selection_notes` 与 `anti_patterns`，为每个候选写出 `fit` 或 `reject` 的具体原因。

`display_code` 只服务 Gallery 浏览；Render Plan 必须写稳定的 `layout_id`。`primitives` 只描述纸墨版式的实现特征，不再要求复制进 Render Plan。

只有上述条件全部满足，才可采用 Gallery。确认采用后才读取对应样张 HTML，禁止先看画册再倒推内容。Gallery 查询结果为空不是失败；Custom 是正常主路径之一。

## 三种决策结果

- `copy`：结构、区域、顺序、容量与组件全部匹配。保留 Gallery 结构，所有组件均 `keep`。
- `adapt`：Gallery 结构、区域和顺序完全匹配，但至少一个组件需要替换。被替换组件标记 `replace`，其余标记 `keep`。
- `custom`：Gallery 不满足；使用 `custom.*` ID 与页内 `custom_contract`，所有组件标记 `select`。

只要需要增减区域、重排 slot、改变 reading order 或修改主结构，就不能继续标记为 `adapt`，必须进入 `custom`。Custom 页面不写回 manifest、不新增 Gallery 样张，也无需注册。把成熟 Custom 提升进 Gallery，是独立的主题维护任务。

禁止因“想显得原创”而拒绝精确匹配的版式，也禁止为了套 Gallery 而改写事实关系。

## 三档密度

- `breathing`：1–2 个语义单元，留白不低于 60%。适合封面、章节、金句、单一隐喻和收尾。
- `balanced`：3–5 个语义单元。65/35 只是纸墨主题的起始构图比例。
- `dense`：6–12 个语义单元，或一张完整表格、数据、UI、架构复合。无固定留白比例，但必须通过字号、安全区、遮挡与溢出门禁。

容量超出时先拆页或进入合适的 Custom；不得靠缩小字号、装饰填充或隐藏 must 内容伪装 `fit`。

## 居中与网格

- Grid 是矩阵、同级并列和证据墙的正确表达，不是默认骨架。
- 只有 `centered-type`、`particle-field`、`concentric-rings` 等中心型原语要求几何居中。
- 非对称分栏、证据墙、时间轴、章节轨、UI、流程和架构页按结构线定位，以视觉配平收尾。
- 同页可以一行两列、三列、六格或不使用格子；列数来自信息单元和关系，不来自固定模板偏好。

## 组件是插槽，不是版式

布局决定区域、比例、顺序和层级；组件决定某个 slot 如何绘制。一个布局可分别装 ECharts、Atlas、截图、表格、SVG 或原生 HTML。Atlas 与 ECharts 都是可选参考源，页面可以完全使用原生能力。每页只允许一个主要视觉角色，但可有多个支持组件。
