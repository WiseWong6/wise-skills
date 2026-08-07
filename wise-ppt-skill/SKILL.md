---
name: wise-ppt-skill
description: 纸墨线稿风网页 PPT 技能。把已有内容（html/ppt/pptx/pdf/图片）或纯文稿（链接/md/文章）重排为 1920×1080 精细线稿分镜页：单色纸墨底、四族开源字体、精密细线图版、自由程序化 SVG 图形化表达。分页骨架=封面→Context→内容循环→极简 Outro。每页一个 HTML 文件，产出单页双模式 index.html（画板缩略图总览 ↔ 全屏放映一键切换，点缩略图进全屏，ESC/右下角按钮回画板；全屏方向键/滑动翻页并预加载下一页，?ppt 显示页码署名），支持整 deck 导出 16:9 PDF 与逐页 PNG。可按需引入 FontAwesome 图标与 ECharts（强制纸墨化改造）。当用户要做网页 PPT、内容排版优化、把文章/旧 PPT 重做成统一风格的 slides 时使用。
---

# 纸墨线稿 PPT（wise-ppt-skill）

把内容变成**纸墨线稿风**的网页 PPT：冷调纸底 + 单色墨线 + 精密细线图版，像一本被测量过的工程档案。

视觉基准样本（20 页成品，一切规约的来源）：`trace/video/frames/shot-01..20.html`（项目内）。
设计标准全文：`references/design-tokens.md` —— **动手前必读**。

## 这个 Skill 做什么

- 输入两类：
  - **A · 已有内容优化排版**：html / ppt / pptx / pdf / 图片 → 提取内容 → 重排为线稿分镜页
  - **B · 只有文稿**：链接 / md / 文章 → 提炼叙事 → 设计分镜 → 逐页生成
- 产出单页双模式 `index.html`（同一套分镜页，一个壳内切两态）：
  - **画板态**：缩略图总览网格（缩略图为 PNG，零 iframe 开销），点任意镜头进入全屏
  - **全屏态**：全视口放映，←/→/↑/↓/空格/滑动翻页并预加载下一页，ESC 或右下角按钮回画板，每页以 `?ppt` 打开（显示左下页码+署名）

## 硬规则（违反任何一条都会垮）

> 本节是**速查索引**：每条只写"不可破的红线 + 指向权威章节"。所有具体数值（色值/字号/线宽/坐标/阈值/留白比例）的**唯一权威源**是 `references/design-tokens.md`，本节不抄数值，避免双写漂移。判定合格时以 design-tokens 对应章节为准。

1. **单色**：全 deck 只有墨色及其透明度阶梯 + 纸底，无彩色、无渐变；强调靠线宽/字重/字族/虚实。色板与填充禁令见 §一。
2. **图形化优先 + 原语驱动**：排版决策由 `layout-primitives.md` 的原语驱动（识别内容关系形状 → 选原语组合），不由版式/组件驱动。版式画册和组件库是参考样本，不是必须选的表。主体图形优先自由绘制程序化 SVG；禁止"框+字+箭头"的同构矩形阵列充当图形。语义图形语言见 §3.6。
3. **绝对主角 + 激进留白**：一页一个视觉事件，主角占比与留白比例见 §4.4；封面/Outro/金句页留白从严。禁止三段式幻灯片、禁止双图形抢视线。
4. **可用空间双向居中**：内容主体在"剔除固定件后的可用矩形"内水平+垂直双向居中。可用矩形定义、容差阈值、`getBBox()` 判定法见 §4.4。
5. **对齐纪律**：结构同类元素共线（信息柱左齐 / 图表轴基线齐 / 附属标注锚对象），孤立主图元视觉配平，位移按目的落网格或算差值。三律全文见 §4.8。
6. **Font Mixing**：衬线气质族（标题/金句/大字）× 无衬线族（正文/数据/UI/标签）不串岗；手写批注限量。四族分工、字号阶梯、字重纪律见 §二。
7. **视觉平衡 65/35**：内容 ≈65% + 视觉 ≈35%；留白即构图，不把留白当"没排满"去填。见 §4.4。
8. **间距、阴影与边框**：间距落 4pt 网格；实心组件两档阴影、同层级不叠影；UI 边框一律 1px 靠颜色阶梯分层，SVG 图形轮廓保留多档线宽。档位表与规约见 §4.7、§3.1。
9. **固定件三件套**：左上 doc 角注、底部居中 caption、左下 folio（仅 `?ppt`）。位置/字号/格式见 §4.2。
10. **数据自编**：UI mock、示例数据的名称与数值全部虚构，不搬用户真实业务数据。（本条无 design-tokens 对应，SKILL 独有）
11. **开放依赖（按需、纸墨化）**：FontAwesome 6（图标墨色无彩无动效）、ECharts 5（复杂数据图表，强制去色改造）。引入规约与改造法见 §六、`references/components.md`。

