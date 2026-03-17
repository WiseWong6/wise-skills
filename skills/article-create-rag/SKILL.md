---
name: article-create-rag
description: 基于文章库进行检索增强写作，支持主题创作、调研内容增强、草稿润色和提纲生成。
license: Proprietary
---

# Article Create RAG - 文章创作与 RAG 增强技能

## 何时使用
- 用户要求"基于文章库写文章"、"从知识库生成内容"
- 用户有外部调研内容，需要从本地文章库补充相关素材
- 用户给主题和关键词，需要检索相关内容创作
- 用户有初稿，需要用本地文章库进行 RAG 增强和润色
- **用户需要生成提纲方案，规划文章结构**

## 使用方法

```bash
# 模式1：主题+关键词直接生成文章
/article-create-rag --topic="如何提升执行力" --keywords="习惯,自律,系统"

# 模式2：基于外部调研内容 + 本地文章库生成文章
/article-create-rag --research="/path/to/research.md" --topic="如何提升执行力"

# 模式3：RAG 增强已有草稿（新增）
/article-create-rag --draft="/path/to/draft.md" --enhance

# 模式4：生成提纲方案
/article-create-rag --research="/path/to/research.md" --topic="如何提升执行力" --outline
```

## 参数说明

| 参数 | 必填 | 说明 |
|------|------|------|
| `research` | 否 | 外部调研内容文件路径（模式2/4/5） |
| `draft` | 模式3必填 | 初稿文件路径（模式3：RAG 增强模式） |
| `--enhance` | 否 | **RAG 增强模式**，对已有草稿进行增强和润色 |
| `topic` | 模式1必填 | 文章主题 |
| `keywords` | 模式1必填 | 关键词（逗号分隔） |
| `--run-dir` | 否 | Orchestrator 提供的运行目录，输出路径将相对于此目录 |
| `--output-path` | 否 | 输出文件相对路径，默认 `generated_article.md` |
| `--count` | 否 | 从文章库召回的片段数量，默认5 |
| `--outline` | 否 | **生成提纲模式**，输出 2-3 个差异化提纲方案 |

**字数约束（文章生成模式）：固定 1500-2000 字**

## Handoff 落盘协议

**当作为 article-workflow 子技能调用时：**

### 模式3：RAG 增强模式

```yaml
step_id: "05_rag_enhance"
inputs:
  - "{input_draft_file}"
outputs:
  - "{output_path}"  # 如 wechat/05_enhanced.md
  - "{retrieval_snippets_path}"  # 如 wechat/05_retrieval_snippets.md
  - "wechat/05_handoff.yaml"
summary: "使用本地文章库对初稿进行 RAG 增强和润色"
next_instructions:
  - "下一步：title-gen 生成标题方案"
  - "只能引用 snippets 中的内容，不得杜撰来源"
open_questions: []
```

### 模式1/2：直接生成模式（向后兼容）

```yaml
step_id: "02_rag"
inputs:
  - "{input_research_file}"
outputs:
  - "{output_path}"  # 如 wechat/02_rag_content.md
  - "wechat/02_handoff.yaml"
summary: "基于调研资料和本地文章库生成草稿"
next_instructions:
  - "下一步：title-gen 生成标题方案"
open_questions: []
```

## 工作流程

### 模式3：RAG 增强已有草稿

**适用场景**：用户已有一个初稿，需要用本地文章库进行增强和润色

**流程**：
1. 读取 `--draft` 文件（初稿内容）
2. 从初稿中提取关键段落和观点
3. 用提取的关键词从本地文章库检索相关片段
4. 将检索结果与初稿内容进行融合：
   - 补充数据/案例/引用
   - 优化表达和论证
   - 保持原有结构和观点不变
5. 保存增强后的文章
6. 保存检索证据片段（用于溯源）

**关键原则**：
- 只能在检索到的片段范围内进行增强，不得杜撰
- 保持初稿的核心观点和结构不变
- 补充的内容必须标注来源

### 模式4：提纲生成

1. 接收 `research` 文件或 `keywords`
2. 从文章库检索相关片段（RAG 增强）
3. 分析素材，提取核心论点
4. 生成 2-3 个差异化提纲方案：
   - **方案 A**：深度解析版（理性分析型，2500-3000字）
   - **方案 B**：精简速读版（故事驱动型，1500-2000字）
   - **方案 C**：思辨讨论版（对话评论型，2000-2500字）

