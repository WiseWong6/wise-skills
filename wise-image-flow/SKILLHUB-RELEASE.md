# 小红书 SkillHub 发布档案（wise-image-flow）

> 每次更新发布按本档案执行，避免重复决策。此文件仅供发布流程使用，**不进入上传包**。

## 固定参数（不再每次问）

| 项 | 值 |
|---|---|
| Skill ID（跨版本不可改） | `wise-image-flow`（CLI 加 `--identifier wise-image-flow` 显式锁定） |
| 发布名称 | PPT/笔记/文章配图工作流 |
| 简介 | 基于 内容/草稿/大纲/资料，一站式生成图片，会基于场景自动适配图片比例，基于内容选取风格，并快捷生成PDF/HTML。 |
| source | 原创 |
| tags | 效率工具, 内容创作 |

## 平台适配清单（每次打包必做）

1. 以本仓库最新代码为源，构建干净的暂存目录（不含 `.git`、不含 `LICENSE`——平台白名单不允许无扩展名文件）
2. 仓库内保持 `styles.json`（`.yaml` 不在平台文件白名单）
3. 暂存目录 `SKILL.md` frontmatter：`name` 替换为发布名称、`description` 替换为上方简介（平台从 frontmatter 读取）
4. zip 打包时 `SKILL.md` 必须位于压缩包根目录
5. 上传前用官方 CLI 校验包：`redskillhub-upload publish <zip> --dry-run --agent --source original --tag "效率工具,内容创作" --identifier wise-image-flow`

## 打包命令参考

```bash
STAGE=~/Desktop/wise-image-flow
rsync -a --exclude '.git' /Users/wisewong/Documents/Developer/wise-image-flow/ "$STAGE"/
rm -f "$STAGE/LICENSE"
# 替换 frontmatter name/description 为本档案的发布名称与简介
cd "$STAGE" && zip -r -X ~/Desktop/配图工作流-wise-image-flow.zip . -x "*.DS_Store"
```

## 真实发布命令（CLI 通道，需用户明确说「提交」）

```bash
printf 'submit\n' | redskillhub-upload publish ~/Desktop/配图工作流-wise-image-flow.zip \
  --agent --source original --tag "效率工具,内容创作" --identifier wise-image-flow
```

---

## 介绍全文（SkillHub 页面展示用，照此粘贴）

# Wise Image Flow · 配图全流程

一个 skill 覆盖「内容 → 提示词 → 生图」全链路

## 触发方式

### 普通配图模式
- "帮我给内容配几张图？"

### PPT 配图模式
检测到 PPT 相关信号自动进入

### 直接生图模式
- "生成一张……的图"、"画一个……"、"帮我出图"

---

## 风格目录

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
| `cream-journal` | 奶油手账 | 手账风知识卡片、小红书图文、学习笔记（3:4） | 手账/笔记/知识卡片 |
| `editorial-paper` | 社论纸艺 | 责任关系、工作流重构、AI 工作产品；默认 3:4，也可按场景扩展横版 | 纸艺/拼贴/责任/工作流 |

---

## 布局系统

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

---

## 配图助手流程

### 普通模式

| 阶段 | 名称 | 目标 | 详细文件 |
|---|---|---|---|
| 1 | 需求澄清 | 需求分析：内容/场景/受众/字多字少 | `stages/01-brief.md` |
| 2 | 配图规划 | 内容拆解（几张/每张讲啥/用啥模板） | `stages/02-plan.md` |
| **2.5** | **风格选择** | **展示 10 种风格表，必须等用户明确选择** | `stages/02-plan.md` 2D 节 |
| 3 | 文案定稿 | 逐字定稿"图上写什么" | `stages/03-copy.md` |
| 4 | 提示词封装 | 把文案封装成可复制提示词 | `stages/04-prompts.md` |
| 5 | 迭代润色 | 减字、换隐喻、提可读性 | `stages/05-iterate.md` |

### PPT 模式（3 阶段）

适用于已有完整 PPT 大纲：

| 阶段 | 名称 | 目标 |
|---|---|---|
| P1 | 解析确认 | 解析大纲，提取每页布局+文案，确认页数 |
| P2 | 风格配色 | 选风格 + 确认配色（文案已固定） |
| P3 | 批量生成 | 为每页生成完整提示词，一次性输出 |

---

## 输出规范（提示词阶段必守）

- 每张图一个"核心信息"，不塞解释性段落
- 所有中文清晰可读：大字号、少字短句、避免密集小字
- 全图字体最多 2 种：标题字体 + 正文字体，层级靠字号、字重与颜色深浅区分，禁止引入第三种字体、禁止手写体与印刷体混排（手账类风格则两种都用手写体）
- 每张提示词独立代码块输出，便于复制
- 比例由场景判定，不单独询问：小红书 3:4；公众号封面 21:9、公众号正文及其他 16:9；纯 PPT 16:9。用户明说 → 直接用；可推断 → 复述确认；未说明 → 阶段 1 询问；仍不明确 → 默认 16:9 并告知可改

---

## 生图工具

### 生图通道判定

提示词就绪后，先判定当前运行环境，按优先级选生图通道——**能不依赖 API 就不依赖**：

| 优先级 | 环境 | 判定方式 | 生图通道 |
|---|---|---|---|
| 1 | Codex / ChatGPT 网页端 / Gemini 网页端 | 宿主本身自带生图能力 | 直接用宿主内置生图：把提示词原样交给宿主执行，**不调用 API、不要求配 Key** |
| 2 | 其他宿主（Claude Code / ZCode / 通用 CLI 等） | 检查会话可用工具列表里有没有生图类 MCP 工具（工具名含 image-gen / generate_image / seedream / draw / banana 等） | 有就直接用该 MCP 工具生图 |
| 3 | 以上都不可用 | — | 走本 skill 的 `scripts/generate_image.py`（需 API Key），并按「依赖与环境变量」引导用户配置 |

### 平台比例识别

| 平台 | 图片类型 | 比例 |
|------|----------|------|
| 公众号（WeChat） | 封面图 | 21:9 |
| 公众号（WeChat） | 正文图 | 16:9 |
| 小红书（Xiaohongshu） | 全部 | 3:4 |
| PPT | 全部 | 16:9 |

PPT 场景（含 PPT 配图模式）所有页面统一 16:9 横版。

### 生成后分享交付

PDF/HTML，内置能力，继承自 image-to-pages

**触发条件**：场景判定为**小红书**（3:4 竖版合集）或 **PPT**（16:9 横版系列），且本次生成 ≥ 2 张；公众号及其他场景不触发。

生成完成后主动询问用户：「需要将这组图拼成可翻阅的 PDF / HTML 吗？」用户同意后，直接运行本 skill 自带脚本。

---

## 出处与致谢

### 风格部分

| 风格 | 出处 |
|---|---|
| 奶油纸手绘（cream-paper） | @云舒的AI实践笔记 |
| 小红书卡通（xhs-cartoon） | @宝玉 |
| 方格纸手绘（handdrawn） | @松果先森 |
| 极简手绘笔记（minimalist-sketch） | @Aki聊AI |
| 社论全景（editorial） | @歸藏 |
| 奶油手账（cream-journal） | @歪斯Wise |
| 社论纸艺（editorial-paper） | @歪斯Wise |
| 拼版交付能力（scripts/generate_html.py） | @歪斯Wise（继承自其 image-to-pages skill） |
| 扁平风 / 治愈系 / 描边插画 等 | 网络整理，出处待补 |

### Skill 部分

生图参考 @宝玉 @云舒 老师整合。

感谢开源的各位老师。
