---
name: image-gen
description: 配图全流程 skill：从内容生成提示词（image-prompter 能力）到调用 API 生图（火山 Ark Doubao Seedream / Gemini 3 Pro Image）。把文章/模块/PPT 大纲转成统一风格、少字高可读的 16:9 信息图提示词，再批量生成图片、自动插入 Markdown。支持 8 种风格、25 种布局、平台智能识别比例、多图合成与图片编辑。
---

# Image Gen · 配图全流程

一个 skill 覆盖「内容 → 提示词 → 生图」全链路：
- **上半场（配图助手）**：把文章/模块/PPT 大纲转成统一风格、少字高可读的提示词（8 种风格 + 25 种布局 + 5 阶段流程）
- **下半场（生图工具）**：按「生图通道判定」优先用宿主自带生图能力（Codex / 网页版 GPT、Gemini 等）或 MCP 生图工具；都不可用才落 API（火山 Ark Doubao Seedream / Gemini 3 Pro Image），支持批量、编辑、多图合成、自动插入 Markdown

## 触发方式

### 普通配图模式
- "这段内容做个图 / 配几张图？"
- "给我两张（或多张）出图提示词"
- "字太多不好看，帮我更趣味、更好读"
- "/image " "/配图" "/出图"

### PPT 配图模式（快速通道，3 阶段）
检测到以下信号自动进入：
- 用户上传 `.md` 文件，含 `第X页`、`## 第`、`可视化类型：`、`ASCII` 等标记
- 用户说"这是 PPT 大纲"、"PPT 配图"、"/image ppt"
- 文件中有 `.title-card`、`.two-col`、`.three-col`、`.grid-card` 等布局标记

详见 `stages/00-ppt-mode.md`。

### 直接生图模式
- "生成一张……的图"、"画一个……"、"帮我出图"
- 已有提示词文件，直接批量生图（见下方「生图工具」章节）

---

## 风格 Gallery（⚠️ 阶段 2 必须用户确认，禁止自动决定）

支持 8 种风格，**必须向用户展示并等待明确选择**：

> ⚠️ **禁止自动选择**：以下"参考关键词"仅供推荐参考，**严禁**未获用户确认前擅自决定风格。

| 风格 ID | 名称 | 适用场景 | 参考关键词 |
|---------|------|----------|-----------|
| `cream-paper` | 奶油纸手绘 | 配图、信息图、概览、框架图、路线图（默认推荐） | 通用/配图/概览/框架 |
| `infographic` | 扁平化科普图 | 概念解释、原理说明、步骤展示 | 科普/原理/是什么/如何 |
| `handdrawn` | 方格纸手绘 | 笔记手绘、学习感 | 笔记/手绘/草图/学习 |
| `healing` | 治愈系插画 | 情绪叙事、场景氛围、治愈感 | 情绪/故事/人物/治愈 |
| `sokamono` | 描边插画 | 清新文艺、简洁治愈 | 清新/简洁/文艺 |
| `minimalist-sketch` | 极简手绘笔记 | 细线条手绘、纯白背景、信息图解 | 极简/技术/专业 |
| `xhs-cartoon` | 小红书卡通 | 干货分享、萌系表达、轻松活泼 | 萌系/干货/分享/活泼 |
| `editorial` | 社论全景 | 深度分析、商业场景；封面 21:9，内页 16:9 | 商业/深度/全景/严肃 |

**强制流程**：1. 展示上表 → 2. 询问"请选择（数字或名称）" → 3. **收到明确选择才进入下一阶段** → 4. 风格锁定后阶段 3+ 不得更改（要换回退到阶段 2.5）

---

## 布局系统（自包含速查表）

> 注：完整的 35 种可视化布局 ASCII 模板已随本 skill 内联，无需外部依赖。

