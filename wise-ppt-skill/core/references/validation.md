# 验证门禁：从 JSON 到真实页面

验证顺序固定为“结构 → 引用 → 容量 → DOM → 视觉”。后一个门禁不能替代前一个；构建成功也不能替代真实浏览器复核。

## 1. 命令入口

```bash
python3 scripts/validate.py content  <deck-or-content.json>
python3 scripts/validate.py plan     <deck-or-deck-plan.json>
python3 scripts/validate.py render   <deck-or-render-plan.json>
python3 scripts/validate.py coverage <deck-dir>
python3 scripts/validate.py gallery  <skill-root-or-theme-dir>
python3 scripts/validate.py all      <deck-dir>
```

命令退出码必须可靠：任一 P0 失败返回非零；不存在的文件、未知主题或无法读取的 manifest 都不得报告成功。

## 2. Content 门禁

- schema 合法；
- source、item、atom ID 全局唯一；
- 每个 `source_ref` 存在；
- 每个 relation 的 `target_ref` 存在；出现 `contradicts` 时必须进入 confirmation trigger；
- sourced 至少一个来源；
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
- takeaway / caption 只陈述页面内容，能由本页证据推出；不得混入版式选择条件、画册复用说明或制作方法；
- 页角 `.doc.tl` 只标当前主题/章节，不得把 gallery、layout、mock 或组件名称当作 PPT 文案；
- 每页 `spatial_primitive` 属于十二个通用原语；
- must 内容有 include 决策和页面承载；
- `needs_confirmation` 时停止进入 render。

## 4. Render 门禁

- schema 合法，render page 与 deck page 一一对应；
- `theme_id` 存在于主题 registry；未知主题立即失败；
- layout ID 存在于该主题 manifest，角色、relation、density、capacity 和 slots 匹配；
- 每页 `core_primitive` 必须等于对应 deck page 的 `spatial_primitive`；
- `theme_primitives` 必须是当前 layout manifest 声明的 1–3 个主题原语；
- block 与 slot 一一映射，恰好一个 primary visual role；
- copy / adapt / compose 有 `reuse_source`，全部模式有具体 rationale；
- ECharts 有 `data_ref` 和非空 `encode`；
- `capacity_status` 只能在 `fit` 时进入最终渲染。

## 5. Coverage 门禁

从 `content.json` 正向追踪：

`must item / atom → coverage_decision → deck page → semantic block → render slot → HTML data-content-ref`

任何一环缺失都失败。对 HTML 中的标题、表格、图表数据和关键文字做值级核对，避免“有引用 ID，但实际没渲染”。对 inferred / placeholder 输出显式清单，禁止静默混入事实。

## 6. HTML 与浏览器门禁

每页 `output_file` 必须存在，并与 render plan 的六个 page data 属性一致；每个组件包装节点必须有 block、provider、component、content-ref 四个属性。

页面只有在字体、图片和异步图表全部完成后才能设置：

```js
document.documentElement.dataset.renderReady = 'true';
```

截图脚本必须等待该标记，超时或浏览器退出异常都应失败，并再次检查输出图片真实存在且非空。

真实浏览器复核至少覆盖：

- 1920×1080 无横纵溢出；
- 最小字号、对比度、安全区和文本截断；
- breathing / balanced / dense 的实际信息负担；
- 图表轴、图例、单位、排序与源数据一致；
- 主视觉唯一，支持件没有抢夺焦点；
- 主体包络位于主题定义的可用内容区；中心型原语检查水平与垂直中心；被设计成一个中心型局部单元的图形、标题和标签检查共同轴线，侧注与引线则按结构锚点验收；意图性非对称按结构锚点与视觉重量复核，不能用全页 bbox 强行居中；
- 短标签、等权矩阵和稀疏固定高度单元格默认水平、垂直居中；分析表格的文字按扫读路径左对齐，数字按位数、单位或小数点右对齐；
- 对称结构的左右/上下外缘成镜像，连接线、标注轨和主体仍保持结构关系；
- 二维码、条码等从最终截图解码回权威 payload，不能只验证源码矩阵；
- 图片、字体、外部依赖没有空白或闪退。

`validate.py all` 与主题 `lint.py` 不计算浏览器 bbox，也不解码机器码；使用 `runtime/screenshot.sh <DECK> "" "" audit` 测量 `#body`。audit 缺少主体/框架、枚举或容差非法、主体越出主题安全区时必须失败；只有安全区内的 `structural` / `intentional-asymmetry` 才可报告而不自动判中心。普通截图模式会对 `data-qr-payload` 调用 QR 独立解码器；其他机器码须配置对应解码器。交付记录仍须写明中心型主体的 `dx/dy`、意图性非对称的结构锚点，以及机器码的 expected / decoded payload；不得把静态 lint 通过描述成这些项目已通过。

## 7. Gallery 与主题隔离门禁

- registry 的默认主题存在；
- 每个 layout ID 唯一，display code 只用于展示；
- manifest 的 general / domain examples 数量与文件一一对应；
- 画册目录由 manifest 生成，禁止维护第二份手写数组；
- 画册外层用途文案与 iframe 内页面结论分层：外层不直出机器筛选谓词，页内不讲版式如何制作；
- core schema 与文档不含任何具体主题 token、layout ID 或资产路径；
- 用最小测试主题运行 schema、catalog 与 render 校验，证明 core 不依赖默认主题。

## 8. Core 示例的边界

`core/examples/` 是主题中立的契约示例：三份 JSON 应分别通过 schema，`content.json` 与 `deck-plan.json` 还应通过来源、引用、Ghost Deck、must 覆盖和 semantic block 校验。示例 `render-plan.json` 使用虚拟主题名称，只证明通用 render contract，不承诺直接通过需要已注册主题、layout manifest 与真实 HTML 的 `render`、`coverage` 或 `all`。完整链路由测试目录中的隔离最小主题与页面 fixture 验证。
