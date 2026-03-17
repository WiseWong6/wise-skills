---
name: article-workflow
description: 文章创作流水线：调研→提纲→写作→RAG增强→标题→重写→润色→出图→HTML→草稿箱。默认使用 Obsidian 存储模式，可选传统文件系统模式（--traditional）。
version: "4.3.1"
requires:
  - Obsidian 模式（默认）: Obsidian vault + frontmatter
  - 传统模式（--traditional）: run_context.yaml + handoff.yaml
---

# 文章创作超级技能

## 概述

纯技能链架构，通过 Claude Code 技能调用链实现端到端的文章生产流水线。

**存储模式（二选一）：**

| 模式 | 推荐度 | 特点 |
|------|--------|------|
| **Obsidian 模式** | ⭐⭐⭐ 推荐 | 用 frontmatter 替代 yaml，双链关联，Obsidian 原生支持 |
| 传统模式 | 兼容 | run_context.yaml + handoff.yaml，文件系统结构 |

**核心原则：**
1. **零适配器层** - 直接调用各技能，不创建中间抽象
2. **技能同步** - 自动同步依赖技能的更新
3. **用户极简** - 只需提供"话题"，其他按默认值
4. **SSOT架构** - Obsidian frontmatter / run_context.yaml 作为单一事实源
5. **可恢复执行** - 支持从任意步骤 resume，不重复已完成工作
6. **强制确认点** - 关键参数缺失时进入 WAITING_FOR_USER 状态，不允许跳过
7. **有限度流水线（默认）** - 允许自动推进，但发布链路关键节点必须用户明确确认，不得推断

## 有限度流水线（默认）

### 发布上下文（新增 SSOT）

当工作流涉及飞书沟通、公众号预览、微信草稿箱时，必须在主文件 frontmatter / run_context 中显式维护 `delivery`：

```yaml
delivery:
  chat_channel: feishu
  preview_channel: feishu
  publish_channel: wechat
  publish_account: human   # wise/human
  preview_image_mode: feishu-image
  article_render_mode: article
  content_image_mode: wechat-cdn
```

作用：后续步骤不再猜测当前在哪沟通、发哪个号、图片如何预览、HTML 应用哪套默认值。

## 有限度流水线（默认）

默认按“有限度流水线”执行，以下节点必须人工确认，未确认一律阻断并进入 `WAITING_FOR_USER`：

1. 提纲选择（阶段 3）：必须收到用户明确选择 `A/B/C...`，禁止“回车默认 A”
2. 标题选择（阶段 7）：必须收到用户明确标题编号或标题文本，禁止默认第一个
3. image-prompter（阶段 12）：风格、布局、Copy Spec 必须用户确认；`confirmed_by` 必须为 `user`
4. 公众号账号（阶段 15/16）：必须明确 `wise/main` 或 `human/sub`，禁止自动猜测
5. 草稿箱入库（阶段 16）：必须收到显式动作确认（如“确认上传草稿箱”）

**禁止行为（强制）：**
- 禁止把“继续后面流程”解释为“同意上传/发布”
- 禁止在缺少确认时使用“推荐值/默认值/assumption”代替用户选择
- 禁止先执行上传再回填确认记录

## 激活条件

- 用户要求"完整流程"或"从调研到草稿箱"
- 用户要求"文章一体化创作"
- 用户提到"公众号+小红书双平台输出"

## 调用参数

- `--topic` (必需)：文章话题
- `--output-dir` (可选)：指定输出目录路径（覆盖默认路径）
- `--traditional` (可选)：使用传统存储模式，路径：`/Documents/Developer/auto-write/runs/`
- `--resume` (可选)：从现有项目恢复执行（自动检测模式）

**默认行为**：Obsidian 模式，输出到 `/Documents/Obsidian Vault/01_文章项目/`

## Obsidian 模式

### 目录结构

```
Obsidian Vault/
├── 00_研究库/                          # 与 research-workflow 共用
│   └── {YYYY-MM-DD}-{topic-slug}/
│       └── index.md
│
└── 01_文章项目/                         # 项目制
    └── {YYYY-MM-DD}__{topic-slug}/
        ├── 📋 项目看板.base
        ├── 00_素材与链接.md              # 引用研究库
        ├── 01_提纲.md
        ├── 02_初稿.md
        ├── 03_RAG增强.md
        ├── 04_标题方案.md
        ├── 05_润色稿.md
        ├── 06_终稿.md
        └── 07_发布记录.md
```

### Frontmatter 状态管理

替代 `run_context.yaml`，使用 frontmatter：

```yaml
---
project_id: "2026-02-26__topic__a1b2c3"
topic: "文章话题"
status: "in_progress"
platforms: ["wechat", "xhs"]
created: 2026-02-26
updated: 2026-02-26

research_ref: "[[00_研究库/2026-02-26-topic/index|调研资料]]"

steps:
  research: { status: "done", file: "00_素材与链接.md" }
  outline: { status: "done", file: "01_提纲.md" }
  draft: { status: "done", file: "02_初稿.md" }
  rag_enhance: { status: "in_progress", file: "03_RAG增强.md" }

publish:
  wechat: { status: "pending", title: "", url: "" }
  xhs: { status: "pending", title: "", url: "" }

delivery:
  chat_channel: "feishu"
  preview_channel: "feishu"
  publish_channel: "wechat"
  publish_account: "human"
  preview_image_mode: "feishu-image"
  article_render_mode: "article"
  content_image_mode: "wechat-cdn"

tags: ["article-project", "ai"]
---
```

### 项目看板 (Obsidian Bases)

```yaml
# 📋 项目看板.base
filters:
  and:
    - file.hasTag("article-project")
views:
  - type: table
    name: "所有项目"
    groupBy:
      property: status
      direction: ASC
```

### 目录重命名规则（强制）

项目目录在标题确认后**必须**重命名：

```
初始格式: {YYYY-MM-DD}__{topic-slug}__{shortid}/
           ↓ (确认标题后)
最终格式: {YYYY-MM-DD}-{标题slug}/

示例:
2026-02-26__ai-agent-trends__a1b2c3/
           ↓
2026-02-26-AI-Agent发展趋势深度解析/
```

**触发时机：** 阶段 7（用户选择标题）完成后**立即自动执行**

**执行方式（使用脚本）：**
```bash
# 阶段7完成后，立即运行重命名脚本
python3 ~/.claude/skills/article-workflow/scripts/stage_manager.py \
  --project-dir "/path/to/project" \
  --rename "用户选择的标题"

# 验证重命名是否成功
python3 ~/.claude/skills/article-workflow/scripts/workflow_guardian.py \
  --project-dir "/path/to/project" \
  --before-stage 08
```

**强制检查点：**
- 如果目录名仍包含 `__` 格式，但缺少 `rename_completed` 标记，阶段8及以后将被**阻断**
- AI 必须在阶段7完成后立即执行重命名，不得跳过
- 重命名后更新主文件 frontmatter 中的 `topic` 字段和 `steps.selected_title.rename_completed: true`

---

## article-outliner 与 Obsidian 集成

### 提纲生成流程（Obsidian 模式）

当使用 Obsidian 模式时，article-outliner 技能被调用方式：

```bash
# 从 article-workflow 调用 article-outliner
python article_outliner.py \
    --topic "AI Agent发展趋势" \
    --file "/path/to/00_素材与链接.md" \
    --output-dir "/Users/wisewong/Documents/Obsidian Vault/01_文章项目/2026-02-26__ai-agent__a1b2c3/" \
    --obsidian-mode \
    --count 3
```

**关键参数：**
- `--output-dir`: 指向 Obsidian 项目目录
- `--obsidian-mode`: 启用 Obsidian 格式输出

### 提纲文件位置

**澄清：** 提纲文件 **始终** 存储在项目目录下：

```
01_文章项目/
└── 2026-02-26__ai-agent__a1b2c3/
    ├── 📋 测试 Obsidian 集成.md      # 主文件（frontmatter）
    ├── 📝 提纲.md                    # ← 提纲在这里（阶段2生成）
    ├── ✏️ 初稿.md                    # 初稿（阶段4生成）
    └── ...
```

**NOT** 存储在 `posts/` 或 `_log/` 目录下。

### 提纲文件格式（Obsidian）

```markdown
---
outline_id: "a"
style: "mainstream"
estimated_length: "1800字"
selected: true  # 用户选择后标记
---

# 方案A：主流稳重型

【风格定位】...
【叙事骨架】...

## 正文结构
...
```

---

## SSOT 架构设计

### 模式 A：Obsidian Frontmatter（推荐）

在 Obsidian 模式下，使用 Markdown frontmatter 作为状态管理：

```yaml
---
project_id: "2026-02-26__topic-slug__a1b2c3"
topic: "你的文章话题"
status: "in_progress"  # draft | in_progress | review | done | published
current_step: "05_polish"
platforms: ["wechat", "xhs"]
created: 2026-02-26
updated: 2026-02-26

research_ref: "[[00_研究库/2026-02-26-topic/index|调研资料]]"

steps:
  research: { status: "done", file: "00_素材与链接.md" }
  outline: { status: "done", file: "01_提纲.md" }
  draft: { status: "done", file: "02_初稿.md" }
  rag_enhance: { status: "done", file: "03_RAG增强.md" }
  titles: { status: "done", file: "04_标题方案.md" }
  polish: { status: "in_progress", file: "05_润色稿.md" }
  final: { status: "pending", file: "06_终稿.md" }
  publish: { status: "pending", file: "07_发布记录.md" }

publish:
  wechat: { status: "pending", title: "", url: "" }
  xhs: { status: "pending", title: "", url: "" }

delivery:
  chat_channel: "feishu"
  preview_channel: "feishu"
  publish_channel: "wechat"
  publish_account: "human"
  preview_image_mode: "feishu-image"
  article_render_mode: "article"
  content_image_mode: "wechat-cdn"

tags: ["article-project", "ai"]
---
```

