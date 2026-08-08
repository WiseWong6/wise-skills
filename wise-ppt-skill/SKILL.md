---
name: wise-ppt-skill
description: 标准网页 PPT 编排内核。接收原始资料，先完成内容治理、叙事与页数规划、逐页语义表达，再组合主题版式与 ECharts、PPT Component Atlas、SVG、图片、表格或原生 HTML，输出可放映、截图和导出 PDF 的 16:9 HTML deck。适用于制作、重排、扩写、审查演示文稿；当前唯一且默认主题为 paper-ink 纸墨风。
---

# Wise PPT

## 定位

这是一个标准编排内核，不是单一模板提示词。内部固定分为：

- `core/`：决定讲什么、讲几页、每页回答什么问题、采用什么信息关系和表达媒介。
- `themes/`：决定这些语义页在某种视觉语言中如何排版、适配组件和渲染。

当前只有 `paper-ink`，因此省略主题时默认使用它。不存在的主题必须报错并列出已注册主题，不得偷偷回退或临时伪造。

模板复制是合法能力：语义、证据、关系和容量都精确匹配时，优先复制已经验证的画册样张。禁止的是跳过语义规划，直接用画册编号代替思考。

本 Skill 输出 HTML、逐页 PNG 和 PDF，不承诺 PPTX。

## 完成标准

一次制作只有同时满足以下条件才算完成：

1. `content.json`、`deck-plan.json`、`render-plan.json` 三份权威文件存在且通过校验。
2. 所有 `must` 内容被页面覆盖；来源事实没有被改写成无来源结论；推断和占位明确标记。
3. 每页先有主张、观众问题、证据关系与密度意图，再有主题版式和组件。
4. Render Plan 中的 layout、slot、renderer、content ref、复用方式和理由都可解析。
5. HTML 契约、溢出、安全区、资源、字体和真实截图通过；人工检查内容、叙事和视觉。

## 不可跳过的规则

- 权威数据流固定为：`原始资料 → content.json → deck-plan.json → render-plan.json → HTML → QA`。
- JSON 是机器权威源；storyboard 或 Markdown 只能是派生的人读视图。
- 业务数字、引语和事实默认保真并记录来源。只有用户要求 mock 或资料确实缺失时才允许 `inferred` / `placeholder`，并明确标记。
- Core 产物不得出现主题字体、颜色、坐标、画册短码或 ECharts option。
- 一页只有一个主结论和一个主视觉角色，但可以有多个辅助组件。
- 版式回答“空间怎么组织”，组件回答“信息块怎么表达”；两者必须正交。
- Grid 适合真正等权并列或二维交叉。数量相同不代表关系相同：步骤用流程，核心与维度用辐射，证据用证据墙。
- 不以缩小字号解决溢出。先换媒介，再换密度，再拆页；Theme 只能提议，Core 决定改动。
- 不手写或复制画册目录数组；主题 manifest 是唯一事实源。
- 旧 `A1/B19/C0` 等只能是画册展示码，禁止写入 Render Plan，也不提供旧编号兼容。
- 需要生成或编辑图片时，只使用 Codex 宿主内置 `image_gen.imagegen`；不可回退到第三方生图 Skill、CLI 或 API。

## 渐进加载

开始任务时读本文件，然后按当前步骤只读需要的资料：

1. 内容治理：`core/references/content-contract.md`
2. 页数、叙事和 Ghost Deck：`core/references/deck-planning.md`
3. 逐页关系、密度和空间表达：先读 `core/references/page-expression.md`，需要选择或组合空间结构时再读 `core/references/layout-primitives.md`
4. ECharts / atlas / SVG / 图片 / 表格路由：`core/references/component-routing.md`
5. 交付门禁：`core/references/validation.md`
6. 解析主题：`themes/registry.json`，再读该主题的 `theme.json` 和 `layout-manifest.json`
7. 只有在实际使用某主题时，再读该主题 `theme.json` 声明的相应视觉规则；当前默认主题对应 `themes/paper-ink/references/`

不要为“熟悉一下”一次性载入 126 个 HTML 样张。先用 catalog 缩小候选，再打开 1–3 个最相关样张。

## 标准工作流

### 0. 确认任务边界

从用户资料提取：受众、场景、目标、希望观众采取的行动、演讲或自读、时长、页数约束、必留/可删内容、来源、主题和输出方式。

内部规划永远执行；只有出现以下任一情况才暂停向用户确认：

- 目标或受众缺失，且不同答案会改变叙事。
- 来源彼此冲突，无法判断哪个是权威事实。
- `must` 内容在最大页数内无法承载。
- 必须新增推断/占位、删除 `must` 或改变用户事实。
- 原始长文自动规划达到 16 页或更多，用户又没有给页数/时长边界。

