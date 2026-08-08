# 验证门禁：从 JSON 到真实页面

验证顺序固定为“结构 → 引用 → 容量 → DOM → 视觉”。后一个门禁不能替代前一个；构建成功也不能替代真实浏览器复核。

## 1. 命令入口

```bash
python3 scripts/validate.py location <deck-dir> --workspace <workspace-root>
python3 scripts/validate.py content  <deck-or-content.json>
python3 scripts/validate.py plan     <deck-or-deck-plan.json>
python3 scripts/validate.py render-plan <deck-or-render-plan.json>
python3 scripts/validate.py render   <deck-or-render-plan.json>
python3 scripts/validate.py coverage <deck-dir>
python3 scripts/validate.py gallery  <skill-root-or-theme-dir>
python3 scripts/validate.py all      <deck-dir>
```

命令退出码必须可靠：任一 error 返回非零；warning 不改变退出码。不存在的文件、未知主题或无法读取的 manifest 都不得报告成功。

`location` 是创建文件前的第一道门禁：正式 deck 必须位于用户当前工作区内，同时位于 Skill 根目录之外。`content`、`plan`、`render-plan`、`render`、`coverage`、`all` 也会拒绝落在 Skill 根目录内的正式产物；`core/examples`、gallery 和测试夹具只作为仓库内部契约资产保留，不视为用户交付物。主题目录不得再维护完整 deck 示例；主题视觉样张只进入 gallery，三种渲染决策只进入测试夹具。

## 2. Content 门禁

- schema 合法；
- source、item、atom ID 全局唯一；
- 每个 `source_ref` 存在；
- 每个 relation 的 `target_ref` 存在；出现 `contradicts` 时必须进入 confirmation trigger；
- sourced 至少一个来源；
- 引用 `synthetic: true` 来源的内容只能标记为 placeholder；
- inferred / placeholder 有说明；
- `brief.page_limits.min <= max`；
- must 项与原子值可被 coverage 逐一追踪。

## 3. Plan 门禁

- schema 合法，page order 连续且唯一；
- target 等于实际页数，且位于 min/max 内；
- `page_budget.drivers` 非空，每个 driver 有可数数量与具体理由；
- section、page、block、content 引用全部存在；
- 每页恰好一个 primary block；
- Ghost Deck 的 assertion title / takeaway 均非空；
- 每页 `spatial_primitive` 属于十二个通用原语；
- 每页声明唯一的 `semantic_unit_count`，作为后续容量校验依据；
- must 内容有 include 决策和页面承载；
- `needs_confirmation` 时停止进入 render。

## 4. Render 门禁

- Render Plan 只接受 `schema_version: "2.0"`、`document_mode: "single-html"`、根级 `output_file: "index.html"`；`pages[]` 禁止 `output_file`；
- schema 合法，render page 与 deck page 一一对应；
- `theme_id` 存在于主题 registry；未知主题立即失败；
- role、density、空间原语和容量值直接从 Deck Plan 读取，Render Plan 不得维护副本；
- 每页先声明布局需求，再通过 `layout_decision` 选择 `gallery` 或 `custom`，并保留候选判断理由；
- Gallery 路径要求 layout ID 存在，且角色、relation、core primitive、density、capacity、slot 集合、slot 顺序与 provider 全部匹配；
- `copy` 必须全部 `keep`；`adapt` 必须至少一个 `replace`，且不得增减、重排 slot 或嵌入 custom contract；结构变化统一报 `render.gallery_structure_changed`；
- Custom 路径要求 `custom.*` ID 不与 Gallery 冲突，并声明 reading order、regions 与 capacity；每个 block 恰好映射一次，reading order 覆盖全部 region；
- block 与 slot 一一映射，恰好一个 primary visual role；Custom 的每个组件决策必须是 `select`；
- `emphasis=semantic-focus` 必须指向本页已渲染内容并声明语义成员角色；`none` 不得暗示隐藏焦点；
- ECharts 只要求 `data_ref`、非空 `encode`、主题 adapter 与真实渲染通过，不使用本地图表类型白名单；
- Atlas 只在实际使用 `provider=atlas` 时加载，并校验精确组件名；
- 原生 HTML、SVG、Typography、Table、Image 都可独立通过，不强制 Atlas 或 ECharts；