### 模式 B：run_context.yaml（传统模式）

每个运行目录自动生成 `run_context.yaml`，记录：

```yaml
run_id: "20260113__topic-slug__a1b2c3"
topic: "你的文章话题"
platforms: ["wechat"]
status: "RUNNING"  # RUNNING | WAITING_FOR_USER | DONE | FAILED
current_step: "06_polish"

decisions:
  wechat:
    account: "main"  # main/sub/alias
    title: "用户选择的标题"
  image:
    count: 4
    poster_ratio: "16:9"
    cover_ratio: "16:9"
    model: "doubao-seedream-4-5-251128"
    resolution: "2k"

pending_questions: []  # 非空 => status=WAITING_FOR_USER

steps:
  00_init:            { state: "DONE", artifacts: ["run_context.yaml"] }
  01_research:        { state: "DONE", artifacts: ["wechat/00_research.md"] }
  02_outliner:        { state: "DONE", artifacts: ["wechat/02_outlines/"] }
  03_select_outline:  { state: "DONE", artifacts: ["wechat/03_outline_selected.md"] }
  04_writer:          { state: "DONE", artifacts: ["wechat/04_draft.md"] }
  05_rag_enhance:     { state: "DONE", artifacts: ["wechat/05_enhanced.md"] }
  06_titles:          { state: "DONE", artifacts: ["wechat/06_titles.md"] }
  07_select_title:    { state: "DONE", artifacts: ["wechat/07_title_selected.md"] }
  08_polish:          { state: "RUNNING", artifacts: [] }
  # ...
```

### 执行模式控制

`decisions.llm.provider` 控制阶段5（文章创作）的执行方式：

| provider | 执行方式 | 参数传递 |
|----------|----------|----------|
| `claude-code`（默认） | AI 直接生成文章 | 传递 `--use-claude-code` |
| `deepseek` / `kimi` | 调用脚本使用第三方 API | 不传递 `--use-claude-code` |

**配置示例：**
```yaml
# 在 run_context.yaml 中设置
decisions:
  llm:
    provider: "claude-code"  # 或 "deepseek" / "kimi"
```

**切换模式的场景：**
- 默认使用 `claude-code`：AI 直接生成，质量最高
- 切换到 `deepseek`/`kimi`：调用脚本使用第三方 API，适用于批量生成或成本控制

### 状态机设计

```
PENDING → RUNNING → DONE
            ↓
          FAILED
            ↓
   WAITING_FOR_USER
```

**状态转换规则：**
- `PENDING`：步骤未开始
- `RUNNING`：步骤执行中（写入日志 `_log/step_xx.log`）
- `DONE`：步骤成功完成（artifacts 已落盘）
- `FAILED`：步骤执行失败（记录错误信息）
- `WAITING_FOR_USER`：需要用户确认参数（pending_questions 非空）

### 强制确认点（Stage Gates）

**Gate A - 前置确认（Account）：**
```yaml
# decisions.wechat.account 为 null 时触发
pending_questions:
  - id: "account_selection"
    question: "请选择公众号账号"
    type: "choice"
    options: ["main", "sub"]
    required: true
```

**Gate B - 前置确认（Image Config）：**
```yaml
# decisions.image.confirmed 为 false 时触发
pending_questions:
  - id: "image_config"
    question: "请确认配图：当前设置 横屏，4张"
    type: "text"
    required: true
```

**Gate C - 提纲/标题选择（No Default）：**
```yaml
# 阶段3和阶段7必须用户明确选择
rules:
  - no_implicit_default: true
  - require_explicit_choice: true
  - allowed_sources: ["user_explicit_input"]
```

**Gate D - image-prompter 人工确认（No Assumption）：**
```yaml
# 阶段12 contract 约束
rules:
  - image_prompter.stages.*.confirmed_by must_equal "user"
  - style_selected required
  - layout_selected required
  - copy_spec_confirmed must_equal true
```

**Gate E - 草稿箱上传确认（Explicit Consent）：**
```yaml
# 阶段16执行前必须显式同意
pending_questions:
  - id: "draftbox_consent"
    question: "是否确认上传到公众号草稿箱？"
    type: "confirm"
    required: true
```

**Gate F - 发布动作语义白名单：**
```yaml
allowed_publish_intents:
  - "确认上传草稿箱"
  - "现在上传到草稿箱"
  - "同意入库草稿箱"
blocked_ambiguous_intents:
  - "继续"
  - "继续后面的流程"
  - "往下走"
```

### Resume 机制

**检测现有运行：**
```python
if os.path.exists(f"{run_dir}/run_context.yaml"):
    context = load_yaml(f"{run_dir}/run_context.yaml")

    if context["status"] == "WAITING_FOR_USER":
        # 只处理 pending_questions，不继续执行
        ask_and_update_decisions()
        return

    # 从 current_step 继续
    start_from_step = context["current_step"]
    skip_completed_steps = True
```

**执行逻辑：**
1. 加载现有 run_context.yaml
2. 如果 status=WAITING_FOR_USER：
   - 显示 pending_questions
   - 获取用户回答
   - 更新 decisions 和 pending_questions
   - 保存后退出（等待下次 resume）
3. 如果 status=RUNNING 或 FAILED：
   - 从 current_step 继续
   - 跳过所有 state=DONE 的步骤
   - 重试 FAILED 步骤（最多 1 次）

## 工作流（技能调用链）

**并行要点：**
1. `01_research` 完成后，`02_rag` 与 `03_titles` 可并行启动
2. `05_draft` 完成后，`06_polish → 07_humanize` 与 `08_prompts → 09_images → 10_upload_images` 可并行推进

### 阶段 0：初始化项目目录

**执行操作：**
1. 检测存储模式（默认 Obsidian，`--traditional` 使用传统模式）
2. 创建运行目录结构
3. 生成 frontmatter（Obsidian 模式）或 run_context.yaml（传统模式）
4. 创建 _log 目录

```bash
# 模式检测
if [ "$TRADITIONAL_MODE" = "true" ]; then
    # 传统模式
    BASE_DIR="/Users/wisewong/Documents/Developer/auto-write/runs"
else
    # Obsidian 模式（默认）
    BASE_DIR="/Users/wisewong/Documents/Obsidian Vault/01_文章项目"
fi

# 生成 run_id / project_id
DATE=$(date +"%Y%m%d")

# 处理 topic：保留中文、英文、数字，其他字符替换为横线，全部转小写
# 使用 Python 正确处理 Unicode 字符
SLUG=$(python3 -c "
import sys
import re
topic = sys.argv[1] if sys.argv[1] else 'untitled'
# 保留：中文(\u4e00-\u9fff)、英文(a-zA-Z)、数字(0-9)，其他替换为-
slug = re.sub(r'[^\u4e00-\u9fffa-zA-zA-Z0-9]+', '-', topic.strip())
# 去除首尾的 -
slug = slug.strip('-')
# 限制长度最多 40 个字符
slug = slug[:40] if slug else 'untitled'
print(slug)
" "$TOPIC")

SHORTID=$(openssl rand -hex 3)
PROJECT_ID="${DATE}__${SLUG}__${SHORTID}"

# 创建项目目录
PROJECT_DIR="${BASE_DIR}/${PROJECT_ID}"
mkdir -p "$PROJECT_DIR"

if [ "$TRADITIONAL_MODE" = "true" ]; then
    # 传统模式：创建 wechat/xhs/_log 子目录
    mkdir -p "$PROJECT_DIR"/wechat "$PROJECT_DIR"/xhs "$PROJECT_DIR"/_log

    # 生成 run_context.yaml
    cp templates/run_context.template.yaml "$PROJECT_DIR/run_context.yaml"
    sed -i '' "s/run_id: \"\"/run_id: \"$PROJECT_ID\"/" "$PROJECT_DIR/run_context.yaml"
    sed -i '' "s/topic: \"\"/topic: \"$TOPIC\"/" "$PROJECT_DIR/run_context.yaml"
else
    # Obsidian 模式：创建步骤文件
    touch "$PROJECT_DIR/📋 ${TOPIC}.md"  # 主文件（含 frontmatter）
    touch "$PROJECT_DIR/00_素材与链接.md"
    touch "$PROJECT_DIR/01_提纲.md"
    touch "$PROJECT_DIR/02_初稿.md"
    touch "$PROJECT_DIR/03_RAG增强.md"
    touch "$PROJECT_DIR/04_标题方案.md"
    touch "$PROJECT_DIR/05_润色稿.md"
    touch "$PROJECT_DIR/06_终稿.md"
    touch "$PROJECT_DIR/07_发布记录.md"
    mkdir -p "$PROJECT_DIR/08_图片"
    mkdir -p "$PROJECT_DIR/_log"

    # 生成 frontmatter
    cat > "$PROJECT_DIR/📋 ${TOPIC}.md" << EOF
---
project_id: "${PROJECT_ID}"
topic: "${TOPIC}"
status: "in_progress"
platforms: ["wechat", "xhs"]
created: $(date +"%Y-%m-%d")
updated: $(date +"%Y-%m-%d")

steps:
  research: { status: "pending", file: "00_素材与链接.md" }
  outline: { status: "pending", file: "01_提纲.md" }
  draft: { status: "pending", file: "02_初稿.md" }
  rag_enhance: { status: "pending", file: "03_RAG增强.md" }
  titles: { status: "pending", file: "04_标题方案.md" }
  polish: { status: "pending", file: "05_润色稿.md" }
  final: { status: "pending", file: "06_终稿.md" }
  publish: { status: "pending", file: "07_发布记录.md" }

publish:
  wechat: { status: "pending", title: "", url: "" }
  xhs: { status: "pending", title: "", url: "" }

tags: ["article-project"]
---

# ${TOPIC}

EOF
fi

# 更新状态
update_step_state("00_init", "DONE", ["📋 ${TOPIC}.md"])
```

