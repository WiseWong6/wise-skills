---
name: paper-ink-ppt
description: 纸墨线稿风网页 PPT 技能。把已有内容（html/ppt/pptx/pdf/图片）或纯文稿（链接/md/文章）重排为 1920×1080 精细线稿分镜页：单色纸墨底、四族开源字体、精密细线图版、自由程序化 SVG 图形化表达。分页骨架=封面→Context→内容循环→极简 Outro。每页一个 HTML 文件，产出单页双模式 index.html（画板缩略图总览 ↔ 全屏放映一键切换，点缩略图进全屏，ESC/右下角按钮回画板；全屏方向键/滑动翻页并预加载下一页，?ppt 显示页码署名），支持整 deck 导出 16:9 PDF 与逐页 PNG。可按需引入 FontAwesome 图标与 ECharts（强制纸墨化改造）。当用户要做网页 PPT、内容排版优化、把文章/旧 PPT 重做成统一风格的 slides 时使用。
---

# 纸墨线稿 PPT（paper-ink-ppt）

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

1. **单色**：全 deck 只有墨 `#191917` 及其透明度阶梯，纸底 `#DFE0D9`；无彩色、无渐变、无阴影堆叠。强调靠线宽/字重/字族/虚实。
2. **图形化优先**：可视化是第一表达。**自由绘制程序化 SVG 表达内容 > 套用表达组件**；组件库（html-ppt-components）只是 layouts 没覆盖时的兜底骨架。禁止"框+字+箭头"的同构矩形阵列充当图形。
3. **绝对主角 + 激进留白**：一页一个视觉事件，主角图形占画面 40–70%；封面/Outro/金句页留白必须 >60%。禁止标题+正文+结论条的幻灯片三段式；禁止两个图形抢视线。
4. **Font Mixing（衬线 × 无衬线不串岗）**：标题/金句/大字=衬线气质族（statement=思源宋体 Medium，全 deck ≤3 页；引用/金句=霞鹜文楷大字）；正文/数据/UI/标签=无衬线族（思源黑体 Light=正文、Courier Prime=编号/数字/档案注）；手写批注=文楷（≤3 处）。全部本地开源可商用字体。
5. **视觉平衡 65/35**：内容（文字信息）≈65% + 视觉元素（图形/装饰）≈35%；留白即构图，不把留白当"没排满"去填。
6. **三件套**：左上 doc 角注（mono 两行）、底部居中 caption 一句结论、左下 folio 页码署名（仅 `?ppt` 模式显示）。
7. **线宽档位**：主轮廓 1.2–1.4px @ 墨 80%，双线卡框内圈 0.6px，构造线 0.5–0.7px 虚线；强调线每页至多一处。
8. **数据自编**：UI mock、示例数据的名称与数值全部虚构，不搬用户真实业务数据。
9. **开放依赖（按需、纸墨化）**：可引入 FontAwesome 6（图标强制墨色、无彩色无动效）与 ECharts 5（仅复杂数据图表，必须去色改造为墨色阶梯；权威参考为官网 echarts.apache.org）。模板里放了注释掉的 CDN 链接，用时解开。

## 字体就绪（动手前必做一次）

skill 依赖 5 个本地开源字体（共约 79MB），字体文件**不进 git**（体积过大）。任何人拿到 skill（clone / 解压 / 拷贝）后，**第一次动手前必须先跑一次检测脚本**，确保字体就绪：

```bash
bash <SKILL_ROOT>/assets/fonts/download-fonts.sh
```

脚本会逐个检测：已存在且非空的字体跳过，缺失的才从官方源（adobe-fonts / google/fonts / lxgw）自动下载。幂等，可反复执行。详见 `assets/fonts/README.md`。

- 字体命名统一为官方 **`CN`**（思源官方仓库 SubsetOTF/CN/ 提供，与早期 `SC` 字形一致），`shared.css` 的 `@font-face` 同步引用 `CN` 名。
- 若某字体下载失败（网络/上游路径变动），脚本会明确报出失败项与 URL，修好后重跑即可。

## 分页骨架（每份 deck 必须贯彻）