`render-plan` 执行上述结构、引用、主题和容量检查，但不要求 HTML 已存在；`render` 在此基础上继续校验 `index.html`。

## 5. Coverage 门禁

从 `content.json` 正向追踪：

`must item / atom → coverage_decision → deck page → semantic block → render slot → HTML data-content-ref`

任何一环缺失都失败。静态覆盖校验会核对带 `data-content-ref` 的 HTML 源码中是否包含 must 原子值及单位；动态 Canvas/SVG 图表的真实可见值由浏览器和人工检查负责。对 inferred / placeholder 输出显式清单，禁止静默混入事实。

## 6. HTML 与浏览器门禁

v2 single-HTML 只解析一次根级 `index.html`，按 `<section class="slide" data-page-id>` 建立页面索引。页面必须与 Render Plan 一一对应，page ID 和源码 ID 不得重复，组件只能归属当前 slide。每页必须有 title、summary、section id/title 与 emphasis 派生元数据，并与权威 JSON 一致。每个组件包装节点必须有 block、provider、component、content-ref 四个属性；语义焦点载体还必须用 `data-emphasis-role` 精确覆盖 Render Plan 的成员角色。

组件声明还必须与真实 DOM 一致：`svg` 包装节点必须实际包含 `<svg>`，`image` 包含 `<img>` / `<picture>`，`table` 包含 `<table>`；手写 Canvas 属于 `native-html`，不得冒充 ECharts。ECharts 页必须声明 `data-render-pending="true"` 并通过 `WisePPT.createEChart()` 注册异步任务。

页面只有在字体、图片和异步图表全部完成后才能设置：

```js
WisePPT.markSlideReady(slide);
```

根节点只有在所有 slide ready 且没有错误时才写 `data-deck-ready="true"`。`check-deck.sh --mode normal|accent` 等待该标记并检查实时画册、Canvas 克隆、深链、翻页与 ESC；accent 模式还必须激活语义焦点组。`export-pdf.sh` 使用 `?print=1` 直接打印 HTML。两者都不得产生 PNG。

真实浏览器复核至少覆盖：

- 1920×1080 无横纵溢出；
- 最小字号、对比度、安全区和文本截断；
- breathing / balanced / dense 的实际信息负担；
- 图表轴、图例、单位、排序与源数据一致；
- 主视觉唯一，支持件没有抢夺焦点；
- 图片、字体、外部依赖没有空白或闪退。

## 7. Gallery 与主题隔离门禁

- registry 的默认主题存在；
- 每个 layout ID 唯一，display code 只用于展示；
- manifest 的 general / domain examples 数量与文件一一对应；
- 画册目录由 manifest 生成，禁止维护第二份手写数组；
- core schema 与文档不含任何具体主题 token、layout ID 或资产路径；
- 用最小测试主题运行 schema、catalog 与 render 校验，证明 core 不依赖默认主题。
- Gallery 查询结果为空不是失败；Custom 是正常主路径之一，普通生成任务不得把 Custom 写回 manifest 或新增 Gallery 样张。

## 8. Core 示例的边界

`core/examples/` 是主题中立的契约示例：三份 JSON 应分别通过 schema，`content.json` 与 `deck-plan.json` 还应通过来源、引用、Ghost Deck、must 覆盖和 semantic block 校验。示例 `render-plan.json` 使用虚拟主题名称，只证明通用 render contract，不承诺直接通过需要已注册主题、layout manifest 与真实 HTML 的 `render`、`coverage` 或 `all`。完整链路由测试目录中的隔离最小主题与页面 fixture 验证。