## 字体就绪（动手前必做一次）

skill 依赖 5 个本地开源字体（共约 79MB），字体文件**不进 git**（体积过大）。任何人拿到 skill（clone / 解压 / 拷贝）后，**第一次动手前必须先跑一次检测脚本**，确保字体就绪：

```bash
bash <SKILL_ROOT>/assets/fonts/download-fonts.sh
```

脚本会逐个检测：已存在且非空的字体跳过，缺失的才从官方源（adobe-fonts / google/fonts / lxgw）自动下载。幂等，可反复执行。详见 `assets/fonts/README.md`。

- 字体命名统一为官方 **`CN`**（思源官方仓库 SubsetOTF/CN/ 提供，与早期 `SC` 字形一致），`shared.css` 的 `@font-face` 同步引用 `CN` 名。
- 若某字体下载失败（网络/上游路径变动），脚本会明确报出失败项与 URL，修好后重跑即可。

## 分页骨架（每份 deck 必须贯彻）

1. **Slide 1 · 封面（必需）**：极简，超大标题（衬线气质族），大留白（比例见 §4.4），mono 元数据块（AUTHOR / DATE / VERSION / KEYWORDS）。版式见 layouts C0。
2. **Slide 2 · Context**：目录或背景（可用 Grid-3 或 L-Type 思路，落到 layouts 版式）。
3. **Slide 3 ~ N-1 · 内容循环**：依据内容在 layouts 版式间切换；**节奏策略**：整 deck 全部纸底（禁止整页深色底），每 3–4 张信息硬页插 1 张纸底呼吸页（章节隔页/金句页/粒子海报页，留白从严见 §4.4），保持 `硬-硬-呼吸-硬` 穿插。
4. **Slide N · Outro（必需）**：极简收尾，一句 CTA 或致谢 + mono 署名，留白从严（见 §4.4），无第二信息层（layouts C4）。**不强制举例、不强制粒子大字尾卡**——素描感、简约是目标；粒子尾卡（C3）只是可选形态之一。

## 工作流

### Step 1 · 需求对齐（动手前）

至少确认三件事，缺就问：

1. **输入是什么**：A（已有内容重排）还是 B（文稿创作）？文件/链接在哪？
2. **页数与场景**：演讲时长定页数（15 分钟 ≈ 8–12 页，30 分钟 ≈ 16–20 页）；有没有必须包含/必须回避的内容？
3. **署名**：folio 的 `BY XXX` 写什么（默认 `BY WISEWONG`）。

### Step 2 · 提取内容（输入 A）或提炼叙事（输入 B）

- **A**：pptx/pdf 先转文本或逐页读图（可用 ReadMediaFile 读图片/pdf 页）；html 直接读源码。产出"每页讲什么"的清单。
- **B**：读文稿，按叙事弧搭骨架：钩子 → 定调 → 主体 → 转折 → 收束。产出分镜表。

**拆解与容量护栏（防超载）**：

- **一页一核心论点**：每张内容页只推进 1 个新结论；结构 = 结论（标题/caption）+ 支撑（图形主体）+ 证据（标注/数据）。
- **不足则合并**：信息撑不起一页时与相邻主题合并（仍保持主次）。
- **超载才拆分**：内容拥挤/溢出/难读时才拆页，不为"看起来更满"堆块。
- **辅助元素 ≤25%**：辅形态（注释卡/小结/第二图形）视觉面积不超过 25%，且形式必须与主形态不同；需要第 3 种形态才放得下 = 超载，必须拆页。

**分镜表**（写到回复里给用户确认，或存为 deck 目录的 `storyboard.md`）：

```
页码 | 版式(layouts.md 编号) | 一句话内容 | 主角图形 | caption 结论句
01   | A1 标本卡            | ...       | ...     | ...
```

### Step 3 · 搭 deck 骨架