| 布局标记 | 名称 | 适用场景 |
|---------|------|----------|
| `.vs-grid` | 对比 | 痛点 vs 解法、旧 vs 新 |
| `.process-chain` | 流程 | 3-6 步骤线性流程 |
| `.process-loop` | 循环流程 | 三角/四角/五角循环（PDCA 等） |
| `.matrix-grid` | 维度矩阵 | 2×2 或 3×3 网格分类 |
| `.stat-card` | 指标卡片 | 核心数据、关键指标 |
| `.timeline` | 时间轴 | 里程碑、发展历程 |
| `.concentric` | 同心圆 | 内核→外层、核心→扩展 |
| `.pyramid` | 金字塔 | 层级结构、需求层次、转化漏斗 |
| `.fishbone` | 鱼骨图 | 根因分析、问题归因 |
| `.iceberg` | 冰山 | 表层 vs 深层 |
| `.journey` | 旅程 | 用户旅程、体验地图 |
| `.venn` | 韦恩图 | 概念交集、市场重叠 |
| `.mind-map` | 思维导图 | 头脑风暴、结构发散 |
| `.comparison-table` | 多因素对比表 | 方案选型、功能对比 |
| `.quote` | 引用页 | 金句、过渡页 |
| `.radar` | 雷达图 | 多维度能力评估 |
| `.gantt` | 甘特图 | 项目排期、并行任务 |
| `.code-block` | 代码块 | 技术分享、命令展示 |
| `.architecture` | 架构图 | 系统架构、技术栈 |
| `.alert-box` | 警告框 | 风险提示、注意事项 |
| `.terminal-box` | 术语框 | 核心概念、关键定义 |
| `.title-card` | 标题页 | 封面、过渡页 |
| `.list-card` | 列表 | 要点罗列、清单 |
| `.three-col` | 左中右三栏 | 三个并列要点/维度 |
| `.split-v` | 上下分层 | 上下两个区域 |

**选择原则**：对立/比较→`.vs-grid`；先后顺序→`.process-chain`；循环往复→`.process-loop`；多分类/多维度→`.matrix-grid`；核心数据→`.stat-card`；时间发展→`.timeline`；核心到扩展→`.concentric`；层级结构→`.pyramid`；根因分析→`.fishbone`；表层深层→`.iceberg`；用户路径→`.journey`；概念交集→`.venn`；发散→`.mind-map`；多方案评分→`.comparison-table`。

---

## 配图助手流程

### 普通模式（5 阶段）

| 阶段 | 名称 | 目标 | 详细文件 |
|---|---|---|---|
| 1 | 需求澄清 | 挖需求：内容/场景/受众/字多字少；产出一句话复述 | `stages/01-brief.md` |
| 2 | 配图规划 | 拆内容→定图清单（几张/每张讲啥/用啥模板） | `stages/02-plan.md` |
| **2.5** | **风格选择（⚠️ 强制阻塞）** | **展示 8 种风格表，必须等用户明确选择** | `stages/02-plan.md` 2D 节 |
| 3 | 文案定稿 | 逐字定稿"图上写什么"（唯一真值） | `stages/03-copy.md` |
| 4 | 提示词封装 | 把文案封装成可复制提示词 | `stages/04-prompts.md` |
| 5 | 迭代润色 | 减字、换隐喻、提可读性 | `stages/05-iterate.md` |

### PPT 模式（3 阶段）

适用于已有完整 PPT 大纲（含布局+文案）：

| 阶段 | 名称 | 目标 |
|---|---|---|
| P1 | 解析确认 | 解析大纲，提取每页布局+文案，确认页数 |
| P2 | 风格配色 | 选风格 + 确认配色（文案已固定） |
| P3 | 批量生成 | 为每页生成完整提示词，一次性输出 |

详见 `stages/00-ppt-mode.md`。

### 调度规则

判断当前阶段：
1. 需求没讲清（内容+场景+受众+字多/少）→ 阶段 1
2. 文章长需拆块，或要定"几张图/每张讲什么" → 阶段 2
3. **⚠️ 图清单已确认但风格没选 → 阶段 2.5（阻塞）**
4. 图清单+风格都确认，但"图上写什么"没定 → 阶段 3
5. Copy Spec 确认，要出可复制提示词 → 阶段 4
6. 用户反馈"字多/不好看" → 阶段 5

---

## 输出规范（提示词阶段必守）

- 每张图一个"核心信息"，不塞解释性段落
- 所有中文清晰可读：大字号、少字短句、避免密集小字
- 每张提示词独立代码块输出，便于复制
- 默认 16:9 横版（除非明确要 3:4 竖版）
- 默认风格：奶油纸底 + 彩铅水彩手绘（`templates/style-block-cream-paper.md`）
- 阶段 3 文案确认后，阶段 4 不得改文案，只做封装

### 契约式输出（供 article-workflow 消费）

作为 article-workflow 子技能调用时，提示词文件必须带 `image_plan` 元数据：