**输出：**
- Obsidian 模式：`📋 {话题}.md`（主文件，含 frontmatter）+ 步骤文件
- 传统模式：`run_context.yaml`（SSOT）+ `_log/` 目录

---

### 阶段 1：内容调研（research-workflow）

**调用方式：**
```
使用 research-workflow 技能
```

**输入：**
- 话题：用户提供的主题
- 平台：wechat + xhs
- 时间范围：month（默认）

**输出：**
- `wechat/00_research.md`
- `xhs/00_research.md`（内容相同）

**AI 执行：**
```text
用户说："帮我调研 [话题]，为文章准备资料包"

AI 调用 /research-workflow 技能：
1. 使用 firecrawl_search 搜索话题相关资料
2. 分析趋势、竞品缺口、关键发现
3. 生成带置信度标签的调研报告
4. 保存到 wechat/00_research.md 和 xhs/00_research.md
```

---

### 阶段 2：生成提纲方案（article-outliner）

**调用方式：**
```
使用 article-outliner 技能
```

**Handoff 读取：**
```python
# 读取上一阶段的 handoff.yaml，获取输入文件路径
prev_handoff = load_yaml(f"{run_dir}/wechat/01_handoff.yaml")
input_file = prev_handoff['outputs'][0]  # wechat/00_research.md
```

**输入：**
- 调研内容：通过 handoff 读取（`wechat/00_research.md`）
- 提纲数量：默认 3 个

**输出：**
- `wechat/02_outlines/outline-a.md`（方案A：主流稳重型）
- `wechat/02_outlines/outline-b.md`（方案B：故事驱动型）
- `wechat/02_outlines/outline-c.md`（方案C：深度专业型）
- `wechat/02_handoff.yaml`

**AI 执行：**
```text
用户说："基于调研内容生成多个提纲方案"

AI 调用 /article-outliner 技能：
1. 读取 wechat/00_research.md
2. 分析核心论点、背景语境、可复用框架、论证漏洞
3. 生成 2-3 个差异化提纲方案：
   - 方案A：面向大众的产品介绍型（是什么→解决什么→怎么做到→意味着什么）
   - 方案B：故事驱动的体验分享型（故事→问题→探索→解决方案→升华）
   - 方案C：深度分析的思辨型（表面→深层→批判→判断）
4. 保存到 wechat/02_outlines/ 目录
5. 生成 handoff.yaml
```

**handoff.yaml 模板：**
```yaml
step_id: "02_outliner"
inputs:
  - "wechat/00_research.md"
outputs:
  - "wechat/02_outlines/outline-a.md"
  - "wechat/02_outlines/outline-b.md"
  - "wechat/02_outlines/outline-c.md"
  - "wechat/02_handoff.yaml"
summary: "基于调研内容生成 2-3 个差异化提纲方案"
next_instructions:
  - "下一步：用户选择提纲方案"
open_questions: []
```

---

### 阶段 3：用户选择提纲

**调用方式：**
用户交互选择

**输入：**
- `wechat/02_outlines/` 目录下的提纲文件

**输出：**
- `wechat/03_outline_selected.md`（用户选择的提纲）
- `wechat/03_handoff.yaml`

**交互流程：**
```text
展示提纲方案摘要：
【方案A】面向大众的产品介绍型 - 适合入门读者，约1800字
  - 风格：轻松友好
  - 结构：是什么→解决什么→怎么做到→意味着什么
  - 优势：门槛低，易传播

【方案B】故事驱动的体验分享型 - 适合喜欢看故事的读者，约2000字
  - 风格：个人化、有温度
  - 结构：故事→问题→探索→解决方案→升华
  - 优势：代入感强，易引发情感共鸣

【方案C】深度分析的思辨型 - 适合从业者，约2500字
  - 风格：理性、专业、有深度
  - 结构：表面→深层→批判→判断
  - 优势：有深度、有观点，适合建立专业形象

用户选择方案（A/B/C）。
⚠️ 未收到明确选择时必须进入 WAITING_FOR_USER，禁止回车默认 A。
复制选定提纲到 wechat/03_outline_selected.md
```

**handoff.yaml 模板：**
```yaml
step_id: "03_select_outline"
inputs:
  - "wechat/02_outlines/"
outputs:
  - "wechat/03_outline_selected.md"
  - "wechat/03_handoff.yaml"
summary: "用户从多个提纲方案中选择一个"
next_instructions:
  - "下一步：article-writer 根据选中的提纲生成文章"
open_questions: []
```

---

### 阶段 4：根据提纲写作（article-writer）

**调用方式：**
```
使用 article-writer 技能
```

**Handoff 读取：**
```python
# 读取上一阶段的 handoff.yaml，获取选中的提纲
outline_handoff = load_yaml(f"{run_dir}/wechat/03_handoff.yaml")
outline_file = outline_handoff['outputs'][0]  # wechat/03_outline_selected.md

# 读取更早阶段获取调研内容
research_handoff = load_yaml(f"{run_dir}/wechat/01_handoff.yaml")
research_file = research_handoff['outputs'][0]  # wechat/00_research.md
```

**输入：**
- 提纲：通过 handoff 读取（`wechat/03_outline_selected.md`）
- 调研内容：通过 handoff 读取（`wechat/00_research.md`）

**输出：**
- `wechat/04_draft.md`（根据提纲生成的文章草稿，1500-2500字）
- `wechat/04_handoff.yaml`

**AI 执行：**
```text
用户说："根据选中的提纲生成文章草稿"

AI 调用 /article-writer 技能：
1. 读取 wechat/03_outline_selected.md（提纲结构）
2. 读取 wechat/00_research.md（素材内容）
3. 严格按照提纲结构生成文章：
   - 执行开头策略（设问/故事/数据/引用）
   - 每个小标题对应一节内容
   - 体现情绪标签（共鸣/好奇/借势/升华）
   - 执行结尾策略（总结/展望/行动/升华）
4. 控制字数在提纲预估范围内
5. 保存到 wechat/04_draft.md
6. 生成 handoff.yaml
```

**handoff.yaml 模板：**
```yaml
step_id: "04_writer"
inputs:
  - "wechat/03_outline_selected.md"
  - "wechat/00_research.md"
outputs:
  - "wechat/04_draft.md"
  - "wechat/04_handoff.yaml"
summary: "根据选中的提纲生成文章草稿"
next_instructions:
  - "下一步：article-create-rag 使用本地文章库进行 RAG 增强"
open_questions: []
```

---

### 阶段 5：RAG 增强润色（article-create-rag --enhance）

**调用方式：**
```
使用 article-create-rag 技能（增强模式）
```

**Handoff 读取：**
```python
# 读取上一阶段的 handoff.yaml，获取初稿
prev_handoff = load_yaml(f"{run_dir}/wechat/04_handoff.yaml")
draft_file = prev_handoff['outputs'][0]  # wechat/04_draft.md
```

**输入：**
- 初稿：通过 handoff 读取（`wechat/04_draft.md`）
- 模式：`--enhance`（增强模式，非直接生成）

**输出：**
- `wechat/05_enhanced.md`（RAG 增强后的文章）
- `wechat/05_retrieval_snippets.md`（检索证据片段）
- `wechat/05_handoff.yaml`

**AI 执行：**
```text
用户说："使用本地文章库对初稿进行 RAG 增强和润色"

AI 调用 /article-create-rag 技能（--enhance 模式）：
1. 读取 wechat/04_draft.md（初稿）
2. 提取初稿关键段落和观点
3. 从本地文章库召回相关内容
4. 用召回内容增强初稿：
   - 补充数据/案例/引用
   - 优化表达和论证
   - 保持原有结构和观点不变
5. 保存到 wechat/05_enhanced.md
6. 保存检索证据到 wechat/05_retrieval_snippets.md
7. 生成 handoff.yaml
```

**向后兼容说明：**
- `--enhance` 模式：接收已有草稿进行增强（新标准流程）
- `--outline` 模式：直接基于调研内容生成（保留快速模式）

**handoff.yaml 模板：**
```yaml
step_id: "05_rag_enhance"
inputs:
  - "wechat/04_draft.md"
outputs:
  - "wechat/05_enhanced.md"
  - "wechat/05_retrieval_snippets.md"
  - "wechat/05_handoff.yaml"
summary: "使用本地文章库对初稿进行 RAG 增强和润色"
next_instructions:
  - "下一步：title-gen 生成标题方案"
  - "只能引用 snippets 中的内容，不得杜撰来源"
open_questions: []
```

---

### 阶段 6：生成标题方案（title-gen）

**调用方式：**
```
使用 title-gen 技能
```

**Handoff 读取：**
```python
# 读取 RAG 增强后的文章
prev_handoff = load_yaml(f"{run_dir}/wechat/05_handoff.yaml")
input_file = prev_handoff['outputs'][0]  # wechat/05_enhanced.md
```

**输入：**
- 增强后的文章：通过 handoff 读取（`wechat/05_enhanced.md`）

**输出：**
- `wechat/06_titles.md`（多组标题方案）
- `wechat/06_handoff.yaml`

**AI 执行：**
```text
用户说："基于增强后的文章生成多组标题方案"

AI 调用 /title-gen 技能：
1. 提取文章核心关键词
2. 参考本地标题库生成多组标题
3. 保存到 wechat/06_titles.md
4. 生成 handoff.yaml
```

**handoff.yaml 模板：**
```yaml
step_id: "06_titles"
inputs:
  - "wechat/05_enhanced.md"
outputs:
  - "wechat/06_titles.md"
  - "wechat/06_handoff.yaml"
summary: "基于增强后的文章生成多组爆款标题方案"
next_instructions:
  - "下一步：用户选择标题"
open_questions: []
```

---

### 阶段 7：用户选择标题

**调用方式：**
用户交互选择