```bash
DECK=<目标目录>   # 例如 项目/xxx/ppt
mkdir -p "$DECK/frames"
cp <SKILL_ROOT>/assets/app-template.html  "$DECK/index.html"          # 单页双模式（画板 ↔ 全屏）
cp <SKILL_ROOT>/assets/shot-template.html "$DECK/frames/shot-01.html"  # 每页一份
```

- 模板内引用的 `../assets/shared.css`、`../assets/particles.js` 和字体：把 `<SKILL_ROOT>/assets/` 整个软链或拷贝到 `$DECK/assets`（推荐软链，规约更新全 deck 受益）：
  ```bash
  ln -s <SKILL_ROOT>/assets "$DECK/assets"
  ```
- 改 `index.html` 顶部配置区的 `CONFIG` / `ACTS` / `SHOTS`（**单文件单份配置**，画板与全屏共用，无需像旧 board+deck 双文件那样手工同步两份）。
- 画板缩略图引用 `frames/thumb-NN.png`，这些 PNG 由 Step 5 的 `shot-screenshot.sh thumb` 模式生成 —— **不要手画、不要手截图，必须跑脚本**。

### Step 4 · 逐页生成

1. **先识别内容的关系形状**（对立？序列？嵌套？辐射？收敛？）→ 按 `references/layout-primitives.md` 的**决策方法论**（Step A-D：提炼论点 → 拆信息单元 → 定主原语 → 叠辅助原语）选 1 个主原语 + 1-2 个辅助原语。常见汇报场景可直接套用文档里的"场景配方"（述职/发布/数据/架构/流程/漏斗/证据）；遇到歧义查"歧义判例"。
2. **参考版式成品**：查 `references/layouts.md` / `gallery/` 找用同样原语组合的版式样本，借鉴坐标和图元画法。**版式是参考不是约束**——如果内容需要原语的新组合或超出 59 版式覆盖，有权发明新版式（只要守 design-tokens 空间纪律）。
3. 主体图形**优先自由绘制程序化 SVG**（细线可控、构造线保留）；复杂形状（真实地图、复杂数据图等自绘成本过高的）可从 html-ppt-components 导出组件做"改造五步"纸墨化——组件库是素材来源，不是降级兜底。
4. 每页都是 `shot-template.html` 的实例：改角注、folio、FIG 图题、主体图形、caption。
5. 图标用 FontAwesome（墨色）；复杂数据图表用 ECharts（去色改造）——规约见 `references/components.md`；粒子质感用 `particles.js`（仅粒子海报页/崩解语义）。

### Step 5 · 机检 + 截图复核 + 缩略图生成（三道闸门都不可省）

```bash
<SKILL_ROOT>/scripts/shot-lint.py "$DECK"                              # 闸门一：机检 P0（彩色/粗线/字体串岗/三件套/同构 rect）
<SKILL_ROOT>/scripts/shot-screenshot.sh "$DECK" /tmp/review            # 闸门二：普通模式截图复核
<SKILL_ROOT>/scripts/shot-screenshot.sh "$DECK" /tmp/review-ppt "?ppt" # 验证页脚显示
<SKILL_ROOT>/scripts/shot-screenshot.sh "$DECK" "" "" thumb            # 闸门三：生成画板缩略图 frames/thumb-NN.png（640×360）
```

- 机检有 FAIL 先修再截图。
- **缩略图闸门不可省**：画板态 `<img>` 直接引用 `frames/thumb-NN.png`，缺图 = 画板破图。改了任何 `shot-NN.html` 后必须重跑 `thumb` 模式（脚本幂等，重跑只覆盖同名文件）。
- 机检全过 ≠ 目检通过（循环变量画的图形、构图平衡、美感机检看不到）——仍须逐张 ReadMediaFile 目检，对照 `references/checklist.md`（目检顺序：远观主角与视觉重心 → 中距层级 → 近看线宽字距 → 和样本页并排对比）。
- **居中复核（硬规则 4，每页必做）**：目检时必须额外确认内容主体在可用空间内水平+垂直双向居中。对含复杂绝对定位坐标的版式（矩阵、多区块构图），用浏览器 `getBBox()` 量内容包围盒，容差与判定法见 design-tokens §4.4（以该节为准）。

### Step 6 · 交付与迭代

