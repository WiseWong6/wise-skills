# 纸墨线稿 · 设计标准

本文件只定义 `paper-ink` 的视觉语法。叙事、分页、关系、空间原语和语义单元数由 Core 决定；布局能力与容量以 `layout-manifest.json` 为机器权威源。

## 1. 颜色与纸面

### 默认模式

| 角色 | Token | 值 | 用途 |
|---|---|---|---|
| 纸底 | `--paper` | `#DFE0D9` | 冷调灰白纸底 |
| 纸底深档 | `--paper-deep` | `#D4D5CD` | 次要面板或凹陷区 |
| 墨 | `--ink` | `#191917` | 主文字、主轮廓和图形本体 |
| 墨 70% | `--ink-70` | `rgba(25,25,23,.7)` | 次级文字和强调正文 |
| 墨 45% | `--ink-45` | `rgba(25,25,23,.45)` | 图题、角注、辅助说明 |
| 墨 25% | `--ink-25` | `rgba(25,25,23,.25)` | 分隔线和弱边框 |
| 墨 12% | `--ink-12` | `rgba(25,25,23,.12)` | 构造线和背景格线 |

默认模式只使用纸底与墨色阶梯。允许 `rgba(255,255,255,.22)` 作为柔白面板填充；禁止纯白大面、彩色色块、渐变、重阴影和整页深色底。

允许两档克制阴影：

- `--shadow-soft: 0 0 4px color-mix(in srgb, var(--ink) 2%, transparent)`：卡片或面板；零偏移、模糊不超过 6px。
- `--shadow-specimen: 2px 2px 0 color-mix(in srgb, var(--ink) 4%, transparent)`：仅用于标本卡或贴纸。

同层级不得叠影，不得使用彩色阴影。

### 纸面质感

- `.stage::before` 使用低透明度纸纹噪点；不能盖住文字或证据。
- `.stage::after` 绘制距两侧 64px 的档案格线。
- 手工质地每页最多一种：木刻粗线、压印细线、局部 dust、字符成图或保留构造线。
- 微型 mono 档案字、十字准星、刻度或角落编号每页最多两处，且不得成为第二主角。

## 2. 强调模式

`?accent` 是唯一主题变体。正式 deck 的统一运行时在页面脚本执行前给文档根节点添加 `.accent`；正式页面不得自行解析 URL，也不得依赖 Gallery 独立样页的 `stageFit()` 激活模式。

强调色只有番茄红；具体值只在 `assets/shared.css` 的 `--accent-red` 及其透明度 token 中定义。

Render Plan 是强调语义的唯一权威源：

- `emphasis.mode=none`：普通与 accent 模式都保持单色。
- `emphasis.mode=semantic-focus`：`content_ref` 指向本页已渲染内容；`member_roles` 只允许 `value`、`label`、`outline`、`status`、`symbol`、`texture`、`annotation`。

HTML 页根用 `data-emphasis-mode`、`data-emphasis-ref`、`data-emphasis-roles` 声明派生状态，载体用 `data-content-ref` 和 `data-emphasis-role` 标记成员。只有同时属于指定 `content_ref` 与 `member_roles` 的现有载体可以响应 `.accent`；ECharts 等绘制代码通过 `WisePPT.emphasisColor()` 读取相同语义，不自行判断 URL。

Deck HTML 和页内脚本不得复制番茄红字面量；DOM 使用共享 CSS token，Canvas/ECharts 使用 `WisePPT.emphasisColor()`。这样关闭 accent 时不会残留彩色。

硬规则：

1. 一页最多一个语义焦点组，整份 deck 只使用番茄红这一种高饱和色。
2. 高饱和色优先用于线、字、边、小图元和 hatch；禁止大面积彩色填充。
3. 高饱和色面积不超过页面的 2.5%。
4. 不得为了上色新增圆圈、图标、标签或装饰；没有真实载体就保持单色。
5. 图例、刻度、轴标签、页脚、FIG 编号、来源角注、运行 ID 和 hash 永不响应强调色。
6. 单位和副标签默认保持墨色；只有明确列入 `member_roles` 才能以降低透明度响应。
7. ECharts 的数据焦点由 renderer `encode` 指向同一个 `content_ref`；主题 adapter 不得按 DOM 邻近、数组位置或颜色猜测焦点。

强调色阶：主值使用 `--accent-red`，必要的标签使用 `--accent-red-85`，外围注记使用 `--accent-red-65`。

