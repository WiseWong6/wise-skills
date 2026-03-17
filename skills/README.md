# Private Skills

个人 Claude Code 技能库，包含 30+ 个专门用于内容创作、文档处理、前端开发等场景的 AI 技能。

## 技能分类

### 📝 内容创作

| 技能 | 描述 |
|------|------|
| **article-workflow** | 文章创作流水线：调研→提纲→写作→RAG增强→标题→重写→润色→出图→HTML→草稿箱 |
| **article-create-rag** | 基于文章库进行检索增强写作，支持主题创作、调研内容增强、草稿润色和提纲生成 |
| **article-plug-classicLines** | 基于知识库（金句库/文章库）智能插入高质量金句 |
| **article-formatted** | Markdown 格式规范化，处理中英文混排的空格、标点、引号问题 |
| **research-workflow** | 全流程内容创作调研，集成 Firecrawl、Context7、TrendRadar、Exa、社交媒体搜索 |
| **research-review** | 调研报告审计 + 成品文章事实核查 |
| **ppt-speech-creator** | 创建 PPT 内容并生成配套演讲逐字稿，支持 35 种逻辑可视化呈现方式 |

### 🎨 设计与视觉

| 技能 | 描述 |
|------|------|
| **canvas-design** | 使用设计哲学创建精美的 PNG/PDF 视觉艺术作品（海报、设计图等） |
| **swiss-editorial** | 将 Markdown 转换为 600x800px 杂志风信息海报（Swiss Style + Modern Editorial） |
| **algorithmic-art** | 使用 p5.js 创建算法艺术，支持生成艺术、流场、粒子系统 |
| **slack-gif-creator** | 创建针对 Slack 优化的动画 GIF |
| **theme-factory** | 为各种输出物（幻灯片、文档、报告、HTML 页面）应用预设或自定义主题 |
| **xhs-image-layout** | 将图片拼接成 3:4 白色容器的 HTML 页面，支持打印 PDF |

### 📄 文档处理

| 技能 | 描述 |
|------|------|
| **docx** | 创建、读取、编辑 Word 文档（.docx），支持目录、页眉页脚、修订模式等 |
| **pptx** | 创建、读取、编辑 PowerPoint 演示文稿（.pptx），支持模板、备注、批注等 |
| **xlsx** | 处理电子表格（.xlsx, .csv, .tsv），支持公式、图表、数据清洗等 |
| **pdf** | 处理 PDF 文件，支持合并、拆分、旋转、水印、OCR 等 |
| **defuddle** | 使用 Defuddle CLI 从网页提取干净的 Markdown 内容 |

### 🌐 前端开发

| 技能 | 描述 |
|------|------|
| **frontend-design** | 创建高质量的前端界面（网站、落地页、仪表板、React 组件等） |
| **frontend-slides** | 创建精美的 HTML 演示文稿，支持动画效果 |
| **web-artifacts-builder** | 使用 React、Tailwind CSS、shadcn/ui 创建复杂的多组件 HTML 产物 |
| **webapp-testing** | 使用 Playwright 测试本地 Web 应用 |

### 🧠 提示词与技能开发

| 技能 | 描述 |
|------|------|
| **skill-creator** | 创建新技能、修改和改进现有技能、测试和评估技能性能 |
| **omega-prompt-forge** | 从头创建提示词，选择合适的提示词框架，融合 OmegaPromptForge |
| **prompt-version-editor** | 在严格变更控制下编辑、版本化并存储提示词 |

### 📚 Obsidian 集成

| 技能 | 描述 |
|------|------|
| **obsidian-cli** | 使用 Obsidian CLI 与 Obsidian 仓库交互，支持笔记管理、插件开发 |
| **obsidian-markdown** | 创建和编辑 Obsidian Flavored Markdown（WikiLinks、Callouts、Frontmatter） |
| **json-canvas** | 创建和编辑 JSON Canvas 文件（思维导图、流程图等） |
| **obsidian-bases** | 创建和编辑 Obsidian Bases（数据库视图、筛选、公式等） |

### 🔧 工具与平台

| 技能 | 描述 |
|------|------|
| **agent-reach** | 安装和配置平台访问工具（Twitter/X、Reddit、YouTube、GitHub、Bilibili、小红书、抖音等） |

## 使用方法

这些技能用于 [Claude Code](https://claude.ai/code) 环境。每个技能目录包含：

- `SKILL.md` - 技能的详细说明文档
- 相关脚本和资源文件

## 技能结构

```
<skill-name>/
├── SKILL.md          # 技能描述和使用说明
├── [scripts/]        # 可选：相关脚本
└── [resources/]      # 可选：资源文件
```

## Git 历史清理

2025-03-15 使用 `git-filter-repo` 清理了历史中的大文件（76MB 的 `文章库.jsonl`），仓库大小从 76MB 减少到 3.6MB。

```bash
# 使用的命令
git-filter-repo --strip-blobs-bigger-than 10M --force
```

## License

Private - 个人使用
