# 排版原语：关系到空间的通用语法

原语不是模板编号，而是可组合的空间规律。AI 先理解内容关系，再把唯一主原语写入 deck page 的 `spatial_primitive`，最后到当前主题的 manifest 查找已验证实例。模板完全匹配时直接 copy；不匹配时 adapt、compose 或 novel。

## 1. 十二个通用原语

| 原语 | 空间结构 | 适用关系 |
|---|---|---|
| `focus-field` | 一个主对象占据视觉中心，其他信息退后 | focus、单一判断 |
| `bilateral-split` | 两个完整体系以一条轴分开 | comparison |
| `peer-array` | 同级单元按一维或二维对齐 | decomposition、matrix |
| `linear-sequence` | 节点沿共享路径按顺序推进 | sequence、flow |
| `parallel-tracks` | 两条链逐站对位 | comparison + sequence |
| `radial-burst` | 多个维度围绕同一核心 | mapping、network |
| `nested-regions` | 外层包含内层，边界表达保护或粒度 | nesting |
| `layered-stack` | 多层自下而上支撑或调用 | hierarchy |
| `matrix-field` | 两个维度交叉定位 | matrix |
| `network-field` | 节点与边表达多对多依赖 | network、mapping |
| `converging-path` | 多个输入汇入单一结果，或逐级收窄 | convergence、funnel |
| `evidence-annotation` | 原始证据为主体，引线与批注解释细节 | evidence、spatial |

常用辅助结构不单独决定版式：结论横带、KPI 带、引线、图例、坐标轴、局部放大框。它们只能支持主原语，不能形成第二主角。

## 2. 四步推导

### A. 写唯一 takeaway

问“观众离开这一页只能记住一句什么”。如果答案仍是栏目名，继续提炼到可判断的结论。

### B. 拆信息单元并识别关系

- 有先后：sequence / flow；末尾返回起点则 cycle。
- 有上下支撑：hierarchy；物理包裹则 nesting。
- 两个完整体系对立：comparison + bilateral split。
- 两条链逐点对照：comparison + parallel tracks。
- 围绕核心：mapping + radial burst。
- 两个维度交叉：matrix。
- 多对多连接：network。
- 逐级减少或多入一出：funnel / convergence。
- 必须看原图才能相信：evidence。
- 无先后、无中心、无层级：decomposition + peer array。

### C. 选主原语

用删除测试：去掉哪个结构后 takeaway 就讲不成立，哪个就是主原语。只允许一个主原语，并把其 canonical 名称写入 `spatial_primitive`。

### D. 添加最多两个辅助原语

需要总账时加 KPI / 结论带；需要解释细节时加 annotation；需要显式收口时加 converging path。主题选定 layout 后，把主原语及辅助原语记录到 `theme_primitives`，总数最多三个。超过两个辅助结构通常意味着应拆页。

## 3. 高频歧义

- 整套 A 对整套 B 用 `bilateral-split`；逐环节 A/B 用 `parallel-tracks`。
- 无中心的多个同级项用 `peer-array`；围绕一个核心的维度用 `radial-burst`。
- 单向步骤用 `linear-sequence`；最后回到开头才是 cycle。
- 上下调用或支撑用 `layered-stack`；外层包住内层用 `nested-regions`。
- 数值恰好递减仍可能只是排行；只有存在逐层筛选关系才用 `converging-path`。

## 4. 原语组合示例

| 页面任务 | 主原语 | 辅助原语 |
|---|---|---|
| 痛点、动作与结果逐项对应 | `parallel-tracks` | KPI 带 |
| 产品核心与六个能力维度 | `radial-burst` | annotation |
| 六阶段上线过程 | `linear-sequence` | cycle 回钩、结论带 |
| 技术架构与规格约束 | `layered-stack` | table |
| 真实界面问题审阅 | `evidence-annotation` | 局部放大、KPI |
| 转化过程 | `converging-path` | 出口结论 |

## 5. 原语质量门禁

- 数量本身没有决定 layout；关系理由写入 `relation_shape.reason`，语义选择写入 `spatial_primitive`。
- 同构框只有在信息确实同级时才成立。
- 箭头必须表达方向或因果，不能只是装饰。
- 视觉距离、层级、包裹、连线和尺度都应编码语义。
- 找到完全匹配的主题样例时优先 copy，不为“原创”强行重画。
- 找不到匹配样例时可以 novel，但仍需满足主题 capacity 与可读性门禁。
