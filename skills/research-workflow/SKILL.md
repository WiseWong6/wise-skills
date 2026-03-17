---
name: research-workflow
description: 全流程内容创作调研技能，集成 Firecrawl、Context7、TrendRadar、zread、Exa、社交媒体搜索，实现趋势分析、竞品缺口、深度搜索和 Brief 生成。支持 Obsidian 集成、智能路由、置信度标签、时效性窗口
version: "2.8.0"
author: "Wise Wong"
category: "Content & Media"
tags: [research, content-creation, trends, seo, brief-generator, confidence-scoring, reproducibility, intent-analysis, chinese-hotlist, exa, social-media, obsidian]
config:
  output_path: "~/Documents/Obsidian Vault/00_研究库/{YYYY-MM-DD}-{topic}/"
  auto_init: true
  format: "markdown"
  encoding: "utf-8"
  handoff_required: true

---

# 内容创作调研工作流 (Content Research Workflow)

这是一个端到端的内容创作调研技能，帮助创作者从选题到 Brief 生成的完整流程。

**重要说明：** 此技能通过 AI 直接调用 MCP 工具执行，Python 脚本仅用于 CLI 测试。

## 输出配置
- **输出路径**: `~/Documents/Obsidian Vault/00_研究库/{YYYY-MM-DD}-{topic}/`
- **主文件**: `index.md`（带 YAML frontmatter）
- **引用格式**: `[[文章项目/xxx|引用]]` 双向链接
- **Frontmatter**: 包含研究 ID、状态、工具使用、置信度等元数据

**输入参数：**
- `--idea`: 核心参数，接受以下两种输入类型：
  - **明确标题**：`--idea "AI Agent 最佳实践"` - 按现有逻辑生成标准 Brief
  - **模糊想法**：`--idea "我想写一篇关于 AI 帮助程序员写代码的文章"` - 解析意图，生成多角度综合 Brief

### 目录结构

所有研究输出保存到：

```
~/Documents/Obsidian Vault/
└── 00_研究库/
    └── {YYYY-MM-DD}-{topic}/
        ├── index.md          # 主研究文件（带 YAML frontmatter）
        └── citations.md      # 完整引用列表
```

**index.md Frontmatter 结构：**
```yaml
---
research_id: "2026-02-26-ai-agent-trends"
topic: "AI Agent 发展趋势"
status: "completed"  # in_progress | completed
platforms: ["wechat", "xhs"]
created: 2026-02-26
updated: 2026-02-26
tools_used: ["firecrawl", "exa", "twitter", "github"]
confidence_level: "HIGH"
article_refs: []  # 引用此研究的文章项目
metadata:
  findings_count: 15
  freshness_score: 0.85
  version: "2.8.0"
tags: ["research", "content-brief", "ai", "agent"]
---
```

### 与 article-workflow 集成

Obsidian 模式下，研究库可以与文章项目无缝集成：

1. **创建研究并生成引用路径：**
   ```bash
   python scripts/research_search.py --idea "AI Agent 发展趋势" --markdown
   ```
   输出：`📎 Obsidian 引用路径: [[00_研究库/2026-02-26-ai-agent-trends/index]]`

2. **在 article-workflow 中引用研究：**
   ```bash
   python scripts/orchestrator.py --topic "AI Agent 发展趋势" --research-ref "00_研究库/2026-02-26-ai-agent-trends/index"
   ```

3. **文章项目 frontmatter 中的研究引用：**
   ```yaml
   research_ref: "[[00_研究库/2026-02-26-ai-agent-trends/index|调研资料]]"
   ```

### 使用示例

```bash
# 基础用法
python scripts/research_search.py --idea "AI Agent 发展趋势" --markdown

# 指定平台
python scripts/research_search.py --idea "AI Agent 发展趋势" --markdown --platforms wechat xhs zhihu

# 资讯模式
python scripts/research_search.py --news "AI 最新动态" --days 7 --markdown
```

```python
from research_search import ResearchSearcher
from obsidian_utils import get_research_path

searcher = ResearchSearcher()
results = searcher.search("AI Agent 发展趋势")

output_dir = get_research_path("AI Agent 发展趋势")
research_ref = searcher.export_markdown(
    output_dir,
    topic="AI Agent 发展趋势",
    platforms=["wechat", "xhs"]
)
print(f"研究引用: [[{research_ref}]]")
```

每次调研运行自动创建：
```
~/Documents/Obsidian Vault/00_研究库/{YYYY-MM-DD}-{topic}/
├── index.md          # 主研究文件（带 YAML frontmatter）
├── citations.md      # 完整引用列表
└── artifacts/        # 原始数据和搜索结果
```

## 输出落盘协议

**输入：**
- `run_dir`: orchestrator 提供的运行目录
- `idea`: 核心参数，接受明确标题或模糊想法
- `platforms`: 目标平台列表 ["wechat", "xhs"]

**输出（必须落盘）：**
- `index.md` - 主调研报告（带 YAML frontmatter，含置信度标签）
- `citations.md` - 引用来源列表
- `handoff.md` - 交接文件（嵌入在 frontmatter 中）

**明确标题输入 - index.md frontmatter 模板：**
```yaml
---
research_id: "2026-03-09-{topic-slug}"
topic: "{topic}"
status: "completed"
platforms: ["wechat", "xhs"]
created: 2026-03-09
updated: 2026-03-09
tools_used: ["firecrawl", "exa"]
confidence_level: "HIGH"
article_refs: []
handoff:
  step_id: "01_research"
  inputs:
    - idea: "{idea}"
    - platforms: ["wechat", "xhs"]
  outputs:
    - "index.md"
    - "citations.md"
  summary: "基于 Firecrawl 和 Context7 的深度调研"
  next_instructions:
    - "下一步：article-create-rag 生成草稿"
    - "不得修改调研中的事实点和数据"
  open_questions: []
metadata:
  findings_count: 10
  freshness_score: 0.95
---
```