**输入：**
- `wechat/06_titles.md`（多组标题方案）

**输出：**
- `wechat/07_title_selected.md`（用户选择的标题）
- `wechat/07_handoff.yaml`

**交互流程：**
```text
显示多组标题方案：
1. 【悬念式】标题A
2. 【痛点式】标题B
...

用户输入选择的标题编号或完整标题文本。
⚠️ 未收到明确输入时必须进入 WAITING_FOR_USER，禁止默认第一个。
保存到 wechat/07_title_selected.md
```

**handoff.yaml 模板：**
```yaml
step_id: "07_select_title"
inputs:
  - "wechat/06_titles.md"
outputs:
  - "wechat/07_title_selected.md"
  - "wechat/07_handoff.yaml"
summary: "用户从多组标题方案中选择一个"
next_instructions:
  - "下一步：用选中的标题替换文章中的临时标题"
open_questions: []
```

---

### 阶段 8：用选中标题更新文章

**说明：**
此阶段将用户选择的标题应用到 RAG 增强后的文章上，作为文章的最终标题。

**Handoff 读取：**
```python
# 读取选中的标题
title_handoff = load_yaml(f"{run_dir}/wechat/07_handoff.yaml")
title_file = title_handoff['outputs'][0]  # wechat/07_title_selected.md

# 读取 RAG 增强后的文章
enhance_handoff = load_yaml(f"{run_dir}/wechat/05_handoff.yaml")
content_file = enhance_handoff['outputs'][0]  # wechat/05_enhanced.md
```

**输入：**
- 增强后的文章：`wechat/05_enhanced.md`
- 用户选择的标题：`wechat/07_title_selected.md`

**输出：**
- `wechat/08_with_title.md`（带最终标题的文章）
- `wechat/08_handoff.yaml`

**AI 执行：**
```text
1. 读取 wechat/07_title_selected.md（用户选择的标题）
2. 读取 wechat/05_enhanced.md（RAG 增强后的文章）
3. 将选中的标题作为文章标题（替换临时标题）
4. 保存到 wechat/08_with_title.md
5. 生成 handoff.yaml
```

**handoff.yaml 模板：**
```yaml
step_id: "08_apply_title"
inputs:
  - "wechat/05_enhanced.md"
  - "wechat/07_title_selected.md"
outputs:
  - "wechat/08_with_title.md"
  - "wechat/08_handoff.yaml"
summary: "将用户选择的标题应用到文章上"
next_instructions:
  - "下一步：article-rewrite 专业重写（HKR + 四步爆款法 + 反AI写作）"
open_questions: []
```

---

### 阶段 9：文章专业重写（article-rewrite）

**前置交互：选择重写风格**（Gate C）

检查 `run_context.yaml` 中 `decisions.rewrite.style`：
- 如果为 `null` 或 `confirmed: false` → 显示风格选项并等待用户选择
- 如果已确认 → 跳过交互，使用已保存的风格

**风格选择界面（智能推荐）：**
```text
🎯 推荐风格: 成长风格（粥左罗：对比手法 + 金句密度 + 对话感）
   理由: 检测到 3 个相关关键词

请选择文章重写风格：

【成长】成长风格（粥左罗式）
- 对话感强，问题牵引
- 对比手法："不是...而是"、"越...越..."
- 金句密度高，每300-500字至少一句可传播金句

【知识】知识风格（专业写作）
- 高信息密度，结构化表达
- 方法论型：FRCE结构（框架→原则→案例→执行）
- 知识型：知识晶格结构

【商业】商业风格（刘润式）
- 设问开场，编号分层（01/02/03）
- 金句收尾，每小节结尾凝练总结
- 现象洞察链：现象→背景→洞察→启示

【地气】地气风格（卡兹克式）
- HKR结构（Hook-Knowledge-Resonance）
- 第一人称，短句快节奏
- 口语化："就是"、"然后"、"其实"、"说实话"

选择 [成长/知识/商业/地气，回车使用推荐]：
```

**保存选择到 run_context.yaml：**
```yaml
decisions:
  rewrite:
    style: "growth"  # 或 "knowledge"/"business"/"casual"
    confirmed: true
```

**调用方式：**
```text
使用 article-rewrite 技能，传递 --style {decisions.rewrite.style} 参数 [必须调用 Skill 工具]
```

**Handoff 读取：**
```python
# 读取上一阶段的 handoff.yaml，获取带标题的文章
prev_handoff = load_yaml(f"{run_dir}/wechat/08_handoff.yaml")
content_file = prev_handoff['outputs'][0]  # wechat/08_with_title.md

# 从 run_context.yaml 读取风格选择
context = load_yaml(f"{run_dir}/run_context.yaml")
style = context.get('decisions', {}).get('rewrite', {}).get('style', 'style1')
```

**输入：**
- 带标题的文章：`wechat/08_with_title.md`
- 风格选择：`decisions.rewrite.style`

**输出：**
- `wechat/09_rewritten.md`（专业重写后的文章）
- `wechat/09_handoff.yaml`

**AI 执行（必须执行）：**
```text
1. 从 run_context.yaml 读取风格：{style}
2. 调用 article-rewrite 技能，传递 --style {style} 参数
3. HKR 快速检查（Hook/Knowledge/Resonance）- 内部质量门槛
4. 按选择的风格特征重写：
   - 成长风格：对比手法 + 金句密度 + 对话感
   - 知识风格：高信息密度 + 结构化表达
   - 商业风格：设问开场 + 编号分层 + 金句收尾
   - 地气风格：HKR + 第一人称 + 短句快节奏
5. 应用反AI写作指南：
   - 消除翻译腔
   - 避免机械小标题和列表
   - 保留主观视角和情绪表达
6. 双平台适配：公众号版（1500字）+ 小红书版（600-800字）
```

**handoff.yaml 模板：**
```yaml
step_id: "09_rewrite"
inputs:
  - "wechat/08_with_title.md"
outputs:
  - "wechat/09_rewritten.md"
  - "wechat/09_handoff.yaml"
summary: "使用 HKR + 反AI写作进行专业重写（风格：{style}）"
next_instructions:
  - "下一步：article-plug-classicLines 知识库润色"
open_questions: []
```

---

### 阶段 10：知识库润色（article-plug-classicLines）

**调用方式：**
```
检索本地知识库并润色文章
```

**Handoff 读取：**
```python
# 读取上一阶段的 handoff.yaml，获取输入文件路径
prev_handoff = load_yaml(f"{run_dir}/wechat/09_handoff.yaml")
input_file = prev_handoff['outputs'][0]  # wechat/09_rewritten.md
```

**输入：**
- 重写后的文章：通过 handoff 读取（`wechat/09_rewritten.md`）

**知识库路径：**
- 文章库：`/Users/wisewong/Documents/Developer/auto-write/文章库`
- 金句库：`/Users/wisewong/Documents/Developer/auto-write/金句库`

**输出：**
- `wechat/10_polished.md`（金句点缀稿）
- `wechat/10_retrieval_snippets.md`（检索证据片段）
- `xhs/10_polished.md`
- `xhs/10_retrieval_snippets.md`
- `wechat/10_handoff.yaml`
- `xhs/10_handoff.yaml`

**AI 执行：**
```text
1. 使用 rg 搜索关键词，检索相关文章和金句
2. 融合金句到关键段落（保持事实准确）
3. 提升可读性与金句密度
4. 输出：
   - wechat/10_polished.md（金句点缀稿）
   - wechat/10_retrieval_snippets.md（检索证据片段）
   - xhs/10_polished.md
   - xhs/10_retrieval_snippets.md
5. 生成 handoff.yaml
```

**handoff.yaml 模板：**
```yaml
step_id: "10_polish"
inputs:
  - "wechat/09_rewritten.md"
outputs:
  - "wechat/10_polished.md"
  - "wechat/10_retrieval_snippets.md"
  - "xhs/10_polished.md"
  - "xhs/10_retrieval_snippets.md"
  - "wechat/10_handoff.yaml"
  - "xhs/10_handoff.yaml"
summary: "基于知识库检索和金句润色文章"
next_instructions:
  - "只能引用 snippets 中的内容，不得杜撰来源"
  - "保持文章事实点和结构不变"
open_questions: []
```

---

### 阶段 11：文本去机械化（article-formatted）

**调用方式：**
```
使用 article-formatted 技能
```

**Handoff 读取：**
```python
# 读取上一阶段的 handoff.yaml，获取输入文件路径
prev_handoff = load_yaml(f"{run_dir}/wechat/10_handoff.yaml")
input_file = prev_handoff['outputs'][0]  # wechat/10_polished.md
```

**输入：**
- 润色稿：通过 handoff 读取（`wechat/10_polished.md`）
- 同样处理 xhs 平台

**输出：**
- `wechat/11_final_final.md`
- `xhs/11_final_final.md`
- `wechat/11_handoff.yaml`
- `xhs/11_handoff.yaml`

**AI 执行：**
```text
用户说："使用 article-formatted 技能进一步去机械化，提升自然度"

AI 调用 /article-formatted 技能：
1. 消除AI写作模式（翻译腔、过度结构化等）
2. 提升中文地道性
3. 生成最终稿：
   - wechat/11_final_final.md
   - xhs/11_final_final.md
4. 生成 handoff.yaml
```

**handoff.yaml 模板：**
```yaml
step_id: "11_formatted"
inputs:
  - "wechat/10_polished.md"
  - "wechat/10_retrieval_snippets.md"
outputs:
  - "wechat/11_final_final.md"
  - "wechat/11_handoff.yaml"
summary: "文本去机械化，提升自然度和中文地道性"
next_instructions:
  - "并行任务：image-prompter 可基于 wechat/09_rewritten.md 生成图片提示词"
  - "保持文章结构和关键信息不变"
open_questions: []
```

---

### 阶段 12：图片提示词生成（image-prompter）- 强制契约模式