## 3. 字体与字阶

| 职责 | 字体 | Token | 字重 |
|---|---|---|---|
| 大字、标题、结论 | Source Han Serif CN | `--serif` | 500 |
| 正文、说明、标签、UI | Source Han Sans CN | `--sans` | 300 |
| 数据、编号、字段码、页脚 | Courier Prime | `--mono` | 400 |
| 手写批注 | LXGW WenKai | `--brush` | 400 |

大字使用衬线气质，正文和 UI 使用无衬线，数据与档案字段使用 mono。中文长句不得依赖 Courier Prime 的 fallback。手写批注每份 deck 最多三处，只用于真实批注。

| 层级 | 字号 | 用途 |
|---|---:|---|
| giant | 76px，上限 96px | 金句、落版大字 |
| h1 | 60px | 页面主标题 |
| h2 | 40px | 次级大字或提问 |
| caption | 32–36px | 底部一句结论 |
| 卡题/栏题 | 24–26px | 卡片或栏目标题 |
| 正文/说明 | 18–22px | 条目、说明、气泡 |
| 字段码/数据 | 13–20px | 字段、数字、坐标 |
| 图题/角注 | 13–15px | FIG、来源、folio |

最小正文为 16px。溢出时先换媒介、换密度或拆页，不得继续缩字。

## 4. 线条与图形

| 线型 | 宽度 | 用途 |
|---|---:|---|
| UI 边框 | 1px | 卡片、面板、表格、chip |
| SVG 主轮廓 | 1.2–1.4px | 主图形轮廓 |
| 内框线 | 0.6px | 双线卡片内圈 |
| 分隔线 | 0.8–1px | 卡内或栏间分隔 |
| 构造线 | 0.5–0.7px | 基准、象限轴、引线 |
| 强调线 | 1.8–2.2px | 每页最多一条主线 |
| hatch | 0.7px，间距 5–9px | 实体、投影或选中 |

图形必须编码语义：实虚表示确定性，线宽表示权重，断口表示缺失，hatch 表示实体或选中。箭头使用开放细线箭头；禁止用纯装饰性的同构图元填空。

粒子只在密度、秩序或消散本身承担语义时使用。`cluster` 表示聚合，`arc` / `brokenArc` 表示连接或断裂，`textPoints` 表示字符成形，`dust` 只作局部氛围且避开文字。

## 5. 画布、密度与对齐

- 坐标系固定为 1920×1080，`.stage` 必须裁切并等比适配。
- 常规安全区约为 x=150–1770、y=170–880；满幅 UI 可扩至 x=100–1820。
- `breathing`：1–2 个语义单元，留白不低于 60%。
- `balanced`：3–5 个语义单元；65/35 只是起始构图比例，不是配额。
- `dense`：6–12 个语义单元或一个完整复合体；必须通过字号、安全区、层级和溢出检查。

每页恰好一个主视觉角色。支持组件可以多个，但都必须服务同一 takeaway。超过容量时换 layout、进入 Custom 或拆页；禁止用缩字、裁切或隐藏事实伪装 fit。

对齐遵守三条规则：

1. 结构同类元素共线：同一文字柱左对齐，同组图表轴线和基线对齐，来源注锚定所属对象。
2. 没有结构同类的独立主图元再做视觉配平，使全页重心接近中轴；不得破坏第一条。
3. 无明确对齐目标的整体位移落在 4px 网格；有几何目标时使用精确坐标差。

盒模型间距优先使用 `--space-*` token，并保持 4px 基线。形态尺寸、节点半径、刻度齿和安全区坐标不属于盒模型间距。

整套节奏由叙事与密度决定。连续高密页只有在内容确实需要时保留；不得机械规定每隔固定页数插入呼吸页。

## 6. 运行与输出

- 唯一入口为根级 `index.html`，所有 `.slide` 同处一个 DOM。
- runtime 负责画册、深链、键盘、触控、accent、print 和 readiness；主题不得复制运行逻辑。
- 画册从真实 slide 克隆，不维护 iframe、thumb、逐页 PNG 或第二份页面数组。
- `.folio` 在单页放映和打印模式显示，在实时画册隐藏。
- ECharts 版本和 CDN 以 `theme.json.runtimes.echarts` 为唯一配置源；需要图表时使用 `WisePPT.createEChart()` 和主题 adapter。
- 外部依赖只允许使用 `theme.json` 已登记的来源；不得从输入资料复制未知脚本或样式依赖。