**模糊想法输入 - 增强型 frontmatter 模板：**
```yaml
---
research_id: "2026-03-09-{topic-slug}"
topic: "{detected_topic}"
original_idea: "{original_idea}"
status: "completed"
platforms: ["wechat", "xhs"]
created: 2026-03-09
updated: 2026-03-09
tools_used: ["firecrawl", "exa"]
confidence_level: "HIGH"
article_refs: []
handoff:
  step_id: "01_research"
  inputs:
    - idea: "{original_idea}"
    - detected_topic: "{detected_topic}"
    - platforms: ["wechat", "xhs"]
  outputs:
    - "index.md"
    - "citations.md"
  summary: "模糊意图解析 + 多角度研究 + 自动推荐最优角度"
  next_instructions:
    - "下一步：article-create-rag 使用推荐角度生成草稿"
    - "recommended_angle: {angle_name}"
  open_questions: []
metadata:
  findings_count: 15
  freshness_score: 0.92
---
```

**更新文章项目 frontmatter：**
```yaml
---
research_ref: "[[00_研究库/2026-03-09-{topic-slug}/index|调研资料]]"
---
```

## 核心能力

### 1. 趋势与热点分析 (Trend Analysis)

检测行业弱信号、分析增长趋势、预测时间窗口。

**使用场景：**
- 每周/每月选题雷达
- 捕捉新兴话题和衰退主题
- 识别讨论热度上升的关键词

**调用方式：**
```
"分析 [领域] 在 [时间范围] 的趋势"
```

**示例：**
- "分析 AI agent 在 2026 年 1 月的趋势"
- "帮我找最近一周科技领域的热点话题"
- "检测保险行业 Q4 的潜在趋势"
- "分析人工智能 最新热榜"（多路召回：自动获取中英文热榜数据）

---

### 2. 竞品与内容缺口分析 (Content Gap Analysis)

分析竞品内容覆盖情况，发现未覆盖的主题和差异化角度。

**使用场景：**
- 确定选题是否值得写
- 找出竞品未覆盖的独特角度
- 生成内容优先级排序

**调用方式：**
```
"分析 [竞品列表] 在 [平台] 的内容缺口"
```

**示例：**
- "分析以下保险博客的内容缺口: [公众号A, 公众号B, 公众号C]"
- "对比竞品内容，找出我们缺失的角度"

---

### 3. 深度网络搜索与引用 (Research with Citations)

基于 MCP 工具进行真实联网搜索，获取带引用和置信度的权威资料。

**多路召回架构：**
1. **Firecrawl** - 网页搜索、爬取、社交媒体搜索、竞品分析
2. **Tavily** - Firecrawl 降级方案（额限时自动切换）
3. **Context7** - 技术文档、API 文档（技术补充）
4. **TrendRadar** - 中文本土热榜（知乎、微博、B站等）
5. **zread** - GitHub 代码研究（真实代码案例）

**使用场景：**
- 事实核查和统计验证
- 技术文档检索
- 多源交叉验证
- 获取实时数据和行业动态
- 中文本土热榜数据（多路召回，不区分语言自动获取）
- GitHub 真实代码案例和实现（检测到代码关键词时自动触发）

**调用方式：**
```
"研究 [主题]，找 [类型] 资料"
```

**示例：**
- "研究 Claude 3.5 Sonnet 的编程能力，找权威资料"
- "查证 2025 年保险行业增长数据"
- "获取 React 19 的最新 API 文档"

---

### 4. 内容 Brief 生成 (Content Brief Generation)

将研究结果整合为可交付的 Content Brief。

**使用场景：**
- 为创作者/编辑提供清晰指南
- 标准化内容生产流程
- 对齐业务目标和 SEO 要求

**调用方式：**
```
"为 [主题] 生成内容 Brief"
```

**示例：**
- "为 'AI Agent 最佳实践' 生成内容 Brief"
- "创建关于保险理赔流程的文章 Brief"

---

### 5. 模糊意图解析 (Ambiguous Intent Analysis)

当用户输入模糊想法而非明确标题时，解析意图并生成多个写作方案。

**使用场景：**
- 用户只有初步想法："我想写一篇关于 AI 帮助程序员写代码的文章"
- 用户想跟进热点："最近大家都在讨论 Agent，我能不能也写点相关的东西"
- 用户需要选题建议："感觉个人成长这个话题挺有意思，想写一篇"

**调用方式：**
```
/research-workflow --idea "模糊想法"
```

**示例：**
- `/research-workflow --idea "我想写一篇关于 AI 帮助程序员写代码的文章"`
- `/research-workflow --idea "最近大家都在讨论 Agent，我能不能也写点相关的东西"`

---

## 6. 资讯搜集模式（新增）

### 使用场景

- 每日搜集 AI 领域高质量资讯
- 跟踪技术动态和行业趋势
- 内容运营的素材来源

### 调用方式

```
/research-workflow --news "主题" --days 7
```

### 参数说明

| 参数 | 资讯模式 | 深度模式 |
|------|---------|---------|
| `--news` | 主题（必填） | 不支持 |
| `--idea` | 不支持 | 主题（必填） |
| `--days` | 1-30 天范围（默认: 7） | 无效 |
| `--limit` | 默认 50 | 默认 10 |
| `--output` | 00_news.md | 00_research.md |