⚠️ **警告：此阶段必须通过 /image-prompter 技能执行，禁止直接生成文件**

**违规后果：** 如果检测到 `07_图片提示词.md` 缺少 `image_prompter` frontmatter 标记，阶段13将被阻断。

---

**调用方式（强制）：**
```
使用 image-prompter 技能，完成5阶段流程
```

**新增要求：**
- 产出的 `07_图片提示词.md` 除了 prompt，还必须包含 `image_plan` 图位元数据
- 每张图必须声明 `role` 与 `insert_after` / `insert_after_heading`
- 后续插图必须优先按图位元数据执行，而不是仅按图片顺序猜测

**前置校验（阶段13前自动执行）：**
```bash
# 阶段13前必须运行检查
python3 ~/.claude/skills/article-workflow/scripts/workflow_guardian.py \
  --project-dir "/path/to/project" \
  --before-stage 13
```

**契约标记检查：**
```bash
# 检查 image-prompter 5阶段是否完成
python3 ~/.claude/skills/article-workflow/scripts/skill_invoker.py \
  --project-dir "/path/to/project" \
  --validate
```

---

**输入：**
- 专业重写后的文章：`06_终稿.md` 或 `wechat/09_rewritten.md`

**输出：**
- `07_图片提示词.md`（**必须包含 image_prompter frontmatter 标记**）
- `08_图片/` 目录（图片生成后）

**输出文件契约格式（必须）：**
```markdown
---
image_prompter:
  version: "1.0"
  stages:
    brief: { status: "done", confirmed_by: "user", timestamp: "..." }
    plan: { status: "done", confirmed_by: "user", timestamp: "..." }
    style: { status: "done", confirmed_by: "user", timestamp: "..." }
    copy: { status: "done", confirmed_by: "user", timestamp: "..." }
    prompts: { status: "done", confirmed_by: "user", timestamp: "..." }
  style_selected: "minimalist-sketch"  # 用户选择的风格
  image_count: 6
  copy_spec_confirmed: true
---

# 图片提示词
...
```

**阶段标记规则（强制）：**
- 每个阶段完成后，更新对应 stage 的 status 为 `done`
- 必须记录 `confirmed_by` 与 `timestamp`
- ⚠️ `confirmed_by` 必须为 `user`，禁止 `assumption` / `default` / `auto`
- `style_selected` 必须记录用户选择的风格 ID
- `layout_selected` 必须记录用户选择的布局 ID
- `copy_spec_confirmed` 必须在阶段3确认后设为 `true`
- 任一字段缺失时，阶段13必须阻断

---

**AI 执行流程（强制5阶段）：**

```
阶段12开始
  │
  ▼
┌──────────────────────────────────────────────────────────┐
│ 1. 向用户说明必须通过 /image-prompter 技能完成            │
│    禁止直接生成 07_图片提示词.md                          │
└──────────────────────────────────────────────────────────┘
  │
  ▼
┌──────────────────────────────────────────────────────────┐
│ 2. 初始化契约模板（如需要）                               │
│    python skill_invoker.py --init                         │
└──────────────────────────────────────────────────────────┘
  │
  ▼
┌──────────────────────────────────────────────────────────┐
│ 3. 引导用户调用技能：                                     │
│    claude /image-prompter --input 06_终稿.md             │
│                                                           │
│    Step 1: 选择 Style（8种）                             │
│    ┌─────────────────────────────────────────────────┐   │
│    │ cream-paper     奶油纸手绘   通用配图（默认）   │   │
│    │ infographic     扁平风       概念解释           │   │
│    │ handdrawn       方格纸手绘   笔记手绘           │   │
│    │ minimalist-sketch 极简手绘   技术内容           │   │
│    │ healing         治愈系插画   情绪叙事           │   │
│    │ sokamono        描边插画     清新文艺           │   │
│    │ xhs-cartoon     小红书卡通   干货分享           │   │
│    │ editorial       社论全景     深度分析           │   │
│    └─────────────────────────────────────────────────┘   │
│                                                           │
│    Step 2: 选择 Layout（5种）                            │
│    ┌─────────────────────────────────────────────────┐   │
│    │ balanced        通用信息图   解释原理（默认）   │   │
│    │ comparison      对比两卡     A vs B            │   │
│    │ list            三卡洞察     要点清单           │   │
│    │ flow            五格漫画     流程步骤           │   │
│    │ sparse          封面路线图   封面/目录          │   │
│    └─────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
  │
  ▼
┌──────────────────────────────────────────────────────────┐
│ 4. 等待用户完成6阶段流程：                                │
│    - 阶段1：需求澄清（4个问题）✓                         │
│    - 阶段2：配图规划（拆块→清单）✓                       │
│    - 阶段2.5：风格选择（8种 Style）✓                    │
│    - 阶段2.6：布局选择（5种 Layout）✓                   │
│    - 阶段3：文案定稿（Copy Spec）✓                       │
│    - 阶段4：提示词封装（生成提示词）✓                    │
│    - 阶段5：迭代润色（如需）✓                            │
└──────────────────────────────────────────────────────────┘
  │
  ▼
┌──────────────────────────────────────────────────────────┐
│ 5. 验证契约标记：                                         │
│    python skill_invoker.py --validate                     │
│    如果失败，回到步骤4                                    │
└──────────────────────────────────────────────────────────┘
  │
  ▼
阶段12完成，可以进入阶段13
```

**handoff.yaml 模板：**
```yaml
step_id: "12_prompts"
inputs:
  - "wechat/09_rewritten.md"
outputs:
  - "wechat/12_prompts.md"
  - "xhs/12_prompts.md"
  - "wechat/12_handoff.yaml"
summary: "生成图片提示词（基于 article-rewrite 后的文章，确保风格匹配）"
next_instructions:
  - "下一步：image-gen 生成图片"
  - "公众号：固定横版（比例由风格决定）"
  - "小红书：固定竖版（比例由风格决定）"
open_questions: []
```

---

### 阶段 13：图片生成（image-gen）- 前置依赖检查

⚠️ **前置强制检查：阶段12必须完成**

---

**前置检查（必须）：**

```bash
# 阶段13执行前，必须验证阶段12的契约标记
python3 ~/.claude/skills/article-workflow/scripts/workflow_guardian.py \
  --project-dir "/path/to/project" \
  --before-stage 13

# 检查失败时会输出：
# ❌ 阶段12检查失败：图片提示词文件未通过 image-prompter 技能生成
#    请先完成阶段12（image-prompter）5阶段流程
```

**阻断条件（满足任一即阻断）：**
- `07_图片提示词.md` 不存在
- 文件缺少 `image_prompter:` frontmatter 标记
- `image_prompter.stages` 中有未完成的阶段
- `style_selected` 为空
- `copy_spec_confirmed` 为 false

---

**调用方式：**
```
使用 image-gen 技能
```

**Handoff 读取：**
```python
# 读取上一阶段的 handoff.yaml，获取输入文件路径
prev_handoff = load_yaml(f"{run_dir}/wechat/12_handoff.yaml")
input_file = prev_handoff['outputs'][0]  # wechat/12_prompts.md
```

**输入：**
- 提示词文件：通过 handoff 读取（`wechat/12_prompts.md`）
- 模型：`doubao-seedream-4-5-251128`
- 清晰度：2K
- 比例规则：
  - 公众号封面：固定 21:9（3024x1296，超宽横版）
  - 公众号正文图片：固定 16:9 横版（2560x1440，标准宽屏）
  - 小红书海报：固定 3:4 竖版（1728x2304）

**输出：**
- `wechat/13_images/cover_21x9.jpg`
- `wechat/13_images/poster_01_16x9.jpg` ...
- `xhs/13_images/poster_01_3x4.jpg` ...
- `wechat/13_handoff.yaml`
- `xhs/13_handoff.yaml`

**AI 执行流程：**
```text
阶段13开始
  │
  ▼
┌─────────────────────────────────────────┐
│ 前置检查：运行 workflow_guardian.py     │
│ --before-stage 13                       │
└─────────────────────────────────────────┘
  │
  ├─ 检查失败 ──▶ 输出错误信息，阻断流程
  │               提示用户先完成阶段12
  │
  ▼ 检查通过
┌─────────────────────────────────────────┐
│ AI 调用 /image-gen 技能：               │
│ 1. 读取 07_图片提示词.md                │
│ 2. 解析每张图的风格要求                 │
│ 3. 调用 Ark API                         │
│ 4. 生成封面（21:9）                     │
│ 5. 生成配图（16:9）                     │
│ 6. 保存到 08_图片/                      │
│ 7. --insert-into 插入到终稿             │
│ 8. 生成 handoff.yaml                    │
└─────────────────────────────────────────┘
  │
  ▼
阶段13完成
```

