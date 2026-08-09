# 内容契约：从原始素材到 `content.json`

`content.json` 是事实、用户约束与素材来源层，不决定页数、版式或视觉风格。字段形状以 [`../schemas/content.schema.json`](../schemas/content.schema.json) 为唯一事实源；当前只接受 `contract_version: 2`。

## 1. Brief 与用户约束

`brief` 保存目标、受众、场景、语言和已知缺口。缺失值写 `null`，不要猜测。

`brief.user_constraints[]` 是可选字段，只登记用户明确给出的限制。支持：

- `page_limit`：精确页数或上下限；
- `duration`：精确时长或上下限；
- `must_avoid`：明确禁止出现的内容或做法；
- `other`：以上无法表达的用户限制。

每条约束必须有稳定 `constraint_id` 和 `source_refs[]`。没有用户页数或时长时不要制造约束；使用场景、页数建议与推导依据属于 Deck Plan。

不存在 `must_include` 约束。必留内容的唯一真相源是 `content_items[].priority: must`。

## 2. 来源与内容状态

所有可核对输入先进入 `sources[]`，包括用户原话、文本、文件、网页、数据集和图片。`locator` 写可复查位置；测试或演示材料才写 `synthetic: true`。

| `status` | 含义 | 要求 |
|---|---|---|
| `sourced` | 可从输入直接核对 | `source_refs` 至少一个 |
| `inferred` | 根据现有材料推导 | `status_note` 写依据 |
| `placeholder` | 尚未获得真实值 | `status_note` 写待补内容 |

不要润色业务数字、日期、专名、单位和限定词；不要把推断或合成内容伪装成来源事实。

## 3. 知识角色与内容形态分离

旧 `kind` 已删除。每个内容项必须同时声明：

- `epistemic_role`：`claim | fact | evidence | instruction`，回答“它在论证中是什么”；
- `content_form`：`prose | metric | quote | definition | process | comparison | table | image | code | cta`，回答“材料以什么形式存在”。

例如，一组指标可写为 `epistemic_role: evidence`、`content_form: metric`；行动要求可写为 `instruction + cta`。两条轴不得互相代替。

## 4. 图片资产记录

`assets[]` 只登记物理素材、文件指纹和衍生关系；具体处理与披露规则以 [`../../capabilities/references/media-contract.md`](../../capabilities/references/media-contract.md) 为唯一规则源。

- `role: source` 保存 locator、media type、SHA-256、来源引用与是否需要重构；
- `role: reconstructed` 保存 `creation_mode`、新文件指纹、用途和事实变化风险；
- reconstruct 记录 `derived_from[]`、重构方式与理由；generate 记录宿主生成器与生成理由；
- `content_form: image` 的内容项通过 `asset_refs[]` 指向实际使用的登记产物。

## 5. 内容关系与原子值

每个内容项都必须带 `relations[]`。关系包括：

- `supports`：当前内容支持目标；
- `contradicts`：来源之间存在冲突；
- `depends_on`：理解或成立依赖目标；
- `elaborates`：展开目标但不新增独立论证。

关系只能指向已存在的 `item.*` 或 `atom.*`。来源冲突保留双方，不自行合并；Deck Plan 必须在 confirmation assessment 中评估其影响和处理方式。

不可丢失的数字、单位、阶段名和专名拆入 `atomic_values[]`。页面既可引用整个 item，也可引用其中 atom；覆盖校验沿稳定 ID 追踪，不依赖模糊文本搜索。

## 6. 优先级与完成条件

- `must`：必须被合法覆盖；需要删减、占位或改变含义时评估是否必须由用户选择；
- `should`：叙事允许时保留；
- `could`：补充、附录或删减候选。

进入规划前必须满足：ID 唯一、引用有效、来源可追溯、推断与占位有说明、必留事实拆到不会被摘要吞掉的粒度、图片资产有重构合同，且 JSON 通过 v2 Schema。
