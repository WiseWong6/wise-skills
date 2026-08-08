# 语义编排：从内容契约到 `deck-plan.json`

`deck-plan.json` 是叙事层，也是制作前必须存在的内部 Ghost Deck。它决定“讲几页、每页推进什么、证据怎样组织”，但绝不包含主题 token、版式 ID、坐标或组件配置。

权威结构见 `../schemas/deck-plan.schema.json`。

## 1. 先写 thesis，再选叙事

把整份 deck 的结论压成一句可争辩、可验证的话。标题只是主题，thesis 必须表达判断。例如“季度复盘”不是 thesis；“缩短首次成功路径是本季度留存提升的主要原因”才是。

按内容的主要推进方式选择 `narrative_type`：

| 类型 | 适用推进 |
|---|---|
| `problem-solution` | 痛点 → 原因 → 解法 → 结果 |
| `situation-complication-resolution` | 现状 → 矛盾 → 决策 |
| `chronology` | 时间、版本或过程演进 |
| `argument-evidence` | 主张 → 多组证据 → 结论 |
| `comparison` | 两套方案或前后状态 |
| `funnel` | 从宽到窄的筛选、转化或聚焦 |
| `custom` | 以上无法准确描述，并在 page budget reason 中解释 |

## 2. 页数由认知动作决定

不要先定模板数量。先把 must 内容按“观众需要完成的认知动作”分组：理解问题、看到机制、相信证据、比较选择、做出决定。每个页面只推进一个新结论；同一结论的证据可以作为 support block 共页。

页数判断顺序：

1. 为每个不可合并的论点建立一页；
2. 把只能作为佐证的内容挂到对应论点页；
3. 页面容量不足才拆页，信息不足则合并；
4. 加入必要的 hook、orient、synthesize、act 或 close；
5. 把影响页数的可数因素写入 `page_budget.drivers[]`，再计算 `target` 并写总理由，检查是否在用户上限内。

`target` 必须等于 `pages[]` 数量。超出 max 时不得偷偷缩字或删除 must 内容，而应触发确认。

`drivers[]` 不能只写一句笼统理由。按真实约束选择 `independent_claim`、`evidence_chain`、`audience_question`、`narrative_turn`、`density_split`、`required_transition`、`time_limit` 或 `page_limit`，记录数量和原因。它们让页数能被审计，但不要求机械相加：例如一个 transition 可能与现有 claim 共页，合并关系应在总 `reason` 中说明。`page_limit.count` 专门记录 must 内容在不牺牲可读性时至少需要的页数；若它大于用户给出的 `brief.page_limits.max`，必须触发 `must_content_overflow` 并暂停确认。

## 3. Ghost Deck 检查

只读 `assertion_title` 和 `takeaway`，应该已经能理解完整故事：

- 相邻页有因果、递进、对照或证据关系；
- 没有两页重复同一个结论；
- 结尾确实回答开头提出的问题；
- 页面标题是结论句，不是“背景”“数据分析”一类栏目名。

若脱离图形后故事不成立，先修叙事，不要进入渲染。

## 4. 页面角色

`role` 使用固定语义集合：

- `hook`：建立注意力或矛盾；
- `orient`：交代范围、路线或背景；
- `explain`：解释概念或机制；
- `prove`：提交事实与证据；
- `compare`：建立选择差异；
- `sequence`：呈现步骤或时间推进；
- `synthesize`：把多条信息收成判断；
- `decide`：给出取舍与建议；
- `act`：明确行动；
- `close`：结束叙事。

角色不是固定骨架。不是每份 deck 都必须有目录、章节页或 outro；只在叙事需要时使用。

## 5. 每页必须回答的七件事

1. `assertion_title`：这一页声称什么？
2. `audience_question`：观众此刻在问什么？
3. `takeaway`：离开这一页应记住什么？
4. `content_refs` / `evidence_refs`：凭什么这样说？
5. `relation_shape`：这些信息为什么需要这样组织？
6. `spatial_primitive`：哪一个通用空间原语直接承载 takeaway？
7. `semantic_unit_count`：实际需要表达多少个最小独立语义单元？

`spatial_primitive` 必须从十二个通用原语中选择，而且由语义规划层确定；它不属于主题。`blocks[]` 只描述语义用途、主次、内容引用和期望信息形态。不要在这里写“左栏”“六宫格”“折线图”或某个库名。

`semantic_unit_count` 统计观众需要分别读取、比较或记忆的最小内容单位：一个独立判断、KPI、流程节点、表格行、截图证据或数据系列各算一个；重复标题、标签、单位、坐标轴和纯装饰不重复计数。它是人工规划值，但必须能从 blocks 与实际内容逐项解释，不得为了匹配某个 layout 的容量倒填。

## 6. 自适应确认

内部计划始终生成。只有以下情况把 `confirmation.decision` 设为 `needs_confirmation` 并暂停渲染：

- 目标或受众缺失，而且不同答案会改变叙事；
- 内容关系中存在 `contradicts`，无法在不选边的情况下表达；
- must 内容在最大页数内放不下；
- 必须推断、占位或删除 must 内容；
- 原始长文预计生成 16 页及以上，且用户没有给页数或时长边界。

其余明确请求使用 `proceed`，同时在面向用户的短说明中给出页数、叙事和版式意图。不要为了形式机械地要求确认。

## 7. 覆盖决策

每个内容项和 must 原子值都应出现在 `coverage_decisions[]`：

- `include`：列出承载它的 `page_refs`；
- `defer`：说明为什么延后或进入附录；
- `omit`：说明为什么删除。

must 项的 defer / omit 或无页引用属于阻塞，不是警告。

## 8. 进入渲染前的停止条件

- thesis 为空且会影响叙事；
- Ghost Deck 不连贯；
- page target 与实际页数不一致；
- page、section、block 或 content 引用断裂；
- 任意 must 内容无合法覆盖；
- `confirmation.decision` 为 `needs_confirmation`。