其余清晰、低风险请求直接推进，并用一句话说明预计页数、叙事主线和主题。不要为了走流程机械提问。

### 1. 建立 `content.json`

按 `core/schemas/content.schema.json` 拆出稳定内容 ID。每项至少记录：

- `kind`：assertion、fact、metric、quote、definition、process、comparison、evidence、table、image、code 或 cta
- `statement`
- `source_refs[]`；原文定位写在对应 `sources[].locator`
- `priority`：must / should / could
- `status`：sourced / inferred / placeholder，并按状态填写 `status_note`
- 不可丢失的数字、单位、阶段名等拆入 `atomic_values[]`，而不是另造顶层 `value` / `unit`
- `relations[]`：用 supports / contradicts / depends_on / elaborates 记录内容间的证据与依赖关系；没有关系时写空数组

来源冲突保留为不同 content item，并在 `brief.gaps[]` 记录，不自行合并成单一事实。字段以 Schema 为唯一准绳，不凭说明文字发明属性。

先校验再规划：

```bash
python3 <SKILL_ROOT>/scripts/validate.py content <DECK>/content.json
```

### 2. 建立 `deck-plan.json`

按 `core/schemas/deck-plan.schema.json` 先写 thesis、叙事类型和 `page_budget.drivers[]`，用独立主张、证据链、观众问题、叙事转折、密度拆页与时间/页数约束解释页数，再写 sections 与 semantic pages。发布、提案、汇报、教程、研究报告不能共用固定骨架。

页数由独立主张、证据链、观众疑问和叙事转折推导；时长只作容量约束。封面、目录、章节页、Context、呼吸页、Outro 都按任务决定，不全局强制。

每个语义页必须有：

- `role` 与 assertion 型 `assertion_title`
- `audience_question` 与 `takeaway`
- `content_refs` / `evidence_refs`
- `relation_shape`、`spatial_primitive` 与 `density_intent`
- 至少一个 `importance: primary` block；其余 block 使用 `support`，并以 `semantic_form` 说明表达任务

这一层禁止写主题、版式、坐标、组件实现或样张编号。先只读标题与 takeaway 做 Ghost Deck，确认顺序能独立讲通，再校验：

```bash
python3 <SKILL_ROOT>/scripts/validate.py plan <DECK>/deck-plan.json
```

### 3. 为每页选择表达

决策顺序固定为：

`页面任务 → 一句话结论 → 证据形态 → 信息关系 → 密度 → 空间构成 → slot renderer → 主题适配`

密度是阅读意图，不是统一留白比例：

- `breathing`：不超过 2 个语义单元，允许 60% 以上留白；适合 hook、章节、金句、收束。
- `balanced`：3–5 个单元，层级清楚；主题可提供如 65/35 的倾向，但不是硬模板。
- `dense`：6–12 个单元，或一个完整表格、数据图、UI、架构复合体；以字号、安全区和溢出为门禁，不设固定留白率。

同样六项内容至少要根据关系区分：等权事实、连续步骤、核心六维、证据集合。不得默认都排成 2×3 卡片。

### 4. 建立 `render-plan.json`

先解析主题，再查询版式与组件：

```bash
python3 <SKILL_ROOT>/scripts/catalog.py layouts --theme paper-ink --role prove --relation evidence --primitive evidence-annotation --density dense
python3 <SKILL_ROOT>/scripts/catalog.py components --provider echarts --task trend
```

候选决策规则：

1. 淘汰丢失 `must`、关系错误、slot 不兼容或容量不合格的候选。
2. 按语义关系匹配、证据清晰度、密度可读性和主题原生程度排序。
3. 其余相同时，优先已验证的画册样张，可直接 `copy`。
4. 近似匹配用 `adapt`；多个现有能力组合用 `compose`；无匹配才用 `novel`。
5. 每页都记录 `rationale` 和 `capacity_status`：fit、underfill、overflow 或 unsupported。

Render Plan 还必须保留原语链：`core_primitive` 原样继承该语义页的 `spatial_primitive`；`theme_primitives` 只能从所选 layout 的 manifest 声明中选择 1–3 个具体实现原语。两者不能混成一组自由字符串。

Renderer 平级选择：

- `typography`：单个 KPI、金句、定义、结论。
- `table`：需要精确查值或多字段逐项比较。
- `echarts`：趋势、分布、相关、构成等定量任务；必须写 `data_ref + encode`，不得把业务数据埋在 option。
- `atlas`：已知名称的流程、架构或图解组件；Core 先完成语义选择，再按精确名称导出裸 HTML，主题负责适配。
- `svg`：独特关系、标注或画册没有覆盖的程序化表达。
- `image`：真实截图、照片、扫描件、证据原件。
- `native-html`：UI、代码、终端、文档或高密信息面板。

