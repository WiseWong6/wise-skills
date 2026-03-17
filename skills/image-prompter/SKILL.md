---
name: image-prompter
description: 配图助手 - 把文章/模块内容转成统一风格、少字高可读的 16:9 信息图提示词；先定"需要几张图+每张讲什么"，再压缩文案与隐喻，最后输出可直接复制的生图提示词并迭代。
---

# 配图助手

## 触发方式

### 普通模式
当用户说类似以下内容时触发：
- "这段内容做个图 / 配几张图？"
- "给我两张（或多张）出图提示词"
- "字太多不好看，帮我更趣味、更好读"
- "把这个流程封装成提示词模板/skills"
- "/image " "/配图" "/出图"

### PPT模式（快速通道）
当检测到以下信号时，自动进入PPT模式（简化流程）：
- 用户上传 `.md` 文件，包含 `第X页`、`## 第`、`可视化类型：`、`ASCII` 等标记
- 用户明确说："这是PPT大纲"、"PPT配图"、"按PPT模式"、"/image ppt"
- 文件中有 `.title-card`、`.two-col`、`.three-col`、`.grid-card` 等布局标记

**PPT模式特点：**
- 自动解析大纲中的布局和文案（不需要"拆内容"）
- 用户只需确认风格 + 配色
- 批量生成全部提示词（3阶段 vs 普通模式5阶段）

详见：`stages/00-ppt-mode.md`

---

## 风格 Gallery（⚠️ 阶段2必须用户确认，禁止自动决定）

系统支持 8 种图片风格，**阶段2必须向用户展示并等待明确选择**：

> **重要**：图片比例由 image-gen 根据输出路径自动识别（公众号 16:9、小红书 3:4 等），本技能仅负责提示词内容。
>
> ⚠️ **禁止自动选择**：以下"信号关键词"仅作为向用户推荐的参考依据，**严禁**在未获得用户确认前擅自决定风格。

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

**阶段2强制流程**：
1. 向用户展示上述8种风格的表格
2. 明确询问："请从以上风格中选择（回复数字或风格名称）"
3. **必须收到用户明确选择后才能进入阶段3**
4. 严禁根据关键词自动决定风格

---

## 布局系统（引用 ppt-speech-creator）

**布局能力完全复用 `ppt-speech-creator` 的 35 种可视化布局。**

> 📖 **完整布局定义**：参见 `~/.claude/skills/ppt-speech-creator/SKILL.md` 的「可视化结构 ASCII 模板」章节

### 布局速查表

| 布局标记 | 名称 | 适用场景 |
|---------|------|----------|
| `.vs-grid` | 对比 | 痛点vs解法、旧vs新、方式对比 |
| `.process-chain` | 流程 | 3-6步骤线性流程 |
| `.process-loop` | 循环流程 | 三角/四角/五角循环（PDCA等） |
| `.matrix-grid` | 维度矩阵 | 2×2或3×3网格分类 |
| `.stat-card` | 指标卡片 | 核心数据、关键指标 |
| `.timeline` | 时间轴 | 里程碑、发展历程 |
| `.concentric` | 同心圆 | 内核→外层、核心→扩展 |
| `.pyramid` | 金字塔 | 层级结构、需求层次、转化漏斗 |
| `.fishbone` | 鱼骨图 | 根因分析、问题归因 |
| `.iceberg` | 冰山 | 表层vs深层 |
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

### 布局选择原则

- **有对立/比较** → `.vs-grid`
- **有先后顺序** → `.process-chain`
- **循环往复** → `.process-loop`
- **多分类/多维度** → `.matrix-grid`
- **核心数据展示** → `.stat-card`
- **时间发展/里程碑** → `.timeline`
- **核心到扩展的层级** → `.concentric`
- **层级结构/战略分解** → `.pyramid`
- **问题根因分析** → `.fishbone`
- **表层与深层分析** → `.iceberg`
- **用户体验路径** → `.journey`
- **概念交集** → `.venn`
- **发散结构** → `.mind-map`
- **多方案评分** → `.comparison-table`

