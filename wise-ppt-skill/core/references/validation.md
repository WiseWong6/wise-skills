# 验证门禁：从 JSON 到真实页面

验证顺序固定为“结构 → 引用 → 决策 → renderer → DOM / 资产 → 浏览器”。后一个门禁不能替代前一个；构建成功也不能替代真实页面复核。

## 1. 命令入口

```bash
python3 scripts/validate.py location <deck-dir> --workspace <workspace-root>
python3 scripts/validate.py content <deck-or-content.json>
python3 scripts/validate.py plan <deck-or-deck-plan.json>
python3 scripts/validate.py render-plan <deck-or-render-plan.json>
python3 scripts/validate.py render <deck-or-render-plan.json>
python3 scripts/validate.py coverage <deck-dir>
python3 scripts/validate.py gallery <skill-root-or-theme-dir>
python3 scripts/validate.py all <deck-dir>
```

任一 error 返回非零；warning 不改变退出码。不存在的文件、未知主题、无法读取的 registry / manifest 或 contract version 不一致都不得报告成功。

正式 deck 必须位于用户工作区内且位于 Skill 根目录外。`core/examples`、主题金样、Gallery 与测试 fixture 是仓库合同资产，不是用户交付物。

## 2. Content 门禁

- 根级 `contract_version` 必须为 2；
- source、asset、constraint、item、atom ID 唯一，所有引用存在；
- `brief.user_constraints[]` 只登记用户明确约束；页数区间内部一致；
- 不允许 `must_include`；必留唯一来自 `content_items[].priority: must`；
- sourced 至少一个来源；inferred / placeholder 有说明；
- `epistemic_role` 与 `content_form` 均合法；
- 每个 relation 目标存在；来源冲突进入 Plan assessment；
- source image 具有 SHA-256 且要求重构；reconstructed asset 的 creation mode、来源链或生成说明、输出 hash、用途与披露合法；generate 资产不得作为 evidence；
- `content_form: image` 的 asset refs 存在。

## 3. Plan 门禁

- Schema 合法，page order 连续且唯一；
- `planning_basis` 的约束、假设和调研来源可解析；
- `scenario_origin: inferred` 至少一个 assumption；`researched` 至少一个 research source；
- `page_budget` 只有 target、basis、reason；target 等于实际页数；
- `scenario_research` basis 只能在实际 researched 时出现；
- section、page、block、content 与 constraint 引用全部存在；
- 每页恰好一个 primary block；
- assertion title、audience question、takeaway 均非空；
- v2 页面不得出现 `density_intent` 或 `semantic_unit_count`；
- must 内容有合法 coverage decision；
- 每个来源冲突、未决 must 与约束溢出均有 assessment；
- assessment 的 affected refs、impact、resolution 与 reason 完整；
- 任一 `needs_user_choice` 推导出 `needs_confirmation`，并有 1–3 条自然语言问题；
- `proceed` 时不存在 `needs_user_choice`，且 `user_questions` 为空。

## 4. Render Plan 门禁

- 根级 contract version 为 2，且 content / deck / render 三份版本一致；
- render page 与 deck page 一一对应；
- `typography_mode` 合法；page override 仅在确有理由时出现；
- `theme_id` 存在于 `themes/registry.json`，recipe 存在于 Gallery manifest，adapter 与能力来源存在于 capabilities registry；
- candidate evaluations 不重复 recipe，并使用 `exact_fit | structure_fit | reject`；
- Gallery：恰好一个 exact fit，选中 `recipe_id` 与它一致，无 structure fit，无 slots；payload binding 必须覆盖 manifest 的完整 slot 集合并严格遵循 reading order，不能省略可选 slot；
- Composition：没有 exact fit，恰好一个 structure fit，选中 recipe 与它一致；slots 满足 structure contract；
- Custom：候选全部 reject，不含 recipe ID；reading order 覆盖全部 regions；
- Composition / Custom 每个 block 恰好映射一次，且恰好一个 primary visual role；
- renderer kind、component source、component ID 与 adapter 的能力组合合法；
- ECharts 只能声明为 svg / canvas + echarts，并有可解析 data binding；
- `data_ref.content_id` 存在，JSON Pointer 解析成功，dataset ID 唯一，encode 非空；Deck Plan 的角色、主要关系与空间原语必须和 exact / structure fit 的 recipe 相符；
- 图片 renderer 的 material treatment 明确为 reconstruct 或 generate；两者输出资产均已登记。reconstruct 有来源链且 hash 不同，generate 来自 codex-host 且不作为 evidence；证据重构声明“重构示意”；
- semantic emphasis 指向本页实际绑定或渲染的内容。

`render-plan` 完成上述 JSON、引用与能力检查，不要求 HTML 已存在；`render` 在此基础上继续检查实际 DOM 与资源。

## 5. Coverage 门禁

从 `priority: must` 内容正向追踪：

`item / atom → coverage_decision → deck page → primary/support block → Gallery payload 或 Composition/Custom slot → HTML 可见内容`

任何一环缺失都失败。Gallery 页沿 payload binding 追踪，不要求伪造 renderer slot。静态检查核对可见文本与单位；动态 SVG / Canvas / 图表由浏览器状态和人工检查补充。

## 6. DOM、资源与浏览器门禁

构建器只处理根级 `index.html`。每页 DOM 元数据必须与 Deck / Render Plan 以及 recipe 或 custom contract 一致；renderer wrapper 的实际元素必须与 `renderer_kind` 一致。

页面只有在字体、图片和异步 renderer 都完成后才能调用 `WisePPT.markSlideReady(slide)`；任一失败调用 `WisePPT.markSlideError`。根节点只在全部页面 ready 且无错误时声明 deck ready。

所有本地脚本、样式、字体和媒体路径必须真实存在；CSS 的 `@import` 与 `url()` 递归检查。ECharts 容器的 `data-dataset-id` 必须与 Render Plan 一致，同页必须恰好有一个对应的 JSON 数据块，且其值与 `data_ref` 指向的 Content 数据完全一致。

无截图浏览器检查至少覆盖：深链、翻页、ESC、实时画册、正文选择复制、字体与图片加载、异步 SVG / Canvas 状态、打印模式和资源错误。人工检查覆盖 1920×1080 溢出、字号、对比度、安全区、事实、单位、阅读顺序、主视觉唯一性与证据披露。

## 7. Core 示例与交付边界

`core/examples/` 的三份 JSON 必须独立通过当前 Schema，并展示 Gallery、Composition、Custom、数据绑定和字体 override 的 v2 写法。`tests/fixtures/deck-contract/` 负责真实主题与 runtime 的最小链路；validator 升级期间不得用旧 validator 的失败否定已通过的新 Schema。

用户交付只列最终 HTML 与 PDF 的绝对路径。三份 JSON、主题资产和 fixture 是内部合同或验证证据，不列为用户交付文件。
