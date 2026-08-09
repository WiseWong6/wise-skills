# 页面表达：从语义页到视觉任务

页面表达的核心不是“选几列”，而是把唯一 takeaway 翻译成可见关系。数量只参与容量校验；关系、证据形态、阅读顺序和主视觉角色决定 recipe 与 renderer。

## 1. 表达推导链

每页按固定顺序处理：

1. 写唯一 takeaway；
2. 确定观众必须看见的证据；
3. 判断 `relation_shape`，选择唯一 `spatial_primitive`；
4. 拆成一个 primary block 和必要的 support blocks；
5. 明确 regions、reading order、slot 集合与各 renderer 的容量要求；
6. 查询 recipe 并记录 `candidate_evaluations`；
7. 选择 Gallery、Composition 或 Custom。

Render Plan 不重复 role、relation 或空间原语；这些字段从 Deck Plan 派生。v2 不存在 `density_intent` 或人工填写的 `semantic_unit_count`。

## 2. 相同数量不代表相同表达

| 内容关系 | 优先表达 | 不应默认 |
|---|---|---|
| 无先后的同级指标 | peer array / matrix | 带箭头流程 |
| 前后相依的阶段 | sequence / flow | 无方向卡片 |
| 上下支撑的系统 | layered stack / hierarchy | 等宽横排 |
| 围绕核心的维度 | radial | 普通列表 |
| 可核查材料 | evidence annotation | 抽象图标卡 |
| 逐步减少的量 | funnel / convergence | 等宽卡片 |

Grid 是并列或二维关系的答案，不是元素多时的自动答案。

## 3. 主角与支持件

每页必须恰好一个 `importance: primary` block。Composition / Custom 页也必须恰好一个 `visual_role: primary` slot。支持组件可以多个，但必须共同证明同一 takeaway，例如主图表配 KPI 与注释、主流程配结果带。

如果两个组件都需要独立解释，应拆成两页。仅为丰富而增加的装饰组件应删除。

## 4. 容量回退

容量来自真实内容和能力注册表，不保存为页面“密度”标签：

- recipe 的 slot 合同限定必填区域、reading order 和每个 slot 的 min/max；
- renderer capacity 按表格行、图表系列、流程节点、文本长度或 UI 区域等实际单位判断；
- Gallery payload 必须逐 slot 落在 recipe 范围内；
- Composition / Custom 的每个 slot 必须与对应 block 和 renderer capacity 匹配。

容量超限时先换媒介、删非必要 support、重组或拆页。禁止用缩小字体、裁切或隐藏 must 事实伪装通过。

## 5. Assertion Title 与页面文案

标题承担观点，图形承担证明：

- 弱：“六阶段流程”
- 强：“六个阶段首尾相接，发布不是终点而是下一轮输入”

标题和图形不应重复朗读同一段文字。图形至少补充顺序、差异、规模、因果、层级或空间关系之一。

recipe 的用途、候选判断、复用说明和组件来源都是制作元数据，不得进入页面正文。页角只写业务主题或章节；禁止写 Gallery、recipe、mock 或组件名称。