---

## 流程概览

### 普通模式（5阶段）

| 阶段 | 名称 | 目标 | 详细文件 |
|---|---|---|---|
| 1 | 需求澄清（Spec/DoD） | 先挖需求：内容/场景/受众/字多字少；产出一句话复述与需求小结 | `stages/01-brief.md` |
| 2 | 配图规划（拆块→清单） | 拆内容→定图清单（几张/每张讲啥/用啥模板） | `stages/02-plan.md` |
| **2.5** | **风格选择（⚠️ 强制确认）** | **向用户展示7种风格表格，必须等待明确选择** | `stages/02-plan.md` 2D节 |
| 3 | 文案定稿（Copy Spec） | 逐字定稿"图上写什么"（唯一真值） | `stages/03-copy.md` |
| 4 | 提示词封装（Prompt Pack） | 把 Copy Spec 封装成可复制提示词 | `stages/04-prompts.md` |
| 5 | 迭代润色 | 根据反馈减字、换隐喻、提可读性 | `stages/05-iterate.md` |

### PPT模式（3阶段）

适用于已有完整PPT大纲（含布局+文案）的场景，详见 `stages/00-ppt-mode.md`

| 阶段 | 名称 | 目标 | 特点 |
|---|---|---|---|
| P1 | 解析确认 | 解析大纲文件，提取每页布局+文案，确认页数 | 自动读取 `可视化类型` 和 `内容要点` |
| P2 | 风格配色 | 选择风格（奶油纸/扁平化等）+ 确认配色方案 | 文案已固定，只调视觉 |
| P3 | 批量生成 | 为每页生成完整提示词（风格+布局+文案） | 一次性输出全部提示词 |
| 2 | 配图规划（拆块→清单） | 拆内容→定图清单（几张/每张讲啥/用啥模板） | `stages/02-plan.md` |
| **2.5** | **风格选择（⚠️ 强制确认）** | **向用户展示7种风格表格，必须等待明确选择** | `stages/02-plan.md` 2D节 |
| 3 | 文案定稿（Copy Spec） | 逐字定稿"图上写什么"（唯一真值） | `stages/03-copy.md` |
| 4 | 提示词封装（Prompt Pack） | 把 Copy Spec 封装成可复制提示词 | `stages/04-prompts.md` |
| 5 | 迭代润色 | 根据反馈减字、换隐喻、提可读性 | `stages/05-iterate.md` |

---

## 调度规则

**如何判断当前阶段：**
1. 还没把需求讲清楚（内容 + 场景 + 受众 + 字多/字少）→ 阶段1
2. 文章很长、需要拆块，或需要确定"几张图/每张讲什么"→ 阶段2
3. **⚠️ 图清单已确认，但风格未明确选择 → 阶段2.5（风格选择，强制阻塞）**
4. 图清单+风格都已确认，但还没确定"图上逐字写什么"→ 阶段3
5. Copy Spec 已确认，要出可复制提示词 → 阶段4
6. 用户反馈"字多/不好看/不符合封面" → 阶段5（必要时回退到阶段1重锁需求与字多/字少）

**⚠️ 关于风格选择的强制规则：**
- **阶段2.5是阻塞点**：即使用户说"确认"了配图清单，若风格未明确选择，禁止进入阶段3
- **禁止自动决定**：即使内容关键词明显匹配某风格（如商业→editorial），也必须让用户亲口确认
- **风格一旦锁定**：阶段3及之后不得更改风格，若用户想换风格，需回退到阶段2.5重新选择

**每个阶段开始时：**
- 告诉用户当前阶段与本阶段输出物
- 读取对应阶段文件并按步骤执行

---

## 输出规范（必须遵守）

- 每张图一个"核心信息"，不把解释性段落塞进图里
- 所有中文必须清晰可读：大字号、少字短句、避免密集小字
- 每张提示词用一个独立代码块输出，便于复制
- 默认输出 16:9 横版（除非用户明确要 3:4 漫画/竖版）
- 默认风格：奶油纸底 + 彩铅水彩手绘 + 轻涂鸦，趣味但干净（可用 `templates/style-block-cream-paper.md`）
- 阶段3产物（Copy Spec）一旦确认，阶段4不得擅自改文案，只做封装与参数/约束补全