### 输出格式

资讯模式输出包含以下部分：

- 📊 **资讯概览**：主题、时间范围、资讯数量、平均评分
- 🏆 **热门资讯（Top 10）**：按评分排序的优质资讯
- 📂 **分类展示**：新技术产品、教程指南、研究报告、行业动态
- 📈 **趋势洞察**：关键词统计、评分分布、趋势分析
- 🔗 **完整列表**：所有资讯的表格视图

### 评分算法

资讯评分采用 0-10 分制，由三个维度加权计算：

| 维度 | 权重 | 说明 |
|------|------|------|
| 创新性 | 30% | 基于关键词匹配（new/breakthrough/最新/突破） |
| 实用性 | 30% | 基于关键词匹配（tutorial/guide/教程/指南） |
| 影响力 | 40% | 基于来源置信度（official=10, high=9, medium=7） |

### 示例调用

```bash
# 搜集近 7 天的 AI Agent 资讯
/research-workflow --news "AI Agent" --days 7

# 搜集近 30 天的机器学习资讯，限制 20 条
/research-workflow --news "机器学习" --days 30 --limit 20
```

### CLI 测试

```bash
# 测试资讯模式
python scripts/research_search.py --news "AI Agent" --days 7 --limit 20

# 测试参数互斥（应报错）
python scripts/research_search.py --news "test" --idea "test"

# 测试参数验证（应报错）
python scripts/research_search.py --news "test" --days 100
```

---

## AI 调用流程

**重要：** 这是技能的核心实现逻辑。当用户调用此技能时，AI 将按以下流程执行。

### 模糊意图解析（新增）

当用户使用 `--idea` 参数输入时：

1. **输入类型检测**：
   ```python
   def is_ambiguous_input(user_input: str) -> bool:
       """判断输入是模糊想法还是明确标题"""
       # 模糊输入特征
       ambiguous_patterns = [
           "我想写", "我想发", "我想写一篇",
           "感觉.*挺有意思", "最近.*都在讨论",
           "能不能.*写点", "想.*写点",
           "关于.*的文章", "关于.*的内容"
       ]
       return any(p in re.sub(r'[，。！？]', '', user_input) for p in ambiguous_patterns)
   ```

2. **如果检测到模糊输入**，执行意图解析：
   ```python
   # 解析用户意图
   prompt = f"""
   分析以下用户想法，提取：
   1. 核心话题（1-2个词）
   2. 潜在写作角度（3-5个不同方向）
   3. 目标读者群体

   用户想法：{idea}
   """
   intent = ai_analyze(prompt)
   ```

3. **为每个写作角度并行研究**：
   ```python
   research_results = {}
   for angle in intent['suggested_angles']:
       # 生成搜索查询
       queries = generate_search_queries(intent['core_topic'], angle)
       # 使用 Firecrawl + Context7 收集资料
       research_results[angle] = collect_research(queries)
   ```

4. **评分每个角度**：
   ```python
   scored_angles = []
   for angle in intent['suggested_angles']:
       research = research_results[angle]
       # 计算可行性评分
       feasibility = calculate_feasibility(research)
       # 计算资料丰富度评分
       richness = calculate_richness(research)
       # 综合评分
       total_score = (feasibility * 0.6) + (richness * 0.4)
       scored_angles.append({
           'angle': angle,
           'feasibility': feasibility,
           'richness': richness,
           'total_score': total_score,
           'research': research
       })
   ```

5. **自动选择最优角度**：
   ```python
   best_angle = max(scored_angles, key=lambda x: x['total_score'])
   ```

6. **生成增强型 Brief**：
   - 包含"模糊输入分析"部分（显示原始想法和识别的核心话题）
   - 包含"写作角度分析"表格（对比所有角度的可行性和资料丰富度）
   - 详细展示"推荐角度"（选择理由、核心论点、论据支撑）
   - 保存到 `index.md`

7. **返回结果**：
   ```json
   {
     "input_type": "ambiguous",
     "original_idea": "我想写一篇关于 AI 帮助程序员写代码的文章",
     "detected_topic": "AI 辅助编程",
     "all_angles": scored_angles,
     "recommended_angle": best_angle,
     "brief_path": "index.md"
   }
   ```

---

### 初始化流程

1. **创建执行目录**：
   ```python
   from datetime import datetime
   from pathlib import Path

   # 生成研究目录（Obsidian 格式）
   topic_slug = slugify(query)
   run_dir = Path.home() / "Documents/Obsidian Vault/00_研究库" / f"{datetime.now().strftime('%Y-%m-%d')}-{topic_slug}"
   run_dir.mkdir(parents=True, exist_ok=True)
   ```

2. **初始化标准文件结构**：
   ```python
   # 初始化研究文件
   files = {
       "index.md": f"---\nresearch_id: \"{run_id}\"\ntopic: \"{query}\"\nstatus: in_progress\ncreated: {datetime.now().strftime('%Y-%m-%d')}\n---\n\n# {query} 调研报告\n",
       "citations.md": "# 引用来源\n",
       "artifacts/": None
   }

   for filename, content in files.items():
       if filename != "artifacts/":
           filepath = run_dir / filename
           filepath.write_text(content, encoding='utf-8')
       else:
           (run_dir / "artifacts").mkdir(exist_ok=True)
   ```

---

### 趋势分析

当用户说"分析 [领域] 在 [时间范围] 的趋势"时：

