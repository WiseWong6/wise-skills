# 语义编排：从内容契约到 `deck-plan.json`

`deck-plan.json` 是叙事层和内部 Ghost Deck。它决定推荐页数、每页推进的结论和证据组织，但不含主题 token、recipe ID、坐标或组件配置。字段形状以 [`../schemas/deck-plan.schema.json`](../schemas/deck-plan.schema.json) 为唯一事实源。

## 1. 先写 thesis，再选叙事

把整份 deck 的结论压成一句可争辩、可验证的话。标题只是主题，thesis 必须表达判断。

`narrative_type` 从以下集合选择：`problem-solution`、`situation-complication-resolution`、`chronology`、`argument-evidence`、`comparison`、`funnel`、`custom`。选择 `custom` 时必须在规划理由中说明现有类型为什么不适用。

## 2. `planning_basis`：事实、推断与调研分开

规划模式只有三种：

- `user-constrained`：用户明确给出页数等限制，引用对应 `constraint.*`；
- `derived`：根据任务上下文、内容结构或时长推导；不要求存在用户约束；
- `scenario-recommended`：用户未给页数或时长，由 Skill 推荐。

使用场景的来源必须单独标记：

- `scenario_origin: user`：来自用户材料；
- `scenario_origin: inferred`：从任务上下文判断，必须写 `assumptions[]`；
- `scenario_origin: researched`：公共背景确实会影响推荐时才调研，必须写 `research_source_refs[]`。

不要因为页数或时长缺失就自动联网。先判断现有资料与任务上下文是否足够；只有外部事实会实质改变场景或页数建议时才调研。

## 3. `page_budget`：只保留一个推荐目标

`page_budget` 只有三个字段：

- `target`：唯一推荐页数，必须等于 `pages[]` 数量；
- `basis[]`：可追溯的依据；
- `reason`：解释依据如何共同形成该目标，而不是机械相加。

依据类型：

- `content_structure`：引用不可合并的结论、证据链或认知动作；
- `user_constraint`：引用明确的页数等用户约束；
- `duration`：引用用户时长约束；
- `scenario_research`：仅在实际做过场景调研时引用来源。

上下文推断的推荐使用 `content_structure` 加 `planning_basis.assumptions`，不要伪造 `scenario_research`。不要把同一个推荐页数重复写进多个字段。

## 4. Ghost Deck 与页面合同

只读各页 `assertion_title` 和 `takeaway`，应该能理解完整故事：相邻页有明确推进，结尾回答开头，没有两页重复同一个结论。

每页必须回答：

1. 这一页声称什么；
2. 观众此刻在问什么；
3. 离开时应记住什么；
4. 哪些内容和证据支撑它；
5. 信息之间是什么关系；
6. 哪个空间原语承载 takeaway；
7. 哪一个 block 是唯一主角。

`blocks[]` 必须恰好有一个 `importance: primary`。其余 block 都是 support，并服务于同一 takeaway。v2 不再保存 `semantic_unit_count` 或 `density_intent`；页面负担由实际 blocks、内容结构与 renderer capacity 校验。

## 5. 自适应确认

内部计划始终生成。`confirmation.assessments[]` 逐项记录：

- `trigger`：`ambiguous_context | source_conflict | must_content_unresolved | user_constraint_overflow | reconstruction_fact_risk`；
- `affected_refs[]`：受影响的来源、内容、原子值、素材或约束；
- `impact`：`none | conclusion | page_order | emphasis | action`；
- `resolution`：`proceed | present_both | needs_user_choice`；
- `reason`：为什么这样判断。

只有出现 `needs_user_choice` 时才把 decision 设为 `needs_confirmation` 并暂停渲染。适用情形是：用户选择会真正改变结论、页序、重点或行动，或缺少选择就形成硬阻塞。

来源冲突若可不选边地并列呈现，应使用 `present_both` 并继续；上下文不完整但不改变故事时使用 `proceed`。原始长文、页数多或字段缺失本身都不是确认理由。

`user_questions[]` 只有暂停时才填写，最多三条。每个问题都要用用户能直接回答的自然语言说清三件事：发生了什么、会影响成品的什么、需要用户在什么之间选择。不得出现 `trigger`、`affected_refs`、Schema 路径或错误码。`decision: proceed` 时问题数组必须为空。

## 6. 覆盖决策与停止条件

每个内容项和每个 `priority: must` 的 atom 都要进入 `coverage_decisions[]`：

- `include`：列出承载页面；
- `defer`：解释为何延后；
- `omit`：解释为何删除。

以下情况停止进入 Render Plan：Ghost Deck 不成立、page target 与页面数不一致、引用断裂、must 内容没有合法处理、或 confirmation 为 `needs_confirmation`。