1. **Slide 1 · 封面（必需）**：极简，超大标题（衬线气质族），大留白（>60%），mono 元数据块（AUTHOR / DATE / VERSION / KEYWORDS）。版式见 layouts C0。
2. **Slide 2 · Context**：目录或背景（可用 Grid-3 或 L-Type 思路，落到 layouts 版式）。
3. **Slide 3 ~ N-1 · 内容循环**：依据内容在 layouts 版式间切换；**节奏策略**：整 deck 全部纸底（禁止整页深色底），每 3–4 张信息硬页插 1 张纸底呼吸页（章节隔页/金句页/粒子海报页，留白 >60%），保持 `硬-硬-呼吸-硬` 穿插。
4. **Slide N · Outro（必需）**：极简收尾，一句 CTA 或致谢 + mono 署名，留白 >60%，无第二信息层（layouts C4）。**不强制举例、不强制粒子大字尾卡**——素描感、简约是目标；粒子尾卡（C3）只是可选形态之一。

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

1. 按分镜表给每页选版式 → 打开 `references/layouts.md` 找对应版式的结构与坐标基准。
2. 主体图形**优先自由绘制程序化 SVG**（细线可控、构造线保留）；layouts 没覆盖且自绘成本过高的形状 → 按 `references/components.md` 从 html-ppt-components 导出组件做"改造五步"兜底。
3. 每页都是 `shot-template.html` 的实例：改角注、folio、FIG 图题、主体图形、caption。
4. 图标用 FontAwesome（墨色）；复杂数据图表用 ECharts（去色改造）——规约见 `references/components.md`；粒子质感用 `particles.js`（仅粒子海报页/崩解语义）。

### Step 5 · 机检 + 截图复核 + 缩略图生成（三道闸门都不可省）

```bash
<SKILL_ROOT>/scripts/shot-lint.py "$DECK"                              # 闸门一：机检 P0（彩色/粗线/字体串岗/三件套/同构 rect）
<SKILL_ROOT>/scripts/shot-screenshot.sh "$DECK" /tmp/review            # 闸门二：普通模式截图复核
<SKILL_ROOT>/scripts/shot-screenshot.sh "$DECK" /tmp/review-ppt "?ppt" # 验证页脚显示
<SKILL_ROOT>/scripts/shot-screenshot.sh "$DECK" "" "" thumb            # 闸门三：生成画板缩略图 frames/thumb-NN.png（640×360）
```

- 机检有 FAIL 先修再截图。
- **缩略图闸门不可省**：画板态 `<img>` 直接引用 `frames/thumb-NN.png`，缺图 = 画板破图。改了任何 `shot-NN.html` 后必须重跑 `thumb` 模式（脚本幂等，重跑只覆盖同名文件）。
- 机检全过 ≠ 目检通过（循环变量画的图形、构图平衡、美感机检看不到）——仍须逐张 ReadMediaFile 目检，对照 `references/checklist.md`（目检顺序：远观主角与重心 → 中距层级 → 近看线宽字距 → 和样本页并排对比）。

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
paper-ink-ppt/
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
│   ├── layouts.md            ← 版式目录 + MECE 内容形状选用速查（样张见 gallery/）
│   ├── components.md         ← 自由 SVG 优先 + ECharts/FontAwesome 规约 + atlas 组件改造五步
│   └── checklist.md          ← P0/P1/P2 自检清单 + 目检顺序
├── gallery/
│   ├── index.html            ← 版式画册（左目录 + 等比预览，←/→ 键与箭头切换）
│   └── frames/               ← 每种版式一页样张（数据全部自编）
├── scripts/
│   ├── shot-screenshot.sh    ← headless Chrome 逐页截图（PNG）；第 4 参数 thumb 生成画板缩略图 frames/thumb-NN.png（640×360）
│   ├── shot-lint.py          ← 机检闸门：彩色/深色底/粗线/字体串岗/三件套/同构 rect（先于截图复核运行）
│   └── export-pdf.sh         ← 整 deck 导出 16:9 PDF（Chrome headless 打印）
```

**加载顺序建议**：
1. 读完本文件 → 2. `references/design-tokens.md` 全文 → 3. 选版式查 `references/layouts.md` → 4. 需要组件查 `references/components.md` → 5. 交付前 `references/checklist.md`。

## 参考样本

《Agent Infra 第一课 · Trace》：`trace/video/`（项目内）——20 页成品分镜 + 画板模式 `index.html` 实例。
新页做完和它并排对比，"像同一支笔画出来的"才算合格。