**输出结构**：
```
posts/YYYY/MM/DD/[slug]/
├── source-1.md           # 原始素材
├── outline-a.md          # 方案 A
├── outline-b.md          # 方案 B
└── outline-c.md          # 方案 C
```

### 模式1：主题+关键词直接生成
1. 接收 `topic` 和 `keywords`
2. 用 rg（ripgrep）从文章库检索相关片段
3. 基于检索结果生成文章
4. 保存输出文件

### 模式2：外部调研内容 + 本地文章库
1. 读取 `research` 文件（外部调研内容）
2. 从调研内容中提取关键词和核心主题
3. 用提取的关键词从本地文章库检索相关片段
4. 合并外部调研内容 + 本地文章库片段
5. 基于合并素材生成文章
6. 保存输出文件

## 文章库结构

**路径**：`/Users/wisewong/Documents/Developer/auto-write/文章库/`

**文件**：
- 刘润.xlsx
- 数字生命卡兹克.xlsx
- 粥左罗(1).xlsx

**首次使用时**：需要将 Excel 解析为可检索格式（JSONL），见 `scripts/parse_xlsx.py`

## 索引与检索

### 检索方式（优先级从高到低）
1. **ripgrep**：关键词检索（当前实现）
2. **llamaindex**：向量索引 + BM25 混合检索（P1，可选，待实现）

### 检索流程
1. 确定关键词来源：
   - 模式1：用户直接提供
   - 模式2：从外部调研内容提取
2. 使用关键词检索本地文章库
3. 过滤和排序（质量分、相关度）
4. 取 top N 条（默认5条）

### 关键词提取策略

从外部调研内容中提取关键词：
- 标题（Markdown `#` 开头）
- 粗体文本（Markdown `**` 包裹）
- 高频词汇（基于词频统计）

## 输出格式

### 模式3：RAG 增强模式输出

**增强后的文章格式**（`{output_path}`）：
```markdown
# [文章标题]

[增强后的文章正文...]

---

## 增强说明

本次 RAG 增强基于本地文章库检索到的 {N} 条相关片段，主要用于：
- 补充数据/案例
- 优化表达和论证
- 保持原有结构和观点不变
```

**检索证据片段**（`{retrieval_snippets_path}`）：
```markdown
# 检索证据片段

## 来源：刘润
- [片段1]

## 来源：粥左罗
- [片段2]

...

共检索到 {N} 条相关片段
```

### 模式1/2：直接生成模式输出

**生成文章格式**：
```markdown
# [文章标题]

[文章正文...]

---

## 素材来源

### 外部调研
- [引用片段] 来源：调研文件

### 本地文章库
- [引用片段] 来源：刘润 / 文章标题
- [引用片段] 来源：粥左罗 / 文章标题
```

## 提示词规范

生成文章时遵循以下原则：
1. **字数范围**：严格控制在 1500-2000 字之间
2. **结构清晰**：标题 → 问题引入 → 核心观点 → 案例支撑 → 总结
3. **观点整合**：将多个来源的观点有机融合，避免简单堆砌
4. **引用标注**：重要观点和金句必须标注来源
5. **语言自然**：避免"AI味"，用真人的表达方式
6. **事实准确**：不编造数据、不杜撰来源

## 依赖

- **ripgrep (rg)**：关键词检索（P0，必需）
- **llamaindex**：RAG 检索后端（P1，可选，未来扩展）

## 注意事项

1. 首次使用需要先解析 Excel 文件：`python scripts/parse_xlsx.py`
2. 检索结果为空时，明确告知用户并建议调整关键词
3. 外部调研内容和本地文章库片段都需要标注来源
4. 避免简单拼接，要进行观点整合和逻辑重构

## 未来扩展

### 语义检索集成（待实现）

当需要语义检索能力时：
1. 安装依赖：
   ```bash
   pip install llama-index-embeddings-huggingface
   ```

2. 使用本地嵌入模型：
   - BAAI/bge-small-zh-v1.5（中文优化）
   - 无需 API Key
   - 本地运行，无需外部服务

3. 构建向量索引：
   ```bash
   python scripts/build_vector_index.py
   ```

4. 使用混合检索：
   - 向量搜索（语义相关）
   - BM25 搜索（关键词精确）

预期效果：
- 搜索"执行力" → 找到"行动习惯"、"自我管理"等语义相关内容
- 检索质量更高，覆盖面更广