1. **自动初始化执行环境**（由 config.auto_init 控制）：
   - 创建输出目录：`~/Documents/Obsidian Vault/00_研究库/{YYYY-MM-DD}-{topic}/`
   - 初始化标准文件结构：index.md、citations.md、artifacts/
   - 生成运行 ID 并保存

2. **构建搜索查询**'根据领域和时间范围构建多组查询
   - 主查询：`"{domain} 趋势 {time_range} 行业分析"`
   - 补充查询：`"{domain} 热门话题 {year}"`、`"{domain} 新兴技术"`

3. **使用 Firecrawl 搜索**（优先）：
   ```python
   results = mcp__firecrawl__firecrawl_search(
       query="AI agent 趋势 2026年1月",
       limit=10,
       sources=[{"type": "web"}]
   )

   # 保存原始数据到 artifacts/
   save_artifact(run_dir, "search_results.json", results)
   ```

   **降级逻辑（当 Firecrawl 失败/限额）**：
   ```python
   # Tavily 优先作为降级（需已配置 Tavily MCP 或可用 Tavily API）
   # 如果 Tavily 不可用，再回退到 web.run 搜索
   try:
       results = mcp__firecrawl__firecrawl_search(query=query, limit=limit, sources=[{"type": "web"}])
       tools_used = ["firecrawl_search"]
   except Exception:
       if tavily_available:
           results = tavily_search(query=query, limit=limit)  # 以 Tavily MCP/SDK 实现为准
           tools_used = ["tavily_search"]
       else:
           results = web.run(search_query=[{"q": query}])
           tools_used = ["web.run"]
   ```
   ```

4. **解析搜索结果**，提取：
   - 话题名称（从结果标题和摘要提取）
   - 信号强度（基于结果数量和讨论热度评分）
   - 增长率（基于时间序列和来源多样性分析）
   - 来源平台（Reddit、Twitter/X、GitHub、新闻等）
   - 关键洞察（从结果内容中提取）

5. **生成报告并保存**：
   - 将趋势分析写入 `index.md`（带置信度标签）
   - 可选：生成 `synthesis.md` 简报

6. **返回 JSON 格式**：
   ```json
   {
     "trends": [
       {
         "topic": "AI 代理自动化",
         "signal_strength": "high",
         "growth_rate": "+45%",
         "time_window": "2026-01 ~ 2026-02",
         "sources": ["Reddit", "Twitter/X", "News"],
         "key_insights": ["企业采用率上升", "新工具涌现"],
         "search_volume": "25000+",
         "engagement_score": 8.7,
         "confidence_type": "FACT",
         "confidence_score": 0.85
       }
     ],
     "emerging_signals": [
       {
         "signal": "AI Agent 编排",
         "confidence": "high",
         "early_mentions": ["Reddit r/LocalLLaMA", "GitHub trending"],
         "prediction_window": "3-6 months"
       }
     ],
     "declining_topics": ["纯文本 GPT 竞争", "非结构化 Prompt"],
     "analysis_metadata": {
       "domain": "AI",
       "time_range": "month",
       "time_window": "2025-12-11 ~ 2026-01-11",
       "timestamp": "ISO格式",
       "run_directory": "~/Documents/Obsidian Vault/00_研究库/2026-01-11-ai-trends/",
       "tools_used": ["firecrawl_search"]
     }
   }
   ```

---

### 研究搜索

当用户说"研究 [主题]，找 [类型] 资料"时：

1. **复杂度检测**：
   ```python
   # 检测查询复杂度，调整搜索参数
   is_complex = any(k in query.lower() for k in reasoning_keywords)
   limit = 15 if is_complex else 8
   depth = 3 if is_complex else 2
   ```

2. **判断来源类型**：
   ```python
   # 学术关键词
   academic_keywords = ["论文", "研究", "学术", "paper", "study", "机制", "对比", "benchmark", "评测"]
   # 技术文档关键词
   doc_keywords = ["API", "文档", "教程", "指南", "reference", "语法", "实现", "代码"]
   ```

3. **根据类型选择工具**：
   - **技术文档**（检测到 doc_keywords）：
     ```python
     # 先解析库名
     library_name = extract_library_name(query)
     mcp__context7__resolve-library-id(libraryName=library_name, query=query)
     mcp__context7__query-docs(libraryId=resolved_id, query=query)
     ```
   - **网页搜索**（默认，含 Tavily 降级）：
     ```python
     try:
         mcp__firecrawl__firecrawl_search(query=query, limit=limit, sources=[{"type": "web"}])
     except Exception:
         if tavily_available:
             tavily_search(query=query, limit=limit)
         else:
             web.run(search_query=[{"q": query}])
     ```

4. **收集和验证来源**：
   - 对每个结果提取标题、URL、日期、摘要
   - 标记源类型（官方/第三方）
   - 使用 Firecrawl 获取详细内容（如需要）

5. **计算置信度**：
   ```python
   def calculate_confidence(finding):
       # 源数量评分
       source_score = 1.0 if len(finding.sources) >= 2 else 0.7

       # 源类型评分
       has_official = any(s.type == "official" for s in finding.sources)
       source_score += 0.2 if has_official else 0

       # 交叉验证加分
       if finding.cross_verified:
           source_score += 0.1

       # 时效性评分
       age_months = (current_date - finding.date).days / 30
       if age_months <= 6:
           freshness = 1.0
       elif age_months <= 12:
           freshness = 0.8
       elif age_months <= 24:
           freshness = 0.6
       else:
           freshness = 0.4

       # 综合置信度
       conf = (source_score + freshness) / 2
       return min(conf, 1.0)
   ```

6. **时效性过滤**：
   ```python
   # 根据话题类型获取时效窗口
   recency_window = get_recency_window(query)  # "default" / "ai" / "volatile"

   # 过滤超出窗口的资料
   valid_findings = [f for f in findings if is_within_window(f.date, recency_window)]

   # 标记被过滤的资料
   filtered_count = len(findings) - len(valid_findings)
   ```

7. **返回格式**：
   ```json
   {
     "query": "Claude 3.5 Sonnet 编程能力",
     "query_complexity": "complex",
     "findings": [
       {
         "claim": "Claude 3.5 Sonnet 在编程任务上表现优异",
         "confidence_type": "FACT",
         "confidence_score": 0.92,
         "sources": [
           {
             "title": "Anthropic 官方发布说明",
             "url": "https://anthropic.com/...",
             "date": "2026-01-01",
             "source_type": "official",
             "excerpt": "..."
           }
         ],
         "cross_verified": true,
         "freshness_status": "current"
       }
     ],
     "research_timestamp": "2026-01-10T12:00:00Z",
     "recency_window": "60 days",
     "filtered_findings": 2,
     "search_metadata": {
       "source_types_requested": ["docs", "news"],
       "depth": 3,
       "limit": 15,
       "total_findings": 12,
       "valid_findings": 10,
       "tools_used": ["Context7", "Firecrawl"]
     }
   }
   ```

---

### 内容缺口分析

当用户说"分析 [竞品列表] 在 [平台] 的内容缺口"时：

1. **创建执行目录**：
   ```python
   from pathlib import Path
   from datetime import datetime
   
   # 生成研究目录（Obsidian 格式）
   run_dir = Path.home() / "Documents/Obsidian Vault/00_研究库" / f"{datetime.now().strftime('%Y-%m-%d')}-competitor-analysis"
   run_dir.mkdir(parents=True, exist_ok=True)
   ```

2. **爬取竞品内容**：
   ```python
   for competitor in competitors:
       result = mcp__firecrawl__firecrawl_scrape(url=competitor_url)

       # 保存原始数据到 artifacts/
       save_artifact(run_dir, f"{competitor_name}.json", result)
   ```

3. **分析主题分布和关键词**：
   - 提取每篇文章的主题标签
   - 统计关键词使用频率
   - 按主题聚类内容

4. **对比发现缺口**：
   - 竞品已覆盖但你未覆盖的主题
   - 竞品高频使用但你不用的关键词
   - 竞品使用但你缺失的内容格式

5. **生成报告**：
   - 将分析结果写入 `index.md`（带置信度标签）
   - 可选：生成 `synthesis.md` 简报

6. **返回缺口数据**：
   ```json
   {
     "coverage_gaps": [
       {
         "topic": "AI Agent 编排最佳实践",
         "your_coverage": "部分覆盖",
         "competitors_covered": ["竞品A", "竞品B"],
         "opportunity_score": 8.5,
         "suggested_angles": [...]
       }
     ],
     "keyword_gaps": [...],
     "format_gaps": [...]
   }
   ```

---

### Brief 生成

当用户说"为 [主题] 生成内容 Brief"时：

1. **创建执行目录**：
   ```python
   from pathlib import Path
   from datetime import datetime
   
   # 生成研究目录（Obsidian 格式）
   run_dir = Path.home() / "Documents/Obsidian Vault/00_研究库" / f"{datetime.now().strftime('%Y-%m-%d')}-{topic_slug}"
   run_dir.mkdir(parents=True, exist_ok=True)
   ```

2. **先执行研究（如果需要）**：
   - 使用研究搜索获取相关资料
   - 使用趋势分析获取背景数据
   - 保存研究数据到 `artifacts/`

3. **使用 Brief 模板格式化**：
   - 可以运行 `brief_generator.py` 脚本生成
   - 或直接基于模板输出 Markdown

4. **保存报告**：
   - 将 Brief 保存为 `brief.md`
   - 生成 `citations.md` 引用列表

5. **返回完整 Brief**（Markdown 格式）

---

## 完整工作流示例

### 示例 1：新选题发现
```
用户：帮我找这个月在 AI 领域值得写的话题