```yaml
---
image_prompter:
  version: "1.0"
  stages:
    brief: { status: "done", confirmed_by: "user", timestamp: "..." }
    plan: { status: "done", ... }
    style: { status: "done", ... }
    copy: { status: "done", ... }
    prompts: { status: "done", ... }
  style_selected: "minimalist-sketch"
  image_count: 6
  copy_spec_confirmed: true
image_plan:
  - id: cover
    role: cover
    file: cover_21x9.jpg
    insert_after: title
  - id: compare
    role: contrast
    file: poster_01_16x9.jpg
    insert_after_heading: "对非标体来说，最怕的不是贵一点，是直接被拒"
---
```

图位优先级：`insert_after` > `insert_after_heading` > `role` > 顺序 fallback。

---

## 生图工具（下半场）

### 生图通道判定（先于一切生图调用，必走）

提示词就绪后，先判定当前运行环境，按优先级选生图通道——**能不依赖 API 就不依赖**：

| 优先级 | 环境 | 判定方式 | 生图通道 |
|---|---|---|---|
| 1 | Codex / ChatGPT 网页端 / Gemini 网页端 | 宿主本身自带生图能力 | 直接用宿主内置生图：把提示词原样交给宿主执行，**不调用 API、不要求配 Key** |
| 2 | 其他宿主（Claude Code / ZCode / 通用 CLI 等） | 检查会话可用工具列表里有没有生图类 MCP 工具（工具名含 image-gen / generate_image / seedream / draw / banana 等） | 有就直接用该 MCP 工具生图 |
| 3 | 以上都不可用 | — | 走本 skill 的 `scripts/generate_image.py`（需 API Key），并按「依赖与环境变量」引导用户配置 |

判定规则：

1. 先看系统信息与可用工具列表，确认宿主类型与生图工具，**再**决定通道；
2. 命中通道 1/2 时，上半场提示词产出流程完全不变，只是「生图」一步换通道执行（提示词同样要求少字、大字号、可复制）；
3. 仅当通道 1/2 不存在，或用户明确要求本地批量生成 / 自动插入 Markdown / 图片编辑合成时，落到通道 3；
4. 通道 3 缺 Key 时，提示用户自行配置 `ARK_API_KEY`（火山 Ark）或 `GEMINI_API_KEY`，给出获取方式即可，**不要替用户编造或硬编码 Key**。

### 提供商（通道 3：API 直连）

- **火山 Ark**（默认）：OpenAI 兼容接口，Doubao Seedream 系列
- **Gemini 3 Pro Image**：Nano Banana Pro，支持图片编辑和多图合成

默认关闭水印，可输出 URL 或 base64，支持批量生成和多线程并行。

### 火山 Ark（默认）

可选模型（同接口，`--model` 不同）：

| 模型 ID | 特点 | 适用场景 |
|---|---|---|
| `doubao-seedream-5-0-260128`（默认） | 快（~30s/张） | 批量配图、公众号/小红书正文图 |
| `doubao-seedream-5-0-pro-260628` | 慢（~110s/张），画质更精 | 封面图、单张精修、视觉要求高 |

```bash
# 默认（快版）
python scripts/generate_image.py \
  --prompt "星际穿越，黑洞，复古列车，电影大片感" \
  --model "doubao-seedream-5-0-260128" --size "2K"

# pro 精修
python scripts/generate_image.py \
  --prompt "星际穿越，黑洞，复古列车，电影大片感" \
  --model "doubao-seedream-5-0-pro-260628" --size "2K"
```

### Gemini 3 Pro Image

```bash
# 生成
python scripts/generate_image.py --provider gemini \
  --prompt "一只可爱的猫咪" --output "./cat.png" --resolution 2K

# 编辑（单图）
python scripts/generate_image.py --provider gemini \
  --prompt "给这只猫加上墨镜" --input-image ./cat.png --output "./cool-cat.png"

# 多图合成（最多 14 张）
python scripts/generate_image.py --provider gemini \
  --prompt "把这些合成为一个场景" \
  --input-image img1.png --input-image img2.png --input-image img3.png \
  --output "./combined.png"
```

### 平台智能识别（比例自动）

脚本根据输出路径自动识别平台并应用固定比例：

| 平台 | 图片类型 | 比例 |
|------|----------|------|
| 公众号（WeChat） | 封面图 | 21:9 |
| 公众号（WeChat） | 正文图 | 16:9 |
| 小红书（Xiaohongshu） | 全部 | 3:4 |