### 契约式输出（供 article-workflow 检查）

**当作为 article-workflow 子技能调用时，输出文件必须包含 frontmatter 标记：**

同时，提示词文件必须带 `image_plan` 元数据，显式描述每张图的角色和图位，避免后续 `image-gen --insert-into` 只能按顺序猜测。

```yaml
---
image_prompter:
  version: "1.0"
  stages:
    brief:
      status: "done"
      confirmed_by: "user"
      timestamp: "2026-02-26T10:00:00"
    plan:
      status: "done"
      confirmed_by: "user"
      timestamp: "2026-02-26T10:05:00"
    style:
      status: "done"
      confirmed_by: "user"
      timestamp: "2026-02-26T10:10:00"
    copy:
      status: "done"
      confirmed_by: "user"
      timestamp: "2026-02-26T10:15:00"
    prompts:
      status: "done"
      confirmed_by: "user"
      timestamp: "2026-02-26T10:20:00"
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

**阶段标记规则：**
- 每个阶段完成后，更新对应 stage 的 status 为 "done"
- 记录 confirmed_by（用户确认）和 timestamp
- style_selected 必须记录用户选择的风格 ID
- copy_spec_confirmed 必须在阶段3确认后设为 true
- `image_plan` 必须至少包含：`id`、`role`、`file`，以及 `insert_after` 或 `insert_after_heading` 之一
- 图位优先级：`insert_after` > `insert_after_heading` > `role` > 顺序 fallback

**示例输出文件结构：**
```markdown
---
image_prompter:
  version: "1.0"
  stages:
    brief: { status: "done", ... }
    plan: { status: "done", ... }
    style: { status: "done", ... }
    copy: { status: "done", ... }
    prompts: { status: "done", ... }
  style_selected: "minimalist-sketch"
  image_count: 6
  copy_spec_confirmed: true
---

# 图片提示词

## 生成参数
- **风格**: minimalist-sketch
- **统一特征**: 细线条 + 纯白背景 + 单色 + 青色强调
- **模型**: doubao-seedream-4-5-251128
- **清晰度**: 2K

## 【封面图｜标题：xxx】
...
```

---

## 快速使用（给用户的最小输入）

用户只要给这四项，就能开始：
1. 要配图的内容（可是一段、一个小节、或整篇文章）
2. 用在哪里 + 观看距离（PPT投影远看 / 手机近看 / 海报）
3. 谁来看（小白/从业者/老板/学生…）
4. 偏好：更"少字清爽"还是更"信息密度"

可选补充（不写也没关系）：
- 你大概想要哪类图：封面/目录、单页概览、讲义解释、社媒海报（不确定我会根据场景与偏好推荐）

你要做的交付顺序：
- 先输出：图清单（几张 + 每张一句话目的 + 模板建议）（阶段2）
- **用户确认后：展示7种风格表格，等待用户明确选择（阶段2.5，强制阻塞）**
- 风格确认后：逐张输出 Copy Spec（逐字定稿）（阶段3）
- Copy Spec 确认后：逐张输出可复制提示词（阶段4）
- 用户说"字多/不好看"就进入迭代（阶段5）

---

## 文件结构

```
stages/
├── 00-ppt-mode.md          # PPT模式专用流程
├── 01-brief.md
├── 02-plan.md
├── 03-copy.md
├── 04-prompts.md
└── 05-iterate.md

templates/
├── styles.yaml              # 风格配置文件
├── style-block-*.md         # 8种风格模板
├── 16x9-*.md               # 16:9 布局模板（基础）
└── checklist.md

examples/
└── ai-tools-selection.md
```

> **布局系统**：复用 `ppt-speech-creator` 的 35 种可视化布局，详见该技能的 SKILL.md