**关键优化：图片自动插入**
- 使用 `--insert-into` 参数将生成的图片自动插入到 `wechat/11_final_final.md`
- 插入策略：
  - 第 1 张图片 → 主标题 (# 标题) 后
  - 第 2+ 张图片 → 各章节标题 (## 章节名) 后
- 相对路径格式：`![](13_images/poster_01_16x9.jpg)`
- 设计原理：详见 `/Users/wisewong/.claude/skills/image-gen/OPTIMIZATION.md`

**handoff.yaml 模板：**
```yaml
step_id: "13_images"
inputs:
  - "wechat/12_prompts.md"
  - "wechat/11_final_final.md"
outputs:
  - "wechat/13_images/"
  - "wechat/11_final_final.md"  # 已插入图片引用
  - "wechat/13_handoff.yaml"
summary: "生成文章配图并插入到 Markdown"
next_instructions:
  - "下一步：上传图片到微信 CDN"
open_questions: []
```

---

### 阶段 14：上传图片到微信 CDN（wechat-uploadimg）

**调用方式：**
```
使用 wechat-uploadimg 技能
```

**发布链路规则：**
- 若 `delivery.preview_channel = feishu` 且需要向用户预览本地图片，必须使用 `feishu-image` 技能发送图片消息
- 若 `delivery.publish_channel = wechat`，正文图片必须先通过 `wechat-uploadimg` 上传到微信 CDN，再交给 `md-to-wxhtml`

**Handoff 读取：**
从 `run_context.yaml` 读取 `decisions.wechat.account`（用户选择的公众号账号）

**输入：**
- 图片目录：`wechat/13_images/`
- 公众号：`decisions.wechat.account`（main/sub）

**输出：**
- `wechat/14_image_mapping.json`（图片 URL 映射）
- `wechat/14_image_mapping_flat.json`（扁平映射）
- `wechat/14_handoff.yaml`

**AI 执行：**
```text
用户说："使用 wechat-uploadimg 技能上传图片到微信 CDN"

AI 调用 /wechat-uploadimg 技能：
1. 批量上传 wechat/13_images/ 中所有图片
2. 自动分类：以 cover 开头为封面，其他为正文图片
3. 获取微信 CDN URL（mmbiz.qpic.cn）
4. 保存映射关系到 wechat/14_image_mapping.json
5. 生成 handoff.yaml
```

**输出示例：**
```json
{
  "cover_urls": {
    "cover_21x9.jpg": "http://mmbiz.qpic.cn/mmbiz_jpg/..."
  },
  "poster_urls": {
    "poster_01_16x9.jpg": "http://mmbiz.qpic.cn/mmbiz_jpg/..."
  },
  "total": 5
}
```

**handoff.yaml 模板：**
```yaml
step_id: "14_upload_images"
inputs:
  - "wechat/13_images/"
outputs:
  - "wechat/14_image_mapping.json"
  - "wechat/14_image_mapping_flat.json"
  - "wechat/14_handoff.yaml"
summary: "上传本地图片到微信 CDN，获取图片 URL 映射"
next_instructions:
  - "下一步：md-to-wxhtml 将使用这些 CDN URL"
open_questions: []
```

---

### 阶段 15：Markdown → 微信 HTML（md-to-wxhtml）

**前置操作：图片已插入 Markdown**
- 阶段 13（image-gen）已通过 `--insert-into` 参数将图片插入到 `wechat/11_final_final.md`
- Markdown 中使用本地路径：`![](13_images/poster_01_16x9.jpg)`
- md-to-wxhtml 读取 `wechat/14_image_mapping_flat.json`，将本地路径替换为微信 CDN URL

**前置交互：选择公众号账号（Gate D）**

检查 `run_context.yaml` 中 `decisions.wechat.account`：
- 如果为 `null` → 显示账号选项并等待用户选择；未收到明确选择时进入 WAITING_FOR_USER，禁止默认账号
- 如果已有值 → 跳过交互，使用已保存的账号

**账号选择界面：**
```text
请选择公众号账号：
1. 歪斯Wise (wise) - ⭐️ 关注星标，收看AI实战
2. 人类 (human) - ⭐️ 关注星标，收看AI、商业新知

选择 [wise/human]：
```

**保存选择到 run_context.yaml：**
```yaml
decisions:
  wechat:
    account: "wise"  # 或 "human"
```

**调用方式：**
```
使用 md-to-wxhtml 技能
```

**Handoff 读取：**
```python
# 读取 wechat/14_handoff.yaml 获取 image_mapping.json 路径
upload_handoff = load_yaml(f"{run_dir}/wechat/14_handoff.yaml")
image_mapping = upload_handoff['outputs'][0]  # wechat/14_image_mapping.json

# 读取更早阶段获取 Markdown 文件
humanize_handoff = load_yaml(f"{run_dir}/wechat/11_handoff.yaml")
markdown_file = humanize_handoff['outputs'][0]  # wechat/11_final_final.md

# 从 run_context.yaml 读取账号选择
context = load_yaml(f"{run_dir}/run_context.yaml")
account_type = context.get('decisions', {}).get('wechat', {}).get('account', 'wise')
```

**输入：**
- Markdown 文件：`wechat/11_final_final.md`
- 图片映射：`wechat/14_image_mapping.json`
- 账号类型：`decisions.wechat.account`（wise/human）

**输出：**
- `wechat/15_article.html`（图片使用 CDN URL，含账号对应的顶部/底部文案）
- `wechat/15_handoff.yaml`

**AI 执行：**
```text
用户说："使用 md-to-wxhtml 技能将 Markdown 转换为微信 HTML"

AI 调用 /md-to-wxhtml 技能：
1. 检查 run_context.yaml / frontmatter 中 `delivery.publish_account`
2. 如未选择，提示用户选择账号（wise/human）
3. 读取 wechat/11_final_final.md
4. 读取 wechat/14_image_mapping.json
5. **文章正文默认使用 `--content-mode article`**，并带上 `--image-mapping` 与 `--account-type`
6. 转换时自动将本地图片路径替换为微信 CDN URL
7. 根据账号类型添加对应的顶部/底部引导文案
8. 保存到 wechat/15_article.html
9. 生成 handoff.yaml
```

**handoff.yaml 模板：**
```yaml
step_id: "15_wx_html"
inputs:
  - "wechat/14_handoff.yaml"
  - "wechat/11_final_final.md"
  - "wechat/14_image_mapping.json"
outputs:
  - "wechat/15_article.html"
  - "wechat/15_handoff.yaml"
summary: "Markdown 转换为微信编辑器兼容 HTML（图片使用 CDN URL，账号类型：{account_type}）"
next_instructions:
  - "下一步：wechat-draftbox 上传到草稿箱"
open_questions: []
```

---

### 阶段 16：草稿箱入库（wechat-draftbox）

**前置交互：发布确认（Gate E，强制）**

执行阶段16前，必须获得用户显式同意上传草稿箱。

- ✅ 允许："确认上传草稿箱"、"现在上传到草稿箱"、"同意入库草稿箱"
- ❌ 禁止："继续"、"继续后面的流程"、"往下走"（语义不够明确）

若仅收到模糊推进语句，必须进入 `WAITING_FOR_USER`，仅追问上传确认，不得执行上传。


**调用方式：**
```
使用 wechat-draftbox 技能
```

**Handoff 读取：**
```python
# 从 run_context.yaml 读取账号选择（已在阶段15完成）
context = load_yaml(f"{run_dir}/run_context.yaml")
account = context.get('decisions', {}).get('wechat', {}).get('account', 'wise')
```

**账号映射：**
| SKILL.md 账号 | wechat-draftbox 账号 | 默认作者 |
|---------------|---------------------|----------|
| `wise` | `main` | Wise Wong |
| `human` | `sub` | 吃粿条 |

**输入：**
- HTML 文件：`wechat/15_article.html`
- 封面图：`wechat/13_images/cover_21x9.jpg`
- 标题：`wechat/08_title_selected.md`（用户选择的标题）
- 账号：`decisions.wechat.account`（wise→main, human→sub）
- **摘要**：由 LLM 生成（见下方 digest 生成规则）

**输出：**
- `wechat/16_draft.json`（包含 draft_media_id 和 thumb_media_id）

**AI 执行：**
```text
用户说："使用 wechat-draftbox 技能上传到草稿箱"

AI 执行流程：
1. 【LLM 生成摘要】阅读文章终稿（wechat/07_final_final.md 或 06_终稿.md），生成 digest
2. 从 run_context.yaml 读取 decisions.wechat.account
3. 映射账号：wise→main, human→sub
4. 调用 /wechat-draftbox 技能，传入 --digest 参数
5. 返回草稿信息，保存到 wechat/16_draft.json
6. 生成 handoff.yaml
```

**摘要（digest）生成规则：**

LLM 阅读文章后，从以下两种策略中选择最合适的一种：

**策略 A：核心观点 + 金句（推荐用于观点类文章）**
```
提取文章最核心的 1-2 个观点，配合一句金句。
格式：{核心观点}。{金句}
长度：50-80 字
示例："OpenClaw 的搜索能力被 Brave Search 额度卡住了。Agent Reach 让你的 AI Agent 重获互联网视野——完全免费，无需 API Key。"
```

**策略 B：内容总结（推荐用于教程/工具类文章）**
```
概括文章解决的问题和提供的方案。
格式：{问题/痛点}。{解决方案}
长度：50-80 字
示例："Brave Search 额度告急、YouTube 无法总结、Twitter 搜索受限？Agent Reach 一键解决 OpenClaw 用户的搜索焦虑，完全免费。"
```

**生成步骤：**
1. AI 阅读文章终稿，判断文章类型（观点类 / 教程类 / 工具类）
2. 选择合适的策略生成 digest
3. 确保 digest 简洁有力，能吸引读者点击
4. 通过 `--digest` 参数传递给 wechat-draftbox

**自动处理（wechat-draftbox 内置）：**
- **摘要后备**：如未提供 `--digest`，自动从正文第一段提取前 120 字（跳过引导文案和 TOC）
- **h1 标签移除**：自动移除正文中的 h1 标签（微信有独立标题字段）
- **默认作者**：main 账号 → "Wise Wong"，sub 账号 → "吃粿条"

**handoff.yaml 模板：**
```yaml
step_id: "16_draftbox"
inputs:
  - "wechat/15_article.html"
  - "wechat/14_image_mapping.json"
  - "wechat/08_title_selected.md"
  - "wechat/16_digest.txt"  # LLM 生成的摘要
outputs:
  - "wechat/16_draft.json"
  - "wechat/16_handoff.yaml"
summary: "上传 HTML 和封面到公众号草稿箱"
next_instructions:
  - "工作流完成：可以在公众号后台编辑和发布"
open_questions: []
```

---

## 图片处理完整流程

### 流程图
```
┌─────────────────────────────────────────────────────────────────┐
│  阶段 13: image-gen                                             │
│  ┌──────────────────┐    ┌──────────────────┐                  │
│  │  生成图片到      │───▶│  自动插入到 MD   │                  │
│  │  13_images/      │    │  (--insert-into) │                  │
│  └──────────────────┘    └──────────────────┘                  │
│                                  │                              │
│                                  ▼                              │
│                    wechat/11_final_final.md                    │
│                    (含本地图片引用)                             │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  阶段 14: wechat-uploadimg                                      │
│  ┌──────────────────┐    ┌──────────────────┐                  │
│  │  上传本地图片    │───▶│  生成映射文件    │                  │
│  │  到微信 CDN      │    │  image_mapping   │                  │
│  └──────────────────┘    └──────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  阶段 15: md-to-wxhtml                                          │
│  ┌──────────────────┐    ┌──────────────────┐                  │
│  │  读取 MD         │───▶│  替换本地路径    │                  │
│  │  + image_mapping │    │  为 CDN URL      │                  │
│  └──────────────────┘    └──────────────────┘                  │
│                                  │                              │
│                                  ▼                              │
│                    wechat/15_article.html                      │
│                    (图片已是 CDN URL)                           │
└─────────────────────────────────────────────────────────────────┘
```

### 关键优化点

| 问题 | 解决方案 | 职责划分 |
|------|---------|---------|
| 图片生成与内容插入脱节 | image-gen 添加 `--insert-into` 参数 | 生成+插入原子化 |
| 图片映射结构不匹配 | wechat-uploadimg 输出 `image_mapping_flat` | 扁平化映射 |
| HTML 中图片引用缺失 | 图片先插入 MD，再转换 HTML | 数据流不断裂 |

### 设计原理
详见：`/Users/wisewong/.claude/skills/image-gen/OPTIMIZATION.md`

---

## 完整输出目录结构

### Obsidian 模式（默认）

```
/Users/wisewong/Documents/Obsidian Vault/01_文章项目/<YYYYMMDD>__<话题>__<shortid>/
├── 📋 {话题}.md                   # 主文件（含 frontmatter 状态管理）
├── 00_素材与链接.md              # 引用研究库
├── 01_提纲.md                    # 提纲方案
├── 02_初稿.md                    # 根据提纲生成的初稿
├── 03_RAG增强.md                 # RAG 增强后的文章
├── 04_标题方案.md                # 多组标题方案
├── 05_润色稿.md                  # 金句点缀稿
├── 06_终稿.md                    # 去机械化最终稿
├── 07_图片提示词.md              # 图片提示词（含 image_prompter 标记）
├── 07_发布记录.md                # 发布记录
├── 08_图片/                      # 本地图片
│   ├── cover_21x9.jpg
│   └── poster_01_16x9.jpg
├── 09_handoff.yaml               # handoff 文件
└── _log/                         # 步骤日志
```

### 传统模式（--traditional）

```
/Users/wisewong/Documents/Developer/auto-write/runs/<YYYYMMDD>__<话题>__<shortid>/
├── run_context.yaml              # SSOT 状态文件
├── wechat/
│   ├── 00_research.md            # 调研资料包
│   ├── 02_outlines/              # 提纲方案目录
│   ├── 04_draft.md               # 初稿
│   ├── 05_enhanced.md            # RAG 增强后的文章
│   ├── 09_rewritten.md           # 专业重写
│   ├── 11_final_final.md         # 最终稿
│   ├── 13_images/                # 本地图片
│   ├── 14_image_mapping.json     # 图片 URL 映射
│   ├── 15_article.html           # 微信 HTML
│   └── 16_draft.json             # 草稿箱结果
├── xhs/
│   # ... 类似结构
└── _log/                         # 步骤日志
```

---

## 环境变量

| 变量 | 必需 | 用途 |
|------|------|------|
| `ARK_API_KEY` | ✅ | 火山 Ark API 密钥 |
| `WECHAT_APPID` | ✅ | 微信公众号 AppID |
| `WECHAT_APPSECRET` | ✅ | 微信公众号 AppSecret |

**出网 IP 白名单：** 确保 `wechat-draftbox` 请求来源 IP 在微信白名单中。

---

## 技能依赖

本技能依赖以下 Claude Code 技能，确保已安装：

| 技能 | 用途 | 检查 |
|------|------|------|
| `research-workflow` | 趋势分析、竞品缺口、深度搜索 | `~/.claude/skills/research-workflow/` |
| `article-outliner` | 生成 2-3 个差异化提纲方案 | `~/.claude/skills/article-outliner/` |
| `article-writer` | 根据提纲生成文章草稿 | `~/.claude/skills/article-writer/` |
| `article-create-rag` | 基于本地文章库的 RAG 增强润色 | `~/.claude/skills/article-create-rag/` |
| `title-gen` | 生成多组爆款标题方案 | `~/.claude/skills/title-gen/` |
| `article-plug-classicLines` | 知识库检索与金句润色 | `~/.claude/skills/article-plug-classicLines/` |
| `article-formatted` | 文本去机械化 | `~/.claude/skills/article-formatted/` |
| `image-prompter` | 图片提示词生成（5种风格，五阶段流程） | `~/.claude/skills/image-prompter/` |
| `image-gen` | Ark Doubao 图片生成 | `~/.claude/skills/image-gen/` |
| `wechat-uploadimg` | 上传图片到微信 CDN | `~/.claude/skills/wechat-uploadimg/` |
| `md-to-wxhtml` | Markdown 转微信 HTML | `~/.claude/skills/md-to-wxhtml/` |
| `wechat-draftbox` | 微信草稿箱上传 | `~/.claude/skills/wechat-draftbox/` |

---

## 使用示例

### 完整流程（默认 Obsidian 模式）

```
用户：帮我创作一篇关于"你的话题"的文章，要完整流程从调研到公众号草稿箱

AI 执行流程（默认 Obsidian 模式）：
1. 初始化 Obsidian 项目：
   创建目录：Obsidian Vault/01_文章项目/2026-02-27__你的话题__a1b2c3/
   创建主文件：📋 你的话题.md（含 frontmatter）
   创建步骤文件：00_素材与链接.md, 01_提纲.md, ...

2. 调研阶段：
   - 调用 /research-workflow 生成调研内容
   - 保存到 00_素材与链接.md
   - 更新主文件 frontmatter steps.research.status: "done"

3. 提纲阶段：
   - 调用 article-outliner 生成 3 个提纲方案
   - 保存到 01_提纲.md（使用 frontmatter 标记各方案）
   - 用户选择后更新 frontmatter: selected_outline: "a"

4. 写作阶段：
   - 调用 article-writer 根据选中提纲生成 02_初稿.md
   - 调用 article-create-rag --enhance 生成 03_RAG增强.md
   - 更新主文件 frontmatter steps.draft.status: "done"

5. 标题阶段：
   - 调用 title-gen 生成 04_标题方案.md
   - 用户选择标题后：
     * 更新主文件 frontmatter 中的 topic 字段
     * 重命名项目目录：2026-02-27__你的话题__a1b2c3/ → 2026-02-27-用户选择的标题/
     * 重命名主文件

6. 后续阶段（重写、润色、出图、HTML、草稿箱）同上

7. 返回 Obsidian 项目路径和草稿箱链接
```

### 传统模式（--traditional）

```
用户：帮我创作一篇关于"你的话题"的文章，使用传统模式
使用参数：--topic "你的话题" --traditional

AI 执行流程：
1. 创建 run 目录：auto-write/runs/20260227__你的话题__a1b2c3/
2. 前置确认：公众号账号 + 图片配置（Gate A/B）
3. 调用 /research-workflow 生成 wechat/00_research.md
4. 调用 /article-outliner 生成 wechat/02_outlines/ 目录（2-3个提纲方案）
5. ... 后续流程同上，输出到传统目录结构
```

### 单阶段执行

用户可以要求从某个阶段开始：

```
用户：调研已经做好了，从提纲生成阶段继续

AI 执行流程：
1. 检查 00_素材与链接.md 是否存在（Obsidian 模式）
   或 wechat/00_research.md 是否存在（传统模式）
2. 从阶段 2（article-outliner）开始执行
```

### 指定输出目录

用户可以通过`--output-dir`参数指定输出目录：

```
用户：帮我创作一篇关于"你的话题"的文章，输出到指定目录
使用参数：--topic "你的话题" --output-dir "/path/to/output/dir"

AI 执行流程：
1. 使用指定目录：/path/to/output/dir/
2. 调用 /research-workflow 生成调研内容
3. 后续流程与完整流程相同，输出到指定目录
```

### 从现有 Obsidian 项目恢复

```
用户：继续完善昨天的 AI Agent 文章

AI 执行流程：
1. 扫描 Obsidian Vault/01_文章项目/ 目录
2. 找到最近修改的项目：2026-02-26-AI-Agent发展趋势深度解析/
3. 读取主文件 frontmatter，确定当前阶段
4. 从当前阶段继续执行
```

---

## 失败处理

| 阶段 | 失败场景 | 回退方案 |
|------|---------|---------|
| 图片生成 | Ark API 不支持 size 参数 | 退回 2K 清晰度，在 prompt 中明确比例 |
| 图片生成 | 尺寸不符预期 | 使用图片处理工具后处理裁切 |
| 图片上传 | Token 过期 | 刷新 access_token 后重试 |
| 图片上传 | IP 不在白名单 | 提示用户检查微信配置 |
| 图片上传 | 图片超过 1MB | 提示用户压缩图片或调整 image-gen 参数 |
| HTML 转换 | 渲染内容无法复制 | 返回 HTML 文件路径，提示用户手动复制 |
| 草稿箱上传 | IP 不在白名单 | 提示用户检查微信配置 |
| 草稿箱上传 | Token 过期 | 刷新 access_token 后重试 |

---

## 设计原则

### 1. 零适配器层（Zero Abstraction）

**坏设计（已删除）：**
```python
# 之前有多层适配器
ResearchWorkflowAdapter().execute(topic)
ArticleRewriteAdapter().execute(research_file)
```

**好设计（当前）：**
```text
直接通过 Claude Code 技能调用链：
→ /research-workflow
→ /article-create-rag
→ ...
```

### 2. 技能同步（Skill Sync）

- 依赖技能更新时，本技能自动同步
- 无需调用适配器代码更新
- 消除"中间层过时"问题

### 3. 用户极简（User Simplicity）

- 必填：仅"话题"
- 可选：平台（默认：公众号+小红书）
- 其他所有参数使用默认值

### 4. 向后兼容（Backward Compatibility）

- 输出目录结构保持不变
- 文件命名约定不变
- 兼容现有 run 目录恢复

---

## Handoff 串联协议（v1）

### Handoff 读取逻辑

每个阶段通过读取上一阶段的 handoff.yaml 获取输入文件：

```python
# 读取上一阶段的 handoff.yaml，获取输出文件路径
prev_handoff = load_yaml(f"{run_dir}/wechat/{prev_step}_handoff.yaml")
input_file = prev_handoff['outputs'][0]  # 通常第一个输出是 Markdown 文件
```

### Handoff.yaml 格式（v1 标准）

```yaml
step_id: "<step_code>"
inputs:
  - "<input_file_path>"
outputs:
  - "output_file_1.md"
  - "output_file_2.md"
  - "wechat/<step_code>_handoff.yaml"
summary: "<step_summary>"
next_instructions:
  - "下一步：xxx"
open_questions: []
```

**关键要求：**
- 每阶段必须生成 `{step_id}_handoff.yaml`
- handoff.yaml 必须包含 `outputs` 数组，列出所有生成的文件
- handoff.yaml 必须包含 `next_instructions`

### 工作流阶段 Handoff 说明

| 阶段 | 上一阶段 handoff | 当前阶段 handoff |
|------|------------------|------------------|
| 00_init | 无（初始化步骤） | - |
| 01_research | 无（第一阶段） | ✅ 已有 handoff 描述（参考模板） |
| 02_rag | 01_research | 读取 `wechat/01_handoff.yaml`，获取输入文件 |
| 03_titles | 01_research（优先） | 优先读取 `wechat/00_research.md`；若已有 `02_rag_content_no_title.md` 则使用该文件 |
| 04_select_title | 03_titles | 读取 `wechat/03_handoff.yaml`，获取输入文件 |
| 05_draft | 02_rag + 04_select_title | 同时读取 `wechat/02_handoff.yaml` 与 `wechat/04_handoff.yaml` |
| 06_polish | 05_draft | 读取 `wechat/05_handoff.yaml`，获取输入文件 |
| 07_humanize | 06_polish | 读取 `wechat/06_handoff.yaml`，获取输入文件 |
| 08_prompts | 05_draft | 读取 `wechat/05_handoff.yaml`，获取输入文件 |
| 09_images | 08_prompts | 读取 `wechat/08_handoff.yaml`，获取输入文件 |
| 10_upload_images | 09_images | 读取 `wechat/09_handoff.yaml`，获取输入文件 |
| 11_wx_html | 10_upload_images + 07_humanize | 读取 `wechat/10_handoff.yaml` 与 `wechat/07_handoff.yaml` |
| 12_draftbox | 11_wx_html | 读取 `wechat/11_handoff.yaml`，获取输入文件 |

---

## 文件路径 Canonicalize（规范化映射）

由于各技能使用不同的步骤编号，article-workflow 需要做路径映射：

```python
# Canonicalize 映射表
CANONICAL_OUTPUTS = {
    # article-create-rag 输出映射
    "02_rag": {
        "actual": ["generated_article.md"],
        "canonical": ["wechat/02_rag_content.md"]
    },
    # title-gen 输出映射
    "03_titles": {
        "actual": ["titles.md"],  # 或默认输出名
        "canonical": ["wechat/03_titles.md"]
    },
    # article-rewrite 输出映射
    "05_draft": {
        "actual": ["wechat/01_draft.md"],
        "canonical": ["wechat/05_draft.md"]
    },
    # article-plug-classicLines 输出映射
    "06_polish": {
        "actual": ["wechat/03_polished.md"],
        "canonical": ["wechat/06_polished.md"]
    },
    # article-formatted 输出映射
    "07_humanize": {
        "actual": ["wechat/04_final.md"],
        "canonical": ["wechat/07_final_final.md"]
    },
    # image-prompter 输出映射
    "08_prompts": {
        "actual": ["wechat/05_prompts.md"],
        "canonical": ["wechat/08_prompts.md"]
    },
}

def canonicalize_outputs(step_id, actual_outputs, run_dir):
    """将技能的实际输出规范化为 article-workflow 期望的路径"""
    if step_id not in CANONICAL_OUTPUTS:
        return actual_outputs

    mapping = CANONICAL_OUTPUTS[step_id]

    # 将实际输出文件移动/复制到 canonical 路径
    for i, actual_path in enumerate(mapping["actual"]):
        canonical_path = mapping["canonical"][i]
        src = Path(run_dir) / actual_path
        dst = Path(run_dir) / canonical_path

        if src.exists() and src != dst:
            # 移动或复制文件
            shutil.move(str(src), str(dst))

    return mapping["canonical"]
```

**使用时机：**
- 当技能的实际输出路径与 article-workflow 期望路径不一致时
- 例如：article-rewrite 输出 `wechat/01_draft.md`，但期望是 `wechat/05_draft.md`
- canonicalize 会自动移动/复制文件到正确路径
- 这样下一阶段读取 handoff 时就能找到正确的文件

**注意事项：**
- canonicalize 只在必要时执行（src.exists() and src != dst）
- 不破坏源文件，而是移动或复制
- 如果文件已在正确路径，不执行任何操作

**每个阶段执行后：**
1. 读取 handoff.yaml 中的 outputs
2. 调用 canonicalize_outputs() 规范化路径
3. 下一阶段使用 canonicalize 后的路径

---

## 端到端校验（Doctor）

完成所有步骤后，运行校验脚本：

```bash
python3 ~/.claude/skills/article-workflow/scripts/workflow_doctor.py /path/to/run_dir
```

### 校验脚本位置

**文件**：`~/.claude/skills/article-workflow/scripts/workflow_doctor.py`

### 检查项

1. **run_context.yaml 检查**
   - 文件是否存在
   - 步骤状态（FAILED 步骤标记）

2. **Handoff 文件检查**
   - 每个阶段的 `{step_id}_handoff.yaml` 是否存在
   - handoff.yaml 是否包含必需字段（step_id, inputs, outputs, summary）
   - outputs 中列出的文件是否真实存在

3. **平台检查**
   - wechat 平台所有 handoff 文件
   - xhs 平台所有 handoff 文件（如果存在）

### 运行示例

```bash
# 校验完整运行
python3 ~/.claude/skills/article-workflow/scripts/workflow_doctor.py /Users/wisewong/Documents/Developer/auto-write/runs/20260115__test__abc123

# 预期输出
🔍 检查 article-workflow: /path/to/run_dir

【检查 run_context.yaml】
✅ run_context.yaml 正常

【检查 wechat handoffs】
✅ wechat 平台正常

【检查 xhs handoffs】
✅ xhs 平台正常

✨ 所有检查通过!
```

---

## 版本历史

- **4.3.1** - 新增“有限度流水线”默认规则：阶段3/7/12/15/16必须人工确认，禁止以默认值/assumption 跳过；草稿箱上传需显式同意。
- **4.3.0** - **Obsidian 模式设为默认**：
  - 默认使用 Obsidian 存储模式，输出到 `/Documents/Obsidian Vault/01_文章项目/`
  - 新增 `--traditional` 参数用于使用传统模式（`auto-write/runs/`）
  - 移除 `--obsidian` 参数（现在是默认行为）
  - 修复"设计与行为不一致"问题：推荐模式现在是默认模式
- **4.2.0** - 新增 Obsidian 存储模式（推荐）：
  - 支持 `--obsidian` 参数使用 Obsidian vault 作为存储
  - 使用 Markdown frontmatter 替代 run_context.yaml 作为 SSOT
  - 项目目录：`01_文章项目/{YYYY-MM-DD}__{topic}__{shortid}/`
  - 共享研究库：`00_研究库/`（与 research-workflow 共用）
  - 项目看板：使用 Obsidian Bases (.base) 管理项目列表
  - 目录重命名：确认标题后自动重命名为 `{日期}-{标题}` 格式
  - 双模式架构：Obsidian 模式 / 传统模式（自动检测）
- **4.1.1** - 修复阶段12输入来源：阶段12（image-prompter）现在从阶段9（article-rewrite）的输出读取，确保图片提示词与经过HKR+四步爆款法重写后的文章风格一致
- **4.1.0** - 新增阶段9（article-rewrite 专业重写）：调整流程顺序，article-rewrite 移到选择标题后执行。article-writer 只生成初稿（简单骨架），RAG增强后选择标题，最后进行专业重写（HKR + 四步爆款法 + 反AI写作）
- **4.0.0** - 新标准流程：调研→提纲→写作→RAG增强。新增 article-outliner（提纲生成）和 article-writer（根据提纲写作），article-create-rag 改造为增强模式
- **3.3.0** - wechat-uploadimg 独立成正式步骤（10_upload_images），并行链路明确
- **3.2.0** - 新增 wechat-uploadimg 集成，图片自动上传到微信 CDN
- **3.1.0** - 新增 Handoff 串联协议、Canonicalize 映射、端到端 Doctor 校验
- **3.0.0** - 新增 RAG 写作流程（article-create-rag + title-gen + 用户选择标题）
- **2.0.0** - 重构为纯技能链架构，移除所有适配器层
- **1.0.0** - 初始版本，带适配器层