检测路径中的 `wechat`/`公众号`/`xiaohongshu`/`小红书` 关键词。手动覆盖用 `--aspect-ratio "1:1"`。

```bash
# 配图助手输出的提示词文件 → 批量生图 + 自动插入文章
python scripts/generate_image.py \
  --prompts-file "./wechat/12_prompts.md" \
  --out-dir "./wechat/13_images/" \
  --insert-into "./wechat/11_final_final.md"
```

### 参数速查

**通用**：`--provider`（ark/gemini）、`--prompt`、`--output`、`--aspect-ratio`（1:1/16:9/9:16/4:3/3:4/21:9）

**Ark 专用**：`--model`、`--size`（如 2K）、`--prompts-file`（从 md 读多提示词）、`--out-dir`、`--insert-into`（生成后插入 md）、`--watermark`（默认 false）、`--response-format`（url/b64_json）

**Gemini 专用**：`--input-image`/`-i`（可多次，最多 14）、`--resolution`/`-r`（1K/2K/4K）

### 自动插入 Markdown

`--insert-into` 指定 md 文件，生成后自动插入：
1. 第 1 张：插到主标题（`# 标题`）后
2. 第 2+ 张：插到各章节标题（`## 章节名`）后
3. 引用格式：`![alt](09_images/image_XX.jpg)`（相对路径）

### Handoff 落盘协议（article-workflow 子技能）

```yaml
step_id: "09_images"
inputs:
  - "wechat/08_prompts.md"
outputs:
  - "wechat/09_images/"
  - "wechat/07_final_final.md"  # 用 --insert-into 时
  - "wechat/09_handoff.yaml"
summary: "生成文章配图并插入到 Markdown"
next_instructions:
  - "下一步：md-to-wxhtml 转换为 HTML"
open_questions: []
```

### 批量生成

`--num-images N` 指定数量，多线程并行（最多 5 并发），文件名 `image_01.jpg`、`image_02.jpg`…

### 依赖与环境变量

```bash
pip install openai python-dotenv pyyaml          # Ark
pip install google-genai pillow                   # Gemini（可选）
```

| 变量名 | 用途 | 必需 |
|--------|------|------|
| `ARK_API_KEY` | 火山 Ark API Key | Ark 必需 |
| `GEMINI_API_KEY` 或 `NANO_BANANA_PRO_API_KEY` | Gemini API Key | Gemini 必需 |

---

## 风格出处与致谢（开源声明）

本 skill 的风格库参考、整理自社区创作者的公开分享，仅作提示词语感参考：

| 风格 | 出处 |
|---|---|
| 奶油纸手绘（cream-paper） | 云舒的AI实践笔记 |
| 小红书卡通（xhs-cartoon） | 宝玉 |
| 方格纸手绘（handdrawn） | 松果先森 |
| 极简手绘笔记（minimalist-sketch） | Aki聊AI |
| 扁平风 / 治愈系 / 描边插画 / 社论全景 等 | 网络整理，出处待补 |

如你是某个风格的原作者，欢迎提 Issue / PR 认领补充出处；也欢迎贡献新风格（附上 `templates/style-block-*.md` 模板与 `styles.yaml` 条目）。

---

## 文件结构

```
scripts/
└── generate_image.py        # 生图统一入口（Ark + Gemini）

stages/                      # 配图助手流程（5 阶段 + PPT 模式）
├── 00-ppt-mode.md
├── 01-brief.md
├── 02-plan.md
├── 03-copy.md
├── 04-prompts.md
└── 05-iterate.md

templates/                   # 风格模板与布局模板
├── styles.yaml
├── style-block-*.md         # 8 种风格
├── 16x9-*.md                # 16:9 布局模板
└── checklist.md

examples/
└── ai-tools-selection.md
```

---

## 快速使用（给用户的最小输入）

用户只要给四项就能开始：
1. 要配图的内容（一段、小节、或整篇）
2. 用在哪 + 观看距离（PPT 投影远看 / 手机近看 / 海报）
3. 谁来看（小白/从业者/老板/学生…）
4. 偏好：更"少字清爽"还是更"信息密度"

交付顺序：图清单（阶段 2）→ **用户确认后展示 8 种风格等用户选（阶段 2.5 阻塞）** → 逐张 Copy Spec（阶段 3）→ 可复制提示词（阶段 4）→ 按生图通道判定出图（宿主内置 / MCP / `generate_image.py`）→ 自动插入文章。