- 交付路径：`$DECK/index.html`（单页双模式：画板 ↔ 全屏）、`$DECK/frames/shot-NN.html`（单页原尺寸）；`$DECK/frames/thumb-NN.png` 为画板缩略图（由脚本生成，非手工产物）。
- **导出**：`scripts/export-pdf.sh "$DECK"` 整 deck 导出 16:9 PDF（每页一张）；逐页 PNG 用 `scripts/shot-screenshot.sh`。
- 迭代时改对应单页 `shot-NN.html`，改完**必须两件事**：① 重截该页复核 ② 重跑 `thumb` 模式刷新该页缩略图：
  ```bash
  <SKILL_ROOT>/scripts/shot-screenshot.sh "$DECK" /tmp/review            # ① 复核截图
  <SKILL_ROOT>/scripts/shot-screenshot.sh "$DECK" "" "" thumb            # ② 刷新缩略图（幂等，整体重跑即可）
  ```

## 资源文件导览

```
wise-ppt-skill/
├── SKILL.md                  ← 本文件
├── assets/
│   ├── shared.css            ← 设计 token + 舞台/三件套/纸纹样式（每页必链）
│   ├── particles.js          ← 粒子工具库 + stageFit()（识别 ?ppt / ?cool / ?mono）
│   ├── shot-template.html    ← 单页模板（stage + 三件套 + FIG 骨架）
│   ├── app-template.html     ← ★ 单页双模式模板（画板 PNG 缩略图 ↔ 全屏放映，点缩略图进全屏，ESC/按钮回画板，预加载下一页）—— 新 deck 必用
│   ├── board-template.html   ← [已废弃] 旧画板模板（仅向后兼容，新 deck 用 app-template）
│   ├── deck-template.html    ← [已废弃] 旧全屏模板（仅向后兼容，新 deck 用 app-template）
│   └── fonts/                ← 5 个开源字体（不进 git）+ download-fonts.sh（首次使用自动下载）+ README（来源/版权/CN 命名说明）
├── references/
│   ├── design-tokens.md      ← ★ 设计标准：背景色/字体字重/线宽/留白/质感/外部依赖（动手前必读）
│   ├── layout-primitives.md  ← ★ 排版原语：12 个可组合的空间结构原语 + 内容关系形状映射（排版决策起点）
│   ├── layouts.md            ← 版式目录 + MECE 内容形状选用速查（样张见 gallery/，原语实例库）
│   ├── components.md         ← 自由 SVG 优先 + ECharts/FontAwesome 规约 + atlas 组件改造五步
│   └── checklist.md          ← P0/P1/P2 自检清单 + 目检顺序
├── gallery/                  ← 版式画册 · 通用主题（运营/品牌/汇报等）
│   ├── index.html            ← 画册浏览壳（LAYOUTS 数组即目录，按 15 个结构族分组；族序 = 字母序 A→O，每族一个字母前缀）
│   └── frames/               ← 每种版式一页样张（数据全部自编）
├── gallery-ai/               ← 版式画册 · AI 主题（Agent/RAG/评测/Infra…，与 gallery/ 同 59 版式、内容主题不同）
│   ├── index.html            ← AI 画册浏览壳（与 gallery/ 同分类，署名 BY @歪斯Wise）
│   └── frames/               ← 每种版式一页样张（AI 场景）
│   ↑ 两套画册共用同一套 15 结构族分类（A 证据 / B 时序 / C 数据 / D 骨架 / E 对比 / F 拆解 / G 放射 / H 嵌套 / I 流程 / J 循环 / K 矩阵 / L 映射 / M 情绪 / N 合并 / O 漏斗），每族恰好一个字母前缀，分类反映版式结构、与内容主题无关
├── scripts/
│   ├── shot-screenshot.sh    ← headless Chrome 逐页截图（PNG）；第 4 参数 thumb 生成画板缩略图 frames/thumb-NN.png（640×360）
│   ├── shot-lint.py          ← 机检闸门：彩色/深色底/粗线/字体串岗/三件套/同构 rect（先于截图复核运行）
│   └── export-pdf.sh         ← 整 deck 导出 16:9 PDF（Chrome headless 打印）
```

**加载顺序建议**：
1. 读完本文件 → 2. `references/design-tokens.md` 全文 → 3. `references/layout-primitives.md`（学排版语法，理解内容关系形状怎么映射到空间结构）→ 4. 选/参考版式查 `references/layouts.md` + `gallery/` → 5. 需要组件查 `references/components.md` → 6. 交付前 `references/checklist.md`。

## 参考样本

《Agent Infra 第一课 · Trace》：`trace/video/`（项目内）——20 页成品分镜 + 画板模式 `index.html` 实例。
新页做完和它并排对比，"像同一支笔画出来的"才算合格。