AI 执行流程：
1. 使用 firecrawl_search 搜索 AI 趋势
2. 分析搜索结果，提取 10-15 个趋势
3. 对每个趋势计算机会评分
4. 返回优先级排序的选题池
```

### 示例 2：单选题深度调研
```
用户：调研 "Claude 3.5 Sonnet 编程能力"，生成 Brief

AI 执行流程：
1. 使用 Context7 获取 Anthropic 官方文档
2. 使用 firecrawl_search 获取社区反馈、案例
3. 分析现有内容覆盖（可选）
4. 使用 brief_generator.py 模板生成 Brief
5. 返回完整 Markdown Brief
```

### 示例 3：竞品对比研究
```
用户：分析竞品内容，找差异化角度

AI 执行流程：
1. 使用 firecrawl_scrape 爬取竞品网站内容
2. 分析主题分布和关键词使用
3. 对比发现未覆盖的角度
4. 返回内容缺口和差异化建议
```

---

## MCP 工具使用

### Firecrawl

**可用工具：**
- `firecrawl_search` - 搜索网页，获取结果列表
- `firecrawl_scrape` - 抓取单个 URL 的完整内容
- `firecrawl_agent` - 自主搜索和导航
- `firecrawl_extract` - 结构化数据提取

**使用场景：**
- 趋势分析：搜索社交媒体和新闻
- 竞品分析：爬取竞品网站内容
- 深度搜索：自主搜索和导航

### Context7

**可用工具：**
- `resolve-library-id` - 解析库名到 Context7 ID
- `query-docs` - 获取库的最新文档和代码示例

**使用场景：**
- 获取库的最新 API 文档
- 查找代码示例
- 验证技术细节

### TrendRadar

**安装：**
```bash
# Codex
codex mcp add trendradar -- npx -y @wantcat/trendradar-mcp
# Claude Desktop
claude mcp add trendradar -- npx -y @wantcat/trendradar-mcp
```

**可用工具：**
- `get_latest_news` - 获取最新热榜数据
- `search_hot_news` - 模糊搜索热榜话题
- `analyze_trends` - 趋势分析

**使用场景：**
- 获取中文本土热榜数据（知乎、微博、B站等）
- 跟踪中文社区热门话题
- 与 Firecrawl/Context7 互补的多路召回

**平台支持：**
- 知乎 (zhihu)
- 微博 (weibo)
- 哔哩哔哩 (bilibili)
- 更多平台见 TrendRadar 配置

### Tavily

**说明：** Tavily 作为 Firecrawl 的降级方案，当 Firecrawl 到达限额时自动切换。
提供 `tavily-search`（搜索）与 `tavily-extract`（网页抽取）工具。

**远程 MCP URL（推荐）**：
```
https://mcp.tavily.com/mcp/?tavilyApiKey=<your-api-key>
```

**本地安装（可选）**：
```bash
TAVILY_API_KEY="your_tavily_api_key" npx -y @tavily/mcp
```

**不支持远程 MCP 的客户端（桥接）**：
```bash
npx -y mcp-remote https://mcp.tavily.com/mcp/?tavilyApiKey=<your-api-key>
```

**环境变量（不要写入仓库）**：`TAVILY_API_KEY`

**使用场景：**
- Firecrawl 额限时的自动降级
- 备用网页搜索结果
- 保证研究流程不中断

**source_type 标记：** `tavily`

### zread

**安装：**
```bash
# Codex
codex mcp add zread -- npx -y zread-mcp
# Claude Desktop
claude mcp add zread -- npx -y zread-mcp
```

**可用工具：**
- `search_doc` - 搜索 GitHub 仓库中的文档和代码
- `read_file` - 读取 GitHub 仓库中的特定文件
- `get_repo_structure` - 获取仓库结构

**使用场景：**
- 获取真实的代码实现案例
- 查看官方仓库的最佳实践
- 验证技术细节和实现方式
- 研究开源项目的设计理念

**触发条件：**
- 查询包含 GitHub 关键词
- 查询包含代码相关关键词（实现、案例、源码等）
- 查询包含仓库名模式 (owner/repo)

**source_type 标记：** `code`

---

## 输出格式

### 趋势分析输出 (JSON)
```json
{
  "trends": [
    {
      "topic": "AI 代理自动化",
      "signal_strength": "high|medium|low",
      "growth_rate": "+45%",
      "time_window": "2026-01 ~ 2026-02",
      "sources": ["Reddit", "Twitter/X", "News"],
      "key_insights": ["企业采用率上升", "新工具涌现"],
      "search_volume": "25000+",
      "engagement_score": 8.7
    }
  ],
  "emerging_signals": [
    {
      "signal": "AI Agent 编排",
      "confidence": "high",
      "early_mentions": ["Reddit r/LocalLLaMA", "GitHub trending"],
      "prediction_window": "3-6 months"
    }
  ],
  "declining_topics": ["纯文本 GPT 竞争", "非结构化 Prompt"]
}
```

### 缺口分析输出 (JSON)
```json
{
  "coverage_gaps": [
    {
      "topic": "AI Agent 编排最佳实践",
      "your_coverage": "部分覆盖",
      "competitors_covered": ["竞品A", "竞品B"],
      "opportunity_score": 8.5,
      "suggested_angles": [
        "从工程化角度讲解",
        "结合实际案例对比"
      ]
    }
  ],
  "keyword_gaps": [
    {
      "keyword": "编排",
      "competitor_usage_count": 15,
      "your_usage_count": 0,
      "opportunity_level": "high"
    }
  ],
  "format_gaps": [...]
}
```

### 研究结果输出 (JSON)
```json
{
  "query": "Claude 3.5 Sonnet 编程能力",
  "findings": [
    {
      "claim": "Claude 3.5 Sonnet 在编程任务上表现优异",
      "sources": [
        {
          "title": "Anthropic 官方发布说明",
          "url": "https://anthropic.com/...",
          "date": "2026-01-01",
          "confidence": "official",
          "excerpt": "..."
        }
      ],
      "cross_verified": true,
      "source_type": "docs"
    }
  ],
  "research_timestamp": "2026-01-10T12:00:00Z",
  "freshness_score": 0.95,
  "search_metadata": {
    "source_types_requested": ["docs", "news"],
    "depth": 3,
    "total_findings": 5,
    "tools_used": ["Context7", "Firecrawl"]
  }
}
```

### Content Brief 输出 (Markdown)
```markdown
# 内容 Brief：[主题]