Atlas 只执行名称到 HTML 的确定性映射，不替 Core 做语义判断：

```bash
node ~/.codex/skills/ppt-component-atlas/scripts/export-component-html.mjs --list
node ~/.codex/skills/ppt-component-atlas/scripts/export-component-html.mjs "<精确组件名>" --output <PATH>
```

校验 Render Plan：

```bash
python3 <SKILL_ROOT>/scripts/validate.py render <DECK>/render-plan.json
```

### 5. 渲染 HTML

输出目录固定包含：

```text
<DECK>/
├── content.json
├── deck-plan.json
├── render-plan.json
├── index.html
├── frames/shot-NN.html
└── assets/
```

复制运行壳和已解析主题声明的资产，不用软链。先从 registry 取得 `<THEME_CONFIG>`，再读取其中的 `assets.bundle` 与 `assets.shot_template`；不得在通用步骤硬编码某个主题目录：

```bash
cp <SKILL_ROOT>/runtime/app-template.html <DECK>/index.html
cp -R <SKILL_ROOT>/<THEME_CONFIG.assets.bundle> <DECK>/assets
cp <SKILL_ROOT>/<THEME_CONFIG.assets.shot_template> <DECK>/frames/shot-01.html
```

每页 `<html>` 必须声明：

```html
data-page-id data-page-role data-theme data-layout data-density data-reuse-mode
```

每个内容组件根节点必须声明：

```html
data-block-id data-provider data-component data-content-ref
```

异步字体、图片和图表完成后调用主题提供的 `markRenderReady()`。不要自行修改第三方组件源文件；把导出的 atlas 或 ECharts 放进 slot wrapper，再做主题 adapter。

HTML 落盘后再跑完整来源覆盖链；这一步会从 must item / atom 一直追踪到 DOM，因此不能提前到 Render Plan 之前：

```bash
python3 <SKILL_ROOT>/scripts/validate.py coverage <DECK>
```

### 6. 三层验收

先跑确定性检查：

```bash
python3 <SKILL_ROOT>/scripts/validate.py all <DECK>
```

再用真实浏览器截图；脚本会检查 Chrome 退出、ready 标记、PNG 存在与尺寸：

```bash
bash <SKILL_ROOT>/runtime/screenshot.sh <DECK> /tmp/wise-ppt-review
bash <SKILL_ROOT>/runtime/screenshot.sh <DECK> "" "" thumb
bash <SKILL_ROOT>/runtime/export-pdf.sh <DECK>
```

若主题 `theme.json` 声明 `validation.lint_script`，还要按其 `modes` 运行主题机检。纸墨主题必须检查普通与强调色两种模式：

```bash
python3 <SKILL_ROOT>/themes/paper-ink/scripts/lint.py <DECK>
python3 <SKILL_ROOT>/themes/paper-ink/scripts/lint.py <DECK> --accent
```

最后人工逐页检查：

- 内容：事实、数字、单位、引用、来源、must 覆盖。
- 叙事：标题串起来是否能独立说明问题、是否重复或断裂。
- 表达：关系是否选对，图表是否回答问题，模板是否真的匹配。
- 视觉：1920×1080 下无溢出、字号可读、密度合理、主次明确、主题一致。

临时截图默认放 `/tmp`。验收后删除不需要的临时产物；若保留，交付时说明路径。

## 主题与画册开发规则

- 主题注册：`themes/registry.json`
- 纸墨主题契约：`themes/paper-ink/theme.json`
- 版式唯一源：`themes/paper-ink/layout-manifest.json`
- 通用与 AI 两册是同一主题的两套内容语料，不是两个主题。
- 新主题必须通过同一 Core 契约；Core 不得引用 paper-ink 的 token、稳定 ID 或资产路径。
- 新版式先写 manifest 能力和 slot 合同，再做两个画册样张；目录由生成脚本刷新。
- “版式 + 组件”的复合能力见 `themes/paper-ink/examples/`，这些组合不是新的 layout ID。
- 修改纸墨画册后运行 `python3 scripts/generate-gallery.py --check`，禁止留下 manifest 与目录不一致的手改结果。

## 交付说明

向用户交付时说明：三份 JSON 的决策摘要、实际产物路径、验证命令与结果、真实浏览器复核范围、仍有风险、人工验收步骤。若有 commit 给 hash；若启动服务给 URL；若有临时文件说明是否需要清理。