## 1. 内容概览
- **标题建议：** [基于趋势和缺口的标题]
- **内容类型：** 文章/教程/案例研究
- **目标受众：** [[基于受众分析]
- **核心目标：** [educate|convert|entertain]

## 2. 趋势背景
- 相关趋势：[列出 2-3 个趋势]
- 信号强度：[high/medium/low]
- 时间窗口：[2026-01 ~ 2026-03]

## 3. 差异化角度
- 内容缺口：[竞品未覆盖的角度]
- 建议切入点：[2-3 个独特观点]

## 4. 研究支撑
### 关键发现
- [带引用的发现 1]
- [带引用的发现 2]

## 5. 结构建议
### 建议大纲
1. [第一节] - [要点]
2. [第二节] - [要点]

### SEO 要素
- 主关键词：[...]
- 次关键词：[...]
- 搜索意图：[informational]

## 6. 成功指标
- 目标阅读时间：3+ 分钟
- SEO 排名目标：Top 10
```

### 增强型 Brief 输出 (Markdown - 模糊输入场景)

当用户输入模糊想法时，生成包含多个写作角度的综合 Brief：

```markdown
## 模糊输入分析

**原始想法：** "我想写一篇关于 AI 帮助程序员写代码的文章"
**识别核心话题：** AI 辅助编程
**检测到输入类型：** 模糊想法

---

## 写作角度分析

| 角度 | 可行性评分 | 资料丰富度 | 综合评分 | 推荐度 |
|------|-----------|-----------|---------|--------|
| AI Copilot 使用教程 | 9.2 | 高 (0.9) | 9.0 | ⭐⭐⭐ 推荐 |
| Agent 自动化工作流案例 | 7.5 | 中 (0.7) | 7.4 | ⭐ 可选 |
| 程序员对 AI 工具接受度研究 | 5.8 | 低 (0.5) | 5.6 | - 暂缓 |

---

## 推荐角度：AI Copilot 使用教程

### 选择理由
- 官方文档完善（GitHub Copilot Impact Study 2024）
- 社区案例丰富（Stack Overflow、GitHub Discussions）
- 目标读者明确（GitHub 程序员为主要受众）
- 有明确的数据支撑和案例素材

### 核心论点
- [FACT, conf: 0.92] Copilot 能减少 40-55% 的编码时间
  → [GitHub Copilot Impact Study](https://github.blog) — (GitHub, 2024-09)
  → 验证: 由 2 个独立来源确认
- [BELIEF, conf: 0.78] 新手开发者收益比资深开发者更明显
  → [Stack Overflow 调研](https://stackoverflow.blog) — (Stack Overflow, 2024-11)
- [ASSUMPTION, conf: 0.65] 存在学习曲线，但 3 个月内的 ROI 显著
  → 基于多个社区讨论的推断

### 论据支撑
- [官方] GitHub Copilot Impact Study 2024 - 基于 100 万用户数据分析
- [第三方] Stack Overflow 2025 调研报告 - 开发者满意度调查
- [社区] GitHub Discussions - 1000+ 讨论，500+ 个正面反馈

---

## 其他角度概览

### 角度 2：Agent 自动化工作流案例
**可行性：** 中 (7.5)
**资料丰富度：** 中
**适用场景：** 企业级自动化、CI/CD 集成

### 角度 3：程序员对 AI 工具接受度研究
**可行性：** 低 (5.8)
**资料丰富度：** 低
**挑战：** 调研数据有限，建议推迟或结合其他角度

---

## 总结建议

基于模糊想法「我想写一篇关于 AI 帮助程序员写代码的文章」，建议优先撰写「AI Copilot 使用教程」，因为：
1. 研究资料最丰富（官方文档 + 社区案例）
2. 有明确的数据支撑（40-55% 编码时间减少）
3. 目标读者需求清晰（GitHub 程序员为主）
4. 写作角度独特（教程型内容在社区中有需求）

---

## 后续步骤

1. 使用推荐角度「AI Copilot 使用教程」调用 `/article-create-rag` 生成草稿
2. 或者在 `00_research.md` 中查看其他角度的方案，手动选择一个
```

---

## 工作原理

### 趋势检测方法

1. **弱信号识别** - 从多平台（社交媒体、新闻、搜索趋势）提取早期信号
2. **增长率计算** - 分析讨论频次的时间序列变化
3. **时间窗口预测** - 基于历史数据预测趋势持续时间
4. **机会评分** - 结合信号强度、增长率、竞争度计算综合分数

### 内容缺口分析逻辑

1. **竞品内容爬取** - 使用 Firecrawl 系统性获取竞品内容
2. **主题聚类** - 使用 NLP 技术将内容聚类为主题类别
3. **覆盖对比** - 对比自身内容库与竞品主题分布
4. **机会识别** - 找出竞品未覆盖但搜索有需求的主题
5. **角度建议** - 基于缺口生成差异化写作角度

---

## CLI 工具说明

Python 脚本位于 `scripts/` 目录，用于独立测试和批量处理。

**注意：** 这些脚本仅用于 CLI 调用，真实 MCP 集成请在 Claude Code 中调用此技能。

### 可用脚本

- `trend_analysis.py` - 趋势分析（返回模拟数据）
- `gap_analysis.py` - 缺口分析（返回模拟数据）
- `research_search.py` - 研究搜索（返回模拟数据）
- `brief_generator.py` - Brief 生成（可直接使用）

### 示例命令

```bash
# 生成 Brief 模板
python scripts/brief_generator.py --topic "AI Agent 最佳实践"

# 查看帮助
python scripts/trend_analysis.py --help
```

---

## 最佳实践

### 1. 研究深度平衡

- **快速话题**：使用 Firecrawl 足够
- **技术文档**：使用 Context7 获取最新 API 和代码

### 2. 时效性控制

- 所有研究输出包含 `research_timestamp`
- 计算并显示 `freshness_score`（0-1）
- 对超过 6 个月的资料标记为"需更新"

### 3. 引用管理

- 每个发现至少提供 1 个引用源
- 官方来源置信度标记为 "official"
- 第三方验证来源置信度标记为 "high" 或 "medium"
- 提供完整的 URL、标题、发布日期

### 4. Brief 质量

- Brief 必须包含趋势背景和竞品对比
- 提供至少 3 个差异化角度
- 定义明确的 SEO 关键词和搜索意图
- 设定可量化的成功指标

---

## 常见问题

**Q: 如何确保研究的时效性？**
A: 每个研究结果都带时间戳和新鲜度评分。技能会优先选择最近 6 个月内的资料。

**Q: 可以只做趋势分析不做研究吗？**
A: 可以。每个核心能力都可以独立调用。趋势分析只需要 Firecrawl。

**Q: Brief 生成需要多长时间？**
A: 取决于研究深度。完整流程（趋势+缺口+研究+Brief）通常需要 2-5 分钟。

**Q: Python 脚本和 AI 调用有什么区别？**
A: Python 脚本用于 CLI 测试（返回模拟数据），AI 调用时直接使用 MCP 工具获取真实数据。

---

## 数据完整性标准

### 置信度标签

所有发现必须标注置信度类型：

| 类型 | 置信度范围 | 定义 | 验证要求 |
|------|------------|------|----------|
| **FACT** | 0.9-1.0 | 多源验证的事实 | ≥2 独立来源 |
| **BELIEF** | 0.6-0.8 | 单一来源的高可信信息 | 1 权威来源 |
| **CONTRADICTION** | 0.5 | 源之间冲突的声明 | 需明确解释冲突 |
| **ASSUMPTION** | 0.3-0.4 | 基于线索的推测 | 明确标记为推测 |

**输出格式：**
```markdown
[FACT | conf: 0.92] Claude 3.5 在编程任务上表现优异
→ [Anthropic 官方文档](https://anthropic.com/docs) — (Anthropic, 2026-01-01)
验证: 由 3 个独立来源确认
```

### 时效性窗口

根据话题性质自动调整时效性要求：

| 话题类型 | 时效性要求 | 适用场景 |
|---------|------------|----------|
| **默认** | ≤12 个月 | 通用话题 |
| **AI/技术前沿** | ≤60 天 | AI 模型、框架更新 |
| **易变主题** | ≤30 天 | 社交媒体 API、算法变化 |

**时效性评分计算：**
```python
# 6 个月内: 0.9-1.0
# 6-12 个月: 0.7-0.9
# 12-24 个月: 0.5-0.7
# 超过 24 个月: 0.0-0.5
```

### 验证规则

1. **来源验证**
   - 每个主声明至少 2 个独立来源
   - 优先同行评审期刊、官方文档
   - 拒绝匿名来源或未署名内容

2. **时间过滤**
   - 自动过滤超出时效性窗口的资料
   - 在输出中标注资料新鲜度状态

3. **引用完整性**
   - 每个发现必须包含 URL、标题、发布日期
   - 官方来源标记为 `official`
   - 需要时使用 Firecrawl 获取完整内容

---

## 复杂度检测

### 复杂度判定逻辑

根据查询类型自动调整搜索深度：

```python
# 推理关键词（触发深度搜索）
reasoning_keywords = [
    "compare", "versus", "vs", "对比",
    "explain", "mechanism", "why", "explain",
    "analyze", "analysis", "分析",
    "trade-off",", "pros and cons", "advantage",
    "synthesize", "meta-analysis", "systematic review"
]

# 简单查询匹配任何关键词即判定为复杂
is_complex = any(k in query.lower() for k in reasoning_keywords)
```

### 参数调整策略

| 查询类型 | 搜索深度 | 结果数量 | 用途 |
|---------|---------|---------|------|
| 简单查询 | 1-2 | 5-8 | 事实检索、文档查找 |
| 复度查询 | 3-5 | 15-20 | 对比分析、机制解释 |

---

## 工作流回溯机制

### 执行文件夹结构

每次研究运行创建新的时间戳目录（Obsidian 格式）：

```
~/Documents/Obsidian Vault/00_研究库/{YYYY-MM-DD}-{topic}/
├── index.md          # 主研究文件（带 YAML frontmatter）
├── citations.md      # 完整引用列表
├── artifacts/        # 原始数据、爬取内容
└── synthesis.md      # 可选的事实简报（可选）
```

### 回溯特性

- **不可变性**: 已完成的研究永远不会被修改
- **可追溯性**: 每次执行记录完整的工具调用链
- **可复现性**: 保留原始输入和参数配置

---

## 技术栈

- **Python 3.8+** - CLI 脚本（测试用途）
- **MCP Servers** - Firecrawl, Tavily, Context7, TrendRadar, zread
- **Claude Code AI** - 核心执行逻辑
- **JSON/Markdown** - 数据交换和输出格式

---

## 版本历史

- **2.7.0** - 双重增强：Tavily 作为 Firecrawl 降级方案 + zread GitHub 代码研究集成
- **2.6.0** - 多路召回架构：移除语言检测，所有查询并行调用三个数据源（Firecrawl + Context7 + TrendRadar），通过 source_type 区分，结果自动融合
- **2.5.0** - 集成 TrendRadar MCP：中文热榜数据支持（知乎、微博、B站）、时效性评分适配
- **2.4.0** - 整合 noncitizen/research-lookup 设计：置信度标签、时效性窗口、复杂度检测、工作流回溯
- **2.0.0** - 重构为 AI 驱动架构，移除模拟数据，直接使用 MCP 工具
- **1.1.0** - 初始版本
